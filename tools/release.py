#!/usr/bin/env python3
"""Package one verified build with its notices and source provenance.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import macho_inspect

CORE_BINARIES = ("anybor_libretro.so", "anybor_libretro.dll",
                 "anybor_libretro_android.so", "anybor_libretro.dylib")


def sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inventory():
    files = {}
    for folder, dirs, names in os.walk(str(ROOT)):
        dirs[:] = sorted(d for d in dirs if d not in (".git", ".build", "dist", "libs", "obj", "__pycache__"))
        for name in sorted(names):
            path = Path(folder) / name
            rel = path.relative_to(ROOT).as_posix()
            if rel == "SOURCES.json" or rel in CORE_BINARIES or name.endswith((".pyc", ".sym")):
                continue
            if path.is_symlink():
                raise RuntimeError("Linked source file: " + rel)
            files[rel] = sha256(path)
    return files


def source_files(strict=True):
    """Hash build inputs; publication additionally rejects unlisted files."""
    expected = read_json(ROOT / "SOURCES.json")["files"]
    if not strict:
        files = {}
        for name in expected:
            path = ROOT / name
            if path.is_symlink():
                raise RuntimeError("Linked source file: " + name)
            if not path.is_file():
                raise RuntimeError("Missing source file: " + name)
            files[name] = sha256(path)
        return files
    files = inventory()
    if set(files) != set(expected):
        changed = sorted(set(files).symmetric_difference(expected))
        raise RuntimeError("Source inventory file set changed: " + ", ".join(changed[:10]))
    return files


def source_digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


C_ESCAPES = {'a': 7, 'b': 8, 'f': 12, 'n': 10, 'r': 13, 't': 9, 'v': 11,
             "'": 39, '"': 34, '\\': 92, '?': 63, '0': 0}


def embedded_document(wrapper):
    """Decode the generated notice wrapper exactly as the C compiler would."""
    text = wrapper.read_text(encoding='utf-8')
    match = re.search(r'obor_license_text\[\]\s*=\s*\n(.*?);\n#endif', text, re.S)
    if not match:
        raise RuntimeError("Generated notice wrapper not found: " + str(wrapper))
    chunks = []
    for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1)):
        out = bytearray()
        i = 0
        while i < len(literal):
            c = literal[i]
            if c == '\\' and i + 1 < len(literal):
                n = literal[i + 1]
                if n in C_ESCAPES:
                    out.append(C_ESCAPES[n]); i += 2; continue
                if n == 'x':
                    j = i + 2; digits = ''
                    while j < len(literal) and literal[j] in '0123456789abcdefABCDEF':
                        digits += literal[j]; j += 1
                    if not digits:
                        raise RuntimeError("Malformed hexadecimal escape in " + str(wrapper))
                    out.append(int(digits, 16) & 0xff); i = j; continue
                if n in '01234567':
                    j = i + 1; digits = ''
                    while j < len(literal) and literal[j] in '01234567' and len(digits) < 3:
                        digits += literal[j]; j += 1
                    out.append(int(digits, 8) & 0xff); i = j; continue
                if n in 'uU':
                    width = 4 if n == 'u' else 8
                    out.extend(chr(int(literal[i + 2:i + 2 + width], 16)).encode('utf-8'))
                    i += 2 + width; continue
                raise RuntimeError("Unsupported escape in " + str(wrapper) + ": \\" + n)
            out.extend(c.encode('utf-8')); i += 1
        chunks.append(bytes(out))
    return b''.join(chunks)


def verify_notices(binary=None):
    document = (ROOT / "NOTICE.txt").read_bytes()
    for entry in read_json(ROOT / "LICENSES/index.json"):
        path = ROOT / entry["file"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise RuntimeError("Missing or changed notice: " + entry["file"])
        if path.read_bytes() not in document:
            raise RuntimeError("Notice missing from the embedded dossier: " + entry["file"])
    expected = b"ANYBOR_LICENSES_BEGIN\n" + document + b"ANYBOR_LICENSES_END\n"
    # The generated wrapper must reproduce the published dossier exactly; a
    # stale wrapper would ship notices that differ from NOTICE.txt.
    if embedded_document(ROOT / "src/glue/obor_notices.h") != expected:
        raise RuntimeError("src/glue/obor_notices.h does not match NOTICE.txt")
    if binary is not None:
        if expected not in binary.read_bytes():
            raise RuntimeError("The binary does not contain the matching license dossier.")


def command_version(command, apple_linker=False):
    args = shlex.split(command) + (["-v"] if apple_linker else ["--version"])
    output = subprocess.check_output(args, stderr=subprocess.STDOUT,
                                     universal_newlines=True, timeout=30).strip()
    if not output:
        raise RuntimeError("Tool returned no version: " + command)
    return output.splitlines()[0]


def record_build(target, spec, outdir, expected_sources):
    pin = read_json(ROOT / "src/pin.json")
    binary = outdir / (pin["core_basename"] + spec["ext"])
    verify_notices(binary)
    files = source_files(strict=False)
    if files != expected_sources:
        raise RuntimeError("Source files changed during compilation; rebuild from a stable tree.")
    compiler = command_version(spec["cc"])
    linker = command_version(spec["ld"], apple_linker=spec["plat"] == "darwin")
    binary_format = {}
    if spec["plat"] == "darwin":
        # Mach-O: no objdump on a stock macOS.  The dependency list and the
        # exported symbol set come from the inspector, which reads the load
        # commands and the export trie directly.
        info = macho_inspect.inspect(binary)
        imports = info["dependencies"]
        binary_format = {
            "kind": info["filetype"], "arch": info["arch"],
            "platform": info["platform"], "min_os": info["min_os"],
            "install_name": info["install_name"],
            "exported_symbols": info["exports"],
            "expected_export_count": 25,
        }
        if info["filetype"] != "DYLIB":
            raise RuntimeError("macOS core is not a dylib: " + str(info["filetype"]))
        if len(info["exports"]) != 25:
            raise RuntimeError("macOS core exports %d symbols, expected 25"
                               % len(info["exports"]))
    elif spec["plat"] == "windows":
        imports = subprocess.check_output([spec["objdump"], "-p", str(binary)], universal_newlines=True)
        imports = sorted(line.split("DLL Name:", 1)[1].strip() for line in imports.splitlines()
                         if "DLL Name:" in line)
    else:
        imports = subprocess.check_output([spec["objdump"], "-p", str(binary)], universal_newlines=True)
        imports = sorted(line.split()[-1] for line in imports.splitlines()
                         if line.strip().startswith("NEEDED"))
    members = []
    archives = {}
    # The map is scanned for archive members only, and a linker may write
    # raw symbol bytes into it, so unreadable sequences are replaced.
    maps = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(outdir.glob("*.map")))
    for path, member in re.findall(r"([^\s()]+\.a)\(([^()]+)\)", maps):
        archive = Path(path)
        entry = {"archive": archive.name, "member": member}
        if entry not in members:
            members.append(entry)
        if archive.is_file():
            archives[archive.name] = sha256(archive)
    receipt = {
        "schema": 1, "name": pin["core_name"], "version": pin["version"],
        "target": target, "binary": binary.name, "sha256": sha256(binary),
        "source_digest": source_digest(files), "source_files": files,
        "compiler": compiler, "linker": linker,
        "linker_archive_members": members, "linker_archive_sha256": archives,
        "linker_map_scope": "Archive members selected by engine partial links and final link, before final section garbage collection",
        "flags": {key: os.environ.get(key, "") for key in
                  ("CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "NASM", "SOURCE_DATE_EPOCH")},
        "dynamic_dependencies": imports,
        "static_dependencies": list(spec["dep_builds"]),
        "binary_format": binary_format,
        "notice_sha256": sha256(ROOT / "NOTICE.txt"),
    }
    (outdir / "build.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def package(target, build_root, dest):
    folder = build_root / "dist" / target
    receipt = read_json(folder / "build.json")
    if receipt["binary"] not in CORE_BINARIES:
        raise RuntimeError("Unexpected binary filename in build receipt")
    binary = folder / receipt["binary"]
    if receipt["target"] != target or sha256(binary) != receipt["sha256"]:
        raise RuntimeError("Build receipt does not match this binary/target.")
    if source_digest(source_files()) != receipt["source_digest"]:
        raise RuntimeError("Sources changed since this binary was built; rebuild before packaging.")
    if sha256(ROOT / "NOTICE.txt") != receipt["notice_sha256"]:
        raise RuntimeError("Notices changed since this binary was built.")
    verify_notices(binary)
    import check
    import source_release
    check.check_sources()
    check.check_binary(binary, target)
    dest.mkdir(parents=True, exist_ok=True)
    filename = "{0}-{1}-{2}.zip".format(
        read_json(ROOT / "src/pin.json")["core_basename"], receipt["version"], target)
    archive = dest / filename
    entries = [(binary, binary.name), (folder / "build.json", "build.json")]
    for name in ("LICENSE", "LICENSES.md", "NOTICE.txt", "README.md", "PROVENANCE.md",
                 "MODIFICATIONS.md", "CHANGELOG.md", "COMPATIBILITY.md", "SBOM.spdx.json"):
        entries.append((ROOT / name, name))
    entries += [(p, p.relative_to(ROOT).as_posix()) for p in sorted((ROOT / "docs").rglob("*")) if p.is_file()]
    entries += [(p, p.relative_to(ROOT).as_posix()) for p in sorted((ROOT / "examples").rglob("*")) if p.is_file()]
    entries += [(p, p.relative_to(ROOT).as_posix()) for p in sorted((ROOT / "LICENSES").rglob("*")) if p.is_file()]
    entries += [(p, p.name) for p in ROOT.glob("*.info")]
    # Each downloadable ZIP carries its own exact sources, as a tar.gz.
    # Keep temporary output off the release surface until every member passes.
    with tempfile.TemporaryDirectory(prefix="anybor-package-") as temporary_dir:
        source = Path(temporary_dir) / (read_json(ROOT / "src/pin.json")["core_basename"]
                                      + "-" + receipt["version"] + "-source.tar.gz")
        files = source_release.source_inventory()
        source_release.write_archive(source, files)
        metadata = Path(temporary_dir) / "PACKAGE.json"
        metadata.write_text(json.dumps({
            "schema": 1, "binary": binary.name, "binary_sha256": receipt["sha256"],
            "source_archive": source.name, "source_archive_sha256": sha256(source),
            "source_digest": receipt["source_digest"],
            "build_receipt_sha256": sha256(folder / "build.json"),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        entries += [(source, source.name), (metadata, metadata.name)]
        temporary = archive.with_name(archive.name + ".tmp")
        try:
            with zipfile.ZipFile(str(temporary), "w", zipfile.ZIP_DEFLATED) as zf:
                for path, name in entries:
                    zf.write(str(path), name)
            with zipfile.ZipFile(str(temporary)) as zf:
                if sorted(zf.namelist()) != sorted(name for _, name in entries):
                    raise RuntimeError("Release archive file set differs")
                for path, name in entries:
                    if zf.read(name) != path.read_bytes():
                        raise RuntimeError("Incomplete release archive: " + name)
                if hashlib.sha256(zf.read(binary.name)).hexdigest() != receipt["sha256"]:
                    raise RuntimeError("Packaged binary checksum mismatch")
            if source_digest(source_files()) != receipt["source_digest"]:
                raise RuntimeError("Sources changed during packaging")
            temporary.replace(archive)
        finally:
            if temporary.exists():
                temporary.unlink()
    checksum = sha256(archive) + "  " + archive.name + "\n"
    (dest / (archive.name + ".sha256")).write_text(checksum, encoding="utf-8")
    print(str(archive))
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--build-root", default=os.environ.get("OBOR_BUILD_ROOT", str(ROOT / ".build")))
    parser.add_argument("--dest", default=str(ROOT / "dist"))
    args = parser.parse_args()
    package(args.target, Path(args.build_root), Path(args.dest))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        sys.exit(str(error))
