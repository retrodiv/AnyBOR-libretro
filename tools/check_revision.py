#!/usr/bin/env python3
"""Check the source inventory in a Git revision, independently of the checkout.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def check_revision(root, revision):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root)] + list(args))

    tree = git('rev-parse', '--verify', revision + '^{tree}').decode().strip()
    records = git('ls-tree', '-r', '-z', tree).split(b'\0')
    blobs = {}
    for record in records:
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        name = name.decode('utf-8')
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise RuntimeError('Non-regular source in revision: ' + name)
        blobs[name] = oid
    manifest = json.loads(git('show', tree + ':SOURCES.json').decode('utf-8'))
    expected = manifest['files']
    del blobs['SOURCES.json']
    if set(blobs) != set(expected):
        changed = sorted(set(blobs).symmetric_difference(expected))
        raise RuntimeError('Source inventory file set changed in revision: ' + ', '.join(changed[:10]))

    # Stream each blob once. Hash the pushed tree, never unstaged or staged
    # repairs, and do not execute scripts taken from that revision.
    process = subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    changed, checksums = [], {}
    try:
        for name, oid in sorted(blobs.items()):
            if oid not in checksums:
                process.stdin.write(oid + b'\n')
                process.stdin.flush()
                header = process.stdout.readline().split()
                if len(header) != 3 or header[1] != b'blob':
                    raise RuntimeError('Cannot read source blob: ' + name)
                remaining = int(header[2])
                digest = hashlib.sha256()
                while remaining:
                    block = process.stdout.read(min(remaining, 1048576))
                    if not block:
                        raise RuntimeError('Truncated source blob: ' + name)
                    digest.update(block)
                    remaining -= len(block)
                if process.stdout.read(1) != b'\n':
                    raise RuntimeError('Invalid Git blob delimiter')
                checksums[oid] = digest.hexdigest()
            if checksums[oid] != expected[name]:
                changed.append(name)
        process.stdin.close()
        if process.wait(timeout=10):
            raise RuntimeError('Git blob reader failed')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()
    if changed:
        raise RuntimeError('Source inventory changed in revision: ' + ', '.join(changed[:10]))
    print('Committed source inventory: OK (' + revision + ')')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', nargs='?', default='HEAD')
    args = parser.parse_args()
    check_revision(Path(__file__).resolve().parents[1], args.revision)


if __name__ == '__main__':
    main()
