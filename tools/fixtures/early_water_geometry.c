/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Own source geometry is compiled on the same host. The independent pixel
 * adapter accepts valid whole-image offsets and counts discarded events;
 * it never runs an original pixel access outside its object.
 */
@HELPERS@
int screenformat;
#include <math.h>
#define REFERENCE_BOUNDED_PIXELS 1
@REFERENCE@
@PROVIDERS@
@WATER_MATH@
@PLAIN_METHOD@
#include "sprite.h"
#include "screen.h"
static const int positions[][4]={
 {0,0,0,0},{1,1,0,0},{-1,-1,0,0},{4,5,0,0},
 {0,0,1,1},{1,0,-1,1},{-1,1,1,-1},{5,-1,0,0},{1,6,0,0}
};
static s_sprite *water_sprite(int format,int width,int height,int hole)
{
 s_sprite *frame=calloc(1,sizeof(*frame)+128);CHECK(frame);
 frame->width=width;frame->height=height;frame->pixelformat=format==PIXEL_8?PIXEL_8:PIXEL_x8;
 frame->palette=calloc(256,pixelbytes[format]);CHECK(frame->palette);
 for(unsigned i=0;i<256;i++){
  if(format==PIXEL_8)frame->palette[i]=i;
  else if(format==PIXEL_16)((unsigned short*)frame->palette)[i]=i;
  else ((unsigned*)frame->palette)[i]=i;
 }
 unsigned char *data=(unsigned char*)(frame->data+height);
 for(int y=0;y<height;y++){
  frame->data[y]=(int)(data-(unsigned char*)(frame->data+y));
  int clear=hole && !y?1:0;
  if(clear<width){*data++=(unsigned char)clear;*data++=(unsigned char)(width-clear);
   for(int x=clear;x<width;x++)*data++=(unsigned char)(x+y*width+1);}
  *data++=255;
 }
 return frame;
}
static void water_plain_expected(s_screen *dest,s_sprite *frame,int x,int y)
{
 for(int sy=0;sy<frame->height;sy++)for(int sx=0;sx<frame->width;sx++){
  unsigned colour=reference_values[sx+sy*frame->width];
  int dx=x-frame->centerx+sx,dy=y-frame->centery+sy;
  if(colour && dx>=0 && dx<dest->width && dy>=0 && dy<dest->height)
   put(dest,dx+dy*dest->width,colour);
 }
}
static void control_plane(int epoch,s_screen *dest,gfx_entry *entry,int x,int y,
                          int cx,int cy,s_drawmethod *method)
{
 switch(epoch) {
 case 0:reference_plane_0(dest,entry,x,y,cx,cy,method);break;
 case 1:reference_plane_1(dest,entry,x,y,cx,cy,method);break;
 case 2:reference_plane_2(dest,entry,x,y,cx,cy,method);break;
 case 3:reference_plane_3(dest,entry,x,y,cx,cy,method);break;
 case 4:reference_plane_4(dest,entry,x,y,cx,cy,method);break;
 case 5:reference_plane_5(dest,entry,x,y,cx,cy,method);break;
 case 6:reference_plane_6(dest,entry,x,y,cx,cy,method);break;
 default:CHECK(0);
 }
}
@SCREEN_PARENT@
static void water_geometry(int revision,int available,int epoch)
{
 int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
 int shapes[][2]={{2,2},{1,4},{4,1}};
 obor_profile_build=revision;
 CHECK(plainmethod.water.amplitude==0 && plainmethod.water.wavelength==0);
 CHECK(plainmethod.water.wavetime==0 && plainmethod.water.historical_wavespeed==0);
 CHECK(plainmethod.water.watermode==0);
 if(epoch>=4)CHECK(plainmethod.water.beginsize==0 && plainmethod.water.endsize==0 &&
                   plainmethod.water.wavespeed==0 && plainmethod.water.perspective==0);
 for(unsigned f=0;f<3;f++)for(int shape=0;shape<3;shape++)
 for(int type=0;type<3;type++)for(int hole=0;hole<2;hole++){
  int format=formats[f],sw=shapes[shape][0],sh=shapes[shape][1];screenformat=format;
  s_sprite *frame=water_sprite(format,sw,sh,hole);
  int canvas_width=shape==2?7:6;
  s_screen *actual=screen(format,canvas_width,6),*expected=screen(format,canvas_width,6);
  s_screen *source=screen(type==1?PIXEL_x8:format,sw,sh);gfx_entry entry={0};
  if(type==1){source->palette=calloc(256,pixelbytes[format]);CHECK(source->palette);
   for(unsigned i=0;i<256;i++){
    if(format==PIXEL_8)source->palette[i]=i;
    else if(format==PIXEL_16)((unsigned short*)source->palette)[i]=i;
    else ((unsigned*)source->palette)[i]=i;
   }
  }
  for(int i=0;i<4;i++){reference_values[i]=hole&&!i?0:(unsigned)(i+1);
   if(type==1)source->data[i]=(unsigned char)reference_values[i];else put(source,i,reference_values[i]);
  }
  if(type==2){entry.type=gfx_sprite;entry.sprite=frame;}
  else{entry.type=gfx_screen;entry.screen=source;}
  for(unsigned p=0;p<sizeof(positions)/sizeof(*positions);p++)
  for(int effect=0;effect<2;effect++)for(int parameter=0;parameter<3;parameter++)
  for(int mode=0;mode<8;mode++){
   s_drawmethod method={0},saved;method.flag=1;method.scalex=method.scaley=512;
   style(&method,format,mode);method.centerx=positions[p][2];method.centery=positions[p][3];
   method.water.wavetime=parameter-1;
   method.rotate=parameter?90:0;method.flipx=parameter%2;
   method.flipy=parameter==2;method.shiftx=parameter*64;
   method.water.watermode=effect?3:parameter%2+1;
   if(effect){
    if(epoch<4)method.water.wavelength=parameter==0?0.5f:parameter==1?1.0f:2.5f;
    else{method.water.beginsize=parameter==0?0.5f:1.25f;method.water.endsize=parameter==2?2.0f:0.75f;
     method.water.perspective=parameter;}
   }else{method.water.amplitude=parameter==0?0:parameter==1?2:-2;
    method.water.wavelength=parameter==0?2.5f:parameter==1?7.0f:-3.5f;}
   memcpy(&saved,&method,sizeof(method));background(actual);background(expected);
   if(effect)gfx_draw_plane(actual,&entry,positions[p][0],positions[p][1],1,1,&method);
   else gfx_draw_water(actual,&entry,positions[p][0],positions[p][1],1,1,&method);
   if(available){
    if(effect)control_plane(epoch,expected,&entry,positions[p][0],positions[p][1],1,1,&method);
    else reference_water(expected,&entry,positions[p][0],positions[p][1],1,1,&method);
   }
   compare(actual,expected,p,(unsigned)mode,type,hole);CHECK(!memcmp(&method,&saved,sizeof(method)));
   if(type!=2){
    /* Unlike the sprite route, the screen route does not reject zero scale. */
    for(int route=0;route<4;route++){
     s_drawmethod parent_method=method;
     if(route==1)parent_method.flag=0;
     if(route==3)parent_method.scalex=0;
     s_drawmethod *used=route==2?NULL:&parent_method;
     background(actual);background(expected);
     putscreen(actual,source,positions[p][0],positions[p][1],used);
     if(available && used && used->flag){
      if(effect)control_plane(epoch,expected,&entry,positions[p][0],positions[p][1],0,0,used);
      else reference_water(expected,&entry,positions[p][0],positions[p][1],0,0,used);
     }else screen_plain_expected(expected,source,positions[p][0],positions[p][1],used);
     compare(actual,expected,p,(unsigned)mode,type,route);
    }
   }
   if(type==2){
    /* Original fast and zero-scale checks precede water selection. */
    for(int route=0;route<3;route++){
     s_drawmethod parent_method=method;frame->centerx=frame->centery=1;
     if(route==1)parent_method.flag=0;
     if(route==2)parent_method.scalex=0;
     background(actual);background(expected);
     putsprite(positions[p][0],positions[p][1],frame,actual,&parent_method);
     if(route==1)water_plain_expected(expected,frame,positions[p][0],positions[p][1]);
     else if(route!=2){
      if(!available){
       if(parent_method.rotate)reference_rotate_0(expected,&entry,positions[p][0],positions[p][1],
        frame->centerx+parent_method.centerx,frame->centery+parent_method.centery,&parent_method);
       else reference_scale_0(expected,&entry,positions[p][0],positions[p][1],
        frame->centerx+parent_method.centerx,frame->centery+parent_method.centery,&parent_method);
      }
      else if(effect)control_plane(epoch,expected,&entry,positions[p][0],positions[p][1],1,1,&parent_method);
      else reference_water(expected,&entry,positions[p][0],positions[p][1],1,1,&parent_method);
     }
     compare(actual,expected,p,(unsigned)mode,type,route);
    }
    s_drawmethod fast={0};fast.flag=1;fast.scalex=fast.scaley=256;fast.water=method.water;
    background(actual);background(expected);putsprite(3,3,frame,actual,&fast);
    water_plain_expected(expected,frame,3,3);compare(actual,expected,p,99,type,hole);
   }
  }
  free(source->palette);free(source);free(frame->palette);free(frame);free(actual);free(expected);
 }
}
static void range_controls(int revision,int floating)
{
 s_screen *source=screen(PIXEL_8,2,2),*dest=screen(PIXEL_8,6,6);gfx_entry entry={0};
 entry.type=gfx_screen;entry.screen=source;obor_profile_build=revision;
 s_drawmethod method={0};method.water.watermode=1;
 for(int mode=0;mode<8;mode++){
  background(dest);method.centerx=method.centery=0;
  method.water.amplitude=1;method.water.wavelength=7;
  if(mode==0)method.water.wavelength=0;
  else if(mode==1)method.water.wavelength=NAN;
  else if(mode==2)method.centerx=INT_MAX;
  else if(mode==3)method.centerx=INT_MIN;
  else if(floating){method.water.beginsize=0;method.water.endsize=0;
   if(mode==5)method.water.beginsize=NAN;
   if(mode==6)method.water.endsize=INFINITY;
   if(mode==7)method.water.beginsize=-1;}
  else method.water.wavelength=mode==4?NAN:mode==5?INFINITY:mode==6?-1.0f:2147483648.0f;
  if(mode<4)gfx_draw_water(dest,&entry,0,0,mode==2?1:0,0,&method);
  else gfx_draw_plane(dest,&entry,0,0,0,0,&method);
  for(int i=0;i<36;i++)CHECK(get(dest,i)==17);
 }
 free(source);free(dest);
}
int main(void){providers();@SCREEN_CHECKS@@WATER_CHECKS@puts("inverse_transform_water=1");return 0;}
