"""Check native platform-local variant tags, copies and callback cleanup.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-platform-callback-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(set(revisions)) != len(revisions) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own platform callback sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or row['platform_decimal'] not in (0, 1) or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', value) for value in row['source_sha256'].values())):
            raise ValueError('Complete original platform callback observations required')
    return data


def program(data, engine=None):
    engine = engine if engine is not None else ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    script = (engine / 'openborscript.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    values = dict(
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_Copy')),
        INITIALIZED=function(script, 'Script_IsInitialized'),
        CALLBACK=function(source, 'execute_onblockp_script'),
        CONTEXTS=','.join('{%d,%d,%d}' % (
            r['revision'], r['platform_decimal'], r.get('local_cleanup_calls', -1)) for r in data['sources']),
        CASES=','.join('{%d,%d,%d}' % (c['plane'], c['present'], c['initialized']) for c in data['cases']))
    text = Path(__file__).with_name('platform_callback_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native platform callback dependency')
    return text


class PlatformCallbackContracts(unittest.TestCase):
    def test_native_variant_publication_copy_and_cleanup(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])

    def check_platform_callback_cleanup(self, engine_id):
        data = load_contract_fixture(FIXTURE.with_name('profile-impact-callbacks.json'))
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        data = {'engine': engine_id, 'sources': rows, 'cases': load_contract_fixture(FIXTURE)['cases']}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        result = native_output(program(data, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([json.loads(line) for line in result.splitlines()],
                         [dict(revision=revision, status='PASS') for revision in revisions])

    def test_4432_platform_callback_cleanup(self):
        self.check_platform_callback_cleanup('4432')

    def test_6391_platform_callback_cleanup(self):
        self.check_platform_callback_cleanup('6391')


if __name__ == '__main__':
    unittest.main()
