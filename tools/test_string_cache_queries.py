"""Check native cache lookup boundaries and retained per-profile data.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_string_cache import render_string_cache
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class StringCacheQueryTests(unittest.TestCase):
    def test_each_profile_valid_boundaries_growth_release_and_clear(self):
        fixture = load_contract_fixture(Path(__file__).with_name('fixtures').joinpath('string-cache-contracts.json'))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        self.assertEqual(set(fixture['engines']), {e['build'] for e in pin['engines']})
        cc = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
        version = subprocess.check_output(cc + ['--version'], text=True, timeout=10)
        extra = ['-Wno-error=pragma-pack', '-Wno-error=deprecated-non-prototype'] if 'clang' in version.lower() else []
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        for engine, options in fixture['engines'].items():
            with self.subTest(engine=engine), tempfile.TemporaryDirectory(prefix='native-string-cache-') as folder:
                required = {int(p.get('revision', p['build'])) for p in contract_profiles(fixture, pin['profiles']) if p['engine'] == engine}
                self.assertTrue(required <= set(options['revisions']))
                root = SOURCE / 'src/engines' / engine
                work = Path(folder)
                src = work / 'probe.c'
                src.write_text(render_string_cache(**options))
                includes = [root / 'source/scriptlib', root, SOURCE / 'src/port/libretro', root / 'source',
                            *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
                executable = work / 'probe'
                compile_checked(cc + ['-std=gnu11', '-fgnu89-inline', '-Wall', '-Wextra', '-Werror',
                    '-Wno-error=deprecated-declarations', '-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare', '-Wno-unused-variable', '-Wno-unused-function',
                    '-Wno-unused-parameter', '-Wno-unused-but-set-variable', '-Wno-implicit-fallthrough',
                    '-O0', '-g', '-fsigned-char', '-fcommon', '-ffunction-sections', '-fdata-sections',
                    '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + engine, *host, *extra,
                    '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                    *['-I' + str(p) for p in includes], str(src),
                    str(root / 'source/scriptlib/ScriptVariant.c'), *link, '-lm', '-o', str(executable)])
                run = subprocess.run([str(executable)], capture_output=True, text=True,
                                     timeout=15, env=sanitizer_environment())
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(json.loads(run.stdout), dict(status='PASS', contexts=len(options['revisions']),
                    checks=len(options['revisions']) * ((6 if options.get('check_termination',False) else 2) * options['slots'] + 14)))


if __name__ == '__main__':
    unittest.main()
