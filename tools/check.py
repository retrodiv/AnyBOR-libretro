#!/usr/bin/env python3
"""Check source packaging, licenses, binary documentation and core primitives.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import struct
import tempfile
from pathlib import Path
import release
import macho_inspect
from check_modifications import check_modifications
from check_core_info import check_core_info

ROOT = release.ROOT

VERSION_LITERAL = re.compile(r"\b0\.1\.[0-9]+\b")
# Files that legitimately carry the release series: the single source of the
# version, the generated runtime identity, the generated records and the
# release history.  Everywhere else a literal is a copy that can go stale.
VERSION_CARRIERS = {"src/pin.json", "src/glue/obor_engines.h", "CHANGELOG.md",
                    "SOURCES.json", "SBOM.spdx.json"}


def check_version_records(root, files):
    """The version is written once; repeated literals are how copies go stale."""
    found = []
    for name in sorted(files):
        if name in VERSION_CARRIERS:
            continue
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found.extend("%s in %s" % (match.group(0), name) for match in VERSION_LITERAL.finditer(text))
    if found:
        raise RuntimeError("Version literal outside the version records: " + ", ".join(found[:5]))
    print("Version literals confined to the version records: OK")


def check_sources():
    expected = release.read_json(ROOT / "SOURCES.json")["files"]
    current = release.source_files()
    if current != expected:
        changed = [n for n in current if current[n] != expected.get(n)]
        raise RuntimeError("Source inventory changed: " + ", ".join(changed[:10]))
    release.verify_notices()
    for name in current:
        path = ROOT / name
        if path.suffix.lower() in (".pak", ".exe", ".dll", ".so", ".dylib", ".ogg", ".wav", ".webm"):
            raise RuntimeError("Binary or game payload in source inventory: " + name)
        if ".git" in path.relative_to(ROOT).parts or path.is_symlink():
            raise RuntimeError("History or symlink in source inventory: " + name)
    check_version_records(ROOT, current)
    # Operational project files must stay free of local filesystem paths.
    for directory in ("tools", "docs"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                text = path.read_text(encoding="utf-8")
                if re.search(r"[\"']/(?:home|Users|mnt)/[A-Za-z0-9]", text):
                    raise RuntimeError("Private workspace reference: " + str(path))
    for path in (ROOT / "tools").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"))
    if (ROOT / "src/glue/obor_abi.h").read_bytes() != (ROOT / "src/port/libretro/obor_abi.h").read_bytes():
        raise RuntimeError("Glue and engine ABI headers differ")
    pin = release.read_json(ROOT / "src/pin.json")
    check_core_info(ROOT, pin)
    check_modifications(ROOT, pin)
    for eng in pin["engines"]:
        root = ROOT / "src/engines" / eng["build"]
        manifest = release.read_json(root / "ANYBOR-SOURCE.json")
        if manifest["commit"] != eng["commit"]:
            raise RuntimeError("Engine provenance mismatch")
        for rel, data in manifest["files"].items():
            if release.sha256(root / rel) != data["distributed_sha256"]:
                raise RuntimeError("Engine source changed: " + eng["build"] + "/" + rel)
    for name in ("zlib", "libpng", "libogg", "libvorbis", "libvpx"):
        root = ROOT / "src/deps" / name
        manifest = release.read_json(root / "ANYBOR-SOURCE.json")
        if manifest["archive_sha256"] != pin["deps"][name]["sha256"]:
            raise RuntimeError("Dependency pin mismatch: " + name)
        for rel, checksum in manifest["files"].items():
            if release.sha256(root / rel) != checksum:
                raise RuntimeError("Dependency source changed: " + name + "/" + rel)
    print("Source inventory, component provenance and license dossier: OK")


def primitives():
    with tempfile.TemporaryDirectory(prefix="anybor-check-") as temp:
        output = str(Path(temp) / "primitives")
        compiler = shlex.split(os.environ.get("HOST_CC", "cc"))
        subprocess.check_call(compiler + [
            "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "src/port/libretro"),
            "-I", str(ROOT / "src/glue"),
            "-I", str(ROOT / "src/engines/6412/source/adpcmlib"),
            str(ROOT / "tests/test_primitives.c"),
            str(ROOT / "src/port/libretro/obor_adpcm.c"), "-o", output])
        subprocess.check_call([output])
    print("CRT framing, circle clipping/symmetry/blending and ADPCM format vectors: OK")


def expected_exports():
    """The libretro entry points every target must export.

    glue/exports.macho is the source of truth: it drives ld64's
    -exported_symbols_list, and the ELF/PE targets export the same set through
    their version script.  The names are stored in Mach-O form (leading
    underscore), so the ELF/PE comparison drops it.
    """
    text = (ROOT / "src/glue/exports.macho").read_text(encoding="utf-8")
    return sorted(line.strip() for line in text.splitlines()
                  if line.strip().startswith("_"))


def check_binary(path, target=None):
    """Validate a built core: format, architecture, dependencies, exports."""
    path = Path(path)
    if not path.is_file():
        raise RuntimeError("core not found: " + str(path))
    with path.open("rb") as handle:
        head = handle.read(256)
    expected = expected_exports()
    if head[:4] == b"\xcf\xfa\xed\xfe":
        if target and not target.startswith("macos-"):
            raise RuntimeError("Mach-O does not match target " + target)
        info = macho_inspect.inspect(path)
        if info["errors"]:
            raise RuntimeError("Mach-O warnings: " + "; ".join(info["errors"]))
        if info["filetype"] != "DYLIB":
            raise RuntimeError("not a dylib: " + str(info["filetype"]))
        expected_arch = "arm64" if target == "macos-arm64" else "x86_64"
        if target and info["arch"] != expected_arch:
            raise RuntimeError("Mach-O architecture does not match " + target)
        exports = info["exports"]
        if exports != expected:
            missing = sorted(set(expected) - set(exports))
            extra = sorted(set(exports) - set(expected))
            raise RuntimeError("Mach-O export set differs: missing=" + repr(missing) +
                               " extra=" + repr(extra))
        allowed = ("/usr/lib/libSystem.B.dylib",)
        foreign = [d for d in info["dependencies"] if d not in allowed]
        if foreign:
            raise RuntimeError("unexpected Mach-O dependency: " + ", ".join(foreign))
        print("Mach-O core: type=%s arch=%s platform=%s min_os=%s deps=%s exports=%d: OK"
              % (info["filetype"], info["arch"], info["platform"], info["min_os"],
                 ",".join(info["dependencies"]) or "none", len(exports)))
        return
    if head[:4] == b"\x7fELF":
        if len(head) < 64 or head[4:7] != b"\x02\x01\x01":
            raise RuntimeError("Expected a complete little-endian ELF64 header")
        kind, machine = struct.unpack_from("<HH", head, 16)
        if kind != 3 or machine not in (62, 183):
            raise RuntimeError("Expected an x86-64 or AArch64 ELF shared library")
        if target and (target.startswith(("macos-", "windows-")) or
                       machine != (62 if target == "linux-x86_64" else 183)):
            raise RuntimeError("ELF architecture/format does not match " + target)
        names = elf_exports(path)
        require_exports(names, [n[1:] for n in expected])
        dynamic = inspect_tool("READELF", "readelf", ["--dynamic", "--wide", str(path)])
        dependencies = re.findall(r"\(NEEDED\).*?\[([^]]+)\]", dynamic)
        allowed = ({"libc.so", "libdl.so", "libm.so", "liblog.so"}
                   if target == "android-arm64" else
                   {"libc.so.6", "libdl.so.2", "libm.so.6", "libmvec.so.1",
                    "libpthread.so.0", "librt.so.1", "libgcc_s.so.1", "libstdc++.so.6",
                    "ld-linux-x86-64.so.2", "ld-linux-aarch64.so.1"})
        if target is None:
            allowed.update(("libc.so", "libdl.so", "libm.so", "liblog.so"))
        require_dependencies(dependencies, allowed)
        print("ELF core: arch=%s exports=%d deps=%s: OK" %
              ("x86_64" if machine == 62 else "aarch64", len(names), ",".join(dependencies)))
        return
    if head[:2] == b"MZ":
        if target and target != "windows-x86_64":
            raise RuntimeError("PE does not match target " + target)
        if len(head) < 64:
            raise RuntimeError("Truncated DOS header")
        offset = struct.unpack_from("<I", head, 60)[0]
        with path.open("rb") as handle:
            handle.seek(offset)
            pe = handle.read(26)
        if (len(pe) != 26 or pe[:4] != b"PE\0\0" or
                struct.unpack_from("<H", pe, 4)[0] != 0x8664 or
                not struct.unpack_from("<H", pe, 22)[0] & 0x2000 or
                struct.unpack_from("<H", pe, 24)[0] != 0x20b):
            raise RuntimeError("Expected a complete x86-64 PE32+ DLL header")
        listing = inspect_tool("OBJDUMP", "objdump", ["-p", str(path)])
        if "[Ordinal/Name Pointer] Table" not in listing:
            raise RuntimeError("PE export table is missing")
        table = listing.split("[Ordinal/Name Pointer] Table", 1)[1].split("\n\n", 1)[0]
        names = sorted(line.split()[-1] for line in table.splitlines()
                       if re.match(r"\s*\[\s*\d+\]", line))
        require_exports(names, [n[1:] for n in expected])
        dependencies = re.findall(r"DLL Name:\s*(\S+)", listing)
        require_dependencies([d.lower() for d in dependencies],
                             {"kernel32.dll", "msvcrt.dll", "advapi32.dll", "psapi.dll",
                              "winmm.dll", "user32.dll"})
        print("PE core: arch=x86_64 exports=%d deps=%s: OK" %
              (len(names), ",".join(dependencies)))
        return
    raise RuntimeError("unrecognized core format: " + head[:4].hex())


def inspect_tool(variable, default, arguments):
    command = shlex.split(os.environ.get(variable, default))
    if not command or not shutil.which(command[0]):
        raise RuntimeError("Required binary inspection tool is missing: " + default)
    try:
        return subprocess.check_output(command + arguments, stderr=subprocess.STDOUT,
                                       env=dict(os.environ, LC_ALL="C"),
                                       universal_newlines=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("Binary inspection failed with %s: %s" % (default, error))


def require_exports(names, expected):
    if sorted(names) != sorted(expected):
        raise RuntimeError("Binary exports differ: missing=%r extra=%r" %
                           (sorted(set(expected) - set(names)), sorted(set(names) - set(expected))))


def require_dependencies(names, allowed):
    foreign = set(names) - allowed
    if not names or foreign:
        raise RuntimeError("Missing or unexpected dynamic dependencies: " + repr(sorted(foreign)))


def elf_exports(path):
    """Use the architecture-independent ELF reader; errors must stop release checks."""
    listing = inspect_tool("READELF", "readelf", ["--dyn-syms", "--wide", str(path)])
    # AArch64 can insert [VARIANT_PCS] between visibility and section index.
    entries = re.findall(r"^\s*\d+:\s+\S+\s+\S+\s+FUNC\s+(?:GLOBAL|WEAK)\s+"
                         r"(?:DEFAULT|PROTECTED)\s+(?:\[[^]]+\]\s+)?(\S+)\s+(\S+)",
                         listing, re.M)
    return sorted(name.split("@", 1)[0] for section, name in entries if section != "UND")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=str)
    parser.add_argument("--sources-only", action="store_true")
    parser.add_argument("--target", choices=("linux-x86_64", "linux-aarch64", "recalbox-aarch64",
                                             "windows-x86_64", "android-arm64", "macos-x86_64", "macos-arm64"))
    args = parser.parse_args()
    check_sources()
    if args.binary:
        release.verify_notices(Path(args.binary))
        print("Matching notices embedded in binary: OK")
        check_binary(args.binary, args.target)
    if not args.sources_only:
        primitives()


if __name__ == "__main__":
    main()
