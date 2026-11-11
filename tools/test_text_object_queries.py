"""Check stored-text queries with the matching native variant/cache unit.

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


HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
ENGINES = ('6391', '7142', '7533', '8023')


def program(engine, profiles):
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    enum = re.search(r'enum gtop_enum\s*\{[^}]*\};', source)
    if enum is None:
        raise ValueError('Complete native text-property enumeration required')
    code = (HERE / 'text_object_queries_contract.c.in').read_text()
    ownership = '#include "obor_text_table_ownership.inc"'
    if source.count(ownership) != 1:
        raise ValueError('Native table ownership helpers required')
    parts = dict(ENUM=enum[0], MAPPER=function(source, 'mapstrings_textobjproperty'),
                 GETTER=function(source, 'openbor_gettextobjproperty'),
                 HELPERS=ownership,
                 PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                                   for p in profiles))
    for name, value in parts.items():
        code = code.replace('@' + name + '@', value)
    return code


class NativeTextQueryTests(unittest.TestCase):
    def test_absent_empty_and_present_text_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack', '-Wno-error=deprecated-non-prototype'] if (
            sys.platform == 'darwin' or any('clang' in Path(p).name for p in compiler)) else []
        for build in ENGINES:
            engine = ROOT / 'src/engines' / build
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build), tempfile.TemporaryDirectory(prefix='native-text-query-') as name:
                work = Path(name)
                source, binary = work / 'probe.c', work / 'probe'
                source.write_text(program(engine, profiles))
                includes = [engine / 'source/scriptlib', engine, ROOT / 'src/port/libretro',
                            engine / 'source', *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
                links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
                command = compiler + warnings + [
                    '-std=gnu11', '-fgnu89-inline', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                    '-Wno-error=deprecated-declarations', '-Wno-error=sign-compare',
                    # The complete variant unit retains native numeric
                    # negation fallthrough; this is a separate contract.
                    '-Wno-error=implicit-fallthrough',
                    '-ffunction-sections', '-fdata-sections', '-DLIBRETRO=1', '-DSAFEALLOC_H=1',
                    '-DOBOR_ENGINE_BUILD=' + build, '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', *('-I' + str(p) for p in includes), str(source),
                    str(engine / 'source/scriptlib/ScriptVariant.c'), *links, '-lm', '-o', str(binary)]
                subprocess.run(command, check=True, timeout=60)
                output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                                 env=sanitizer_environment())
                self.assertEqual(json.loads(output), dict(status='PASS', profiles=len(profiles),
                                                          cases=24 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
