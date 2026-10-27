"""Render full animation-frame functions against their actual native headers.

Header/include paths and compiler context belong to the caller's bound plan.
Allocation tracking is a bounded fixture; model parsing, fatal-allocation
policy, raster output, VM execution and gameplay require separate checks.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from native_header_fixtures import inline_refusals, graphics_refusals


def render_frames(parts, *, visible_components, revision, labels,
                  unused_graphics_inlines=False, unused_inline_declarations=None):
    required={'alloc_frames','free_frames','addframe','setDrawMethod','getDrawMethod','cache'}
    if (not isinstance(parts,dict) or set(parts)!=required or
            any(not isinstance(value,str) or len(value)>65536 or
                (name!='cache' and not value.strip()) for name,value in parts.items())):
        raise ValueError('Bounded exact native frame functions and optional cache required')
    if (('retain_anim_drawmethod(' in parts['addframe'] or
         'release_anim_drawmethod(' in parts['free_frames']) and not parts['cache'].strip()):
        raise ValueError('Actual cache source required by the selected native functions')
    if type(visible_components) is not int or visible_components not in (5,6):
        raise ValueError('Explicit source-defined coordinate extent required')
    if type(revision) is not int or not 0<=revision<=0x7fffffff:
        raise ValueError('Bounded native profile context required')
    if type(unused_graphics_inlines) is not bool:
        raise ValueError('Explicit native graphics-header declaration context required')
    refusal_definitions=inline_refusals(unused_inline_declarations,forbidden_names=required)
    if (not isinstance(labels,list) or not 0<len(labels)<=256 or
            any(not isinstance(label,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,127}',label)
                for label in labels) or len(set(labels))!=len(labels)):
        raise ValueError('Unique bounded source identifiers required')
    program=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#undef malloc
#undef free
#ifdef NDEBUG
#error Native contract assertions must remain enabled
#endif
#define assert(condition) do {if(!(condition))abort();} while(0)
uint32_t obor_profile_build=@REVISION@;
/* Some native headers declare these interpreter entries inline. The frame
   contract does not link the VM; refuse unexpected execution explicitly. */
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@UNUSED_GRAPHICS@
@UNUSED_INLINES@
enum {VISIBLE_COMPONENTS=@VISIBLE@,
 STORAGE_COMPONENTS=sizeof(((s_attack*)0)->attack_coords)/sizeof(((s_attack*)0)->attack_coords[0])};
typedef __typeof__(((s_attack*)0)->attack_coords[0]) coord_t;
static void *live[128];
static unsigned allocations,releases;
static void *tracked_malloc(size_t bytes) {
 assert(bytes>0 && bytes<=65536);void *p=malloc(bytes);assert(p);
 unsigned slot=0;while(slot<128 && live[slot])++slot;assert(slot<128);
 live[slot]=p;++allocations;return p;
}
static void tracked_free(void *p) {
 if(!p)return;
 unsigned slot=0;while(slot<128 && live[slot]!=p)++slot;assert(slot<128);
 live[slot]=NULL;++releases;free(p);
}
#define malloc tracked_malloc
#define free tracked_free
@CACHE@
@SET@
@GET@
@ALLOC@
@ADD@
@CLEAR@
#undef free
#undef malloc
static int enabled(unsigned mask,unsigned bit,int frame) {
 return (frame==1 || frame==2) && (mask&(1u<<bit));
}
static void attack_value(s_attack *attack,unsigned mask,int frame) {
 memset(attack,0,sizeof(*attack));
 if(enabled(mask,1,frame)) {
  for(unsigned c=0;c<VISIBLE_COMPONENTS;++c)
   attack->attack_coords[c]=(coord_t)(20*(frame+1)+(int)c);
  attack->attack_force=17+frame;attack->attack_type=2;
  attack->no_pain=1;attack->dropv[0]=1.5f;
 }
}
static void drawing_value(s_drawmethod *method,unsigned mask,int frame) {
 memset(method,0,sizeof(*method));method->flag=enabled(mask,2,frame)!=0;
 method->scalex=256;method->scaley=257;
}
static void check_case(unsigned mask,int preallocated) {
 s_anim animation;memset(&animation,0,sizeof(animation));
 assert(STORAGE_COMPONENTS>=VISIBLE_COMPONENTS && STORAGE_COMPONENTS<=6);
 unsigned before_alloc=allocations,before_free=releases;
 if(preallocated)alloc_frames(&animation,4);
 for(int frame=0;frame<4;++frame) {
  coord_t bbox[STORAGE_COMPONENTS],offset[2]={0};
  memset(bbox,0,sizeof(bbox));
  if(enabled(mask,0,frame))for(unsigned c=0;c<VISIBLE_COMPONENTS;++c)
   bbox[c]=(coord_t)(10*(frame+1)+(int)c);
  s_attack attack;attack_value(&attack,mask,frame);
  s_drawmethod method;drawing_value(&method,mask,frame);
  int moving=enabled(mask,3,frame),shadow=enabled(mask,4,frame),media=enabled(mask,5,frame);
  if(shadow) {offset[0]=(coord_t)(frame==1?-4:6);offset[1]=(coord_t)(frame==1?5:0);}
  float platform[8]={0};
  if(media)for(unsigned n=0;n<8;++n)platform[n]=(float)(n+frame+1);
  int capacity=!preallocated && frame==0?4:-4;
  assert(addframe(&animation,100+frame,capacity,3*(frame+1),moving?201:0,
      bbox,&attack,moving?-5-frame:0,moving?6+frame:0,moving?-7-frame:0,
      moving?20+frame:-1,platform,shadow?30+frame:-1,offset,
      media?40+frame:-1,&method)==frame+1);
 }
 assert(animation.numframes==4 && animation.sprite && animation.delay && animation.vulnerable);
 for(int frame=0;frame<4;++frame) {
  int bbox_on=enabled(mask,0,frame),attack_on=enabled(mask,1,frame);
  int moving=enabled(mask,3,frame),shadow=enabled(mask,4,frame),media=enabled(mask,5,frame);
  assert(animation.sprite[frame]==100+frame);
  assert(animation.delay[frame]==3*(frame+1)*GAME_SPEED/100);
  assert(animation.vulnerable[frame]==!!bbox_on);
  if(animation.bbox_coords)for(unsigned c=0;c<STORAGE_COMPONENTS;++c) {
   coord_t expected=bbox_on && c<VISIBLE_COMPONENTS?(coord_t)(10*(frame+1)+(int)c):0;
   assert(animation.bbox_coords[frame][c]==expected);
  } else assert(!(mask&1));
  s_attack expected_attack;attack_value(&expected_attack,mask,frame);
  if(animation.attacks && animation.attacks[frame]) {
   assert(attack_on && !memcmp(animation.attacks[frame],&expected_attack,sizeof(expected_attack)));
  } else assert(!attack_on);
  s_drawmethod expected_method;drawing_value(&expected_method,mask,frame);
  if(animation.drawmethods) {
   s_drawmethod *method=getDrawMethod(&animation,frame);
   if(method)assert(enabled(mask,2,frame) && !memcmp(method,&expected_method,sizeof(*method)));
   else assert(!enabled(mask,2,frame));
  } else assert(!(mask&4));
  if(animation.idle)assert(animation.idle[frame]==(moving?201:0));else assert(!(mask&8));
  if(animation.move)assert(animation.move[frame]==(moving?-5-frame:0));else assert(!(mask&8));
  if(animation.movez)assert(animation.movez[frame]==(moving?6+frame:0));else assert(!(mask&8));
  if(animation.movea)assert(animation.movea[frame]==(moving?-7-frame:0));else assert(!(mask&8));
  if(animation.seta)assert(animation.seta[frame]==(moving?20+frame:-1));else assert(!(mask&8));
  if(animation.shadow)assert(animation.shadow[frame]==(shadow?30+frame:-1));else assert(!(mask&16));
  if(animation.shadow_coords) {
   assert(animation.shadow_coords[frame][0]==(shadow?(frame==1?-4:6):0));
   assert(animation.shadow_coords[frame][1]==(shadow?(frame==1?5:0):0));
  } else assert(!(mask&16));
  if(animation.soundtoplay)assert(animation.soundtoplay[frame]==(media?40+frame:-1));else assert(!(mask&32));
  if(animation.platform)for(unsigned n=0;n<8;++n)
   assert(animation.platform[frame][n]==(media?(float)(n+frame+1):0));
  else assert(!(mask&32));
 }
 free_frames(&animation);
 assert(animation.numframes==4);
 assert(!animation.sprite && !animation.delay && !animation.vulnerable && !animation.bbox_coords);
 assert(!animation.attacks && !animation.drawmethods && !animation.idle);
 assert(!animation.move && !animation.movez && !animation.movea && !animation.seta);
 assert(!animation.shadow && !animation.shadow_coords && !animation.soundtoplay && !animation.platform);
 assert(allocations-before_alloc==releases-before_free);
 for(unsigned i=0;i<128;++i)assert(!live[i]);
}
static void frame_checks(void) {
 for(unsigned mask=0;mask<64;++mask)for(int mode=0;mode<2;++mode)check_case(mask,mode);
}
int main(void) {
 @CALLS@
 puts(@OUTPUT@);return 0;
}
'''
    unused_graphics=graphics_refusals(unused_graphics_inlines)
    values=dict(REVISION=str(revision),VISIBLE=str(visible_components),CACHE=parts['cache'],
                UNUSED_GRAPHICS=unused_graphics,
                UNUSED_INLINES=refusal_definitions,
                SET=parts['setDrawMethod'],GET=parts['getDrawMethod'],ALLOC=parts['alloc_frames'],
                ADD=parts['addframe'],CLEAR=parts['free_frames'],
                CALLS='\n'.join('frame_checks();' for label in labels),
                OUTPUT=json.dumps(json.dumps({'status':'PASS','sources':len(labels),
                    'cases_each':128,'frames_each':512})))
    for name,value in values.items():program=program.replace('@'+name+'@',value)
    return program
