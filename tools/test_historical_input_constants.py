"""Check source-defined input constants at mapping and script API entry.

The native mapper and entry execute with the real variant type. Unrelated
constant values and dynamic animation tables are controlled providers.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-input-constants-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    mapper = function(source, 'mapstrings_transconst')
    entry = function(source, 'openbor_transconst')
    macro = re.findall(r'(?m)^#define[ \t]+ICMPCONST\(x\)[\s\S]*?'
                       r'(?=^void mapstrings_transconst)', source)
    if len(macro) != 1:
        raise ValueError('One native constant mapper macro required')
    header = '\n'.join((engine / name).read_text() for name in
                       ('openbor.h', 'source/globals.h'))
    assessed = set(data['assessed_names'])
    mapped = set(re.findall(r'ICMPCONST\((\w+)\)', mapper))
    if not assessed <= mapped:
        raise ValueError('Assessed constants must exist at the native mapper')
    definitions = []
    for name in sorted(mapped | {'MAX_ATKS', 'STA_ATKS'}):
        value = '0'
        if name in assessed:
            matches = re.findall(r'(?m)^#define[ \t]+' + name + r'[ \t]+([^\n]+)', header)
            if len(matches) != 1:
                raise ValueError('One native assessed constant definition required')
            value = matches[0]
        definitions.append('#ifndef %s\n#define %s %s\n#endif' % (name, name, value))
    arrays = sorted(set(re.findall(r'\b(anim\w+)\[', entry)))
    if not 1 <= len(arrays) <= 32:
        raise ValueError('Bounded native animation dependencies required')
    definitions += ['static int %s_storage[64]; static int *%s=%s_storage;' %
                    (name, name, name) for name in arrays]
    if re.search(r'\bobor_entity_type_reserved\s*\(', mapper):
        # This numeric domain is outside the assessed input constants.
        signature = function(source, 'obor_entity_type_reserved').split('{', 1)[0]
        definitions.append(signature + '{abort();}\n')
    parts = dict(DEFINITIONS='\n'.join(definitions), MACRO=macro[0],
                 MAPPER=mapper, ENTRY=entry,
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join('{%s}' % ','.join(
                     json.dumps(row[key]) if isinstance(row[key], str) else str(row[key])
                     for key in data['parameters']) for row in data['cases']))
    text = Path(__file__).with_name('input_constants_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native input constant dependency')
    return text


class InputConstantContracts(unittest.TestCase):
    def test_native_mapping_and_direct_or_precompiled_entry(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
