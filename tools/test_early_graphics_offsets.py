#!/usr/bin/env python3
"""Check historical graphics offset names, numeric IDs and queued coordinates."""
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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-graphics-offsets.json'


class EarlyGraphicsOffsetTests(unittest.TestCase):
    def test_names_numeric_ids_and_render_coordinates(self):
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
        method, cases = switch_cases(core, 'getsyspropertybyindex', 'index')
        getter = re.split(r'\bswitch\s*\(index\)', method, maxsplit=1)[0]
        getter += 'switch(index){' + '\n'.join(
            'case _e_' + name + ':' + cases['_e_' + name]['body']
            for name in ['gfx_x_offset', 'gfx_y_offset', 'gfx_y_offset_adj'])
        getter += 'default:return 0;}return 1;}'
        ns_start = script.index('/* Own script-visible system IDs')
        ns_end = script.index('void mapstrings_systemvariant(', ns_start)
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', script)
        self.assertIsNotNone(macro)
        pieces = [function(variant, name) for name in
                  ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']]
        pieces += [function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
                   script[ns_start:ns_end], function(script, 'mapstrings_systemvariant'), getter,
                   function(script, 'openbor_systemvariant'),
                   function(script, 'mapstrings_changesystemvariant'),
                   function(core, 'changesyspropertybyindex'),
                   function(script, 'openbor_changesystemvariant'),
                   function(core, 'display_ents'), function(core, 'draw_scrolled_bg')]
        plain = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{[^;]+\};', core)
        self.assertIsNotNone(plain)
        arrays, checks = [], []
        for index, row in enumerate(rows):
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            names = row['setter_names']
            arrays.append('static const char *names%d[]={%s};' %
                          (index, ','.join(map(json.dumps, names))))
            arrays.append('static const int ids%d[]={%s};' %
                          (index, ','.join(map(str, row['setter_ids']))))
            arrays.append('static const int getters%d[]={%s};' %
                          (index, ','.join(map(str, row['getter_indices']))))
            checks.append('check(%d,%d,%d,names%d,ids%d,getters%d,%d,%d);' %
                          (row['revision'], row['adjustments'], len(names), index, index, index, row['position_without_level'], row['position_only']))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef printf
uint32_t obor_profile_build;
int pixelformat=PIXEL_8,screenformat=PIXEL_8,pixelbytes[5]={1,1,2,3,4};
static unsigned time,neon_time;
static int pause,BGHEIGHT=160,current_palette,bgbuffer_updated;
static int PLAYER_MIN_Z=160,PLAYER_MAX_Z=232;
static s_screen screen,*vscreen=&screen,*background,*bgbuffer;
static s_bitmap *texture;
static s_videomodes videomodes;
static s_level instance,*level=&instance;
static int gfx_x_offset,gfx_y_offset,gfx_y_offset_adj;
static int lasthitc,lasthitt;
static float lasthita,lasthitx,lasthitz,advancex,advancey,scrollminz,scrollmaxz,blockade;
static unsigned char slowmotion[2],pal[MAX_PAL_SIZE],neontable[MAX_PAL_SIZE];
static entity *smartbomber,*textbox,*self,*ent_list[1],*platform;
static int ent_max=1,sprites_loaded=8,shadowcolor,shadowalpha,light[2],shadowsprites[6];
static int panels_loaded,panel_width,frontpanels_loaded,holesprite;
static s_panel panels[1];
static s_sprite panel_normal,panel_neon,panel_screen,front,*frontpanels[1]={&front};
static int wall_index=-1,wall_below=-1;
static char cache[32][256],diagnostic[1024];
CHAR *StrCache_Get(int index){assert(index>=0 && index<32);return cache[index];}
void StrCache_Collect(int index){(void)index;}
int StrCache_Pop(void){abort();}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
struct queued {int x,y,z,id,frame;} queued[64];
static int count;
void spriteq_add_sprite(int x,int y,int z,int id,s_drawmethod *method,int sortid){
 (void)method;(void)sortid;assert(count<64);queued[count++]=(struct queued){x,y,z,id,0};
}
void spriteq_add_frame(int x,int y,int z,s_sprite *sprite,s_drawmethod *method,int sortid){
 (void)method;(void)sortid;assert(count<64);int id=0;
 if(sprite==&panel_normal)id=10;else if(sprite==&panel_neon)id=11;else if(sprite==&panel_screen)id=12;else if(sprite==&front)id=13;else abort();
 queued[count++]=(struct queued){x,y,z,id,1};
}
static void drawenemystatus(entity *e){(void)e;abort();}
entity *check_platform(float x,float z){(void)x;(void)z;return platform;}
int checkwall(float x,float z){(void)x;(void)z;return wall_index;}
int checkwall_below(float x,float z,float a){(void)x;(void)z;(void)a;return wall_below;}
int checkhole(float x,float z){(void)x;(void)z;return 0;}
int inair(entity *e){(void)e;return 1;}
s_drawmethod *getDrawMethod(s_anim *animation,int frame){(void)animation;(void)frame;abort();}
static void applybglayers(s_screen *s){(void)s;abort();}
static void applyfglayers(s_screen *s){assert(s==vscreen);}
void putscreen(s_screen *dst,s_screen *src,int x,int y,s_drawmethod *method){(void)dst;(void)src;(void)x;(void)y;(void)method;abort();}
void apply_texture_plane(s_screen *dst,int x,int y,int width,int height,int offset,int factor,s_bitmap *src,s_drawmethod *method){(void)dst;(void)x;(void)y;(void)width;(void)height;(void)offset;(void)factor;(void)src;(void)method;abort();}
void apply_texture_wave(s_screen *dst,int x,int y,int width,int height,int offset,int factor,s_bitmap *src,int wave_time,int amplitude,s_drawmethod *method){(void)dst;(void)x;(void)y;(void)width;(void)height;(void)offset;(void)factor;(void)src;(void)wave_time;(void)amplitude;(void)method;abort();}
@PLAIN@
@PIECES@
@ARRAYS@
static ScriptVariant input,value,result,*args[]={&input,&value},*out;
static void name(const char *text){memset(&input,0,sizeof(input));input.vt=VT_STR;input.strVal=0;snprintf(cache[0],sizeof(cache[0]),"%s",text);diagnostic[0]=0;}
static void set_numeric(int index,int amount){
 memset(&input,0,sizeof(input));input.vt=VT_INTEGER;input.lVal=index;
 memset(&value,0,sizeof(value));value.vt=VT_INTEGER;value.lVal=amount;out=&result;
 assert(openbor_changesystemvariant(args,&out,2)==S_OK && out==&result);
}
static void verify_apis(int modern,int n,const char **names,const int *ids,const int *getters){
 static const char *gfx[]={"gfx_x_offset","gfx_y_offset","gfx_y_offset_adj"};
 gfx_x_offset=17;gfx_y_offset=31;gfx_y_offset_adj=-9;
 for(int i=0;i<n;i++){
  name(names[i]);mapstrings_changesystemvariant(args,2);
  assert(input.vt==VT_INTEGER && input.lVal==i && !diagnostic[0]);
  if(!strcmp(names[i],"lasthita")){set_numeric(i,43);assert(lasthita==43 && gfx_x_offset==17 && gfx_y_offset==31);}
  if(!strcmp(names[i],"ypos")){set_numeric(i,47);assert(advancey==47);}
  assert(ids[i]==i+(modern?0:(i>=2?3:0)));
 }
 for(int i=0;i<3;i++){
  name(gfx[i]);mapstrings_changesystemvariant(args,2);
  if(!modern){
   assert(input.vt==VT_STR);
   char expected[160];snprintf(expected,sizeof(expected),"changeopenborvariant: System variable name not found: '%s'\n",gfx[i]);assert(!strcmp(diagnostic,expected));
   out=&result;assert(openbor_changesystemvariant(args,&out,2)==E_FAIL && !out);
  }else{
   assert(input.vt==VT_INTEGER && input.lVal==i+2);set_numeric(i+2,50+i);
   assert((i==0?gfx_x_offset:i==1?gfx_y_offset:gfx_y_offset_adj)==50+i);
  }
 }
 assert(changesyspropertybyindex(n,&value)==0);
 for(int i=0;i<3;i++){
  name(gfx[i]);out=&result;memset(&result,0,sizeof(result));
  int available=getters[i]>=0;
  HRESULT status=openbor_systemvariant(args,&out,1);
  if(!available){assert(status==E_FAIL && !out);continue;}
  assert(status==S_OK && out==&result && result.vt==VT_INTEGER);
  assert(input.vt==VT_INTEGER && input.lVal==getters[i]);
  assert(result.lVal==(i==0?gfx_x_offset:i==1?gfx_y_offset:gfx_y_offset_adj));
  level=NULL;out=&result;result.vt=VT_INTEGER;result.lVal=99;
  assert(!getsyspropertybyindex(&result,getters[i]) && result.vt==VT_INTEGER && result.lVal==99);
  level=&instance;
 }
}
static void verify_position(int position_without_level){
 // The native setter reports success; its script wrapper leaves output intact.
 // Before the field move the no-level write was discarded by the next load.
 name("levelpos");mapstrings_changesystemvariant(args,2);
 assert(input.vt==VT_INTEGER);const int position_id=input.lVal;
 result.vt=VT_INTEGER;result.lVal=321;
 level=&instance;instance.pos=19;set_numeric(position_id,-73);
 assert(result.vt==VT_INTEGER && result.lVal==321 && instance.pos==-73);
 value.vt=VT_DECIMAL;value.dblVal=6.75;
 assert(changesyspropertybyindex(position_id,&value)==1 && instance.pos==6);
 level=NULL;value.vt=VT_INTEGER;value.lVal=91;
 assert(changesyspropertybyindex(position_id,&value)==position_without_level && instance.pos==6);
 input.vt=VT_INTEGER;input.lVal=position_id;out=&result;
 HRESULT position_status=openbor_changesystemvariant(args,&out,2);
 assert(position_status==(position_without_level?S_OK:E_FAIL));
 assert(out==(position_without_level?&result:NULL));
 assert(result.vt==VT_INTEGER && result.lVal==321 && instance.pos==6);
 // Conversion failure never touched either original storage representation.
 value.vt=VT_STR;value.strVal=31;strcpy(cache[31],"unused");out=&result;
 assert(changesyspropertybyindex(position_id,&value)==1);
 assert(openbor_changesystemvariant(args,&out,2)==S_OK && out==&result);
 assert(result.vt==VT_INTEGER && result.lVal==321 && instance.pos==6);
 level=&instance;
}
static void verify_entities(int modern){
 entity actor={0},other={0};s_anim animation={0},other_anim={0};
 int sprites[1]={1};
 short coords[1][2]={{2,3}};
 animation.sprite=sprites;animation.shadow_coords=coords;actor.animation=&animation;
 actor.exists=1;actor.x=100.75f;actor.z=MIRROR_Z+40.5f;actor.a=10.25f;actor.sortid=2;actor.direction=1;
 actor.modeldata.parrow[0][0]=3;actor.modeldata.parrow[0][1]=7;actor.modeldata.parrow[0][2]=9;
 actor.arrowon=1;actor.invincible=1;ent_list[0]=self=&actor;other.animation=&other_anim;
 float platform_rows[1][8]={{0}};other_anim.platform=platform_rows;platform_rows[0][7]=2;other.a=3;other.z=actor.z;
 level=&instance;memset(level,0,sizeof(*level));level->walls[0][7]=4;
 advancex=12.25f;advancey=0;gfx_y_offset=6;light[0]=32;light[1]=128;shadowcolor=1;shadowsprites[0]=4;
 for(int shadow=0;shadow<3;shadow++)for(int surface=0;surface<3;surface++)for(int mirror=0;mirror<2;mirror++){
  level->mirror=mirror;actor.modeldata.gfxshadow=shadow==2;actor.modeldata.shadow=shadow?1:0;
  platform=surface==1?&other:NULL;wall_index=surface==2?0:-1;wall_below=surface==2?0:-1;
  gfx_x_offset=0;count=0;display_ents();int baseline_count=count;struct queued baseline[64];memcpy(baseline,queued,sizeof(queued));
  assert(baseline_count>=2);
  for(int sign=-1;sign<=1;sign+=2){
   gfx_x_offset=sign*13;count=0;display_ents();assert(count==baseline_count);
   for(int i=0;i<count;i++){assert(queued[i].x==baseline[i].x+(modern?sign*13:0));assert(queued[i].y==baseline[i].y && queued[i].z==baseline[i].z && queued[i].id==baseline[i].id);}
  }
 }
 platform=NULL;wall_index=wall_below=-1;ent_list[0]=self=NULL;count=0;
}
static void verify_background(int modern){
 
 level=&instance;memset(level,0,sizeof(*level));level->numholes=1;level->numpanels=1;level->order[0]=0;
 level->holes[0][0]=55;level->holes[0][1]=70;level->holes[0][6]=2;
 panels[0]=(s_panel){&panel_normal,&panel_neon,&panel_screen};panels_loaded=1;panel_width=1000;
 frontpanels_loaded=1;front.width=1000;videomodes.hRes=320;advancex=12;advancey=9;neon_time=100000;holesprite=5;
 time=1;smartbomber=textbox=NULL;current_palette=0;pixelformat=PIXEL_8;screenformat=PIXEL_8;
 for(int scrolling=0;scrolling<2;scrolling++)for(int rocking=0;rocking<4;rocking++){
  level->scrolldir=scrolling?SCROLL_UP:SCROLL_RIGHT;level->rocking=rocking;level->quake=8;level->quaketime=100;
  gfx_x_offset=0;gfx_y_offset_adj=0;count=0;draw_scrolled_bg();int baseline_count=count,base_y=gfx_y_offset;
  struct queued baseline[64];memcpy(baseline,queued,sizeof(queued));assert(baseline_count==5);
  gfx_x_offset=-13;gfx_y_offset_adj=7;count=0;draw_scrolled_bg();assert(count==baseline_count && gfx_y_offset==base_y+(modern?7:0));
  for(int i=0;i<count;i++){assert(queued[i].x==baseline[i].x-(modern?13:0) && queued[i].y==baseline[i].y+(modern?7:0));assert(queued[i].id==baseline[i].id && queued[i].z==baseline[i].z);}
 }
 panels_loaded=frontpanels_loaded=0;
}
static void check(unsigned revision,int modern,int n,const char **names,const int *ids,const int *getters,int position_without_level,int position_only){
 obor_profile_build=revision;
 if(!position_only){verify_apis(modern,n,names,ids,getters);verify_entities(modern);verify_background(modern);}
 verify_position(position_without_level);
}
int main(void){@CHECKS@ puts("early_graphics_offsets=1");return 0;}
'''
        for key, value in dict(PLAIN=plain[0], PIECES='\n'.join(pieces),
                               ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-graphics-offsets-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-Dstricmp=strcasecmp', '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
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
            if os.environ.get('OBOR_GRAPHICS_OFFSET_OBSERVATIONS'):
                Path(os.environ['OBOR_GRAPHICS_OFFSET_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows),
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(),
                    script_sha256=hashlib.sha256(script.encode()).hexdigest(),
                    returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                    scope=fixture['scope'], retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_graphics_offsets=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
