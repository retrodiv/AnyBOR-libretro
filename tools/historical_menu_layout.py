"""Select an intact native render prefix before a named frame boundary.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

DATA = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\[\s\S]|[^"\\])*"|'
                  r"'(?:\\[\s\S]|[^'\\])*'", re.S)


def frame_prefix(source, *, condition, boundary):
    """Keep branches, loops and preprocessing; refuse a nested frame boundary."""
    if (not isinstance(source, str) or not 0 < len(source) <= 262144 or '\0' in source
            or not isinstance(condition, str) or not re.fullmatch(r'!?[A-Za-z_]\w*', condition)
            or not isinstance(boundary, str) or not re.fullmatch(r'[A-Za-z_]\w*', boundary)):
        raise ValueError('Bounded native source and explicit loop/boundary identifiers required')
    masked = DATA.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), source)
    loops = list(re.finditer(r'\bwhile\s*\(\s*' + re.escape(condition) + r'\s*\)\s*\{', masked))
    if len(loops) != 1:
        raise ValueError('One complete named native frame loop required')
    start = loops[0].end()
    stop = re.search(r'\b' + re.escape(boundary) + r'\s*\(', masked[start:])
    if stop is None:
        raise ValueError('Native frame boundary missing')
    end = start + stop.start()
    depth = 0
    for token in re.finditer(r'[{}]', masked[start:end]):
        depth += 1 if token[0] == '{' else -1
        if depth < 0:
            raise ValueError('Boundary is outside the selected frame loop')
    if depth:
        raise ValueError('Boundary must follow complete render branches')
    return source[start:end]
