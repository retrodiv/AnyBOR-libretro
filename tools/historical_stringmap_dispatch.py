"""Keep a complete native string-map dispatcher in a bounded address probe.

Only explicitly retained callback and mapper addresses remain external. Other
address references receive distinct sentinels which refuse being called. This
checks dispatch selection, not execution of the unrelated API functions.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_dispatch(source, *, retained_references,
                    function_name='Script_GetStringMapFunction'):
    identifier = r'[A-Za-z_]\w*'
    if (not isinstance(function_name, str) or
            not re.fullmatch(identifier, function_name) or
            not isinstance(source, str) or not 0 < len(source) <= 65536 or
            '\0' in source or not re.match(
                r'\s*void\s*\*\s*' + re.escape(function_name) + r'\s*\(', source)):
        raise ValueError('A complete bounded native address dispatcher is required')
    if (not isinstance(retained_references, list) or
            not 1 <= len(retained_references) <= 16 or
            any(not isinstance(n, str) or not re.fullmatch(identifier, n)
                for n in retained_references) or
            len(set(retained_references)) != len(retained_references)):
        raise ValueError('Explicit unique retained native address references required')
    # Keep comments/literals out of the address inventory without rewriting
    # the original definition used by the compiler.
    tokens = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|'
                        r"'(?:\\.|[^'\\])*'", re.S)
    masked = tokens.sub(lambda m: ' ' * len(m[0]), source)
    references = set(re.findall(r'\(\s*void\s*\*\s*\)\s*(' + identifier + ')', masked))
    if (not 1 <= len(references) <= 1024 or
            not set(retained_references) <= references or
            'obor_map_external_' in source):
        raise ValueError('Retained addresses must exist in the native dispatcher')
    external = sorted(references - set(retained_references))
    rows = []
    for index, name in enumerate(external):
        local = 'obor_map_external_' + str(index)
        rows += ['static void ' + local + '(void){abort();}',
                 '#define ' + name + ' ' + local]
    rows += [source]
    rows += ['#undef ' + name for name in external]
    return '\n'.join(rows) + '\n'
