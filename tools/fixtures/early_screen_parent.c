/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Screen parent contract: ordinary copy ignores transform-only parameters;
 * an enabled water method precedes the equal-size fast copy. The expected
 * normal pixels use bounded coordinates, not the candidate copy services.
 */
static void screen_plain_expected(s_screen *dest,s_screen *src,int x,int y,
                                  const s_drawmethod *method)
{
 int enabled=method && method->flag;
 int table=enabled && method->table,alpha=enabled?method->alpha:0;
 int key=enabled?method->transbg:0;
 int format=dest->pixelformat,indexed=src->pixelformat==PIXEL_x8;
 if(format==PIXEL_8 && indexed && !table && alpha<=0 && !key)return;
 int fast=!table && alpha<=0 && !key && src->pixelformat==format &&
          src->width==dest->width && src->height==dest->height;
 for(int sy=0;sy<src->height;sy++)for(int sx=0;sx<src->width;sx++){
  int dx=fast?sx:x+sx,dy=fast?sy:y+sy;
  if(dx<0 || dx>=dest->width || dy<0 || dy>=dest->height)continue;
  unsigned value=indexed?src->data[sx+sy*src->width]:get(src,sx+sy*src->width);
  if(!fast){
   if((format==PIXEL_8?(table || alpha>0 || key):key) && !value)continue;
   if(table && (format==PIXEL_8 || indexed))value=value*5+3;
   if(alpha>0 && !(format==PIXEL_8 && table))value+=3*get(dest,dx+dy*dest->width)+17*alpha;
  }
  if(format==PIXEL_8)value&=255;
  else if(format==PIXEL_16)value&=65535;
  put(dest,dx+dy*dest->width,value);
 }
}
static void screen_parent_normal(int revision,int water_available)
{
 int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
 obor_profile_build=revision;
 for(unsigned f=0;f<3;f++)for(int indexed=0;indexed<2;indexed++)
 for(int equal=0;equal<2;equal++)for(int hole=0;hole<2;hole++){
  int format=formats[f],canvas=equal?2:6;
  s_screen *src=screen(indexed?PIXEL_x8:format,2,2);
  s_screen *actual=screen(format,canvas,canvas),*expected=screen(format,canvas,canvas);
  if(indexed){src->palette=calloc(256,pixelbytes[format]);CHECK(src->palette);
   for(unsigned i=0;i<256;i++){
    if(format==PIXEL_8)src->palette[i]=i;
    else if(format==PIXEL_16)((unsigned short*)src->palette)[i]=i;
    else ((unsigned*)src->palette)[i]=i;
   }
  }
  for(int i=0;i<4;i++){
   unsigned value=hole && !i?0:(unsigned)(i+1);reference_values[i]=value;
   if(indexed)src->data[i]=(unsigned char)value;else put(src,i,value);
  }
  for(unsigned p=0;p<sizeof(positions)/sizeof(*positions);p++)
  for(int mode=0;mode<8;mode++)for(int route=0;route<4;route++){
   s_drawmethod method={0},saved;method.flag=1;style(&method,format,mode);
   /* These fields do not select scale/rotate in the original screen parent. */
   method.rotate=90;method.flipx=method.flipy=1;method.shiftx=64;
   method.scalex=route%2?0:512;method.scaley=384;method.centerx=method.centery=1;
   if(route==1)method.flag=0;
   if(route>=1)method.water.watermode=3;
   const s_drawmethod *used=route==2?NULL:&method;
   if(route==3){method.water.watermode=1;method.water.amplitude=1;method.water.wavelength=7;}
   memcpy(&saved,&method,sizeof(method));background(actual);background(expected);
   putscreen(actual,src,positions[p][0],positions[p][1],(s_drawmethod*)used);
   if(route==3 && water_available){
    gfx_entry entry={0};entry.type=gfx_screen;entry.screen=src;
    reference_water(expected,&entry,positions[p][0],positions[p][1],0,0,&method);
   }else screen_plain_expected(expected,src,positions[p][0],positions[p][1],used);
   compare(actual,expected,p,mode,indexed,route);CHECK(!memcmp(&saved,&method,sizeof(method)));
  }
  free(src->palette);free(src);free(actual);free(expected);
 }
}
