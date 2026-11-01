/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#pragma pack(push,4)
struct BeforeGif {char tag;uint64_t value;};
#include "anigif.h"
struct AfterGif {char tag;uint64_t value;};
#pragma pack(pop)
uint32_t obor_profile_build;
int screenformat,pixelformat,pixelbytes[5]={1,1,2,3,4};
@COLORS@
@DATA@
typedef struct {const unsigned char *data;int size,width,height;} media;
static const media media_files[]={@MEDIA@};
typedef struct {int format,opened,code,delay,position,live,bitdepth,colours,transparent;
 const unsigned char *palette,*pixels;int palette_size,pixel_size;} expectation;
typedef struct {int media_index,noblacken,palette_present,x,y;expectation expected[7][4];} scenario;
static const scenario cases[]={@CASES@};
static struct {const media *file;int position,active;} files[4];
static const media *opening;
static int last_position;
int openpackfile(const char *name,const char *pack) {
 assert(name && !strcmp(name,"fixture") && pack && !strcmp(pack,"control"));
 assert(opening);
 for(int i=0;i<4;i++) if(!files[i].active) {
  files[i].file=opening;files[i].position=0;files[i].active=1;last_position=0;return i;
 }
 abort();
}
int readpackfile(int handle,void *destination,int length) {
 assert(handle>=0 && handle<4 && files[handle].active && length>=0);
 int available=files[handle].file->size-files[handle].position;
 if(length>available) length=available;
 memcpy(destination,files[handle].file->data+files[handle].position,(size_t)length);
 files[handle].position+=length;last_position=files[handle].position;return length;
}
int seekpackfile(int handle,int offset,int whence) {
 assert(handle>=0 && handle<4 && files[handle].active);
 int position=whence==SEEK_SET?offset:whence==SEEK_CUR?files[handle].position+offset:files[handle].file->size+offset;
 if(position<0) position=0;
 if(position>files[handle].file->size) position=files[handle].file->size;
 files[handle].position=last_position=position;return position;
}
int closepackfile(int handle) {
 if(handle==-1) return -1;
 assert(handle>=0 && handle<4 && files[handle].active);last_position=files[handle].position;files[handle].active=0;return 0;
}
#include @DECODER@
static int next_image(s_screen *screen,int *delay,int x,int y,unsigned char *palette,anigif_info *info) {
 int code,steps=0;
 do {assert(++steps<16384);code=anigif_decode_ex(screen,delay,x,y,palette,info);}while(code==ANIGIF_DECODE_RETRY);
 return code;
}
static void require_int(int got,int want,unsigned scenario_index,int format,const char *field) {
 if(got!=want) {fprintf(stderr,"GIF revision=%u case=%u format=%d %s got=%d want=%d\n",obor_profile_build,scenario_index,format,field,got,want);abort();}
}
static void require_bytes(const unsigned char *got,const unsigned char *want,int size,unsigned scenario_index,int format,const char *field) {
 for(int i=0;i<size;i++) if(got[i]!=want[i]) {
  fprintf(stderr,"GIF revision=%u case=%u format=%d %s byte=%d got=%u want=%u\n",obor_profile_build,scenario_index,format,field,i,got[i],want[i]);abort();
 }
}
static void check(unsigned revision,unsigned era) {
 obor_profile_build=revision;
 assert(sizeof(struct BeforeGif)==sizeof(struct AfterGif) && offsetof(struct AfterGif,value)==4);
 assert(sizeof(gifheaderstruct)==13 && sizeof(gifblockstruct)==9 && sizeof_gifheaderstruct==13 && sizeof_iblock==9);
 assert(offsetof(gifheaderstruct,screenwidth)==6 && offsetof(gifheaderstruct,flags)==10);
 assert(offsetof(gifblockstruct,width)==4 && offsetof(gifblockstruct,flags)==8);
 for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);n++) for(int mode=0;mode<4;mode++) {
  const scenario *c=&cases[n];const expectation *want=&c->expected[era][mode];opening=&media_files[c->media_index];
  screenformat=want->format==PIXEL_x8?PIXEL_8:want->format;pixelformat=want->format;
  size_t bytes=(size_t)opening->width*(size_t)opening->height*(size_t)pixelbytes[want->format];
  unsigned char *allocation=malloc(16+offsetof(s_screen,data)+bytes+16);assert(allocation);
  memset(allocation,0xa5,16+offsetof(s_screen,data)+bytes+16);
  s_screen *screen=(s_screen*)(allocation+16);screen->width=opening->width;screen->height=opening->height;screen->pixelformat=(char)want->format;screen->palette=NULL;
  _Alignas(4) unsigned char palette[1024];memset(palette,0xcc,sizeof(palette));
  anigif_info info={.handle=-1,.transparent=-1,.noblackenbg=c->noblacken};
  unsigned char *pal=c->palette_present?palette:NULL;int delay=77,code=-1;
  int opened=anigif_open_ex("fixture","control",pal,&info);
  if(opened) code=next_image(screen,&delay,c->x,c->y,pal,&info);
#define EXPECT(field,actual) require_int((actual),want->field,n,want->format,#field)
  EXPECT(opened,opened);EXPECT(code,code);EXPECT(delay,delay);EXPECT(position,last_position);
  EXPECT(live,info.handle>=0);EXPECT(bitdepth,info.bitdepth);EXPECT(colours,info.numcolours);EXPECT(transparent,info.transparent);
#undef EXPECT
  require_bytes(palette,want->palette,want->palette_size,n,want->format,"palette");
  assert(want->pixel_size==(int)bytes);require_bytes(screen->data,want->pixels,want->pixel_size,n,want->format,"pixels");
  for(int i=0;i<16;i++) assert(allocation[i]==0xa5 && screen->data[bytes+(size_t)i]==0xa5);
  anigif_close_ex(&info);assert(info.handle==-1);for(int i=0;i<4;i++) assert(!files[i].active);free(allocation);
 }
 /* Two opens through the old interface distinguish persistent old transparency
  * from the per-open context initialization of the later decoder. */
 screenformat=pixelformat=PIXEL_8;_Alignas(4) unsigned char palette[1024];
 size_t bytes=sizeof(s_screen)+4;s_screen *screen=calloc(1,bytes);assert(screen);
 screen->width=screen->height=2;screen->pixelformat=PIXEL_8;
 opening=&media_files[7];assert(anigif_open("fixture","control",palette));int delay=0,code,steps=0;
 do {assert(++steps<16384);code=anigif_decode(screen,&delay,0,0);}while(code==ANIGIF_DECODE_RETRY);
 assert(code==ANIGIF_DECODE_FRAME);anigif_close();
 memset(screen->data,0xa5,4);opening=&media_files[0];assert(anigif_open("fixture","control",palette));steps=0;
 do {assert(++steps<16384);code=anigif_decode(screen,&delay,0,0);}while(code==ANIGIF_DECODE_RETRY);
 assert(code==ANIGIF_DECODE_FRAME && screen->data[1]==(revision<3418?0xa5:1));anigif_close();free(screen);
 /* Independent contexts must retain different delays/transparency. */
 if(revision>=3418) {
  anigif_info a={.handle=-1,.transparent=-1},b={.handle=-1,.transparent=-1};
  _Alignas(4) unsigned char other_palette[1024];
  opening=&media_files[0];assert(anigif_open_ex("fixture","control",palette,&a));
  opening=&media_files[7];assert(anigif_open_ex("fixture","control",other_palette,&b));
  steps=0;
  while(b.transparent==-1) {
   assert(++steps<16384);
   /* The control extension precedes the first image. */
   s_screen *unused=calloc(1,sizeof(s_screen)+4);assert(unused);
   unused->width=unused->height=2;unused->pixelformat=PIXEL_8;
   assert(anigif_decode_ex(unused,&delay,0,0,other_palette,&b)==ANIGIF_DECODE_RETRY);free(unused);
  }
  assert(a.transparent==-1 && a.lastdelay==1 && b.transparent==1 && b.lastdelay==258);
  screen=calloc(1,sizeof(s_screen)+4);assert(screen);screen->width=screen->height=2;screen->pixelformat=PIXEL_8;
  assert(next_image(screen,&delay,0,0,palette,&a)==ANIGIF_DECODE_FRAME && delay==1 && screen->data[1]==1);
  memset(screen->data,0xa5,4);
  assert(next_image(screen,&delay,0,0,other_palette,&b)==ANIGIF_DECODE_FRAME && delay==258 && screen->data[1]==0xa5);
  anigif_close_ex(&a);anigif_close_ex(&b);free(screen);
 }
 /* A local table remains selected for the following image without a local
  * table, including when its destination differs from the global palette. */
 if(revision>=3477) {
  assert(cases[6].media_index==2);
  const media *first=&media_files[2],*second=&media_files[0];
  int global_end=13+768,length=first->size-1+second->size-global_end;
  unsigned char *wire=malloc((size_t)length);assert(wire);
  memcpy(wire,first->data,(size_t)first->size-1);
  memcpy(wire+first->size-1,second->data+global_end,(size_t)(second->size-global_end));
  media combined={wire,length,2,2};
  for(int mode=2;mode<4;mode++) {
   const expectation *want=&cases[6].expected[era][mode];
   screenformat=pixelformat=want->format;
   _Alignas(4) unsigned char global_palette[1024],local_palette[1024];
   anigif_info info={.handle=-1,.transparent=-1};opening=&combined;
   assert(anigif_open_ex("fixture","control",global_palette,&info));
   screen=calloc(1,sizeof(s_screen)+(size_t)want->pixel_size);assert(screen);
   screen->width=screen->height=2;screen->pixelformat=(char)want->format;
   assert(next_image(screen,&delay,0,0,local_palette,&info)==(ANIGIF_DECODE_FRAME|ANIGIF_DECODE_PAL));
   require_bytes(screen->data,want->pixels,want->pixel_size,6,want->format,"first local image");
   memset(screen->data,0xa5,(size_t)want->pixel_size);
   assert(next_image(screen,&delay,0,0,global_palette,&info)==ANIGIF_DECODE_FRAME);
   require_bytes(screen->data,want->pixels,want->pixel_size,6,want->format,"retained local palette");
   anigif_close_ex(&info);free(screen);
  }
  free(wire);
 }
 for(int i=0;i<4;i++) assert(!files[i].active);
}
int main(void) {
 assert(!anigif_open_ex("fixture","control",NULL,NULL));
 assert(anigif_decode_ex(NULL,NULL,0,0,NULL,NULL)==ANIGIF_DECODE_END);
 anigif_close_ex(NULL);
 @CHECKS@
 puts("early_gif_decoder=1");return 0;
}
