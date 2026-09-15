#!/usr/bin/env python3
"""Generate original geometric diagnostic content; no external game assets.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
The generated scripts and graphics are offered under the same license.
"""
import argparse
import binascii
import struct
import zlib
from pathlib import Path


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", binascii.crc32(tag + data) & 0xffffffff)


def png(width, height, sample):
    palette = bytes([0, 0, 0, 80, 230, 140, 240, 240, 240, 25, 45, 80]) + bytes(252 * 3)
    rows = b"".join(b"\0" + bytes(sample(x, y) for x in range(width)) for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)) +
            chunk(b"PLTE", palette) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def files():
    result = {
        "data/models.txt": b"load TestBlock data/chars/block.txt\n",
        "data/levels.txt": b"set Diagnostics\nfile data/levels/room.txt\n",
        "data/levels/room.txt": b"background data/bgs/room.png\npanel data/bgs/room.png\norder a\n",
        "data/chars/block.txt": (b"name TestBlock\ntype player\nhealth 100\nspeed 2\nshadow 0\n"
                                  b"anim idle\nloop 1\ndelay 10\noffset 8 31\nbbox 0 0 16 32\nframe data/chars/block.png\n"
                                  b"anim walk\nloop 1\ndelay 10\noffset 8 31\nbbox 0 0 16 32\nframe data/chars/block.png\n"),
    }
    result["data/chars/block.png"] = png(16, 32, lambda x, y: 1 if 1 < x < 14 and 1 < y < 30 else 0)
    room = png(320, 240, lambda x, y: 1 if y > 205 else (2 if x % 64 == 0 or y % 48 == 0 else 3))
    for name in ("room", "logo", "title", "titleb", "select", "loading", "loading2", "hiscore", "complete", "unlockbg"):
        result["data/bgs/" + name + ".png"] = room
    # Synthetic markers stand in for glyphs. No font bitmap is copied.
    font = png(128, 128, lambda x, y: 2 if 1 <= x % 8 <= 5 and 1 <= y % 8 <= 6 and
               ((x % 8 in (1, 5)) or y % 8 in (1, 6)) else 0)
    for number in ("", "2", "3", "4"):
        result["data/sprites/font" + number + ".png"] = font
    samples = b"".join(struct.pack("<h", ((i % 100) - 50) * 100) for i in range(2205))
    tone = (b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 1, 22050, 44100, 2, 16) +
            b"data" + struct.pack("<I", len(samples)) + samples)
    for name in ("go", "beat1", "block", "fall", "get", "money", "jump", "indirect", "punch", "1up", "timeover", "beep", "beep2", "bike"):
        result["data/sounds/" + name + ".wav"] = tone
    return result


def write_pak(path, members):
    data = bytearray(b"PACK\0\0\0\0")
    entries = []
    for name, content in sorted(members.items()):
        entries.append((name, len(data), len(content)))
        data += content
    directory = len(data)
    for name, start, size in entries:
        encoded = name.encode("ascii") + b"\0"
        data += struct.pack("<III", 12 + len(encoded), start, size) + encoded
    data += struct.pack("<I", directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".build/fixtures/diagnostic.pak")
    args = parser.parse_args()
    path = Path(args.output)
    write_pak(path, files())
    print(str(path))


if __name__ == "__main__":
    main()
