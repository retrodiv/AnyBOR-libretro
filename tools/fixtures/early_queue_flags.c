/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Queue input ownership and observable member copies; padding is not an oracle.
 */
@HELPERS@
#include <stddef.h>
/* The original water records use five four-byte slots. Later water/plane
 * names alias those slots; queued copies must preserve the representation. */
_Static_assert(sizeof(int)==4 && sizeof(float)==4,"water scalar widths");
_Static_assert(sizeof(water_transform)==20,"water record size");
_Static_assert(offsetof(water_transform,amplitude)==offsetof(water_transform,beginsize),"amplitude/plane origin alias");
_Static_assert(offsetof(water_transform,wavelength)==offsetof(water_transform,endsize),"wavelength/plane extent alias");
_Static_assert(offsetof(water_transform,wavespeed)==offsetof(water_transform,perspective),"speed/perspective alias");
_Static_assert(offsetof(water_transform,wavespeed)==offsetof(water_transform,historical_wavespeed),"retained integer slot");
int screenformat;
@QUEUE_SOURCE@
static s_sprite frame;
static s_screen image;
static s_sprite_map map[1];
static unsigned char palette[256];
static void members(const s_drawmethod *a,const s_drawmethod *b)
{
 CHECK(a->table==b->table && a->fp==b->fp && a->fillcolor==b->fillcolor);
 CHECK(!!a->flag==!!b->flag && a->alpha==b->alpha && a->remap==b->remap);
 CHECK(a->flipx==b->flipx && a->flipy==b->flipy && a->transbg==b->transbg);
 CHECK(a->fliprotate==b->fliprotate && a->rotate==b->rotate);
 CHECK(a->scalex==b->scalex && a->scaley==b->scaley && a->shiftx==b->shiftx);
 CHECK(a->centerx==b->centerx && a->centery==b->centery);
 CHECK(a->water.amplitude==b->water.amplitude && a->water.wavelength==b->water.wavelength);
 CHECK(a->water.wavetime==b->water.wavetime && a->water.historical_wavespeed==b->water.historical_wavespeed);
 CHECK(a->water.watermode==b->water.watermode);
}
static void add(int kind,s_drawmethod *method)
{
 if(kind==0)spriteq_add_frame(10,20,30,&frame,method,40);
 else if(kind==1)spriteq_add_sprite(10,20,30,0,method,40);
 else spriteq_add_screen(10,20,30,&image,method,40);
}
static void check(int revision,int preserve)
{
 obor_profile_build=revision;sprite_map=map;map[0].sprite=&frame;
 map[0].centerx=13;map[0].centery=-7;
 for(int kind=0;kind<3;kind++)for(int flag=0;flag<2;flag++)for(int missing=0;missing<2;missing++){
  s_drawmethod method={0},saved,expected;
  method.table=palette;method.fp=&frame;method.fillcolor=123;method.flag=flag;
  method.alpha=3;method.remap=2;method.flipx=1;method.transbg=1;
  method.rotate=90;method.scalex=128;method.scaley=512;method.shiftx=-64;
  method.centerx=4;method.centery=-3;
  method.water.amplitude=2;method.water.wavelength=7.5f;
  method.water.wavetime=19;method.water.historical_wavespeed=-2;method.water.watermode=1;
  saved=method;expected=method;
  spritequeue_len=0;queue[0].drawmethod=method;order[0]=NULL;
  add(kind,missing?NULL:&method);
  if(missing)expected.flag=0;else if(!preserve)expected.flag=1;
  CHECK(spritequeue_len==1 && order[0]==queue);
  CHECK(queue[0].x==10 && queue[0].y==20 && queue[0].z==30 && queue[0].sortid==40);
  CHECK(queue[0].frame==(kind==2?(void*)&image:(void*)&frame));
  CHECK(queue[0].type==(kind==2?SQT_SCREEN:SQT_SPRITE));
  if(kind==0)CHECK(queue[0].params[0]==0);
  if(kind==1)CHECK(queue[0].params[0]==1 && queue[0].params[1]==13 && queue[0].params[2]==-7);
  members(&queue[0].drawmethod,&expected);members(&method,&saved);
  spritequeue_len=MAXQSPRITES;add(kind,&method);CHECK(spritequeue_len==MAXQSPRITES);
 }
 spritequeue_len=0;sprite_map=NULL;
}
int main(void){@QUEUE_CHECKS@ puts("inverse_transform_queue=1");return 0;}
