/* Layer call/clock observations with bounded resource providers.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Layer rendering mismatch: revision=%u case=%u sequence=%d line=%d\n",obor_profile_build,test_case,sequence,__LINE__);abort();}}while(0)
#undef time
#define time layer_time
uint32_t obor_profile_build;
static unsigned test_case;
static int sequence;
static s_level room,*level=&room;
static u32 time;
static int traveltime,texttime,current_palette;
int pixelformat,PLAYER_MAX_Z=232;
static float bgtravelled,advancex,advancey;
static entity *textbox,box;
static s_videomodes videomodes;
static s_screen destination,images[2];
static s_sprite sprites[2];
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@PLAIN@
struct event {
 int kind,x,y,z,sort,amplitude,phase,mode;
 float wavelength;
 void *source,*target;
 s_drawmethod method;
};
static struct event events[4096],expected[4096];
static unsigned used;
static struct event *record(int kind,int x,int y,void *source,s_screen *target,s_drawmethod *method) {
 assert(used<sizeof(events)/sizeof(*events));struct event *e=events+used++;
 memset(e,0,sizeof(*e));e->kind=kind;e->x=x;e->y=y;e->source=source;e->target=target;e->method=*method;return e;
}
void putscreen(s_screen *target,s_screen *source,int x,int y,s_drawmethod *method) {record(1,x,y,source,target,method);}
void putsprite(int x,int y,s_sprite *source,s_screen *target,s_drawmethod *method) {record(2,x,y,source,target,method);}
void putscreen_water(s_screen *target,s_screen *source,int x,int y,int amplitude,float wavelength,int phase,int mode,s_drawmethod *method) {
 struct event *e=record(3,x,y,source,target,method);e->amplitude=amplitude;e->wavelength=wavelength;e->phase=phase;e->mode=mode;
}
void spriteq_add_frame(int x,int y,int z,s_sprite *source,s_drawmethod *method,int sort) {
 struct event *e=record(4,x,y,source,NULL,method);e->z=z;e->sort=sort;
}
void spriteq_add_screen(int x,int y,int z,s_screen *source,s_drawmethod *method,int sort) {
 struct event *e=record(5,x,y,source,NULL,method);e->z=z;e->sort=sort;
}
@FUNCTIONS@
@ORIGINALS@
typedef void (*layers_fn)(s_screen*);
static layers_fn reference_bg[]={@REFERENCE_BG@},reference_fg[]={@REFERENCE_FG@};
struct input {
 int x,z;float bgspeed,travelled;int scroll_up,textbox,rocking,format,palette,style,source_type,method_enabled;
 u32 clock;int previous_clock,text_clock;float xratio,zratio;
};
static const struct input inputs[]={@INPUTS@};
static void setup(const struct input *in) {
 memset(level,0,sizeof(*level));memset(events,0,sizeof(events));used=0;
 time=in->clock;traveltime=in->previous_clock;texttime=in->text_clock;bgtravelled=in->travelled;
 textbox=in->textbox?&box:NULL;pixelformat=in->format;current_palette=in->palette;
 advancex=3.5f;advancey=2.25f;videomodes.hRes=13;videomodes.vRes=11;
 level->scrolldir=in->scroll_up?SCROLL_UP:0;level->rocking=in->rocking;level->bgspeed=in->bgspeed;
 level->numbglayers=level->numfglayers=3;level->numpalettes=3;
 for(int i=0;i<3;++i) {
  s_bglayer *b=level->bglayers+i;s_fglayer *f=level->fglayers+i;
  b->type=in->source_type==2?(bglayer_type)9:(bglayer_type)in->source_type;
  f->type=in->source_type==2?(fglayer_type)9:(fglayer_type)in->source_type;
  if(in->source_type==0){b->sprite=sprites+i%2;f->sprite=sprites+i%2;}
  else {b->screen=images+i%2;f->screen=images+i%2;}
  b->width=f->width=i?4:5;b->height=f->height=i?6:7;
  b->xspacing=f->xspacing=1;b->zspacing=f->zspacing=2;
  b->xoffset=f->xoffset=in->x+i*2;b->zoffset=f->zoffset=in->z-i;
  b->xratio=f->xratio=in->xratio;b->zratio=f->zratio=in->zratio;
  b->xrepeat=f->xrepeat=6;b->zrepeat=f->zrepeat=i==2?0:4;
  b->bgspeedratio=f->bgspeedratio=i?0.75f:1.25f;
  b->enabled=f->enabled=1;f->z=7+i;
  b->alpha=f->alpha=1;b->transparency=f->transparency=0;
  b->amplitude=f->amplitude=in->style==0?0:in->style==1?2:4;
  b->watermode=f->watermode=in->style==0?0:in->style==1?1:3;
  b->wavelength=f->wavelength=7;b->wavespeed=f->wavespeed=in->style==1?-0.5f:1.25f;
  b->drawmethod=f->drawmethod=plainmethod;
  s_drawmethod *methods[]={&b->drawmethod,&f->drawmethod};
  for(int k=0;k<2;++k) {
   s_drawmethod *m=methods[k];m->flag=in->method_enabled;m->alpha=3;m->transbg=1;
   m->remap=2;m->fillcolor=17;m->centerx=1;m->centery=2;m->scalex=384;m->flipy=1;
   m->water.watermode=b->watermode;
   if(in->style==2){m->water.beginsize=1.5f;m->water.endsize=2.25f;m->water.perspective=2;}
   else {m->water.amplitude=in->style==1?2:0;m->water.wavelength=7.5f;m->water.wavespeed=0.25f;}
  }
 }
}
static void calls(layers_fn bg,layers_fn fg) {
 switch(sequence) {
 case 0:bg(&destination);break;
 case 1:fg(&destination);break;
 case 2:bg(&destination);fg(&destination);break;
 case 3:fg(&destination);bg(&destination);break;
 case 4:bg(&destination);time+=7;fg(&destination);bg(&destination);break;
 default:fg(&destination);fg(&destination);break;
 }
}
static void same_method(const s_drawmethod *a,const s_drawmethod *b) {
 @METHOD_CHECKS@
 assert(a->table==b->table && a->fp==b->fp);
 assert(!memcmp(&a->water.amplitude,&b->water.amplitude,sizeof(a->water.amplitude)));
 assert(!memcmp(&a->water.wavelength,&b->water.wavelength,sizeof(a->water.wavelength)));
 assert(!memcmp(&a->water.wavespeed,&b->water.wavespeed,sizeof(a->water.wavespeed)));
 assert(a->water.wavetime==b->water.wavetime && a->water.watermode==b->water.watermode);
}
static void check(int bg,int fg) {
 for(test_case=0;test_case<sizeof(inputs)/sizeof(*inputs);++test_case)for(sequence=0;sequence<6;++sequence) {
  setup(inputs+test_case);calls(reference_bg[bg],reference_fg[fg]);
  unsigned count=used;memcpy(expected,events,used*sizeof(*events));
  float travelled=bgtravelled;int travel_clock=traveltime,text_clock=texttime;u32 clock=time;
  setup(inputs+test_case);calls(applybglayers,applyfglayers);
  assert(used==count && !memcmp(&bgtravelled,&travelled,sizeof(travelled)) &&
    traveltime==travel_clock && texttime==text_clock && time==clock);
  for(unsigned n=0;n<used;++n) {
   struct event *a=events+n,*b=expected+n;
   assert(a->kind==b->kind && a->x==b->x && a->y==b->y && a->z==b->z && a->sort==b->sort);
   assert(a->source==b->source && a->target==b->target && a->amplitude==b->amplitude &&
          a->wavelength==b->wavelength && a->phase==b->phase && a->mode==b->mode);
   same_method(&a->method,&b->method);
  }
 }
}
static void stable_inputs(void) {
 sequence=0;test_case=0;
 for(int test=0;test<7;++test) {
  setup(inputs);level->numbglayers=level->numfglayers=1;
  s_bglayer *b=level->bglayers;s_fglayer *f=level->fglayers;
  if(test==0){b->width=f->width=-1;b->xspacing=f->xspacing=0;}
  if(test==1){b->height=f->height=0;b->zspacing=f->zspacing=0;}
  if(test==2){b->xratio=f->xratio=NAN;}
  if(test==3){b->xoffset=f->xoffset=INT_MAX;b->xratio=f->xratio=0;}
  if(test==4){b->zoffset=f->zoffset=INT_MAX;level->scrolldir=0;}
  if(test==5){b->height=f->height=INT_MAX;level->scrolldir=SCROLL_UP;}
  if(test==6){b->xratio=f->xratio=INFINITY;}
  applybglayers(&destination);applyfglayers(&destination);assert(used==0);
 }
 setup(inputs);current_palette=INT_MAX;applybglayers(&destination);applyfglayers(&destination);
 for(unsigned i=0;i<used;++i)assert(events[i].method.table==NULL);
 setup(inputs);level->numbglayers=level->numfglayers=INT_MAX;applybglayers(&destination);applyfglayers(&destination);
 setup(inputs);level=NULL;used=0;applybglayers(&destination);applyfglayers(&destination);assert(!used);level=&room;
}
int main(void) {@CHECKS@ stable_inputs();return 0;}
