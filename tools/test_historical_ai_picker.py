"""Check random attack choices and ordered services against own-source cases.

The native picker and records execute. Range, energy and RNG are observed
providers; their internal behavior and the AI callers are separate contracts.
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-ai-picker-contracts.json'
INPUTS = ('target', 'testonly', 'weapon', 'valid', 'range', 'mp', 'hp', 'random')


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source picker coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not row['source_sha256'] or any(not re.fullmatch('[0-9a-f]{64}', v)
                    for v in row['source_sha256'].values()) or
                not isinstance(row['cases'], list) or not 1 <= len(row['cases']) <= 128):
            raise ValueError('Bound original picker identities and bounded cases required')
        for case in row['cases']:
            if (set(case) != {'name', 'inputs', 'expected'} or
                    not isinstance(case['name'], str) or not 0 < len(case['name']) <= 96 or
                    set(case['inputs']) != set(INPUTS) or
                    any(type(case['inputs'][k]) is not int or not 0 <= case['inputs'][k] <= 255
                        for k in INPUTS if k != 'random') or
                    type(case['inputs']['random']) is not int or not 0 <= case['inputs']['random'] <= 0x7fffffff or
                    set(case['expected']) != {'result', 'trace'} or
                    type(case['expected']['result']) is not int or not -1 <= case['expected']['result'] <= 7 or
                    not isinstance(case['expected']['trace'], str) or
                    not re.fullmatch(r'[A-Z0-9:;\-]{0,1024}', case['expected']['trace'])):
                raise ValueError('Explicit bounded picker inputs and ordered observations required')
    return data


def program(data):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    entries = []
    for row in data:
        for case in row['cases']:
            values = [str(row['revision']) + 'u', json.dumps(case['name'])]
            values += [str(case['inputs'][k]) for k in INPUTS]
            values += [str(case['expected']['result']), json.dumps(case['expected']['trace'])]
            entries.append('{' + ','.join(values) + '}')
    return Path(__file__).with_name('ai_picker_contract.c.in').read_text().replace(
        '@PICKER@', function(source, 'pick_random_attack')).replace('@CASES@', ',\n'.join(entries))


class AIPickerContracts(unittest.TestCase):
    def test_eligible_pool_selection_and_service_order(self):
        engine = ROOT / 'src/engines/3741'
        paths = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-ai-picker-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(rows()))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-Wall', '-Wextra',
                '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-g', *('-I' + str(p) for p in paths),
                str(source), '-o', str(executable)], check=True, timeout=45)
            subprocess.run([str(executable)], check=True, timeout=30, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
