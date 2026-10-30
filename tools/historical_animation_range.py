"""Render animation distance loading and native range consumers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement, continued_macro


def render_animation_range(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    default = re.search(r'(?m)^[ \t]*if\(!newanim->range\.xmin\)[^\r\n]+\r?\n'
        r'(?:[ \t]*newanim->range\.(?:xmax|zmin|zmax|amin|amax|bmin|bmax)[^\r\n]+\r?\n){7}', source)[0]
    loads = []
    for name in ('RANGE', 'RANGEZ', 'RANGEA', 'RANGEB'):
        label = 'case CMD_MODEL_' + name + ':'
        if source.count(label) != 1:
            raise ValueError('Exactly one range model command required: ' + name)
        rest = source[source.index(label) + len(label):]
        loads.append(rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest).start()])
    think = function(source, 'common_think')
    warp = braced_statement(think, 'if(self->modeldata.subtype == SUBTYPE_FOLLOW && self->parent &&')
    getter = braced_statement(script, 'case _gep_range:')
    getter = getter[getter.index('{') + 1:getter.rfind('}')]
    enum = re.search(r'enum\s+gep_range_enum\s*\{[^{}]+\};', script)[0]
    numbers = ','.join('{%d,%d}' % (row['input'], row['signed16']) for row in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (row['revision'], row['range_bits']) for row in fixture['sources'])
    pieces = '\n'.join(function(source, name) for name in
                       ('diff', 'inair', 'common_try_jump', 'common_try_follow', 'homing_find_target'))
    variants = '\n'.join(function(variant, name) for name in
                         ('ScriptVariant_Clear', 'ScriptVariant_ChangeType'))
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef exit
#undef time
#undef pause
#undef shutdown
#undef kill
uint32_t obor_profile_build;
@MODEL_ERROR@
static s_anim animation,run_animation,blank_animation,target_animation;
static entity actor,candidate,alternative,*self=&actor;
static s_level stage,*level=&stage;
static s_anim *slots[128];
static entity *entities[3];
static entity **ent_list=entities;
static int ent_max=3;
static int supplied[3],wall_calls,wall_selected,jump_calls,walk_calls;
static float wall_x[2];
static const char *shutdownmessage;
#define GET_INT_ARG(i) (assert((i)>=1 && (i)<=2),supplied[i])
static void defaults(s_anim *newanim,s_model *newchar){@DEFAULT@}
static void load(s_anim *newanim,int axis,int first,int last){
 @MODEL_ERROR_STORAGE@
 supplied[1]=first;supplied[2]=last;
 switch(axis){case 0:do{@LOADX@}while(0);break;case 1:do{@LOADZ@}while(0);break;
 case 2:do{@LOADA@}while(0);break;case 3:do{@LOADB@}while(0);break;default:assert(0);}
 return;
lCleanup:assert(!"unexpected range command rejection");
}
int checkwall_below(float x,float z,float a){assert(wall_calls<2 && z==0 && a==999999);wall_x[wall_calls++]=x;return wall_calls==wall_selected?0:-1;}
int checkwall(float x,float z){(void)x;(void)z;return -1;}
int checkhole(float x,float z){(void)x;(void)z;return 0;}
void tryjump(float height,float speed,float depth,int animation_id){
 assert(height>0 && speed>0 && depth==0 && animation_id==(wall_selected==2?ANI_RUNJUMP:ANI_JUMP));++jump_calls;
}
void adjust_walk_animation(entity *target){assert(target==&candidate);++walk_calls;}
void npc_warp(void){}
@PIECES@
static void warp(void){if(self->dead)return;@WARP@}
void StrCache_Collect(int index){(void)index;assert(!"unexpected string result");}
int StrCache_Pop(void){assert(!"unexpected string result");return 0;}
@VARIANTS@
@ENUM@
static HRESULT getter(entity *ent,int property,ScriptVariant *result){
 ScriptVariant values[4],*varlist[4],*result_pointer=result,**pretvar=&result_pointer;
 int paramCount=4,i,coords[1]={0};LONG ltemp;
 memset(values,0,sizeof(values));memset(result,0,sizeof(*result));
 for(i=0;i<4;++i){varlist[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[2].lVal=property;values[3].lVal=ANI_IDLE;
 do{@GETTER@}while(0);return S_OK;
}
static const struct {int input,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){assert(bits==16 || bits==32);return bits==16?numbers[i].v16:numbers[i].input;}
static void read_values(int actual[8]){
 const int properties[]={_gep_range_xmin,_gep_range_xmax,_gep_range_zmin,_gep_range_zmax,
  _gep_range_amin,_gep_range_amax,_gep_range_bmin,_gep_range_bmax};
 for(int k=0;k<8;++k){ScriptVariant result;assert(getter(self,properties[k],&result)==S_OK && result.vt==VT_INTEGER);actual[k]=(int)result.lVal;}
}
static void check_values(const int want[8]){int actual[8];read_values(actual);for(int k=0;k<8;++k)assert(actual[k]==want[k]);}
static void check_macros(const int want[8],int axis){
 const float coordinates[]={-65536,-32768,-50,-1,0,1,50,32768,65536};
 entity *origin=self,*target=&candidate;
 for(unsigned n=0;n<sizeof(coordinates)/sizeof(coordinates[0]);++n)for(int direction=0;direction<2;++direction)for(int side=-1;side<=1;side+=2){
  actor.direction=direction;actor.x=actor.z=actor.a=actor.base=0;
  candidate.x=side*10.0f;candidate.z=candidate.a=candidate.base=0;
  if(axis==0)candidate.x=coordinates[n];else if(axis==1)candidate.z=coordinates[n];
  else if(axis==2)candidate.a=coordinates[n];else candidate.base=coordinates[n];
  int forward=candidate.x>(float)want[0] && candidate.x<(float)want[1];
  int backward=candidate.x<-(float)want[0] && candidate.x>-(float)want[1];
  int other=candidate.z>(float)want[2] && candidate.z<(float)want[3] &&
   candidate.a>(float)want[4] && candidate.a<(float)want[5] && candidate.base>(float)want[6] && candidate.base<(float)want[7];
  assert(!!check_range(origin,target,ANI_IDLE)==((direction?forward:backward)&&other));
  assert(!!check_range_both(origin,target,ANI_IDLE)==((forward||backward)&&other));
 }
 target=NULL;assert(!check_range(origin,target,ANI_IDLE) && !check_range_both(origin,target,ANI_IDLE));
}
static void check_ai(int first,int last){
 const float distances[]={0,1,50,100,32768,65536};
 actor.x=actor.z=actor.a=actor.base=0;actor.tossv=0;actor.parent=&candidate;
 actor.modeldata.nomove=0;actor.modeldata.speed=2;actor.modeldata.subtype=SUBTYPE_FOLLOW;
 actor.modeldata.jumpheight=actor.modeldata.runjumpheight=2;actor.modeldata.jumpspeed=3;actor.modeldata.runjumpdist=2;
 actor.modeldata.jumpmovez=0;stage.walls[0][7]=5;
 for(unsigned n=0;n<sizeof(distances)/sizeof(distances[0]);++n){
  candidate.x=distances[n];candidate.z=0;walk_calls=0;
  int follow=common_try_follow();assert(follow==(distances[n]>=(float)first) && walk_calls==follow);
  actor.takeaction=NULL;warp();assert((actor.takeaction==npc_warp)==(distances[n]>(float)last));
 }
 for(int direction=0;direction<2;++direction)for(int selected=1;selected<=2;++selected){
  actor.direction=direction;actor.running=0;wall_selected=selected;wall_calls=jump_calls=0;
  run_animation=animation;run_animation.numframes=selected==2?1:0;
  int jump=common_try_jump();assert(jump==((float)last>=5) && jump_calls==jump);
  assert(wall_calls==selected && wall_x[selected-1]==(direction?(float)first:-(float)first));
 }
 actor.direction=1;candidate.x=10;candidate.z=0;alternative.x=20;alternative.z=0;
 candidate.exists=alternative.exists=1;candidate.modeldata.type=alternative.modeldata.type=TYPE_ENEMY;
 entity *found=homing_find_target(TYPE_ENEMY);
 entity *want=10>=first && 10<=last?&candidate:20>=first && 20<=last?&alternative:NULL;
 assert(found==want && !homing_find_target(TYPE_PLAYER));
}
int main(void){
 assert(sizeof(int)==4 && sizeof(short)==2);
 for(int i=0;i<128;++i)slots[i]=&blank_animation;
 slots[ANI_IDLE]=slots[ANI_WALK]=slots[ANI_JUMP]=&animation;slots[ANI_RUNJUMP]=&run_animation;
 actor.modeldata.animation=slots;actor.modeldata.animation_capacity=128;actor.animation=&animation;
 entities[0]=&actor;entities[1]=&candidate;entities[2]=&alternative;
 short vulnerable[]={1};target_animation.vulnerable=vulnerable;candidate.animation=alternative.animation=&target_animation;
 animation.numframes=1;const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  const int heights[]={-2000,0,4,1639,2000},grabs[]={-100000,0,40,100000};
  for(unsigned j=0;j<5;++j)for(unsigned g=0;g<4;++g){
   s_model model;memset(&model,0,sizeof(model));model.jumpheight=heights[j];model.grabdistance=grabs[g];
   animation.range.xmin=0;defaults(&animation,&model);
   int max=heights[j]*20,low=-grabs[g]/3,high=grabs[g]/3;
   if(contexts[p].bits==16){max=(short)max;low=(short)low;high=(short)high;}
   int want[]={-10,max,low,high,-1000,1000,-1000,1000};check_values(want);
   animation.range.xmin=7;defaults(&animation,&model);want[0]=7;check_values(want);
  }
  for(unsigned n=0;n<count;++n)for(int axis=0;axis<4;++axis){
   int want[]={1,100,-1000,1000,-1000,1000,-1000,1000};
   for(int k=0;k<4;++k)load(&animation,k,want[2*k],want[2*k+1]);
   unsigned next=(n+7)%count;load(&animation,axis,numbers[n].input,numbers[next].input);
   want[2*axis]=expected(n,contexts[p].bits);want[2*axis+1]=expected(next,contexts[p].bits);
   check_values(want);check_macros(want,axis);
   if(!axis)check_ai(want[0],want[1]);
  }
 }
 printf("animation range contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@MODEL_ERROR@', function(source, 'obor_model_error') + '\n' + continued_macro(source, 'OBOR_MODEL_ERROR')).replace(
        '@MODEL_ERROR_STORAGE@', re.search(r'char legacy_model_error\[\d+\][^;]*;', function(source, 'load_cached_model')).group()).replace(
        '@DEFAULT@', default).replace('@LOADX@', loads[0]).replace('@LOADZ@', loads[1]).replace(
        '@LOADA@', loads[2]).replace('@LOADB@', loads[3]).replace('@PIECES@', pieces).replace(
        '@WARP@', warp).replace('@VARIANTS@', variants).replace('@ENUM@', enum).replace(
        '@GETTER@', getter).replace('@NUMBERS@', numbers).replace('@CONTEXTS@', contexts)
