#!/usr/bin/env python3
"""Reuse the exact packaged core in an independent CI runtime runner.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import release


def unpack(package, target, destination, source_digest):
    package, destination = Path(package), Path(destination)
    expected = package.with_name(package.name + '.sha256').read_text().split()
    if expected != [release.sha256(package), package.name]:
        raise ValueError('CI package checksum differs')
    with zipfile.ZipFile(package) as archive:
        receipt_bytes = archive.read('build.json')
        receipt = json.loads(receipt_bytes)
        metadata = json.loads(archive.read('PACKAGE.json'))
        binary = receipt['binary']
        if (binary not in release.CORE_BINARIES or receipt['target'] != target
                or receipt['source_digest'] != source_digest
                or metadata['source_digest'] != source_digest
                or metadata['binary'] != binary
                or metadata['binary_sha256'] != receipt['sha256']
                or metadata['build_receipt_sha256'] != hashlib.sha256(receipt_bytes).hexdigest()):
            raise ValueError('CI package does not match the checkout and target')
        if archive.getinfo(binary).file_size > 256 * 1024 * 1024:
            raise ValueError('Unexpected core size')
        payload = archive.read(binary)
        if hashlib.sha256(payload).hexdigest() != receipt['sha256']:
            raise ValueError('CI core checksum differs')
    output = destination / binary
    with output.open('xb') as stream:
        stream.write(payload)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    packages = list((release.ROOT / '.build/ci-package').rglob('*.zip'))
    if len(packages) != 1:
        parser.error('Expected exactly one release package from this workflow')
    receipt = unpack(packages[0], args.target, release.ROOT,
                     release.source_digest(release.source_files()))
    print('Reused packaged core:', receipt['target'], receipt['sha256'], flush=True)


if __name__ == '__main__':
    main()
