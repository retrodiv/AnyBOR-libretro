"""Check native attack-exit and jump-landing continuations.

Providers observe movement, idle, airborne, animation and spawn operations.
Only defined live target, animation and frame inputs are used.
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
from test_historical_common_think import native_output

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-action-exit-contracts.json'


class FallRecoveryContracts(unittest.TestCase):
    def test_native_fall_recovery_delays_and_continuations(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-fall-recovery-contracts.json')
        rows = data['sources']
        self.assertEqual({row['revision'] for row in rows},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({row['revision'] for row in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        text = Path(__file__).with_name('fall_recovery_contract.c.in').read_text()
        for key, value in {
            'FUNCTION': function(core, 'common_fall'),
            'PROFILES': ','.join(str(row['revision']) + 'u' for row in rows),
            'CASES': ',\n'.join('{' + ','.join(str(c[k]) for k in data['parameters']) + '}'
                              for c in data['cases']),
        }.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, output in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(output, {'revision': row['revision'],
                    'results': data['contracts'][row['contract']]})


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    parts = {
        'FUNCTIONS': '\n'.join(function(core, name) for name in data['functions']),
        'PROFILES': ','.join(str(row['revision']) + 'u' for row in data['sources']),
        'CASES': ',\n'.join('{%s}' % ','.join(str(row[k]) for k in data['parameters'])
                            for row in data['cases'])}
    text = Path(__file__).with_name('action_exit_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native action-exit caller dependency')
    return text


class ActionExitContracts(unittest.TestCase):
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
        with tempfile.TemporaryDirectory(prefix='anybor-action-exit-') as temporary:
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
