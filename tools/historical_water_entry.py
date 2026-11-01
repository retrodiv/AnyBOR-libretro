"""Check indexed water remap/blend ordering and the actual parent route.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path

from historical_water_phase import water_source


def render_water_entry(engine, fixture):
    rows = fixture['sources']
    if (not 1 <= len(rows) <= 128 or len({r['revision'] for r in rows}) != len(rows) or
            any(type(r['revision']) is not int or not 0 < r['revision'] <= 0xffffffff or
                type(r['unified']) is not bool for r in rows)):
        raise ValueError('Unique bounded water entry contexts required')
    code = (Path(__file__).parent/'fixtures/early_water_entry.c').read_text()
    checks = '\n'.join('check(%d,%d);' % (r['revision'],r['unified']) for r in rows)
    return code.replace('@NATIVE@',water_source(engine,include_entry=True)).replace('@CHECKS@',checks)
