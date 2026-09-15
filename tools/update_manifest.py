#!/usr/bin/env python3
"""Refresh local modification hashes after reviewing source changes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import release


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    root = release.ROOT
    release.verify_notices()
    for directory in sorted((root / "src/engines").iterdir()):
        path = directory / "ANYBOR-SOURCE.json"
        data = release.read_json(path)
        old = data["files"]
        files = {}
        for source in sorted(directory.rglob("*")):
            if not source.is_file() or source == path:
                continue
            rel = source.relative_to(directory).as_posix()
            original = old.get(rel, {}).get("upstream_sha256")
            checksum = release.sha256(source)
            # Retain the modification explanation and source topics.
            entry = dict(old.get(rel, {}))
            entry.update({"upstream_sha256": original,
                          "distributed_sha256": checksum,
                          "modified": checksum != original})
            files[rel] = entry
        data["files"] = files
        write_json(path, data)
    for directory in sorted((root / "src/deps").iterdir()):
        path = directory / "ANYBOR-SOURCE.json"
        data = release.read_json(path)
        old = data["files"]
        current = {p.relative_to(directory).as_posix(): release.sha256(p)
                   for p in sorted(directory.rglob("*")) if p.is_file() and p != path}
        changed = sorted(n for n in set(old) | set(current) if old.get(n) != current.get(n))
        data["locally_modified_files"] = sorted(set(data.get("locally_modified_files", [])) | set(changed))
        data["files"] = current
        write_json(path, data)
    pin = release.read_json(root / "src/pin.json")
    write_json(root / "SOURCES.json", {"schema": 1, "version": pin["version"],
                                     "files": release.inventory()})
    print("Local source hashes updated; original upstream hashes and pins retained.")


if __name__ == "__main__":
    main()
