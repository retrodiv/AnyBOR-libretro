/* Layer command, loader and post-load observations.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "commands.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Layer parser mismatch: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static unsigned test_case;
static s_level room,expected_room,*level=&room;
static ArgList arglist;
static char bgPath[512],expected_path[512];
static char *filename="fixture.txt",*command,*parser_error;
char packfile[OBOR_CONTENT_PATH_MAX]="fixture.pak";
int pixelformat=PIXEL_8;
static int blendfx[MAX_BLENDINGS];
static char blendfx_is_set;
static s_screen image;
static s_sprite picture;
static int provider_height;
struct event {int kind;const char *name;float amplitude;};
static struct event events[16],expected_events[16];
static unsigned used;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
void shutdown(int status,char *message,...) {(void)status;(void)message;abort();}
static void event(int kind,const char *name,float amplitude) {
 assert(used<16);events[used++]=(struct event){kind,name,amplitude};
}
s_sprite *loadsprite2(char *name,int *width,int *height) {
 event(1,name,0);*width=7;*height=provider_height;return &picture;
}
int loadscreen(char *name,char *pack,unsigned char *palette,int format,s_screen **out) {
 assert(pack==packfile && !palette && format==PIXEL_8);event(2,name,0);s_screen *loaded=&image;memcpy(out,&loaded,sizeof(loaded));return 1;
}
void load_texture(char *name) {event(3,name,0);}
void texture_set_wave(float amplitude) {event(4,NULL,amplitude);}
@PLAIN@
@HELPERS@
@MACROS@
static int parse(int cmd) {
 char *value,*errormessage=NULL;
 int i;
 s_drawmethod *dm;
 char legacy_level_error[1024];
 switch(cmd) {
 @CASES@
 default:abort();
 }
 return 0;
lCleanup:
 parser_error=errormessage;
 return -1;
}
@ORIGINALS@
@OWNERSHIP@
typedef int (*parse_fn)(int);
typedef void (*post_fn)(void);
static parse_fn reference_background[]={@BACKGROUND@},reference_bglayer[]={@BGLAYER@},
 reference_fglayer[]={@FGLAYER@},reference_water[]={@WATER@};
static post_fn reference_post[]={@POST@};
struct input {int command,count;char *words[18];};
static const struct input inputs[]={@INPUTS@};
static void setup(const struct input *input,int existing,int rocking,int blend,int height) {
 memset(level,0,sizeof(*level));memset(bgPath,0,sizeof(bgPath));memset(events,0,sizeof(events));
 memset(blendfx,0,sizeof(blendfx));blendfx_is_set=blend;used=0;parser_error=NULL;
 memset(&image,0,sizeof(image));image.width=7;image.height=provider_height=height;
 level->numbglayers=level->numfglayers=existing;level->rocking=rocking;
 level->bglayers[0].screen=&image;level->bglayers[0].type=bg_screen;
 level->bglayers[0].width=7;level->bglayers[0].height=height;
 level->bglayers[0].xrepeat=5;level->bglayers[0].zrepeat=3;level->bglayers[0].enabled=1;
 memset(&arglist,0,sizeof(arglist));arglist.count=input->count;command=input->words[0];
 for(int i=0;i<input->count;++i){arglist.args[i]=input->words[i];arglist.arglen[i]=strlen(input->words[i]);}
}
static void same_method(const s_drawmethod *a,const s_drawmethod *b) {
 @METHOD_CHECKS@
 assert(a->table==b->table && a->fp==b->fp);
 assert(!memcmp(&a->water.amplitude,&b->water.amplitude,sizeof(a->water.amplitude)));
 assert(!memcmp(&a->water.wavelength,&b->water.wavelength,sizeof(a->water.wavelength)));
 assert(!memcmp(&a->water.wavespeed,&b->water.wavespeed,sizeof(a->water.wavespeed)));
 assert(a->water.wavetime==b->water.wavetime && a->water.watermode==b->water.watermode);
}
static void same_layers(void) {
 assert(level->numbglayers==expected_room.numbglayers && level->numfglayers==expected_room.numfglayers);
 for(int i=0;i<3;++i) {
  {s_bglayer *a=level->bglayers+i,*b=expected_room.bglayers+i;@LAYER_CHECKS@ same_method(&a->drawmethod,&b->drawmethod);}
  {s_fglayer *a=level->fglayers+i,*b=expected_room.fglayers+i;@LAYER_CHECKS@ assert(a->z==b->z);same_method(&a->drawmethod,&b->drawmethod);}
 }
}
static void check(int background,int bg,int fg,int water,int post) {
 for(test_case=0;test_case<sizeof(inputs)/sizeof(*inputs);++test_case)
 for(int existing=0;existing<2;++existing)for(int rocking=0;rocking<2;++rocking)
 for(int blend=0;blend<2;++blend) {
  int height=test_case%2?23:11;
  const struct input *in=inputs+test_case;
  parse_fn reference=in->command==CMD_LEVEL_BACKGROUND?reference_background[background]:
   in->command==CMD_LEVEL_BGLAYER?reference_bglayer[bg]:
   in->command==CMD_LEVEL_FGLAYER?reference_fglayer[fg]:reference_water[water];
  setup(in,existing,rocking,blend,height);int expected_status=reference(in->command);
  if(!expected_status)reference_post[post]();
  expected_room=*level;memcpy(expected_path,bgPath,sizeof(bgPath));
  unsigned expected_used=used;memcpy(expected_events,events,used*sizeof(*events));
  int expected_blend[MAX_BLENDINGS];memcpy(expected_blend,blendfx,sizeof(blendfx));
  const char *expected_error=parser_error;
  setup(in,existing,rocking,blend,height);int status=parse(in->command);
  if(!status)obor_finish_layers();
  assert(status==expected_status && used==expected_used);
  assert(!strcmp(bgPath,expected_path) && !memcmp(blendfx,expected_blend,sizeof(blendfx)));
  assert((!parser_error && !expected_error) || (parser_error && expected_error && !strcmp(parser_error,expected_error)));
  for(unsigned i=0;i<used;++i) {
   assert(events[i].kind==expected_events[i].kind && events[i].amplitude==expected_events[i].amplitude);
   assert((!events[i].name && !expected_events[i].name) ||
     (events[i].name && expected_events[i].name && !strcmp(events[i].name,expected_events[i].name)));
  }
  same_layers();
 }
 /* Defined table behavior is checked without running an invalid original write. */
 for(int alpha=-256;alpha<=256;++alpha)for(int preset=0;preset<2;++preset) {
  memset(blendfx,0,sizeof(blendfx));blendfx_is_set=preset;obor_layer_blend(alpha);
  for(int i=0;i<MAX_BLENDINGS;++i)assert(blendfx[i]==(!preset && alpha>0 && alpha<=MAX_BLENDINGS && i==alpha-1));
 }
 owner_checks();
}
int main(void) {@CHECKS@ return 0;}
