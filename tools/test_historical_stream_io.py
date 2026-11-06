"""Check historical stream IO results, save routes and owned file closure.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from historical_filestreams import extract_storage_helpers
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-stream-io-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()

    def outcomes(rows):
        return '{'+','.join('{%d,%d,%s,%s}' % (
            status, null, "'"+protocol+"'", json.dumps(message))
            for status, null, protocol, message in rows)+'}'

    contexts = []
    for row in data['sources']:
        if len(row['open_expected']) != 14 or len(row['save_expected']) != 10:
            raise ValueError('Complete stream IO result vectors required')
        contexts.append('{%du,%d,%d,%d,%d,%s,%s}' % (row['revision'],
            row['open_namespace'], row['save_legacy_name'], row['nested_directory'], row['level_owned'],
            outcomes(row['open_expected']), outcomes(row['save_expected'])))
    parts = dict(FUNCTIONS='\n'.join(function(script, n) for n in
            ('openbor_openfilestream', 'openbor_savefilestream')),
        HELPERS=extract_storage_helpers(script, function, level_table_provider=
            function((engine / 'openbor.c').read_text(), 'obor_filestream_level_table')),
        VARIANTS='\n'.join(function(variant, n) for n in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        CONTEXTS=','.join(contexts),
        PACKAGES=','.join('{%s,%s,%s}' % tuple(json.dumps(row[k]) for k in
            ('path', 'legacy', 'current')) for row in data['package_cases']))
    text = Path(__file__).with_name('stream_io_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved stream IO dependency')
    return text


class StreamIOContracts(unittest.TestCase):
    def test_native_results_paths_and_file_ownership(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], open_cases=57,
            save_cases=120) for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
