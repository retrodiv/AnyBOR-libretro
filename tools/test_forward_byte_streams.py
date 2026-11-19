"""Check native byte-stream reads, append offsets and save behavior.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-byte-streams-contracts.json'


def program(data, engine):
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    edits = []
    for case in data['append_cases']:
        outcomes = []
        for name in ('legacy', 'native'):
            result = case[name]
            expected = result['bytes'] + [-1] * (64-len(result['bytes']))
            outcomes.append('{%d,%d,{%s}}' % (result['success'], result['size'],
                                                ','.join(map(str, expected))))
        edits.append('{%d,%d,%d,%d,%d,%d,%d,{%s},{%s},{%s}}' % (
            case['size'], case['count'], case['value_type'], case['mode'],
            case['kind'], case['kind_type'], len(case['values']),
            ','.join(map(str, case['initial']+[0]*(32-len(case['initial'])))),
            ','.join(map(str, case['values']+[0]*(3-len(case['values'])))),
            ','.join(outcomes)))
    saves = []
    for case in data['save_cases']:
        outcomes = []
        for name in ('legacy', 'native'):
            result = case[name]
            outcomes.append('{%d,%s,%s,%s}' % (result['success'],
                json.dumps(result['path']), json.dumps(result['data']), json.dumps(result['message'])))
        saves.append('{%d,%d,%d,%d,%s,{%s}}' % (case['count'], case['path_type'],
            case['flag_type'], case['flag'], json.dumps(case['path']), ','.join(outcomes)))
    replacements = dict(
        HEADER='#include '+json.dumps(str(engine/'openbor.h')),
        VARIANTS='\n'.join(function(variants, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_ToString')),
        CORE='\n'.join(function(core, name) for name in ('readByte', 'findarg')),
        APIS='\n'.join(function(script, name) for name in
            ('openbor_getfilestreamargument',
             'openbor_filestreamappend', 'openbor_savefilestream')),
        CONTEXTS=','.join('{%d,%d}' % (r['revision'], r['byte_streams']) for r in data['sources']),
        APPENDS=',\n'.join(edits), SAVES=',\n'.join(saves))
    text = Path(__file__).with_name('forward_byte_streams_contract.c.in').read_text()
    for key, value in replacements.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native stream contract input')
    return text


class ForwardByteStreamTests(unittest.TestCase):
    def test_4432_evolving_append_and_save_arguments(self):
        fixture = Path(__file__).with_name('fixtures') / 'profile-stream-output-contracts.json'
        data = load_contract_fixture(fixture)
        self.assertEqual(data['engine'], '4432')
        contexts = data['sources']
        self.assertEqual({row['revision'] for row in contexts},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(contexts), len({row['revision'] for row in contexts}))
        script = (ROOT / 'src/engines/4432/openborscript.c').read_text()
        callbacks = ('openbor_filestreamappend', 'openbor_savefilestream')
        template = Path(__file__).with_name('stream_output_profile_contract.c.in').read_text()
        checks = []
        for row in contexts:
            self.assertIn(row['path_index'], (2, 3))
            self.assertIs(type(row['always_end_byte']), bool)
            checks.append('check_profile(%du, %d, %d);' % (
                row['revision'], row['path_index'], row['always_end_byte']))
        code = template.replace('@CALLBACKS@', '\n'.join(function(script, n) for n in callbacks))
        code = code.replace('@CHECKS@', '\n'.join(checks))
        result = native_output(code, data, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(json.loads(result), {'contexts': len(contexts), 'cases': 13 * len(contexts)})
        print(result.strip(), flush=True)

    def test_native_reads_append_offsets_and_save_routes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'], data['engine'])
            self.assertIs(type(row['byte_streams']), bool)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        for profile in contract_profiles(data, json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_BYTE_STREAMS_ENGINE', ROOT/'src/engines'/data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
