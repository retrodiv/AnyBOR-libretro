#!/usr/bin/env python3
"""Archive the checked source inventory for inclusion in a binary package.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import gzip
import hashlib
import io
import tarfile
from pathlib import Path
import release


def source_inventory():
    files = dict(release.read_json(release.ROOT / "SOURCES.json")["files"])
    if release.source_files() != files:
        raise RuntimeError("Source inventory changed before archiving")
    files["SOURCES.json"] = release.sha256(release.ROOT / "SOURCES.json")
    return files


def write_archive(archive, files):
    """Stream one file at a time and validate the archive actually delivered."""
    prefix = "AnyBOR-libretro/"
    epoch = release.read_json(release.ROOT / "src/pin.json")["source_date_epoch"]
    with archive.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tf:
                for name, checksum in sorted(files.items()):
                    path = release.ROOT / name
                    if path.is_symlink():
                        raise RuntimeError("Linked source file: " + name)
                    data = path.read_bytes()
                    if hashlib.sha256(data).hexdigest() != checksum:
                        raise RuntimeError("Source changed while archiving: " + name)
                    info = tarfile.TarInfo(prefix + name)
                    info.size, info.mtime = len(data), epoch
                    info.mode = 0o755 if data.startswith(b"#!") else 0o644
                    tf.addfile(info, io.BytesIO(data))
    with tarfile.open(str(archive), "r:gz") as tf:
        members = tf.getmembers()
        if sorted(m.name for m in members) != sorted(prefix + n for n in files):
            raise RuntimeError("Source archive file set differs from its inventory")
        for member in members:
            if not member.isfile():
                raise RuntimeError("Non-regular source archive member")
            data = tf.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != files[member.name[len(prefix):]]:
                raise RuntimeError("Source archive checksum mismatch: " + member.name)


def package(dest):
    import check
    check.check_sources()
    pin = release.read_json(release.ROOT / "src/pin.json")
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / (pin["core_basename"] + "-" + pin["version"] + "-source.tar.gz")
    temporary = archive.with_name(archive.name + ".tmp")
    try:
        write_archive(temporary, source_inventory())
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
