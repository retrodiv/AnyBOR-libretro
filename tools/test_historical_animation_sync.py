"""Check native animation synchronization state against own-profile contracts.

The complete selector runs with native records and a frame-update observer.
The observer records a bounded scheduling effect; it does not render frames.
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-animation-sync-contracts.json'
INPUTS = ('previous', 'same', 'sync', 'position', 'reset', 'sleep')
EXPECTED = ('position', 'sleep', 'animhits', 'animating', 'last_frame', 'lasthit',
            'altbase', 'frame_calls', 'frame', 'nextanim', 'selected')


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source animation sync coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                type(row['frame_history']) is not bool or type(row['sync_mode']) is not int or
                not 0 <= row['sync_mode'] <= 3 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or any(
                    not re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values()) or
                not isinstance(row['cases'], list) or not 1 <= len(row['cases']) <= 64):
            raise ValueError('Bound source identity and bounded sync observations required')
        for case in row['cases']:
            if (set(case) != {'inputs','expected'} or set(case['inputs']) != set(INPUTS) or
                    set(case['expected']) != set(EXPECTED) or
                    any(type(v) is not int or not -(1<<31) <= v <= 0xffffffff
                        for section in case.values() for v in section.values())):
                raise ValueError('Explicit bounded integer animation observations required')
    return data


def program(data):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    cases = []
    for row in data:
        for case in row['cases']:
            values = [str(row['revision'])+'u',str(int(row['frame_history']))]
            values += [str(case['inputs'][k]) for k in INPUTS]
            values += [str(case['expected'][k])+('u' if k in ('sleep','nextanim') else '') for k in EXPECTED]
            cases.append('{'+','.join(values)+'}')
    template = Path(__file__).with_name('animation_sync_contract.c.in').read_text()
    return template.replace('@SELECTOR@', function(source, 'ent_set_anim')).replace('@CASES@', ',\n'.join(cases))


class AnimationSyncContracts(unittest.TestCase):
    def test_selector_state_and_deadline_by_profile(self):
        engine = ROOT / 'src/engines/3741'
        port = ROOT / 'src/port/libretro'
        paths = [port,engine,engine/'source'] + [p for p in sorted((engine/'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC','cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-animation-sync-') as temporary:
            source = Path(temporary)/'contract.c'
            executable = Path(temporary)/'contract'
            source.write_text(program(rows()))
            subprocess.run(compiler + warnings + ['-std=gnu99','-fsigned-char','-Wall','-Wextra',
                '-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-error=deprecated-declarations',
                '-DOBOR_ENGINE_BUILD=3741','-DLIBRETRO=1','-fsanitize=address,undefined','-g',
                *('-I'+str(p) for p in paths),str(source),'-o',str(executable)],check=True,timeout=45)
            subprocess.run([str(executable)],check=True,timeout=30,env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
