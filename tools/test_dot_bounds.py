"""Keep native damage-over-time updates inside their declared effect slots.

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

from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
PIN = json.loads((ROOT / 'src/pin.json').read_text())
NATIVE_ENGINES = {'3400', '3741', '3842', '4086', '4432'}
CONTRACT = Path(__file__).with_name('dot_bounds_contract.c')


def run_contract(engine):
    """Run actual native types/body; HP damage and full combat are out of scope."""
    engine = Path(engine)
    body = function((engine / 'openbor.c').read_text(), 'common_dot')
    if re.search(r'\bobor_(?:profile\w*|active_profile\w*)\b', body):
        raise AssertionError('Profile-aware DOT body requires separate profile executions')
    header = (engine / 'openbor.h').read_text()
    if not re.search(r'^#define\s+MAX_DOTS\s+10\b', header, re.M):
        raise AssertionError('Review changed native effect capacity before reusing this contract')
    includes = [engine, engine / 'source', ROOT / 'src/port/libretro', ROOT / 'src/glue']
    includes += sorted(path for path in (engine / 'source').iterdir() if path.is_dir())
    if re.search(r'\bDOT_MODE_MP\b', body):
        mp_mode = 'DOT_MODE_MP'
    elif 'if(iDot==2||iDot==3||iDot==5)' in re.sub(r'\s+', '', body):
        mp_mode = '2'
    else:
        raise AssertionError('Review the native MP-only mode before reusing this contract')
    attack_type = re.search(r'^\s*(s_\w+)\s+attack\s*;', body, re.M)
    callback = re.search(r'void\s+execute_takedamage_script\s*\(([^;]+)\);', header)
    if not attack_type or not callback or callback[1].count(',') not in (8, 9):
        raise AssertionError('Review native attack type and damage-script signature')
    features = ['-DDOT_ATTACK_TYPE=' + attack_type[1]]
    if callback[1].count(',') == 9:
        if not re.search(r'\bint\s+tag\s*$', callback[1]):
            raise AssertionError('Unrecognized additional damage-script parameter')
        features.append('-DDOT_SCRIPT_HAS_TAG=1')
    with tempfile.TemporaryDirectory(prefix='anybor-dot-bounds-') as temporary:
        work = Path(temporary)
        (work / 'common_dot.inc').write_text(body + '\n')
        command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
            '-std=gnu11', '-O1', '-g', '-DLIBRETRO=1', '-fsigned-char',
            '-fcommon', '-fno-strict-aliasing',
            '-DOBOR_ENGINE_BUILD=' + engine.name,
            '-DDOT_MP_MODE=' + mp_mode,
            '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
            '-fno-omit-frame-pointer', '-ffunction-sections', '-fdata-sections',
            '-Wno-deprecated-declarations', '-I' + str(work),
        ]
        command += ['-I' + str(path) for path in includes]
        command += features
        command += [str(CONTRACT), '-Wl,-dead_strip' if sys.platform == 'darwin'
                    else '-Wl,--gc-sections', '-o', str(work / 'probe')]
        subprocess.run(command, check=True, timeout=45)
        result = subprocess.run([str(work / 'probe')], check=True, timeout=15,
                                capture_output=True, text=True,
                                env=sanitizer_environment())
        return json.loads(result.stdout)


class DotBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {row['build']: run_contract(ROOT / 'src/engines' / row['build'])
                       for row in PIN['engines'] if row['build'] in NATIVE_ENGINES}


def profile_test(profile):
    def check(self):
        # The shared body is explicitly checked above for profile dependencies;
        # this binds every selectable profile to the tested physical layout.
        self.assertEqual(self.results[profile['engine']], {'status': 'PASS', 'contracts': 4})
    return check


for _profile in PIN['profiles']:
    if _profile['engine'] in NATIVE_ENGINES:
        setattr(DotBoundsTests, 'test_profile_' + _profile['build'], profile_test(_profile))


if __name__ == '__main__':
    unittest.main()
