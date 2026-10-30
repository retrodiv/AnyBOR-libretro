"""Check own loading-script lifecycle, queue order and modern timer gates.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-loading-callbacks.json'


class EarlyLoadingCallbackTests(unittest.TestCase):
    def test_lifecycle_queue_and_modern_timers(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        port = ROOT / 'src/port/libretro'
        pieces = [function(variant, name) for name in
                  ['ScriptVariant_Init', 'ScriptVariant_ChangeType', 'ScriptVariant_Clear']]
        pieces += [function(script, 'Script_IsInitialized')]
        pieces += [function((port / 'timer.c').read_text(), 'timer_gettick'),
                   function((port / 'libretroport.c').read_text(), 'obor_wait_frame')]
        pieces += [function(source, name) for name in
                   ['isLoadingScreenTypeBg', 'isLoadingScreenTypeBar', 'init_scripts',
                    'load_scripts', 'execute_loading_script', 'update_loading']]
        checks = []
        for index, row in enumerate(rows):
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('case %d:check(%d,%d,%d,%d,%d);break;' % (
                index, row['revision'], row['loading_script'], row['modern'],
                row['keyboard_lasttick'], row['default_screen']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
@DEPTH_DEFINES@
uint32_t obor_profile_build;
uint64_t obor_clock_us;
static int frame_ready,yields;
static Script update_script,updated_script,level_script,endlevel_script,key_script_all,timetick_script,loading_script,sentinel;
static Script score_script[4],key_script[4],join_script[4],respawn_script[4],pdie_script[4];
Script *pcurrentscript;
static int loading_init,loading_load,loading_clear,loading_compile,loading_success;
static int calls,locals,effective,local_types[4],local_values[4],queue,draw_queue,videos,polls,sounds;
static char trace[4096];
static int at;
static s_screen pixels,bg,*vscreen=&pixels,*background=&bg;
static s_videomodes videomodes;
static s_barstatus loadingbarstatus;
static s_playercontrols *playercontrolpointers[4];
static void event(char c){assert(at+1<(int)sizeof(trace));trace[at++]=c;trace[at]=0;}
CHAR *StrCache_Get(int n){(void)n;abort();}
void StrCache_Collect(int n){(void)n;}
int StrCache_Pop(void){abort();}
void Script_Global_Init(void){}
void Script_Init(Script *s,char *name,int first){s->initialized=1;if(s==&loading_script){assert(!strcmp(name,"loading") && first==1);loading_init++;}}
void Script_Clear(Script *s,int mode){s->initialized=0;if(s==&loading_script){assert(mode==2);loading_clear++;}}
int Script_Compile(Script *s){if(s==&loading_script){assert(loading_init==1);loading_compile++;}return S_OK;}
int load_script(Script *s,char *name){if(s==&loading_script){assert(!strcmp(name,"data/scripts/loading.c"));loading_load++;return loading_success;}return 0;}
int Script_Set_Local_Variant(char *name,ScriptVariant *value){
 int index=locals++%4;assert(!strcmp(name,index%2?"max":"value"));local_types[index]=value->vt;
 if(value->vt==VT_INTEGER)local_values[index]=value->lVal;
 if(pcurrentscript){assert(pcurrentscript==&loading_script);effective++;return 1;}return 0;
}
int Script_Execute(Script *s){
 assert(s==&loading_script && s->initialized && pcurrentscript==s && locals%4==2);
 Script *previous=pcurrentscript;pcurrentscript=s;calls++;queue+=2;event('L');pcurrentscript=previous;return S_OK;
}
void obor_yield_frame(void){yields++;obor_clock_us+=16667;}
void sound_update_music(void){sounds++;event('S');}
void control_update(s_playercontrols **p,int count){assert(p==playercontrolpointers && count==1);polls++;event('I');}
void font_printf(int x,int y,int font,int layer,char *format,...){
 assert(!strcmp(format,"Loading...") && layer==0);
 assert((x==4 && y==5 && font==1)||(x==120 && y==110 && font==0));queue++;event('T');
}
void bar(int x,int y,int value,int max,s_barstatus *status){assert(x==2 && y==3 && value>=0 && max>0 && status==&loadingbarstatus);queue++;event('B');}
void putscreen(s_screen *dst,s_screen *src,int x,int y,s_drawmethod *method){assert(dst==vscreen && src==background && x==0 && y==0 && !method);event('P');}
void clearscreen(s_screen *s){assert(s==vscreen);event('X');}
void spriteq_clear(void){queue=0;event('C');}
void spriteq_draw(s_screen *s,int only,int minz,int maxz){assert(s==vscreen && only==0 && minz==MIN_INT && maxz==MAX_INT);draw_queue=queue;event('D');}
int video_copy_screen(s_screen *s){assert(s==vscreen);videos++;event('V');return 1;}
static void obor_update_loading_legacy(int x,int y,int size,int tx,int ty,int value,int max,int font){
 (void)x;(void)y;(void)size;(void)tx;(void)ty;(void)value;(void)max;(void)font;abort();
}
@PIECES@
static void reset_events(int pending){at=0;trace[0]=0;calls=locals=effective=videos=polls=sounds=0;queue=pending;draw_queue=-1;}
static void check(unsigned revision,int enabled,int modern,int keyboard_old,int default_screen){
 obor_profile_build=revision;
 for(int success=0;success<2;success++){
  memset(&loading_script,0,sizeof(loading_script));loading_init=loading_load=loading_clear=loading_compile=0;loading_success=success;
  load_scripts();
  assert(loading_init==enabled && loading_load==enabled && loading_compile==enabled && loading_clear==(enabled && !success));
  for(int context=0;context<2;context++){
   reset_events(0);pcurrentscript=context?&sentinel:NULL;Script *previous=pcurrentscript;
   execute_loading_script(-1,100);int active=enabled && success;
   assert(pcurrentscript==previous && calls==active && locals==active*4 && effective==active*4);
   if(active)assert(local_types[0]==VT_INTEGER && local_values[0]==-1 && local_types[1]==VT_INTEGER && local_values[1]==100 && local_types[2]==VT_EMPTY && local_types[3]==VT_EMPTY);
  }
 }
 if(!modern)return; /* Dedicated legacy body/representation contract. */
 s_loadingbar s={0};s.set=LSTYPE_BACKGROUND|LSTYPE_BAR;s.bx=2;s.by=3;s.bsize=9;s.tx=4;s.ty=5;s.tf=1;s.refreshMs=100;
 obor_clock_us=0;pcurrentscript=&sentinel;reset_events(7);update_loading(&s,-1,100);
 assert(calls==enabled && videos==1 && queue==0 && draw_queue==(enabled?4:9));
 if(modern)assert(!strcmp(trace,enabled?"CLBTPDVC":"BTPDVC"));
 if(enabled)assert(local_values[0]==-1);
 if(!modern)return; /* Legacy signature, arguments and body remain separate. */
 s.set=LSTYPE_NONE;reset_events(7);update_loading(&s,-1,100);
 if(enabled){assert(!strcmp(trace,"CLXTDVC") && draw_queue==3 && queue==0);}
 else if(default_screen){assert(!strcmp(trace,"XCTDV") && draw_queue==1 && queue==1);}
 else assert(!trace[0] && queue==7);
 s.set=LSTYPE_BACKGROUND|LSTYPE_BAR;reset_events(0);
 for(int value=1;value<=3;value++)update_loading(&s,value,100);
 assert(!videos && !calls && !polls); /* Progress alone cannot add engine callbacks. */
 update_loading(&s,100,100);assert(videos==1 && calls==enabled); /* Own completion repaints without elapsed time. */
 s.set=LSTYPE_BACKGROUND;reset_events(7);update_loading(&s,100,100);
 assert(!strcmp(trace,enabled?"CLTPDVC":"TPDVC") && draw_queue==(enabled?3:8) && queue==0);
 s.set=LSTYPE_BAR;reset_events(7);update_loading(&s,100,100);
 assert(!strcmp(trace,enabled?"CLBTDVC":"BTDVC") && draw_queue==(enabled?4:9) && queue==0);
 s.set=LSTYPE_BACKGROUND|LSTYPE_BAR;s.refreshMs=200;reset_events(0);
 obor_clock_us=150000;update_loading(&s,4,100);assert(!videos && !calls && sounds==1 && !polls);
 obor_clock_us=160000;update_loading(&s,4,100);assert(!videos && sounds==1);
 obor_clock_us=170000;update_loading(&s,4,100);assert(!videos && sounds==1);
 obor_clock_us=171000;update_loading(&s,4,100);assert(!videos && sounds==2);
 obor_clock_us=201000;update_loading(&s,4,100);assert(videos==1 && calls==enabled && sounds==3 && !polls);
 s.refreshMs=100;reset_events(0);
 for(unsigned tick=1000;tick<=1600;tick+=200){obor_clock_us=(uint64_t)tick*1000;update_loading(&s,4,100);}
 assert(videos==4 && calls==enabled*4 && polls==(keyboard_old?1:2) && sounds==4);
 reset_events(0);yields=0;
 for(int model=0;model<40;model++){update_loading(&s,model,40);obor_wait_frame();}
 update_loading(&s,40,40);
 assert(yields==40 && frame_ready && videos>2 && videos<40 && calls==enabled*videos);
}
int main(int argc,char **argv){assert(argc==2);switch(atoi(argv[1])){@CHECKS@default:abort();}puts("early_loading_callbacks=1");return 0;}
'''
        depth = '\n'.join(line for line in source.splitlines() if line.startswith('#define MIN_INT') or line.startswith('#define MAX_INT'))
        self.assertEqual(len(depth.splitlines()), 2)
        program = program.replace('@DEPTH_DEFINES@', depth).replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-loading-callbacks-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(port), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                  '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            runs = []
            for index, row in enumerate(rows):
                run = subprocess.run([str(binary), str(index)], capture_output=True, text=True,
                                     timeout=20, env=sanitizer_environment())
                runs.append(dict(revision=row['revision'], returncode=run.returncode,
                                 stdout=run.stdout, stderr=run.stderr))
                if run.returncode:
                    break
            if os.environ.get('OBOR_LOADING_CALLBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_LOADING_CALLBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), executed=len(runs), runs=runs,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    returncode=runs[-1]['returncode'], stdout=runs[-1]['stdout'], stderr=runs[-1]['stderr'],
                    scope=fixture['scope'], retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            for run in runs:
                self.assertEqual(run['returncode'], 0, str(run))
                self.assertIn('early_loading_callbacks=1', run['stdout'])
            self.assertEqual(len(runs), len(rows))


if __name__ == '__main__':
    unittest.main()
