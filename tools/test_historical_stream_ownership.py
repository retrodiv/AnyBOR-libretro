"""Check source-owned stream selection and level retirement at native entry points.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-stream-ownership-contracts.json'


def program(data):
    root = ROOT / 'src/engines' / data['engine']
    core = (root / 'openbor.c').read_text()
    script = (root / 'openborscript.c').read_text()
    variant = (root / 'source/scriptlib/ScriptVariant.c').read_text()
    names = ('createfilestream', 'getfilestreamposition', 'setfilestreamposition',
             'getfilestreamline', 'getfilestreamargument', 'filestreamnextline',
             'filestreamappend', 'closefilestream')
    parts = dict(HELPERS=extract_storage_helpers(script, function,
            level_table_provider=function(core, 'obor_filestream_level_table')),
        FUNCTIONS='\n'.join(function(script, 'openbor_'+name) for name in names),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        PARSER=function(core, 'findarg'),
        RELEASE=function(core, 'obor_filestream_release_level'),
        FREE_LEVEL=function(core, 'free_level'),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], row['level_owned'],
            row['clears_global']) for row in data['sources']))
    text = Path(__file__).with_name('stream_ownership_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native stream ownership dependency')
    return text


class StreamOwnershipContracts(unittest.TestCase):
    def test_two_levels_keep_native_selection_and_argument_owner_release(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], passes=2)
                                  for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
