"""Check native early blend tables, color results and table ownership.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURES=Path(__file__).parent/'fixtures'


class EarlyPixelBlendTests(unittest.TestCase):
    def test_tables_pixels_and_lifecycle_per_profile(self):
        fixture=load_contract_fixture(FIXTURES/'profile-early-pixel-blends.json')
        rows=fixture['sources']; revisions={r['revision'] for r in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for profile in contract_profiles(fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(profile.get('revision',profile['build']))
            if profile['engine']==fixture['engine'] and fixture['range'][0]<=revision<=fixture['range'][1]:
                self.assertIn(revision,revisions)
        reference=FIXTURES/'blend-luts.bin'; raw=reference.read_bytes()
        self.assertEqual(len(raw),fixture['reference_bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),fixture['reference_sha256'])
        engine=Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',ROOT/'src/engines'/fixture['engine']))
        core=(engine/'openbor.c').read_text()
        pixels=(engine/'source/gamelib/pixelformat.c').read_text()
        # Keep the exact color/table portion together. The unrelated unrolled
        # copy switches are checked in the complete unit's syntax pass below;
        # instrumenting them can exhaust a small compiler guard on Clang.
        self.assertEqual(pixels.count('#define _revcpy '),1)
        colors=pixels[:pixels.index('#define _revcpy ')]
        registry=re.search(r'(?s)blend_table_function blending_table_functions16.*?blending_table_functions32.*?};',core)
        self.assertIsNotNone(registry)
        start=re.search(r'if\(obor_profile_build >= 3454 && pixelformat == PIXEL_x8\)\s*create_blend_tables_x8\(blendtables\);',function(core,'startup'))
        stop=re.search(r'if\(startup_done\) obor_free_blend_tables_x8\(\);',function(core,'shutdown'))
        self.assertIsNotNone(start); self.assertIsNotNone(stop)
        cases=[]
        for case in fixture['cases']:
            expected='{'+','.join('{'+','.join(str(v)+'u' for v in era)+'}' for era in case['expected'])+'}'
            cases.append('{%d,%d,%du,%du,%s}'%(case['bits'],case['mode'],case['source'],case['destination'],expected))
        program=(FIXTURES/'early_pixel_blends.c').read_text()
        values=dict(REGISTRIES=registry[0],HELPERS='\n'.join(function(core,n) for n in
            ['create_blend_tables_x8','obor_free_blend_tables_x8']),START_TABLES=start[0],STOP_TABLES=stop[0],
            CASES=',\n'.join(cases),OLD_DODGE=','.join(map(str,bytes.fromhex(fixture['legacy_dodge16']))),
            REFERENCE=json.dumps(str(reference)),CHECKS='\n'.join('check(%d,%d);'%(r['revision'],r['era'])for r in rows))
        for key,value in values.items(): program=program.replace('@'+key+'@',value)
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        syntax_warnings=['-Wno-error=unused-command-line-argument'] if 'clang' in version.lower() else []
        includes=[engine/'source/gamelib',engine/'source',engine,ROOT/'src/glue',ROOT/'src/port/libretro']
        # Optimization is unnecessary for these bounded arithmetic controls.
        flags=['-std=gnu11','-O0','-g','-UNDEBUG','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD=3400',
            '-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
            '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
            '-fno-omit-frame-pointer','-Wall','-Wextra','-Werror',
            '-Wno-error=deprecated-declarations','-Wno-unused-variable','-Wno-implicit-fallthrough']
        flags+=['-I'+str(p)for p in includes]
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        with tempfile.TemporaryDirectory(prefix='early-pixel-blends-')as temporary:
            directory=Path(temporary); unit=directory/'pixel.o'; source=directory/'probe.c'; binary=directory/'probe'
            source.write_text(program)
            color_source=directory/'colors.c'; color_source.write_text(colors)
            for command in [compiler+flags+syntax_warnings+['-fsyntax-only',str(engine/'source/gamelib/pixelformat.c')],
                            compiler+flags+['-Dmalloc=obor_malloc','-c',str(color_source),'-o',str(unit)],
                            compiler+flags+[str(source),str(unit),*links,'-o',str(binary)]]:
                built=subprocess.run(command,capture_output=True,text=True,timeout=90)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=sanitizer_environment())
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn('early_pixel_blends=1',run.stdout)
            if os.environ.get('OBOR_PIXEL_BLEND_OBSERVATIONS'):
                Path(os.environ['OBOR_PIXEL_BLEND_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=compiler,contexts=len(rows),cases=len(cases),stdout=run.stdout,
                    source_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    color_source_sha256=hashlib.sha256(colors.encode()).hexdigest(),
                    compilation_scope='Full-unit syntax plus exact native color/table prefix under sanitizers; unrelated copy routines are not executed.',
                    scope=fixture['scope']),indent=2)+'\n')


if __name__=='__main__':unittest.main()
