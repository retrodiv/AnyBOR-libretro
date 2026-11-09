"""Check layer transparency and water fields against source-defined contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-layer-drawing-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    enums = re.findall(r'enum getbglp_enum\s*\{[^}]+\};', script)
    if len(enums) != 1:
        raise ValueError('Expected one source-owned layer property enumeration')
    parts = dict(
        ENUM=enums[0],
        FUNCTIONS='\n'.join(function(script, name) for name in
                             ('_getlayerproperty', '_changelayerproperty')),
        VARIANTS='\n'.join(function(variant, name) for name in
                            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        PROPERTIES=','.join(data['properties']),
        GLOBALS=','.join(str(value) + 'u' for value in data['global_masks']),
        CASES=','.join('{%s,%s}' % (row['type'], row['value']) for row in data['cases']))
    text = Path(__file__).with_name('modern_layer_drawing_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved layer drawing contract dependency')
    return text


class ModernLayerDrawingContracts(unittest.TestCase):
    def test_transparency_masks_and_water_fields(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], cases=data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
