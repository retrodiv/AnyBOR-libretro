"""Check native effect/weapon results and own falling/bomb caller boundaries.

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
from test_historical_player import function

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURES=Path(__file__).parent/'fixtures'


class EarlySpawnContinuationTests(unittest.TestCase):
    def test_results_continuations_fall_timing_and_bomb_placement(self):
        fixture=load_contract_fixture(FIXTURES/'profile-early-spawn-continuation.json')
        rows=fixture['sources'];revisions={r['revision']for r in rows}
        self.assertEqual(len(rows),len(revisions));self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for p in contract_profiles(fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(p.get('revision',p['build']))
            if p['engine']==fixture['engine'] and fixture['range'][0]<=revision<=fixture['range'][1]:self.assertIn(revision,revisions)
        engine=Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',ROOT/'src/engines'/fixture['engine']))
        core=(engine/'openbor.c').read_text();effects=[]
        pattern=re.compile(r'(?m)^[ \t]*dust = spawn\([^\n]+;\s*if\(dust\)\s*\{\s*dust->base = self->a;\s*dust->autokill = 1;\s*execute_onspawn_script\(dust\);\s*\}')
        for name,count in [('update_frame',1),('check_gravity',2),('common_jump',2),('common_try_jumpattack',1),('dojump',1)]:
            snippets=list(pattern.finditer(function(core,name)));self.assertEqual(len(snippets),count,name)
            for snippet in snippets:effects.append('static void effect_%d(void){entity *dust;\n%s\n}'%(len(effects),snippet[0]))
        smart=function(core,'smartspawn');first=smart.index('// give the entity a weapon item');last=smart.rindex('}')
        weapon='static entity *weapon_tail(s_spawn_entry *props){entity *e=&actor,*wp;\n'+smart[first:last]+'}'
        falls=[]
        for c in fixture['fall_cases']:
            results=','.join('{%s,%d,%d,%d}'%(json.dumps(r['trace']),r['normal'],r['landed'],r['speedup'])for r in c['results'])
            falls.append('{'+','.join(str(c[k])for k in ['falling','air','toss','projectile','autoland','damage','weaploss','boss','complete'])+',{'+results+'}}')
        bombs=['{'+','.join(str(c[k])for k in ['route','model_speed','nomove','cost','nocost','speed','cantfire'])+'}'for c in fixture['bomb_cases']]
        code=(FIXTURES/'early_spawn_continuation.c').read_text()
        values=dict(FUNCTIONS='\n'.join(function(core,n)for n in ['common_fall','bomb_spawn']),EFFECTS='\n'.join(effects),WEAPON=weapon,
            EFFECT_POINTERS=','.join('effect_%d'%i for i in range(len(effects))),FALL_CASES=',\n'.join(falls),BOMB_CASES=',\n'.join(bombs),
            HEIGHTS=','.join('{'+','.join(map(str,r))+'}'for r in fixture['heights']),
            CHECKS='\n'.join('check(%d,%d,%d);'%(r['revision'],r['fall_era'],r['bomb_era'])for r in rows))
        for key,value in values.items():code=code.replace('@'+key+'@',value)
        compiler=shlex.split(os.environ.get('HOST_CC','cc'));flags=['-std=gnu11','-O1','-g','-UNDEBUG','-DUNIT_TEST=1','-DSAFEALLOC_H=1','-Dstricmp=strcasecmp',
            '-fcommon','-fsigned-char','-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
            '-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable','-Wno-error=deprecated-declarations']
        includes=[engine,ROOT/'src/port/libretro',ROOT/'src/glue',engine/'source',*sorted(p for p in(engine/'source').iterdir()if p.is_dir())]
        flags+=['-I'+str(p)for p in includes]
        with tempfile.TemporaryDirectory(prefix='early-spawn-continuation-')as temporary:
            source=Path(temporary)/'probe.c';binary=source.with_suffix('');source.write_text(code)
            built=subprocess.run(compiler+flags+[str(source),*([]if sys.platform=='darwin'else['-no-pie']),'-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=sanitizer_environment())
            self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn('early_spawn_continuation=1',run.stdout)
            if os.environ.get('OBOR_SPAWN_CONTINUATION_OBSERVATIONS'):
                Path(os.environ['OBOR_SPAWN_CONTINUATION_OBSERVATIONS']).write_text(json.dumps(dict(compiler=compiler,contexts=len(rows),stdout=run.stdout,
                    source_sha256=hashlib.sha256(code.encode()).hexdigest(),scope=fixture['scope']),indent=2)+'\n')


if __name__=='__main__':unittest.main()
