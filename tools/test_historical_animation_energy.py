"""Verify the native energy check for free and paid animations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-animation-energy-contracts.json'
FIELDS = ('declared', 'cost', 'mode', 'disabled', 'seal', 'mp', 'hp', 'type', 'frames')


def program(data, source):
    rows = ',\n'.join('{' + ','.join(str(case[key]) for key in FIELDS) + '}'
                      for case in data['cases'])
    builds = ','.join(str(row['revision']) for row in data['sources'])
    translator = function(source, 'translate_ani_id')
    start = translator.index('else if(stricmp(value, "special")')
    end = translator.index('else if(starts_with_num(value, "freespecial")', start)
    special_defaults = translator[start + len('else '):end]
    template = Path(__file__).with_name('animation_energy_contract.c.in').read_text()
    return (template.replace('@ENERGY_CHECK@', function(source, 'check_energy'))
            .replace('@JUMP_CHECK@', function(source, 'player_jump_check'))
            .replace('@SPECIAL_DEFAULTS@', special_defaults)
            .replace('@PROFILES@', builds).replace('@CASES@', rows))


class HistoricalAnimationEnergyTests(unittest.TestCase):
    def test_native_eligibility_and_aerial_special(self):
        data = load_contract_fixture(FIXTURE)
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data, source), data).splitlines()]
        self.assertEqual([row[0] for row in actual], revisions)
        for row, (_, results, aliases) in zip(data['sources'], actual):
            expected = data['contracts'][row['contract']]
            self.assertEqual(len(results), len(expected))
            self.assertEqual(len(results), len(data['cases']))
            for case, result, want in zip(data['cases'], results, expected):
                with self.subTest(revision=row['revision'], case=case['name']):
                    self.assertEqual(result, want)
            with self.subTest(revision=row['revision'], case='special defaults'):
                self.assertEqual(aliases, data['special_defaults'][row['special_defaults']])


if __name__ == '__main__':
    unittest.main()
