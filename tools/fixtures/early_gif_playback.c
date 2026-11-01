/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <setjmp.h>
#include "types.h"
#include "screen.h"
#include "anigif.h"
uint32_t obor_profile_build;
int pixelformat,screenformat,pixelbytes[5]={1,1,2,3,4};
@COLORS@
@DATA@
typedef struct {const unsigned char *bytes;int size;} media;
static const media media_files[]={@MEDIA@};
typedef struct {
 int hardware,pixelformat,status,stop,updates,vwait,standard,palette_calls;
 const unsigned char *palette_prefix;int prefix_size,sound_calls,queue_calls;
 int alloc_formats[4],alloc_count,allocated,freed,open_roles[8],open_count;
 unsigned pictures[3][8],time,newtime;
} expectation;
typedef struct {
 const char *name,*filename,*names[4];
 int direct,present_channels,main_present,bad_main,bad_channel,alloc_fail;
 int variant,noskip,key_frame,sticky_key,audio,x,y;
 expectation expected[8][3];
} scenario;
static const scenario cases[]={@CASES@};
static const scenario *current;
static unsigned case_index;
static const expectation *want;
static struct {
 int stop,updates,vwait,standard,palette_calls,sound_calls,queue_calls;
 int alloc_formats[4],alloc_count,allocated,freed,open_roles[8],open_count;
 unsigned pictures[3][8];unsigned char palette_prefix[8];
} got;
static struct {s_screen *pointer;int active;} allocations[4];
static struct {const media *file;int active,position;} files[4];
static s_screen original_background,*background,*queued;
static struct {int hRes,vRes;} videomodes={4,2};
static struct {int gamma,brightness;} savedata;
static char packfile[]="control";
static unsigned time,newtime,bothnewkeys;
static unsigned char pal[1024];
enum {GAME_SPEED=200,FLAG_ESC=1,FLAG_ANYBUTTON=2};
static jmp_buf stopped;
static char stop_message[256];
static int palette_find(const unsigned char *colors,int r,int g,int b) {
 (void)colors;(void)r;(void)g;(void)b;abort();
}
@MAKECOLOR@
int openpackfile(const char *name,const char *pack) {
 assert(name && !strcmp(pack,"control"));
 int role=-1;
 for(int i=0;i<4;i++) if(current->names[i] && !strcmp(name,current->names[i])) {role=i;break;}
 if(role<0 || got.open_count>=8) fprintf(stderr,"GIF path revision=%u case=%u(%s) hardware=%d name=%s calls=%d\n",obor_profile_build,case_index,current->name,screenformat,name,got.open_count);
 assert(role>=0 && got.open_count<8);got.open_roles[got.open_count++]=role;
 if(!role && !current->main_present) return -1;
 if(role && !(current->present_channels&(1<<(role-1)))) return -1;
 int index=role;
 if(!role) index=current->variant==1?4:current->variant==3?8:0;
 else if(current->variant==2) index=role+4;
 if((!role && current->bad_main) || (role && current->bad_channel==role-1)) index=9;
 for(int i=0;i<4;i++) if(!files[i].active) {
  files[i].file=&media_files[index];files[i].position=0;files[i].active=1;return i;
 }
 abort();
}
int readpackfile(int handle,void *destination,int length) {
 assert(handle>=0 && handle<4 && files[handle].active && length>=0);
 int available=files[handle].file->size-files[handle].position;
 if(length>available) length=available;
 memcpy(destination,files[handle].file->bytes+files[handle].position,(size_t)length);
 files[handle].position+=length;return length;
}
int seekpackfile(int handle,int offset,int whence) {
 assert(handle>=0 && handle<4 && files[handle].active);
 int position=whence==SEEK_SET?offset:whence==SEEK_CUR?files[handle].position+offset:files[handle].file->size+offset;
 if(position<0) position=0;
 if(position>files[handle].file->size) position=files[handle].file->size;
 files[handle].position=position;return position;
}
int closepackfile(int handle) {
 if(handle==-1) return -1;
 assert(handle>=0 && handle<4 && files[handle].active);files[handle].active=0;return 0;
}
static void *probe_allocate(size_t size) {
 if(current->alloc_fail==got.alloc_count) return NULL;
 void *pointer=malloc(size);assert(pointer);
 for(int i=0;i<4;i++) if(!allocations[i].active) {
  allocations[i].pointer=pointer;allocations[i].active=1;got.allocated++;return pointer;
 }
 abort();
}
static void probe_release(void *pointer) {
 assert(pointer!=queued);
 for(int i=0;i<4;i++) if(allocations[i].active && allocations[i].pointer==pointer) {
  allocations[i].active=0;got.freed++;free(pointer);return;
 }
 abort();
}
static char asBuf[13];
static unsigned short asCnt;
#define malloc probe_allocate
#define free probe_release
@ALLOCATORS@
#undef malloc
#undef free
s_screen *allocscreen(int width,int height,int format) {
 assert(got.alloc_count<4);got.alloc_formats[got.alloc_count++]=format;
 return native_allocscreen(width,height,format);
}
static void standard_palette(int immediate) {assert(immediate==1);got.standard++;memset(pal,0,sizeof(pal));}
static void palette_set_corrected(unsigned char *colors,int r,int g,int b,int x,int y,int z) {
 assert(!r && !g && !b && !x && !y && !z);got.palette_calls++;
 assert(want->prefix_size<=8);memcpy(got.palette_prefix,colors,(size_t)want->prefix_size);
 if(!screenformat) memcpy(pal,colors,768);
}
static void vga_vwait(void) {got.vwait++;}
static void spriteq_add_screen(int x,int y,int z,s_screen *screen,void *method,int flags) {
 assert(!x && !y && !z && !method && !flags && !queued && screen);
 queued=screen;got.queue_calls++;
}
static unsigned sound_getinterval(void) {
 got.sound_calls++;
 return current->audio==1 || (current->audio==2 && got.sound_calls>=2) ? UINT32_MAX : 10;
}
static void update(int first,int subsequent) {
 assert(!first && subsequent==(got.updates>0) && got.updates<3);
 s_screen *screen=queued?queued:background;assert(screen && screen!=&original_background && screen->width==4 && screen->height==2);
 for(int i=0;i<8;i++) {
  unsigned value=0;
  if(screen->pixelformat==PIXEL_8) {unsigned index=screen->data[i];value=colour32(pal[index*3],pal[index*3+1],pal[index*3+2]);}
  else if(screen->pixelformat==PIXEL_x8) {
   assert(screen->palette);unsigned index=screen->data[i];
   if(screenformat==PIXEL_16) {unsigned short packed;memcpy(&packed,screen->palette+index*2,2);value=packed;}
   else memcpy(&value,screen->palette+index*4,4);
  } else if(screen->pixelformat==PIXEL_16) {unsigned short packed;memcpy(&packed,screen->data+i*2,2);value=packed;}
  else {assert(screen->pixelformat==PIXEL_32);memcpy(&value,screen->data+i*4,4);}
  got.pictures[got.updates][i]=value;
 }
 queued=NULL;got.updates++;time+=2;newtime+=7;
 if(current->key_frame==got.updates) bothnewkeys=FLAG_ESC;
 else if(!current->sticky_key) bothnewkeys=0;
}
static _Noreturn void shutdown(int status,const char *format,...) {
 assert(status==1);got.stop++;va_list ap;va_start(ap,format);int n=vsnprintf(stop_message,sizeof(stop_message),format,ap);va_end(ap);
 assert(n>=0 && n<(int)sizeof(stop_message));longjmp(stopped,1);
}
#include @DECODER@
@CALLERS@
static void require_int(int actual,int expected,const char *field) {
 if(actual!=expected) {fprintf(stderr,"GIF playback revision=%u case=%u(%s) hardware=%d %s got=%d want=%d\n",obor_profile_build,case_index,current->name,screenformat,field,actual,expected);abort();}
}
static int invoke(void) {
 if(setjmp(stopped)) return -2;
 return playgif((char*)current->filename,current->x,current->y,current->noskip);
}
static void check(unsigned revision,unsigned era) {
 obor_profile_build=revision;
 for(case_index=0;case_index<sizeof(cases)/sizeof(cases[0]);case_index++) for(int mode=0;mode<3;mode++) {
  current=&cases[case_index];want=&current->expected[era][mode];memset(&got,0,sizeof(got));
  background=&original_background;queued=NULL;time=1000;newtime=2000;bothnewkeys=0;stop_message[0]=0;
  pixelformat=want->pixelformat;screenformat=want->hardware;
  int status=invoke();
  require_int(status,want->status,"status");
#define EXPECT(field) require_int(got.field,want->field,#field)
  EXPECT(stop);EXPECT(updates);EXPECT(vwait);EXPECT(standard);EXPECT(palette_calls);EXPECT(sound_calls);EXPECT(queue_calls);
  EXPECT(alloc_count);EXPECT(allocated);EXPECT(freed);EXPECT(open_count);
#undef EXPECT
  for(int i=0;i<want->alloc_count;i++) require_int(got.alloc_formats[i],want->alloc_formats[i],"allocation format");
  for(int i=0;i<want->open_count;i++) require_int(got.open_roles[i],want->open_roles[i],"open role/order");
  for(int i=0;i<want->updates;i++) for(int j=0;j<8;j++) require_int((int)got.pictures[i][j],(int)want->pictures[i][j],"visible picture");
  assert(!memcmp(got.palette_prefix,want->palette_prefix,(size_t)want->prefix_size));
  if(want->stop) assert(!strcmp(stop_message,"Out of memory! Function Call 'ShowComplete'"));
  assert(background==(want->stop?NULL:&original_background) && !queued && time==want->time && newtime==want->newtime);
  for(int i=0;i<4;i++) assert(!allocations[i].active && !files[i].active);
 }
}
int main(void) {@CHECKS@puts("early_gif_playback=1");return 0;}
