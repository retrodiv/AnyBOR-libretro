"""Check native dive command storage and its gravity policy.

Actual loader cases and gravity expressions execute with native records.
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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-dive-data-contracts.json'


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    loader = function(core, 'load_cached_model')
    loader = loader.replace('switch(cmd)', 'switch(fixture_model_command)', 1)
    _, selected = switch_cases(loader, 'load_cached_model', 'fixture_model_command')
    gravity = function(core, 'check_gravity')
    gate = next(line.strip()[3:-1] for line in gravity.splitlines()
                if 'if((self->falling' in line)
    begin = gravity.index('self->a += self->tossv;')
    end = gravity.index('\n\t\t\tfmin =', begin)
    init = re.search(r'newanim->dive = 0;\s*newanim->obor_legacy_dive_x = newanim->obor_legacy_dive_v = 0;', loader)
    if init is None:
        raise ValueError('Missing native dive initialization')
    parts = {
        'LOADER': '\n'.join('case '+name+':'+selected[name]['body'] for name in
                            ('CMD_MODEL_DIVE', 'CMD_MODEL_DIVE1', 'CMD_MODEL_DIVE2')),
        'INIT': init[0], 'GATE': gate, 'GRAVITY': gravity[begin:end],
        'PROFILES': ','.join(str(row['revision']) + 'u' for row in data['sources']),
        'CASES': ',\n'.join('{%s}' % ','.join(str(row[k]) for k in data['parameters'])
                            for row in data['cases'])}
    text = Path(__file__).with_name('dive_data_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native dive data dependency')
    return text


class DiveDataContracts(unittest.TestCase):
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
        with tempfile.TemporaryDirectory(prefix='anybor-dive-data-') as temporary:
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
