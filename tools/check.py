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
import subprocess
import tempfile
from pathlib import Path
import release
from check_modifications import check_modifications
from check_core_info import check_core_info

ROOT = release.ROOT


def check_sources():
    expected = release.read_json(ROOT / "SOURCES.json")["files"]
    current = release.source_files()
    if current != expected:
        changed = [n for n in current if current[n] != expected.get(n)]
        raise RuntimeError("Source inventory changed: " + ", ".join(changed[:10]))
    release.verify_notices()
    for name in current:
        path = ROOT / name
        if path.suffix.lower() in (".pak", ".exe", ".dll", ".so", ".ogg", ".wav", ".webm"):
            raise RuntimeError("Binary or game payload in source inventory: " + name)
        if ".git" in path.relative_to(ROOT).parts or path.is_symlink():
            raise RuntimeError("History or symlink in source inventory: " + name)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=str)
    parser.add_argument("--sources-only", action="store_true")
    args = parser.parse_args()
    check_sources()
    if args.binary:
        release.verify_notices(Path(args.binary))
        print("Matching notices embedded in binary: OK")
    if not args.sources_only:
        primitives()


if __name__ == "__main__":
    main()
