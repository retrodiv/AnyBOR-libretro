#!/usr/bin/env python3
"""Check historical zoom availability, composition and queue depth intervals."""
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 retrodiv <retrodiv@proton.me>
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
from test_early_system_callbacks import block

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-zoom.json'


class EarlyZoomTests(unittest.TestCase):
    def test_api_depth_intervals_and_composition(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        queue_source = (engine / 'source/gamelib/spriteq.c').read_text()
        update = function(core, 'update')
        start = update.index('if(obor_profile_build >= 3366 && zoom_scale_x)')
        first = block(update, start)
        second_start = start + len(first)
        self.assertRegex(update[second_start:], r'^\s*else\s*\{')
        second = block(update, second_start)
        window = 'static void compose(void){' + first + second + '}'
        name_line = next(line.strip() for line in function(script, 'Script_GetFunctionName').splitlines()
                         if 'openbor_zoom' in line)
        name_window = 'static const char *zoom_name(void *functionRef){' + name_line.replace('else if', 'if', 1)
        name_window += 'return "<unknown function>";}'
        registration = re.search(
            r'if\(obor_profile_build >= 3366\)\s+List_InsertAfter\(&theFunctionList,\s*\(void\*\)openbor_zoom,\s*"zoom"\);',
            function(script, 'Script_LoadSystemFunctions'))
        self.assertIsNotNone(registration)
        registration_window = 'static void register_zoom(void){' + registration[0] + '}'
        begin = re.search(r'(?m)^#define\s+MAXQSPRITES\b', queue_source)
        self.assertIsNotNone(begin)
        queue_globals = queue_source[begin.start():queue_source.index('void spriteq_add_frame(')]
        draw = function(queue_source, 'spriteq_draw')
        prefix = draw[:draw.index('switch(order[i]->type)')]
        selected = draw[draw.index('case SQT_SCREEN:'):draw.index('case SQT_DOT:')]
        draw = prefix + 'switch(order[i]->type){' + selected + 'default:abort();}}}'
        pieces = [function(variant, name) for name in
                  ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']]
        pieces += [function(script, 'openbor_zoom'), name_window, registration_window,
                   queue_globals, function(queue_source, 'spriteq_sort'),
                   function(queue_source, 'spriteq_add_screen'), function(queue_source, 'spriteq_clear'),
                   draw, window]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d,%d,%d);' % (
                row['revision'], row['available'], row['depth_filter'], row['background_copy']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef printf
@DEFINES@
uint32_t obor_profile_build;
int zoom_center_x,zoom_center_y,zoom_scale_x,zoom_scale_y,zoom_z;
static int ingame=1; /* The isolated composition window represents gameplay. */
static s_screen *vscreen,*zoombuffer;
List theFunctionList;
static int registered,draw_mask,draw_count,trace_on,at,observed_background;
static char trace[128],diagnostic[512];
static void event(char c){if(trace_on){assert(at+1<(int)sizeof(trace));trace[at++]=c;trace[at]=0;}}
CHAR *StrCache_Get(int index){(void)index;abort();}
void StrCache_Collect(int index){(void)index;}
int StrCache_Pop(void){abort();}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
void List_InsertAfter(List *list,void *entry,const char *name){assert(list==&theFunctionList && entry==(void*)openbor_zoom && !strcmp(name,"zoom"));registered++;}
static s_screen *screen_new(void){
 s_screen *s=calloc(1,sizeof(*s)+4);assert(s);s->width=4;s->height=1;s->pixelformat=PIXEL_8;return s;
}
s_screen *allocscreen(int w,int h,int format){
 assert(w==4 && h==1 && format==PIXEL_8);s_screen *s=screen_new();memset(s->data,0x5a,4);event('A');return s;
}
void freescreen(s_screen **screen){assert(*screen==zoombuffer);free(*screen);*screen=NULL;event('F');}
void clearscreen(s_screen *s){assert(s==zoombuffer);memset(s->data,0,4);event('C');}
void copyscreen(s_screen *dest,s_screen *src){assert(dest==zoombuffer && src==vscreen);memcpy(dest->data,src->data,4);event('B');}
void putscreen(s_screen *dest,s_screen *src,int x,int y,s_drawmethod *method){
 assert(!x && !y && method);draw_mask|=src->data[0];draw_count++;dest->data[0]=src->data[0];event(dest==zoombuffer?'L':'U');
}
void zoomscreen(s_screen *dest,s_screen *src,int x,int y,int scalex,int scaley){
 assert(dest==vscreen && src==zoombuffer && x==7 && y==9 && scalex==256 && scaley==300);
 observed_background=src->data[1];memcpy(dest->data,src->data,4);event('Z');
}
@PIECES@
static void reset_trace(void){at=0;trace[0]=0;draw_mask=draw_count=0;observed_background=-1;}
static void verify_api(int available){
 registered=0;register_zoom();assert(registered==available);
 assert(!strcmp(zoom_name((void*)openbor_zoom),available?"zoom":"<unknown function>"));
 ScriptVariant value[6],*args[6],result,*out;memset(value,0,sizeof(value));
 int good[]={7,9,256,300,0,99};
 for(int i=0;i<6;i++){value[i].vt=VT_INTEGER;value[i].lVal=good[i];args[i]=value+i;}
 for(int n=5;n<=6;n++){
  out=&result;assert(openbor_zoom(args,&out,n)==(available?S_OK:E_FAIL) && !out);
  if(available)assert(zoom_center_x==7 && zoom_center_y==9 && zoom_scale_x==256 && zoom_scale_y==300 && zoom_z==0);
 }
 if(!available)return;
 ScriptVariant *short_args[]={value,value+1,value+2,value+3};
 for(int n=0;n<5;n++){out=&result;diagnostic[0]=0;assert(openbor_zoom(short_args,&out,n)==E_FAIL && !out && diagnostic[0]);}
 out=&result;assert(openbor_zoom(NULL,&out,5)==E_FAIL && !out);
 args[4]=NULL;out=&result;assert(openbor_zoom(args,&out,5)==E_FAIL && !out);args[4]=value+4;
 for(int bad=0;bad<5;bad++){
  zoom_center_x=zoom_center_y=zoom_scale_x=zoom_scale_y=zoom_z=-1;
  value[bad].vt=VT_EMPTY;out=&result;diagnostic[0]=0;
  assert(openbor_zoom(args,&out,5)==E_FAIL && !out);
  assert(!strcmp(diagnostic,"Function requires 5 int values: zoom(int x, int y, int scalex, int scaley, int z)\n"));
  int actual[]={zoom_center_x,zoom_center_y,zoom_scale_x,zoom_scale_y,zoom_z};
  for(int i=0;i<5;i++)assert(actual[i]==(i<bad?good[i]:-1));
  value[bad].vt=VT_INTEGER;
 }
}
static void verify_queue(int filtered){
 static const int depth[]={MIN_INT,-1,0,1,MAX_INT};
 static const int ranges[][2]={{MIN_INT,MAX_INT},{MIN_INT,MIN_INT},{0,0},{MAX_INT,MAX_INT},{1,-1},{-1,1}};
 s_screen *images[5];spritequeue_len=spriteq_old_len=spriteq_locked=0;
 for(int i=0;i<5;i++){images[i]=screen_new();images[i]->data[0]=1<<i;spriteq_add_screen(0,0,depth[i],images[i],NULL,0);}
 for(int locked=0;locked<2;locked++)for(int only=0;only<2;only++)for(unsigned range=0;range<sizeof(ranges)/sizeof(ranges[0]);range++){
  spriteq_locked=locked;spriteq_old_len=2;reset_trace();int mask=0,count=0;
  for(int i=0;i<5;i++)if(!(only && locked && i<2) && (!filtered || (depth[i]>=ranges[range][0] && depth[i]<=ranges[range][1]))){mask|=1<<i;count++;}
  spriteq_draw(vscreen,only,ranges[range][0],ranges[range][1]);assert(draw_mask==mask && draw_count==count);
 }
 spriteq_locked=0;spriteq_clear();for(int i=0;i<5;i++)free(images[i]);
}
static void verify_composition(int available,int copies){
 s_screen *images[3];spritequeue_len=spriteq_old_len=spriteq_locked=0;
 for(int i=0;i<3;i++){images[i]=screen_new();images[i]->data[0]=1<<i;spriteq_add_screen(0,0,i-1,images[i],NULL,0);}
 trace_on=1;zoom_center_x=7;zoom_center_y=9;zoom_scale_x=256;zoom_scale_y=300;zoom_z=0;
 for(int frame=0;frame<2;frame++){
  vscreen->data[1]=11+frame*10;reset_trace();compose();
  if(available){
   assert(!strcmp(trace,frame?(copies?"BLLZU":"LLZU"):(copies?"ABLLZU":"ACLLZU")));
   assert(observed_background==(copies?11+frame*10:frame?73:0));
   assert(draw_mask==7 && draw_count==3 && zoombuffer);
   zoombuffer->data[1]=73;
  }else assert(!strcmp(trace,"UUU") && !zoombuffer && observed_background==-1 && draw_count==3);
 }
 if(available){
  zoom_z=MAX_INT;reset_trace();compose();assert(!strcmp(trace,copies?"BLLLZ":"LLLZ") && draw_count==3);
  zoom_z=MIN_INT;reset_trace();compose();assert(!strcmp(trace,copies?"BZUUU":"ZUUU") && draw_count==3);
 }
 zoom_scale_x=0;reset_trace();compose();assert(!strcmp(trace,available?"FUUU":"UUU") && !zoombuffer && draw_count==3);
 trace_on=0;spriteq_clear();for(int i=0;i<3;i++)free(images[i]);
}
static void check(unsigned revision,int available,int filtered,int copies){
 obor_profile_build=revision;vscreen=screen_new();verify_api(available);verify_queue(filtered);verify_composition(available,copies);free(vscreen);vscreen=NULL;
}
int main(void){@CHECKS@ puts("early_zoom=1");return 0;}
'''
        defines = '\n'.join(line for line in core.splitlines()
                            if line.startswith(('#define MIN_INT', '#define MAX_INT')))
        self.assertEqual(len(defines.splitlines()), 2)
        for key, value in dict(DEFINES=defines, PIECES='\n'.join(pieces),
                               CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-zoom-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                     '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                 '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_ZOOM_OBSERVATIONS'):
                Path(os.environ['OBOR_ZOOM_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(),
                    script_sha256=hashlib.sha256(script.encode()).hexdigest(),
                    queue_sha256=hashlib.sha256(queue_source.encode()).hexdigest(),
                    returncode=run.returncode, stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_zoom=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
