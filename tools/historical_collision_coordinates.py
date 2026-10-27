"""Render exact collision and authored-coordinate bodies with bounded fixtures.

Native scalar/array shapes and expectations are explicit input data. Entity and
loader contexts are reduced fixtures; these checks do not run full model loads,
AI, combat callbacks, original executables or gameplay.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def render_collision(parts, *, scalar, components, ranges, tolerance_bonus,
                     revision, labels, threshold_only=False):
    if (not isinstance(parts, dict) or set(parts) !=
            {'checkhit', 'bbox', 'bboxz', 'attackz', 'frame_coordinates'} or
            any(not isinstance(value, str) or not value.strip() or
                len(value) > 32768 for value in parts.values())):
        raise ValueError('Bounded exact collision and loader source components required')
    if scalar not in ('short', 'int') or type(components) is not int or components not in (5, 6):
        raise ValueError('Explicit native scalar and coordinate array extent required')
    if any(type(value) is not bool for value in (ranges, tolerance_bonus, threshold_only)) or (ranges and components != 6):
        raise ValueError('Explicit compatible range and default-tolerance expectations required')
    if type(revision) is not int or not 0 <= revision <= 0x7fffffff:
        raise ValueError('Bounded native profile context required')
    if (not isinstance(labels, list) or not 0 < len(labels) <= 256 or
            any(not isinstance(label, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,127}', label)
                for label in labels) or len(set(labels)) != len(labels)):
        raise ValueError('Unique bounded source identifiers required')
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef NDEBUG
#error Native contract assertions must remain enabled
#endif
typedef @SCALAR@ coord_t;
enum { COMPONENTS=@COMPONENTS@, HAS_RANGES=@RANGES@, TOLERANCE_BONUS=@BONUS@ };
enum { TYPE_PLAYER=1, CMD_MODEL_BBOX=2, CMD_MODEL_BBOXZ=3,
       CMD_MODEL_ATTACKZ=4, CMD_MODEL_HITZ=5 };
typedef struct {coord_t attack_coords[COMPONENTS];int attack_type,counterattack;} s_attack;
typedef struct {coord_t (*bbox_coords)[COMPONENTS];s_attack **attacks;short *vulnerable;} s_anim;
typedef struct entity {
 float x,z,a;int direction,animpos;
 struct {int type;float grabdistance;} modeldata;
 s_anim *animation;
} entity;
static struct {int mode;} savedata;
static float lasthitx,lasthitz,lasthita;
static int lasthitt,lasthitc;
static uint32_t obor_profile_build=@REVISION@;
#define diff(a,b) ((a)>(b)?(a)-(b):(b)-(a))
@CHECKHIT@
#undef diff
static int arguments[7],reads[7];
static int get_argument(unsigned index) {
 assert(index<7);++reads[index];return arguments[index];
}
#define GET_INT_ARG(i) get_argument(i)
static void load_coordinates(int command,coord_t *bbox,s_attack *value) {
 s_attack attack=*value;
 switch(command) {
@BBOX@
@BBOXZ@
@ATTACKZ@
 default:assert(0);
 }
 *value=attack;
}
#undef GET_INT_ARG
static void frame_coordinates(coord_t *bbox,coord_t *bbox_con,
                              coord_t *abox,coord_t *offset,s_attack *value) {
 s_attack attack=*value;
@FRAME@
 *value=attack;
}
static void loader_checks(void) {
 coord_t bbox[COMPONENTS];s_attack attack={0};
 for(unsigned i=0;i<COMPONENTS;++i)bbox[i]=17;
 for(unsigned i=0;i<7;++i)arguments[i]=(int)i*3-9;
 memset(reads,0,sizeof(reads));load_coordinates(CMD_MODEL_BBOX,bbox,&attack);
 for(unsigned i=0;i<5;++i)assert(bbox[i]==arguments[i+1] && reads[i+1]==1);
 assert(reads[6]==HAS_RANGES);
 if(COMPONENTS==6)assert(bbox[5]==(HAS_RANGES?arguments[6]:0));
 memset(reads,0,sizeof(reads));load_coordinates(CMD_MODEL_BBOXZ,bbox,&attack);
 assert(bbox[4]==arguments[1] && reads[1]==1 && reads[2]==HAS_RANGES);
 if(COMPONENTS==6)assert(bbox[5]==(HAS_RANGES?arguments[2]:0));
 for(int command=CMD_MODEL_ATTACKZ;command<=CMD_MODEL_HITZ;++command) {
  memset(reads,0,sizeof(reads));load_coordinates(command,bbox,&attack);
  assert(attack.attack_coords[4]==arguments[1] && reads[1]==1 && reads[2]==HAS_RANGES);
  if(COMPONENTS==6)assert(attack.attack_coords[5]==(HAS_RANGES?arguments[2]:0));
 }
}
static void frame_checks(void) {
 const int limits[][2]={{-8,-2},{0,0},{0,8},{2,8},{8,-3}};
 const int offsets[]={-4,0,3};
 for(unsigned span=0;span<5;++span)for(unsigned off=0;off<3;++off) {
  coord_t bbox[COMPONENTS]={1,2,8,9,0},converted[COMPONENTS]={0};
  coord_t abox[COMPONENTS]={3,4,10,12,0},offset[2]={2,(coord_t)offsets[off]};
  s_attack attack={0};bbox[4]=attack.attack_coords[4]=(coord_t)limits[span][0];
  if(COMPONENTS==6)bbox[5]=attack.attack_coords[5]=(coord_t)limits[span][1];
  int bbox_lower=limits[span][0],bbox_upper=limits[span][1];
  int attack_lower=bbox_lower,attack_upper=bbox_upper;
  for(unsigned frame=0;frame<4;++frame) {
   frame_coordinates(bbox,converted,abox,offset,&attack);
   assert(converted[0]==-1 && converted[1]==2-offset[1]);
   assert(converted[2]==7 && converted[3]==11-offset[1]);
   assert(converted[4]==bbox_lower);
   if(COMPONENTS==6)assert(converted[5]==(HAS_RANGES?bbox_upper:0));
   /* The source captures the bbox result before mutating its persistent
      authored range. Consecutive frames test that observable order. */
   if(HAS_RANGES && bbox_upper>bbox_lower) {bbox_lower-=offset[1];bbox_upper-=offset[1];}
   if(HAS_RANGES && attack_upper>attack_lower) {attack_lower-=offset[1];attack_upper-=offset[1];}
   assert(bbox[4]==bbox_lower && attack.attack_coords[4]==attack_lower);
   if(COMPONENTS==6)assert(bbox[5]==bbox_upper && attack.attack_coords[5]==attack_upper);
   assert(attack.attack_coords[0]==1 && attack.attack_coords[1]==4-offset[1]);
   assert(attack.attack_coords[2]==11 && attack.attack_coords[3]==16-offset[1]);
  }
 }
}
typedef struct {float x,z,a;int type,count;} hit_result;
static hit_result reference_hit(const entity *a,const entity *b,int counter) {
 hit_result result={0};
 if(a==b || !b->animation->bbox_coords || !a->animation->attacks ||
    !b->animation->vulnerable[b->animpos] ||
    (a->modeldata.type==TYPE_PLAYER && b->modeldata.type==TYPE_PLAYER && savedata.mode))return result;
 const s_attack *attack=a->animation->attacks[a->animpos];
 if(counter && (!b->animation->attacks || !b->animation->attacks[b->animpos] ||
    b->animation->attacks[b->animpos]->counterattack>attack->counterattack))return result;
 const coord_t *ac=attack->attack_coords;
 const coord_t *bc=counter?b->animation->attacks[b->animpos]->attack_coords:
                         b->animation->bbox_coords[b->animpos];
 float az=a->z,bz=b->z,depth_a,depth_b;
 if(HAS_RANGES && ac[5]>ac[4]) {
  int half=(ac[5]-ac[4])/2;az+=ac[4]+half;depth_a=(float)half;
 } else depth_a=ac[4]?(float)ac[4]:a->modeldata.grabdistance/3+TOLERANCE_BONUS;
 if(HAS_RANGES && bc[5]>bc[4]) {
  int half=(bc[5]-bc[4])/2;bz+=bc[4]+half;depth_b=(float)half;
 } else depth_b=(float)bc[4];
 float separation=az-bz;if(separation<0)separation=-separation;
 if(separation>depth_a+depth_b+1)return result;
 int ax=(int)a->x,bx=(int)b->x,ay=(int)(az-a->a),by=(int)(bz-b->a);
 int left_a=ax+(a->direction?ac[0]:-ac[2]);
 int right_a=ax+(a->direction?ac[2]:-ac[0]);
 int left_b=bx+(b->direction?bc[0]:-bc[2]);
 int right_b=bx+(b->direction?bc[2]:-bc[0]);
 int top_a=ay+ac[1],bottom_a=ay+ac[3],top_b=by+bc[1],bottom_b=by+bc[3];
 if(left_a>right_b || left_b>right_a || top_a>bottom_b || top_b>bottom_a)return result;
 int left=left_a>left_b?left_a:left_b,right=right_a<right_b?right_a:right_b;
 int top=top_a>top_b?top_a:top_b,bottom=bottom_a<bottom_b?bottom_a:bottom_b;
 result.x=(float)(left+right)/2;result.z=(a->z>b->z?az:bz)+1;
 result.a=result.z-(float)(top+bottom)/2;result.type=attack->attack_type;result.count=1;
 return result;
}
static void compare_hit(entity *a,entity *b,int counter) {
 hit_result expected=reference_hit(a,b,counter);
 lasthitx=101;lasthitz=102;lasthita=103;lasthitt=104;lasthitc=105;
 assert(checkhit(a,b,counter)==expected.count);
 if(expected.count) {
  assert(lasthitx==expected.x && lasthitz==expected.z && lasthita==expected.a);
  assert(lasthitt==expected.type && lasthitc==1);
 } else assert(lasthitx==101 && lasthitz==102 && lasthita==103 && lasthitt==104 && lasthitc==105);
}
static void hit_checks(void) {
 const int limits[][2]={{0,0},{-4,5},{2,10},{7,-2},{-8,-3}};
 const int distances[]={-12,-4,-1,0,1,4,12},xs[]={-20,0,20};
 const float grabs[]={0,5.5f,12};
 short vulnerable=1;coord_t box[1][COMPONENTS]={{-5,-9,5,9,0}};
 s_attack aa={.attack_coords={-6,-8,6,8,0},.counterattack=2,.attack_type=23};
 s_attack ba={.attack_coords={-3,-7,8,7,0},.counterattack=1,.attack_type=29};
 s_attack *ap=&aa,*bp=&ba;
 s_anim an={.bbox_coords=box,.attacks=&ap,.vulnerable=&vulnerable};
 s_anim bn={.bbox_coords=box,.attacks=&bp,.vulnerable=&vulnerable};
 entity a={.z=10.25f,.a=2.5f,.animation=&an},b={.a=3.25f,.animation=&bn};
 unsigned cases=0;
 for(int counter=0;counter<2;++counter)for(int ad=0;ad<2;++ad)for(int bd=0;bd<2;++bd)
 for(unsigned al=0;al<5;++al)for(unsigned bl=0;bl<5;++bl)
 for(unsigned distance=0;distance<7;++distance)for(unsigned grab=0;grab<3;++grab)
 for(unsigned x=0;x<3;++x) {
  a.direction=ad;b.direction=bd;a.modeldata.grabdistance=grabs[grab];
  b.x=(float)xs[x];b.z=a.z+(float)distances[distance];
  aa.attack_coords[4]=(coord_t)limits[al][0];
  ba.attack_coords[4]=box[0][4]=(coord_t)limits[bl][0];
  if(COMPONENTS==6) {aa.attack_coords[5]=(coord_t)limits[al][1];ba.attack_coords[5]=box[0][5]=(coord_t)limits[bl][1];}
  compare_hit(&a,&b,counter);++cases;
 }
 assert(cases==12600);
 compare_hit(&a,&a,0);vulnerable=0;compare_hit(&a,&b,0);vulnerable=1;
 a.modeldata.type=b.modeldata.type=TYPE_PLAYER;savedata.mode=1;compare_hit(&a,&b,0);
 savedata.mode=0;a.modeldata.type=b.modeldata.type=0;
 bn.bbox_coords=NULL;compare_hit(&a,&b,0);bn.bbox_coords=box;
 an.attacks=NULL;compare_hit(&a,&b,0);an.attacks=&ap;
 bn.attacks=NULL;compare_hit(&a,&b,1);bn.attacks=&bp;
 ba.counterattack=3;compare_hit(&a,&b,1);
}
static void threshold_checks(void) {
 short vulnerable=1;coord_t box[1][COMPONENTS]={{-5,-9,5,9,0}};
 s_attack attack={.attack_coords={-6,-8,6,8,0}};s_attack *pointer=&attack;
 s_anim animation={.bbox_coords=box,.attacks=&pointer,.vulnerable=&vulnerable};
 entity a={.direction=1,.animation=&animation};
 entity b={.z=2,.direction=1,.animation=&animation};
 savedata.mode=0;
 /* Zero authored depth and grab distance isolate the one-unit default
    tolerance. The broad geometry grid does not replace this exact edge. */
 assert(checkhit(&a,&b,0)==TOLERANCE_BONUS);
 compare_hit(&a,&b,0);
}
int main(void) {
 @CALLS@
 puts(@OUTPUT@);return 0;
}
'''
    values = dict(SCALAR=scalar, COMPONENTS=str(components), RANGES=str(int(ranges)),
                  BONUS=str(int(tolerance_bonus)), REVISION=str(revision),
                  CHECKHIT=parts['checkhit'], BBOX=parts['bbox'], BBOXZ=parts['bboxz'],
                  ATTACKZ=parts['attackz'], FRAME=parts['frame_coordinates'],
                  CALLS='\n'.join(('threshold_checks();' if threshold_only else
                       'loader_checks();frame_checks();hit_checks();threshold_checks();') for label in labels),
                  OUTPUT=json.dumps(json.dumps({'status':'PASS','sources':len(labels),
                       'hit_cases_each':0 if threshold_only else 12600,
                       'loader_cases_each':0 if threshold_only else 4,
                       'frame_cases_each':0 if threshold_only else 60,
                       'threshold_cases_each':1})))
    for name,value in values.items():
        program = program.replace('@'+name+'@',value)
    return program
