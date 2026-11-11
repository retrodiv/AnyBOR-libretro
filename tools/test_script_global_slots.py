"""Check named queries alongside counted empty and indexed script slots.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_common_think import ROOT
from test_historical_player import function


HERE = Path(__file__).resolve().parent


def program(engine, profiles):
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    legacy = engine.name in ('3400', '3741', '3842')
    header = 'openborscript.h' if (engine / 'openborscript.h').exists() else 'scriptcommon.h'
    text = (HERE / 'script_global_slots_contract.c.in').read_text()
    parts = dict(LEGACY=str(int(legacy)), HEADER=header,
                 CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
                 GETTER=function(script, 'Script_Get_Global_Variant' if legacy else 'Varlist_GetByName'),
                 PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                                   for p in profiles))
    for name, value in parts.items():
        text = text.replace('@' + name + '@', value)
    return text


class ScriptGlobalSlotTests(unittest.TestCase):
    def test_native_named_queries_with_empty_counted_storage_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(p).name for p in compiler) else []
        for row in pin['engines']:
            build = row['build']
            engine = ROOT / 'src/engines' / build
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            legacy = build in ('3400', '3741', '3842')
            with self.subTest(engine=build), tempfile.TemporaryDirectory(prefix='native-global-slots-') as name:
                work = Path(name)
                source, binary = work / 'probe.c', work / 'probe'
                source.write_text(program(engine, profiles))
                includes = [ROOT / 'src/port/libretro', engine, engine / 'source',
                            *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
                units = [] if legacy else [str(engine / 'source/scriptlib/List.c')]
                links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
                command = compiler + warnings + [
                    '-std=gnu11', '-fgnu89-inline', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                    '-Wno-error=deprecated-declarations', '-Wno-error=sign-compare',
                    '-Wno-error=ignored-qualifiers',
                    '-ffunction-sections', '-fdata-sections', '-DLIBRETRO=1', '-DSAFEALLOC_H=1',
                    '-DOBOR_ENGINE_BUILD=' + build, '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', *('-I' + str(p) for p in includes),
                    str(source), *units, *links, '-lm', '-o', str(binary)]
                subprocess.run(command, check=True, timeout=60)
                output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                                 env=sanitizer_environment())
                self.assertEqual(json.loads(output), dict(status='PASS', profiles=len(profiles),
                                                          cases=8 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
