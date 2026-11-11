"""Check native projectile health stores at their defined arithmetic bounds.

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


def program(engine, profiles):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    # This component executes stores only. Require the actual scalar type;
    # entity layout, collision decisions and physics callbacks are separate.
    if not re.search(r'\bint\s+health;\s*// current hp', header):
        raise ValueError('Native integer entity health declaration required')
    stores = []
    for name, count in (('arrow_move', 1), ('star_move', 2)):
        body = function(source, name)
        assignments = re.findall(r'self->health\s*=\s*[^;]+;', body)
        if len(assignments) != count:
            raise ValueError('Expected complete native terminal health stores')
        stores.extend(assignments)
    functions = '\n'.join(
        'static int site_%d(int health) { struct {int health;} object={health}, *self=&object; '
        '%s return self->health; }' % (i, store) for i, store in enumerate(stores))
    text = (HERE / 'projectile_terminal_health_contract.c.in').read_text()
    text = text.replace('@STORES@', functions)
    return text.replace('@PROFILES@', ','.join(
        str(int(p.get('revision', p['build'].split('-')[0]))) + 'u' for p in profiles))


class ProjectileTerminalHealthTests(unittest.TestCase):
    def test_all_native_stores_preserve_defined_discount_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        profiles = [p for p in pin['profiles'] if p['engine'] == '3400']
        self.assertTrue(profiles)
        result = json.loads(native_output(program(ROOT / 'src/engines/3400', profiles),
                                          {'engine': '3400'}))
        self.assertEqual(result, dict(status='PASS', profiles=len(profiles),
                                      stores=3, cases=33 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
