"""Split exact C macros/functions to keep native probe compilation bounded.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def split_macro_functions(source, start_marker, end_marker, names):
    """Return the exact prefix and each named function with its macro region."""
    if (not isinstance(source,str) or len(source)>8<<20 or
            not isinstance(start_marker,str) or not start_marker or
            not isinstance(end_marker,str) or not end_marker or
            source.count(start_marker)!=1 or source.count(end_marker)!=1):
        raise ValueError('Bounded source and unique macro delimiters required')
    if (not isinstance(names,(list,tuple)) or not 1<=len(names)<=16 or
            any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z_]\w*',n) for n in names) or
            len(set(names))!=len(names)):
        raise ValueError('Unique bounded C function names required')
    start,end=source.index(start_marker),source.index(end_marker)
    if start>=end:
        raise ValueError('Ordered macro delimiters required')
    macros=source[start:end]
    return [('prefix',source[:start])] + [(name,macros+'\n'+function(source,name)) for name in names]
