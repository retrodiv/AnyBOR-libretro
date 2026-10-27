"""Check native font selection, valid wrapping and unavailable indices.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import re
import subprocess
import sys
import tempfile
import unittest

from historical_font_selection import render_font_selection
from historical_text_display import render_text_display
from test_historical_player import function
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class FontSelectionTests(unittest.TestCase):
    def test_native_text_display_glyphs_and_expiry(self):
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('text-display-contracts.json').read_text())
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        self.assertEqual(fixture['schema'],1)
        cc=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))
        version=subprocess.check_output(cc+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype',
                  '-Wno-error=single-bit-bitfield-constant-conversion']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for row in fixture['models']:
            with self.subTest(engine=row['engine']),tempfile.TemporaryDirectory(prefix='native-text-display-')as folder:
                required={int(p.get('revision',p['build']))for p in pin['profiles']if p['engine']==row['engine']}
                self.assertTrue(required<=set(row['revisions']))
                self.assertEqual(row['revisions'],[v['revision']for v in row['original_sources']])
                for ref in row['original_sources']:
                    self.assertRegex(ref['commit'],r'^[0-9a-f]{40}$')
                    for key in ['used_contract','draw','font_printf']:self.assertRegex(ref[key],r'^[0-9a-f]{64}$')
                root=SOURCE/'src/engines'/row['engine']
                native=(root/'openbor.c').read_bytes().decode('utf8','surrogateescape')
                options={k:row[k]for k in ['revisions','physical_fixed','slots','font_tokens','cases']}
                plain=re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{[\s\S]*?\};',native)
                self.assertIsNotNone(plain)
                code=render_text_display(draw=function(native,'draw_textobjs'),plainmethod=plain[0],**options)
                work=Path(folder);src=work/'probe.c';src.write_text(code,errors='surrogateescape');binary=work/'probe'
                includes=[root/'source/gamelib',root,SOURCE/'src/port/libretro',root/'source',
                          *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
                compile_checked(cc+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                    '-Wno-error=deprecated-declarations','-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare','-Wno-unused-variable','-Wno-unused-function',
                    '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough',
                    '-O0','-g','-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
                    '-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+row['engine'],*host,*warnings,
                    '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                    *['-I'+str(p)for p in includes],str(src),*link,'-lm','-o',str(binary)])
                observed=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15,env=sanitizer_environment())
                self.assertEqual(observed.returncode,0,observed.stdout+observed.stderr)
                self.assertEqual(json.loads(observed.stdout),dict(status='PASS',contexts=len(row['revisions']),
                    checks=len(row['revisions'])*len(row['cases'])))

    def test_each_profile_native_width_dimensions_and_release(self):
        fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('font-selection-contracts.json').read_text())
        pin = json.loads((SOURCE/'src/pin.json').read_text())
        self.assertEqual(set(fixture['engines']), {e['build'] for e in pin['engines']})
        for contract in fixture['original_contracts']:
            self.assertEqual(contract['slots'], fixture['engines'][contract['engine']]['slots'])
            self.assertIn(contract['revision'], fixture['engines'][contract['engine']]['revisions'])
        cc = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
        version = subprocess.check_output(cc+['--version'], text=True, timeout=10)
        extra = ['-Wno-error=pragma-pack', '-Wno-error=deprecated-non-prototype'] if 'clang' in version.lower() else []
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        for engine, options in fixture['engines'].items():
            with self.subTest(engine=engine), tempfile.TemporaryDirectory(prefix='native-font-selection-') as folder:
                required = {int(p.get('revision', p['build'])) for p in pin['profiles'] if p['engine']==engine}
                self.assertTrue(required <= set(options['revisions']))
                root = SOURCE/'src/engines'/engine
                work = Path(folder)
                src = work/'probe.c'
                src.write_text(render_font_selection(**options))
                includes = [root/'source/gamelib', root, SOURCE/'src/port/libretro', root/'source',
                            *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
                executable = work/'probe'
                compile_checked(cc+['-std=gnu11', '-fgnu89-inline', '-Wall', '-Wextra', '-Werror',
                    '-Wno-error=deprecated-declarations', '-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare', '-Wno-unused-variable', '-Wno-unused-function',
                    '-Wno-unused-parameter', '-Wno-unused-but-set-variable', '-Wno-implicit-fallthrough',
                    '-O0', '-g', '-fsigned-char', '-fcommon', '-ffunction-sections', '-fdata-sections',
                    '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+engine, *host, *extra,
                    '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                    *['-I'+str(p) for p in includes], str(src), *link, '-lm', '-o', str(executable)])
                run = subprocess.run([str(executable)], capture_output=True, text=True,
                                     timeout=15, env=sanitizer_environment())
                self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                actual = json.loads(run.stdout)
                self.assertEqual(actual['status'], 'PASS')
                self.assertEqual(actual['contexts'], len(options['revisions']))
                self.assertGreater(actual['checks'], 2*options['slots']*actual['contexts'])


if __name__ == '__main__':
    unittest.main()
