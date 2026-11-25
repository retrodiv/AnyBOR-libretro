#!/usr/bin/env python3
"""Print the standard imohash selector for an original PAK or ZIP.

SPDX-License-Identifier: MIT
Copyright (c) 2015 Jim Kalafut
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
The sampling/size format follows imohash; MurmurHash3 is Austin Appleby's
public-domain algorithm. See LICENSES/imohash.txt and LICENSES/murmur3.txt.
"""
import argparse
from pathlib import Path
import stat

MASK = (1 << 64) - 1


def rotate(value, count):
    return ((value << count) | (value >> (64 - count))) & MASK


def mix(value):
    value ^= value >> 33
    value = value * 0xff51afd7ed558ccd & MASK
    value ^= value >> 33
    value = value * 0xc4ceb9fe1a85ec53 & MASK
    return value ^ (value >> 33)


def murmur(data):
    c1, c2 = 0x87c37b91114253d5, 0x4cf5ad432745937f
    h1 = h2 = 0
    end = len(data) // 16 * 16
    for at in range(0, end, 16):
        k1 = int.from_bytes(data[at:at + 8], 'little')
        k2 = int.from_bytes(data[at + 8:at + 16], 'little')
        h1 ^= rotate(k1 * c1 & MASK, 31) * c2 & MASK
        h1 = (rotate(h1, 27) + h2) & MASK
        h1 = (h1 * 5 + 0x52dce729) & MASK
        h2 ^= rotate(k2 * c2 & MASK, 33) * c1 & MASK
        h2 = (rotate(h2, 31) + h1) & MASK
        h2 = (h2 * 5 + 0x38495ab5) & MASK
    tail = data[end:]
    if len(tail) > 8:
        h2 ^= rotate(int.from_bytes(tail[8:], 'little') * c2 & MASK, 33) * c1 & MASK
    if tail:
        h1 ^= rotate(int.from_bytes(tail[:8], 'little') * c1 & MASK, 31) * c2 & MASK
    h1 ^= len(data)
    h2 ^= len(data)
    h1 = (h1 + h2) & MASK
    h2 = (h2 + h1) & MASK
    h1, h2 = mix(h1), mix(h2)
    h1 = (h1 + h2) & MASK
    h2 = (h2 + h1) & MASK
    return bytearray(h1.to_bytes(8, 'big') + h2.to_bytes(8, 'big'))


def selector(stream, size, kind='pak'):
    if kind not in ('pak', 'zip'):
        raise ValueError('Selector kind must be pak or zip')
    if not 0 < size < (1 << 64):
        raise ValueError('A selector requires a positive 64-bit file size')
    offsets = (0,) if size < 131072 else (0, size // 2, size - 16384)
    length = size if size < 131072 else 16384
    samples = []
    for offset in offsets:
        stream.seek(offset)
        block = stream.read(length)
        if len(block) != length:
            raise ValueError('Input changed or could not be read')
        samples.append(block)
    digest = murmur(b''.join(samples))
    remaining, at = size, 0
    while True:
        digest[at] = (remaining & 127) | (128 if remaining >= 128 else 0)
        at += 1
        remaining >>= 7
        if not remaining:
            break
    return f'imohash:{kind}:{digest.hex()}'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('content', type=Path, help='original .pak/.spk before preparation, or complete .zip')
    args = parser.parse_args()
    suffix = args.content.suffix.lower()
    if suffix not in ('.pak', '.spk', '.zip'):
        parser.error('Input must be a .pak, .spk or .zip file')
    if not stat.S_ISREG(args.content.stat().st_mode):
        parser.error('Input must be a regular file')
    with args.content.open('rb') as stream:
        print(selector(stream, args.content.stat().st_size, 'zip' if suffix == '.zip' else 'pak'))


if __name__ == '__main__':
    main()
