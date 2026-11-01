"""Check own system IDs and selected scene/menu/completion source windows.

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

from contract_fixtures import contract_profiles,load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function,switch_cases

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURES=Path(__file__).parent/'fixtures'


class EarlyMenuSystemTests(unittest.TestCase):
    def test_own_ids_menu_masks_and_lifecycle_windows(self):
        fixture=load_contract_fixture(FIXTURES/'profile-early-menu-system.json')
        rows=fixture['sources']; revisions={r['revision']for r in rows}
        self.assertEqual(len(rows),len(revisions));self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for p in contract_profiles(fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(p.get('revision',p['build']))
            if p['engine']==fixture['engine'] and fixture['range'][0]<=revision<=fixture['range'][1]:self.assertIn(revision,revisions)
        engine=Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',ROOT/'src/engines'/fixture['engine']))
        core=(engine/'openbor.c').read_text();script=(engine/'openborscript.c').read_text()
        method,cases=switch_cases(core,'getsyspropertybyindex','index')
        getter=re.split(r'\bswitch\s*\(index\)',method,maxsplit=1)[0]
        selected=['current_scene','in_gameoverscreen','in_halloffamescreen','in_menuscreen','in_selectscreen','in_titlescreen','in_showcomplete']
        getter+='switch(index){'+'\n'.join('case _e_'+n+':'+cases['_e_'+n]['body']for n in selected)+'default:return 0;}return 1;}'
        first=script.index('/* Own script-visible system IDs');last=script.index('void mapstrings_systemvariant(',first)
        macro=re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}',script);self.assertIsNotNone(macro)
        callbacks=[script[first:last],function((engine/'source/utils.c').read_text(),'searchList'),macro[0],
                   function(script,'mapstrings_systemvariant'),getter,function(script,'openbor_systemvariant')]
        variants=(engine/'source/scriptlib/ScriptVariant.c').read_text()
        scene=function(core,'playscene');hall=function(core,'hallfame');complete=function(core,'showcomplete');select=function(core,'selectplayer')
        start=scene.index('if(buffer_pakfile');end=scene.index('// Now interpret',start)
        windows=['static void scene_begin(char *filename){char *buf;size_t size;'+scene[start:end]+'}',
                 'static void scene_end(void){'+scene[scene.rindex('currentScene = NULL;'):scene.rindex('}') ]+'}']
        start=hall.index('if(obor_profile_build < 3481)');end=hall.index('if(hiscorebg)',start)
        windows+=['static void hall_begin(void){'+hall[start:end]+'}',
                  'static void hall_end(void){'+hall[hall.rindex('unload_background();'):hall.rindex('}') ]+'}']
        start=select.index('selectScreen = 1;');end=select.index('reset_playable_list(1);',start)+len('reset_playable_list(1);')
        finish=select.index('// No longer at the select screen');ending=select.rindex('return (!escape);')
        quick=re.search(r'selectScreen = 0;\s*return 1;',select);self.assertIsNotNone(quick)
        windows+=['static void select_begin(void){'+select[start:end]+'}',
                  'static void select_end(void){'+select[finish:ending]+'}',
                  'static int quick_select(void){'+quick[0]+'}']
        begin=re.search(r'if\(obor_profile_build >= 3481\) showComplete = 1;',complete);self.assertIsNotNone(begin)
        windows+=['static void completion_begin(void){'+begin[0]+'}',
                  'static void completion_end(void){'+complete[complete.rindex('unload_background();'):complete.rindex('}') ]+'}']
        arrays=[];checks=[]
        for i,row in enumerate(rows):
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['names']),len(row['canonical_ids']));self.assertEqual(len(row['names']),len(row['named_indices']))
            arrays+=['static const char *names%d[]={%s};'%(i,','.join(json.dumps(n)for n in row['names'])),
                     'static const int ids%d[]={%s};'%(i,','.join(map(str,row['canonical_ids']))),
                     'static const int resolved%d[]={%s};'%(i,','.join(map(str,row['named_indices']))),
                     'static const struct context row%d={%d,%d,%d,%d,names%d,ids%d,resolved%d};'%
                     (i,row['revision'],len(row['names']),row['scene_empty'],row['menu_mode'],i,i,i)]
            checks.append('check(&row%d);'%i)
        program=(FIXTURES/'early_menu_system.c').read_text()
        values=dict(VARIANTS='\n'.join(function(variants,n)for n in ['ScriptVariant_ChangeType','ScriptVariant_Clear']),
                    CALLBACKS='\n'.join(callbacks),WINDOWS='\n'.join(windows),ARRAYS='\n'.join(arrays),CHECKS='\n'.join(checks))
        for key,value in values.items():program=program.replace('@'+key+'@',value)
        cc=shlex.split(os.environ.get('HOST_CC','cc'));flags=['-std=gnu11','-O1','-g','-UNDEBUG','-DUNIT_TEST=1','-DSAFEALLOC_H=1','-Dstricmp=strcasecmp',
            '-fcommon','-fsigned-char','-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
            '-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable','-Wno-error=deprecated-declarations']
        includes=[engine,ROOT/'src/port/libretro',ROOT/'src/glue',engine/'source',*sorted(p for p in(engine/'source').iterdir()if p.is_dir())]
        flags+=['-I'+str(p)for p in includes]
        with tempfile.TemporaryDirectory(prefix='early-menu-system-')as temporary:
            source=Path(temporary)/'probe.c';binary=source.with_suffix('');source.write_text(program)
            build=subprocess.run(cc+flags+[str(source),*([]if sys.platform=='darwin'else['-no-pie']),'-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=sanitizer_environment())
            self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn('early_menu_system=1',run.stdout)
            if os.environ.get('OBOR_MENU_SYSTEM_OBSERVATIONS'):
                Path(os.environ['OBOR_MENU_SYSTEM_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,contexts=len(rows),stdout=run.stdout,
                    source_sha256=hashlib.sha256(program.encode()).hexdigest(),scope=fixture['scope']),indent=2)+'\n')


if __name__=='__main__':unittest.main()
