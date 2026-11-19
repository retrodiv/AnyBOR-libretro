"""Execute the native entity renderer with historical shadow and sorting inputs.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-shadow-contracts.json'
FIELDS = (
    'route', 'shadowbase', 'subject', 'platform', 'tile_height', 'old_hole', 'new_hole',
    'pair', 'bound', 'owner', 'grab', 'context_move', 'actor_move', 'dying', 'health', 'late_flash',
)


def program(data, previous=None):
    engine = ROOT / 'src/engines' / data['engine']
    core = previous if previous is not None else (engine / 'openbor.c').read_text(encoding='latin1')
    plain = re.search(r'(?ms)^const s_drawmethod plainmethod\s*=\s*\{.*?^\};', core)
    if plain is None:
        raise ValueError('Native plain drawing initializer required')
    # The original platform-row check compares the address of an inline array.
    native = ('#pragma GCC diagnostic push\n'
              '#pragma GCC diagnostic ignored "-Waddress"\n'
              '#ifdef __clang__\n'
              '#pragma clang diagnostic ignored "-Wpointer-bool-conversion"\n'
              '#endif\n' +
              function(core, 'display_ents') + '#pragma GCC diagnostic pop\n')
    if 'static int obor_shadow_in_hole(' in core:
        native = function(core, 'obor_shadow_in_hole') + '\n' + native
    values = {
        'PLAIN': plain[0],
        'NATIVE': native,
        'CASES': ',\n'.join('{' + ','.join(str(row[key]) for key in FIELDS) + '}' for row in data['cases']),
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    template = Path(__file__).with_name('entity_shadow_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class HistoricalEntityShadowTests(unittest.TestCase):
    def test_native_binding_positions_animation_and_script_sort_argument(self):
        fixture = FIXTURE.with_name('profile-4432-entity-binding-contracts.json')
        data = load_contract_fixture(fixture)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(data, pin['profiles'], source_range=data['range']):
            if profile['engine'] == data['engine']:
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        engine = ROOT / 'src/engines' / data['engine']
        source = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        values = dict(
            METHODS='\n'.join((function(variant, 'ScriptVariant_IntegerValue'),
                               function(source, 'adjust_bind'), function(script, 'openbor_bindentity'))),
            PROFILES=',\n'.join('{%du,%d}' % (row['revision'], row['has_sort']) for row in rows))
        template = Path(__file__).with_name('entity_binding_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda item: values[item[1]], template)
        result = json.loads(native_output(probe, data, extra_cflags=('-fgnu89-inline',)))
        self.assertEqual(result, {'contexts': len(rows), 'checks': 23 * len(rows)})

    def test_native_shadows_remaps_and_queue_order(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        observed = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(observed), len(rows))
        for actual, row in zip(observed, rows):
            expected = data['contracts'][row['contract']]
            with self.subTest(revision=row['revision']):
                self.assertEqual(actual['revision'], row['revision'])
                self.assertEqual(len(actual['cases']), len(data['cases']))
                for case, result, want in zip(data['cases'], actual['cases'], expected):
                    self.assertEqual(result, want, case['name'])


if __name__ == '__main__':
    unittest.main()
