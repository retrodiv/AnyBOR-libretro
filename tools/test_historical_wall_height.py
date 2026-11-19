"""Exercise the wall-height script argument and native wall selection.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_entity_namespace import declaration
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-wall-height-contracts.json'


def program(data, original=None):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()

    def native(source, name):
        return original[name] if original else function(source, name)

    values = {
        'WALLS': declaration((engine / 'openbor.h').read_text(), r'typedef struct\s*\{[^{}]*\}\s*s_terrain;'),
        'GEOMETRY': '' if original else function(core, 'obor_terrain_between'),
        'CORE': '\n'.join(native(core, name) for name in ('testwall', 'checkwall_below')),
        'SCRIPT': rename_identifiers(native(script, 'openbor_checkwall'), {'checkwall_below': 'observe_wall'}),
        'VARIANTS': '\n'.join(native(variant, name) for name in ('ScriptVariant_Init', 'ScriptVariant_Copy',
                                                                 'ScriptVariant_DecimalValue', 'ScriptVariant_ChangeType')),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'CASES': ',\n'.join('{%d,%d,%d,%.17g,%.17g,%.17g,%.17g}' % (
            row['argc'], row['kind'], row['level'], row['x'], row['z'], row['y'], row['seed']) for row in data['cases']),
    }
    template = Path(__file__).with_name('wall_height_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class WallHeightContracts(unittest.TestCase):
    def test_original_script_height_and_wall_selection(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = iter(native_output(program(data), data).splitlines())
        for row in data['sources']:
            for index, case in enumerate(data['cases']):
                self.assertEqual(json.loads(next(actual)), [row['revision'], index, *case['outcomes'][row['contract']]],
                                 (row['revision'], case['name']))
        self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
