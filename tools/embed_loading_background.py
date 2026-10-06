#!/usr/bin/env python3
"""Build native preparation backgrounds from the single master image.

The build generates three centred Lanczos3 cover resizes and embeds them with
the unchanged master. Pillow is a host authoring tool, never a core dependency.
A validated generated source copy also supports build hosts without Pillow.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import zlib


DIMENSIONS = ((320, 240), (480, 272), (640, 480), (3200, 1800))


def cover_image(master, width, height):
    from PIL import Image
    sw, sh = master.size
    cw, ch = float(sw), float(sh)
    if width * sh < height * sw:
        cw = float(sh) * width / height
    else:
        ch = float(sw) * height / width
    left, top = (sw-cw)/2.0, (sh-ch)/2.0
    lanczos = getattr(Image, 'Resampling', Image).LANCZOS
    return master.resize((width, height), lanczos, box=(left, top, left+cw, top+ch))


def input_signature(glue):
    source = glue / 'assets/OpenBOR_Logo_3200x1800.png'
    return '/* Master SHA-256: %s; generator SHA-256: %s. */\n' % (
        hashlib.sha256(source.read_bytes()).hexdigest(),
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def generate(glue, output, allow_cache=False):
    signature = input_signature(glue)
    try:
        from PIL import Image
    except ImportError:
        cached = glue / 'obor_loading_background.h'
        if allow_cache and cached.is_file() and signature in cached.read_text():
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.resolve() != cached.resolve():
                shutil.copyfile(str(cached), str(output))
            print('Validated precomputed loading backgrounds (Pillow unavailable).')
            return
        raise SystemExit('Pillow is required to regenerate loading artwork: '
                         'install it for the build host Python interpreter.')
    source = glue / 'assets/OpenBOR_Logo_3200x1800.png'
    with Image.open(source) as image:
        if image.size != (3200, 1800):
            raise SystemExit('Unexpected dimensions in ' + str(source))
        master = image.convert('RGB')
    parts = ['''/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2003, Roel van Mastbergen & Senile Team
 * Copyright (c) 2004 - 2018, OpenBOR Team
 * OpenBOR logo design credited to Fightn' Words in upstream history.
 * Preparation layout adaptation: Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Generated from assets/OpenBOR_Logo_3200x1800.png with centred Lanczos3
 * filtering by tools/embed_loading_background.py.
 * See assets/README.md and assets/LICENSE. */
''', signature, '''#ifndef OBOR_LOADING_BACKGROUND_H
#define OBOR_LOADING_BACKGROUND_H
typedef struct obor_loading_asset {
    int width, height;
    const unsigned char *data;
    unsigned long size;
} obor_loading_asset;
''']
    total = 0
    for width, height in DIMENSIONS:
        image = master if master.size == (width, height) else cover_image(master, width, height)
        pixels = zlib.compress(image.tobytes(), 9)
        symbol = 'obor_loading_background_%dx%d' % (width, height)
        parts.append('static const unsigned char %s[] = {\n' % symbol)
        for start in range(0, len(pixels), 24):
            parts.append('    ' + ', '.join('0x%02x' % b for b in pixels[start:start + 24]) + ',\n')
        parts.append('};\n')
        total += len(pixels)
    parts.append('static const obor_loading_asset obor_loading_assets[] = {\n')
    for width, height in DIMENSIONS:
        symbol = 'obor_loading_background_%dx%d' % (width, height)
        parts.append('    { %d, %d, %s, sizeof(%s) },\n' % (width, height, symbol, symbol))
    parts.append('};\n#endif\n')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(parts))
    print('Built three Lanczos3 backgrounds and embedded the master (%d compressed RGB bytes).' % total)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--glue', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'src/glue')
    parser.add_argument('--output', type=Path, help='generated header (defaults to the source copy)')
    parser.add_argument('--allow-cache', action='store_true',
                        help='without Pillow, accept the precomputed copy only if both inputs match')
    args = parser.parse_args()
    generate(args.glue, args.output or args.glue / 'obor_loading_background.h', args.allow_cache)


if __name__ == '__main__':
    main()
