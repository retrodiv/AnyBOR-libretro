"""Check native basemap generation from level and script entry points.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-basemap-generation-contracts.json'


def program(data, *, original=None):
    engine = ROOT / 'src/engines' / data['engine']
    header = (engine / 'openbor.h').read_text()
    scriptlib = engine / 'source/scriptlib'
    variant_header = (scriptlib / 'ScriptVariant.h').read_text()
    declarations = re.search(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*'
                             r'typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;', variant_header)
    types = [re.search(r'typedef struct\s*\{[^{}]*\}\s*' + name + ';', header)
             for name in ('s_axis_i', 's_basemap')]
    if not declarations or not all(types):
        raise ValueError('Native basemap or script declarations are unavailable')
    variants = (scriptlib / 'ScriptVariant.c').read_text()
    if original is None:
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        generator = '\n'.join(function(core, name) for name in
                              ('obor_basemap_int_coordinate', 'generate_basemap', 'addbasemap'))
        entry = function(script, 'openbor_generatebasemap')
    else:
        generator = original['generate_basemap'] + '\n' + original['addbasemap']
        entry = original['openbor_generatebasemap']
    values = {
        'VARIANT_TYPES': declarations[0],
        'TYPES': '\n'.join(match[0] for match in types),
        'VARIANTS': '\n'.join(function(variants, name) for name in
                              ('ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        'GENERATOR': generator,
        'SCRIPT': entry,
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'CASES': ',\n'.join('{' + ','.join(map(str, [row['route'], row['index'], row['continuation'],
                            row['existing'], row['argc'], row['text_optional']])) + ',{' +
                            ','.join(row['parameters']) + '}}' for row in data['cases']),
    }
    template = Path(__file__).with_name('basemap_generation_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def normalize(record):
    for row in record['maps']:
        row['cells'] = ['nan' if 'nan' in cell else float.fromhex(cell).hex() for cell in row['cells']]
    return record


class BasemapGenerationContracts(unittest.TestCase):
    def test_native_level_and_script_grid_generation(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(data['engine'], '4432')
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = iter(native_output(program(data), data).splitlines())
        for source in data['sources']:
            for case in data['cases']:
                observed = normalize(json.loads(next(actual)))
                expected = dict(case['expected'][source['contract']], revision=source['revision'])
                self.assertEqual(observed, expected, (source['revision'], case['name']))
        self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
