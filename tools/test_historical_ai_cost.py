"""Check native cost-move state and callback order against own-source contracts.

Energy availability, unlink and animation execution are bounded observers.
The complete caller, native records, charges, flags and clearing execute.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-ai-cost-contracts.json'


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source cost-move coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                any(type(row[k]) is not bool for k in
                    ('early_action', 'clear_movestep', 'jump_keeps_action')) or
                not row['source_sha256'] or any(not re.fullmatch('[0-9a-f]{64}', v)
                    for v in row['source_sha256'].values())):
            raise ValueError('Explicit cost-move identities and state contracts required')
    return data


def program(data):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    entries = ['{%du,%d,%d,%d}' % (r['revision'], r['early_action'], r['clear_movestep'],
                                 r['jump_keeps_action']) for r in data]
    return Path(__file__).with_name('ai_cost_contract.c.in').read_text().replace(
        '@COST@', function(source, 'check_costmove')).replace('@CASES@', ',\n'.join(entries))


class AICostContracts(unittest.TestCase):
    def test_eligibility_charge_flags_and_callback_state(self):
        engine = ROOT / 'src/engines/3741'
        paths = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-ai-cost-') as temporary:
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
