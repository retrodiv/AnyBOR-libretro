"""Check native block target selection and animation-call state.

Providers distinguish supplied, normal and block-specific targets.
Only defined native records and selectors execute.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-block-attempt-contracts.json'


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    parts = {
        'FUNCTION': function(core, 'common_try_block'),
        'PROFILES': ','.join(str(row['revision']) + 'u' for row in data['sources']),
        'CASES': ',\n'.join('{%s}' % ','.join(str(row[k]) for k in data['parameters'])
                            for row in data['cases'])}
    text = Path(__file__).with_name('block_attempt_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native block caller dependency')
    return text


class BlockTargetContracts(unittest.TestCase):
    def test_native_finder_and_caller_match_own_profile(self):
        from test_historical_common_think import native_output
        data = load_contract_fixture(Path(__file__).with_name('fixtures') / 'profile-block-target-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        cases = []
        for case in data['cases']:
            items = ','.join('{'+','.join(str(c[k]) for k in data['candidate_fields'])+'}' for c in case['items'])
            cases.append('{'+','.join(str(case[k]) for k in data['case_fields'])+',{'+items+'}}')
        text = Path(__file__).with_name('block_target_contract.c.in').read_text()
        for key, value in dict(DIFF=function(core, 'diff'), FINDER=function(core, 'block_find_target'),
                              CALLER=function(core, 'common_try_block'), CASES=',\n'.join(cases),
                              PROFILES=','.join(str(r['revision'])+'u' for r in rows)).items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        expected = [dict(revision=r['revision'], case=i, **result) for r in rows
                    for i, result in enumerate(data['contracts'][r['contract']])]
        self.assertEqual(len(actual), len(expected))
        for observed, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], case=oracle['case']):
                self.assertEqual(observed, oracle)


class BlockAttemptContracts(unittest.TestCase):
    def test_native_calls_visible_state_and_continuation_writes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        engine = ROOT / 'src/engines' / data['engine']
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in
            sorted((engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-block-attempt-') as temporary:
            source = Path(temporary) / 'probe.c'
            binary = Path(temporary) / 'probe'
            source.write_text(program(data))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-O2', '-fsigned-char',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=' + data['engine'],
                '-DLIBRETRO=1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in includes), str(source), '-o', str(binary)],
                check=True, timeout=60)
            raw = subprocess.check_output([str(binary)], text=True, timeout=30,
                                          env=sanitizer_environment())
        actual = [json.loads(line) for line in raw.splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
