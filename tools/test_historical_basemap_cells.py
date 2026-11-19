"""Execute the native level property setter across the basemap cell boundary.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-basemap-cell-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    scriptlib = engine / 'source/scriptlib'
    variants = (scriptlib / 'ScriptVariant.c').read_text()
    header = (engine / 'openbor.h').read_text()

    def declaration(pattern, source):
        match = re.search(pattern, source, re.M)
        if not match:
            raise ValueError('Missing native basemap dependency: ' + pattern)
        return match[0]

    types = '\n'.join(declaration(r'typedef struct\s*\{[^{}]*\}\s*' + name + ';', header)
                      for name in ('s_axis_i', 's_basemap', 's_terrain'))
    macro = declaration(r'^#define MAPSTRINGS[^\n]*(?:\n[^\n]*\\)*\n\}', script)
    names = ('ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue',
             'ScriptVariant_ChangeType', 'ScriptVariant_ToString')
    values = {
        'TYPES': types,
        'VARIANT_TYPES': declaration(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*'
                                     r'typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;',
                                     (scriptlib / 'ScriptVariant.h').read_text()),
        'MAPPING': declaration(r'^#define _is_not_supported_by_[^\n]*', script) + '\n' + macro,
        'ENUMS': declaration(r'enum levelproperty_enum[\s\S]*?enum terrain_enum\s*\{[^{}]*\};', script),
        'VARIANTS': '\n'.join(function(variants, name) for name in names),
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'FUNCTIONS': '\n'.join(function(script, name) for name in
                              ('mapstrings_levelproperty', 'obor_basemap_set_cell',
                               'openbor_changelevelproperty')),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'CASES': ',\n'.join('{' + ','.join(map(str, [row['width'], row['depth'], row['existing'],
                            row['argc'], row['named'], *row['types'], *row['values']])) + '}'
                            for row in data['cases']),
    }
    template = Path(__file__).with_name('basemap_cell_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class BasemapCellContracts(unittest.TestCase):
    def test_level_property_cell_selection_and_storage(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(data['engine'], '4432')
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        results = iter(native_output(program(data), data).splitlines())
        for source in data['sources']:
            for case in data['cases']:
                observed = json.loads(next(results))
                expected = dict(case[source['contract']], revision=source['revision'])
                self.assertEqual(observed, expected, (source['revision'], case['name']))
        self.assertIsNone(next(results, None))


if __name__ == '__main__':
    unittest.main()
