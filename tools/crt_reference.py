"""Independent floating-point oracle for sharp-bilinear CRT composition.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math


def axis(source, dest, scale):
    result = []
    region = 0.5 - 0.5 / scale
    for pixel in range(dest):
        texel = (pixel + 0.5) * source / dest
        whole = math.floor(texel)
        distance = texel - whole - 0.5
        offset = (distance - max(-region, min(region, distance))) * scale + 0.5
        coordinate = max(0.0, min(source - 1.0, whole + offset - 0.5))
        first = math.floor(coordinate)
        result.append((first, min(first + 1, source - 1), coordinate - first))
    return result


def compose(width, height, pixels):
    """Return RGB bytes, with one rounding after the full bilinear operation."""
    scale = min(640 / width, 480 / height)
    dw, dh = max(1, int(width * scale)), max(1, int(height * scale))
    left, top = (640 - dw) // 2, (480 - dh) // 2
    columns, rows = axis(width, dw, math.ceil(scale)), axis(height, dh, math.ceil(scale))
    result = bytearray(640 * 480 * 3)
    for y, (ya, yb, wy) in enumerate(rows):
        for x, (xa, xb, wx) in enumerate(columns):
            a, b = (ya * width + xa) * 3, (ya * width + xb) * 3
            c, d = (yb * width + xa) * 3, (yb * width + xb) * 3
            dest = ((top + y) * 640 + left + x) * 3
            for channel in range(3):
                upper = pixels[a + channel] * (1 - wx) + pixels[b + channel] * wx
                lower = pixels[c + channel] * (1 - wx) + pixels[d + channel] * wx
                result[dest + channel] = int(upper * (1 - wy) + lower * wy + 0.5)
    return result


def assert_matches(actual, expected):
    assert len(actual) == len(expected)
    # The core rounds Q16 weights and each separable pass. Allow one 8-bit
    # channel level compared with a single-rounding floating-point oracle.
    error = max(abs(a - b) for a, b in zip(actual, expected))
    assert error <= 1, "Sharp-bilinear reference mismatch: max channel error %d" % error
