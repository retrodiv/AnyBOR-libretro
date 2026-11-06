"""Check source-owned background cache lifetime,reuse,neon and clocks.

Pixel operations are typed providers;their raster has separate consumers.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture,contract_revisions
from test_historical_common_think import ROOT,native_output
from test_historical_hud_schedule import native_declarations
from test_historical_player import function

FIXTURE=Path(__file__).with_name('fixtures')/'profile-background-cache-contracts.json'


def program(data):
    core=(ROOT/'src/engines'/data['engine']/'openbor.c').read_text()
    names=['obor_legacy_background_cache_load','obor_legacy_background_cache_unload',
           'obor_legacy_cached_bg','obor_legacy_canvas_bg','draw_scrolled_bg','update_scrolled_bg']
    native=[]
    for name in names:
        if name in ('draw_scrolled_bg','update_scrolled_bg') or ('static void '+name+'(') in core:
            native.append(function(core,name))
        elif name in names[:2]:
            native.append('static void '+name+'(void){}')
    if 'static void obor_legacy_background_cache_load(' in core:
        load=function(core,'load_level');unload=function(core,'unload_level')
        if not re.search(r'obor_legacy_background_cache_load\(\);\s*if\(musicPath\[0\]\)',load):
            raise AssertionError('Cache load must follow layer construction before music')
        if not re.search(r'unload_background\(\);\s*obor_legacy_background_cache_unload\(\);\s*if\(level\)',unload):
            raise AssertionError('Cache release must precede the level-presence guard')
    globals_='' if re.search(r'(?m)^static s_screen \*bgbuffer\s*=',core) else 'static s_screen *bgbuffer;static char bgbuffer_updated;'
    values=dict(DECLARATIONS=native_declarations(core),CACHE_GLOBALS=globals_,NATIVE='\n'.join(native),
        CONTEXTS=','.join('{%d,%d,%d,%d}'%(r['revision'],r['legacy_cache'],r['always_quake_timer'],r['zero_time_offset'])for r in data['sources']))
    text=Path(__file__).with_name('background_cache_contract.c.in').read_text()
    for name,value in values.items():text=text.replace('@'+name+'@',value)
    if re.search(r'@[A-Z_]+@',text):raise AssertionError('Unresolved native cache dependency')
    return text


class HistoricalBackgroundCache(unittest.TestCase):
    def test_owned_lifetime_repaint_reuse_palette_and_clocks(self):
        data=load_contract_fixture(FIXTURE);revisions=[r['revision']for r in data['sources']]
        self.assertEqual(len(revisions),len(set(revisions)))
        self.assertEqual(set(revisions),contract_revisions(data,data['expected_revisions']))
        actual=[json.loads(line)for line in native_output(program(data),data).splitlines()]
        self.assertEqual(actual,[dict(revision=r['revision'],cases=52 if r['legacy_cache']else 19,status='PASS')for r in data['sources']])


if __name__=='__main__':unittest.main()
