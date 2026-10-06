#!/usr/bin/env python3
"""Embed the authored preparation background without a runtime image decoder.

Run after replacing src/glue/assets/OpenBOR_Logo_320x240.png. Pillow is needed
only for this authoring step; builds use the resulting header as ordinary source.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--glue', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'src/glue')
    glue = parser.parse_args().glue
    source = glue / 'assets/OpenBOR_Logo_320x240.png'
    with Image.open(source) as image:
        if image.size != (320, 240):
            raise SystemExit('The preparation background must be 320x240.')
        pixels = image.convert('RGB').tobytes()
    header = '''/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2003, Roel van Mastbergen & Senile Team
 * Copyright (c) 2004 - 2018, OpenBOR Team
 * OpenBOR logo design credited to Fightn' Words in upstream history.
 * Preparation layout adaptation: Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Generated from assets/OpenBOR_Logo_320x240.png by
 * tools/embed_loading_background.py. See assets/README.md and assets/LICENSE. */
#ifndef OBOR_LOADING_BACKGROUND_H
#define OBOR_LOADING_BACKGROUND_H
static const unsigned char obor_loading_background[320 * 240 * 3] = {
'''
    for start in range(0, len(pixels), 24):
        header += '    ' + ', '.join('0x%02x' % b for b in pixels[start:start + 24]) + ',\n'
    (glue / 'obor_loading_background.h').write_text(header + '};\n#endif\n')
    print('Embedded the 320x240 preparation background (%d RGB bytes).' % len(pixels))


if __name__ == '__main__':
    main()
