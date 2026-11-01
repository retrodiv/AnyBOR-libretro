/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Trace the actual background caller with bounded drawing services. Source
 * epochs are supplied by the fixture; expected events do not call that body.
 */
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "texture.h"
#undef printf
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Background revision=%u case=%u sequence=%d line=%d\n",obor_profile_build,test_case,sequence,__LINE__);abort();}}while(0)
#undef time
#define time background_time
uint32_t obor_profile_build;
static unsigned test_case;
static int sequence;
static s_level room,*level=&room;
static s_screen screens[3],*vscreen=&screens[0],*background=&screens[2],*bgbuffer;
static s_bitmap bitmap,*texture;
static s_panel panels[MAX_PANELS];
static s_sprite *frontpanels[MAX_PANELS];
static unsigned panels_loaded,frontpanels_loaded,neon_time;
static unsigned char neontable[MAX_PAL_SIZE],palette[MAX_PAL_SIZE];
static int panel_width,holesprite,smartbomber;
static entity *textbox;
static s_videomodes videomodes;
static u32 time;
static int current_palette,pause,bgbuffer_updated;
static float advancex,advancey;
static int gfx_x_offset,gfx_y_offset,gfx_y_offset_adj,BGHEIGHT=16;
int pixelformat=PIXEL_8,screenformat=PIXEL_8,PLAYER_MIN_Z=0,PLAYER_MAX_Z=232;
int pixelbytes[]={1,1,2,3,4};
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@PLAIN@
struct event {int kind,target,phase;};
static struct event observed[16],expected[16];
static unsigned used,wanted;
static int target(s_screen *s){assert(s==vscreen || s==&screens[1]);return s==vscreen?0:1;}
static void record(int kind,s_screen *s,int phase){assert(used<16);observed[used++]=(struct event){kind,target(s),phase};}
static void expect(int kind,int s,int phase){assert(wanted<16);expected[wanted++]=(struct event){kind,s,phase};}
void clearscreen(s_screen *s){record(1,s,0);}
void applybglayers(s_screen *s){record(2,s,0);}
void applyfglayers(s_screen *s){record(3,s,0);}
void putscreen(s_screen *d,s_screen *s,int x,int y,s_drawmethod *m){assert(d==vscreen && s==bgbuffer && !x && !y && !m);record(6,d,0);}
void apply_texture_wave(s_screen *s,int x,int y,int width,int height,int ox,int oy,s_bitmap *b,int phase,int step,s_drawmethod *m){
 assert(!x && y==2 && width==8 && height==14 && ox==(int)(advancex/2) && !oy && b==texture && step==5 && m->flag==plainmethod.flag);record(5,s,phase);
}
void apply_texture_plane(s_screen *s,int x,int y,int width,int height,int offset,int factor,s_bitmap *b,s_drawmethod *m){
 assert(!x && y==2 && width==8 && height==14 && factor==10 && b==texture && m->flag==plainmethod.flag);record(4,s,offset);
}
void spriteq_add_frame(int x,int y,int z,s_sprite *s,s_drawmethod *m,int sort){(void)x;(void)y;(void)z;(void)s;(void)m;(void)sort;abort();}
void spriteq_add_sprite(int x,int y,int z,int sprite,s_drawmethod *m,int sort){(void)x;(void)y;(void)z;(void)sprite;(void)m;(void)sort;abort();}
@FUNCTION@
struct input {int buffer,cached,paused,rocking,speed,texture,flat,nested,amplitude,count;};
static const struct input inputs[]={@INPUTS@};
static void check(int revision,int epoch)
{
 obor_profile_build=revision;
 for(test_case=0;test_case<sizeof(inputs)/sizeof(*inputs);test_case++){
  const struct input *in=inputs+test_case;
  memset(level,0,sizeof(*level));memset(screens,0,sizeof(screens));
  screens[0].width=8;screens[0].height=8;background->height=2;
  videomodes.hRes=8;videomodes.vRes=8;level->scrolldir=SCROLL_UP;
  memcpy(level->palettes[0],palette,sizeof(level->palettes[0]));level->numpalettes=1;
  bgbuffer=&screens[1];texture=NULL;pause=0;bgbuffer_updated=0;
  advancex=3.5f;advancey=4.25f;current_palette=1;time=0;used=0;
  /* Prime only the cache history; service traces are discarded. */
  draw_scrolled_bg();
  used=0;bgbuffer=in->buffer?&screens[1]:NULL;bgbuffer_updated=in->cached;
  texture=in->texture?&bitmap:NULL;pause=in->paused;
  level->rocking=in->rocking;level->bgspeed=in->speed;level->numbglayers=in->count;
  level->bglayers[0].watermode=in->flat;
  level->bglayers[0].amplitude=in->amplitude;
  level->bglayers[0].drawmethod.water.watermode=in->nested;
  float oldx=3.5f,oldy=4.25f;int oldpal=1,cache=in->cached;
  for(sequence=0;sequence<3;sequence++){
   if(sequence==1)advancex=4.5f;
   if(sequence==2)current_palette=0;
   time=30+(unsigned)sequence;wanted=used=0;
   int where=0;
   if(epoch==2){
    expect(1,0,0);if(in->count)expect(2,0,0);
   }else{
    if(in->buffer){
     int animated=in->rocking || (epoch>=4?in->speed!=0:in->speed>0) || (epoch<4 && in->texture);
     if((animated && !in->paused) || oldx!=advancex || oldy!=advancey || oldpal!=current_palette)cache=0;
     else if(epoch>=1 && in->count && (epoch>=5?in->nested:in->flat) && (epoch>=4 || in->amplitude))cache=0;
     oldx=advancex;oldy=advancey;oldpal=current_palette;
    }else cache=0;
    where=in->buffer && !cache?1:0;
    if(!cache && in->count){if(epoch>=3)expect(1,where,0);expect(2,where,0);}
   }
   expect(3,where,0);
   if(epoch<4 && in->texture){
    int phase=in->rocking?((int)(advancex/2)+(int)(time/(GAME_SPEED/30)))*256:(int)time;
    expect(in->rocking?4:5,where,phase);
   }
   if(epoch!=2){if(in->buffer)expect(6,0,0);cache=1;}
   draw_scrolled_bg();
   assert(used==wanted);
   for(unsigned i=0;i<used;i++){
    assert(observed[i].kind==expected[i].kind);
    assert(observed[i].target==expected[i].target);
    assert(observed[i].phase==expected[i].phase);
   }
   assert(bgbuffer_updated==cache);
  }
 }
}
int main(void){@CHECKS@return 0;}
