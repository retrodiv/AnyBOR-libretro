"""Check native text-table extents, staged counts and bounded loop consumers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent
ENGINES = ('6391', '7142', '7533', '8023')


def program(engine, profiles):
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    release = function(core, 'free_level')
    ownership = '#include "anybor_text_table_ownership.inc"'
    if script.count(ownership) != 1:
        raise ValueError('Native text table ownership helpers required')
    visible = 'obor_textobjs_release_visible(lv);'
    final = 'obor_textobjs_release_all(lv);'
    if (release.count(visible) != 1 or release.count(final) != 1 or
            not release.index(visible) < release.index('Script_Clear(') < release.index(final)):
        raise ValueError('Visible text must retire before callbacks and tables after them')
    draw = function(core, 'draw_textobjs')
    font_source = (engine / 'source/gamelib/font.c').read_text(encoding='latin1')
    font_observers = []
    for name in ('font_printf', 'font_print_length'):
        if re.search(r'\b' + name + r'\s*\(', draw):
            font = function(font_source, name)
            font_observers.append(font[:font.index('{')] + '{ ++font_calls; }')
    if not font_observers:
        raise ValueError('Native text drawing service required')
    clock = re.search(r'(?m)^\s*(?:u32|uint64_t)\s+_time\s*=\s*0;', core)
    if clock is None:
        raise ValueError('Native text timer declaration required')
    code = (HERE / 'text_object_tables_contract.c.in').read_text()
    parts = dict(OWNERSHIP=ownership, VISIBLE=visible, RELEASE=final,
                 DRAW=draw, CLOCK=clock[0].strip(), FONT='\n'.join(font_observers),
                 PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                                   for p in profiles))
    for name, value in parts.items():
        code = code.replace('@' + name + '@', value)
    return code


class NativeTextTableTests(unittest.TestCase):
    def test_staged_counts_views_growth_and_consumers_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for build in ENGINES:
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                output = native_output(program(ROOT / 'src/engines' / build, profiles),
                                       {'engine': build})
                self.assertEqual(json.loads(output), dict(status='PASS', profiles=len(profiles),
                                                          scenarios=16 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
