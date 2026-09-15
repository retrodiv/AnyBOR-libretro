#!/usr/bin/env python3
"""Package exactly the reviewed source inventory, with no build workspace.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import zipfile
from pathlib import Path
import check
import release


def package(dest):
    check.check_sources()
    root = release.ROOT
    pin = release.read_json(root / "src/pin.json")
    files = dict(release.read_json(root / "SOURCES.json")["files"])
    files["SOURCES.json"] = release.sha256(root / "SOURCES.json")
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / (pin["core_basename"] + "-" + pin["version"] + "-source.zip")
    temporary = archive.with_suffix(".zip.tmp")
    prefix = "AnyBOR-libretro/"
    try:
        with zipfile.ZipFile(str(temporary), "w", zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(files):
                zf.write(str(root / name), prefix + name)
        with zipfile.ZipFile(str(temporary)) as zf:
            if sorted(zf.namelist()) != sorted(prefix + name for name in files):
                raise RuntimeError("Source archive file set differs from its inventory")
            for name, checksum in files.items():
                if hashlib.sha256(zf.read(prefix + name)).hexdigest() != checksum:
                    raise RuntimeError("Source changed during packaging: " + name)
        temporary.replace(archive)
    finally:
        if temporary.exists():
            temporary.unlink()
    (dest / (archive.name + ".sha256")).write_text(
        release.sha256(archive) + "  " + archive.name + "\n", encoding="utf-8")
    print(str(archive))
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path("dist"))
    args = parser.parse_args()
    package(args.dest)


if __name__ == "__main__":
    main()
