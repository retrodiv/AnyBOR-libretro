/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <unistd.h>
#include <png.h>
#include "types.h"
uint32_t obor_profile_build;
static unsigned scenario,collisions,attempts,debug_calls;
static char basename[100],last_path[1024],debug_text[1200];
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Screenshot revision=%u scenario=%u line=%d: %s\n",obor_profile_build,scenario,__LINE__,#c);abort();}}while(0)
void savepng(const char *,s_screen *,unsigned char *);
static void getPakName(char *name,size_t capacity,int type) {
 CHECK(type==99 && strlen(basename)<capacity);strcpy(name,basename);
}
static int fileExists(char *name) {
 CHECK(strlen(name)<sizeof(last_path));strcpy(last_path,name);
 ++attempts;return attempts<=collisions;
}
static void debug_printf(char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(debug_text,sizeof(debug_text),format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(debug_text));++debug_calls;
}
@SCREENSHOT@
static unsigned char sample(unsigned x,unsigned y,unsigned plane,int pattern) {
 if(!pattern && x%143<66)return 193;
 return (unsigned char)(x*17+y*29+plane*61);
}
static void shot(int format,int width,int pattern,unsigned collision,int ingame) {
 const int height=2;size_t size=(size_t)width*height;
 s_screen *screen=calloc(1,sizeof(*screen)+size*4);CHECK(screen);
 screen->width=width;screen->height=height;screen->pixelformat=(char)format;
 unsigned char palette[768];
 for(unsigned i=0;i<sizeof(palette);++i)palette[i]=(unsigned char)(i*17+3);
 for(int y=0;y<height;++y)for(int x=0;x<width;++x) {
  size_t pos=(size_t)y*width+x;
  if(format==PIXEL_16) {
   uint16_t color=(uint16_t)(x*13+y*17);memcpy(screen->data+pos*2,&color,2);
  }else if(format==PIXEL_32) {
   for(unsigned p=0;p<4;++p)screen->data[pos*4+p]=sample((unsigned)x,(unsigned)y,p,pattern);
  }else screen->data[pos]=sample((unsigned)x,(unsigned)y,0,pattern);
 }
 snprintf(basename,sizeof(basename),"case-%u-%u",obor_profile_build,scenario);
 attempts=debug_calls=0;debug_text[0]=last_path[0]=0;collisions=collision;
 screenshot(screen,palette,ingame);free(screen);
 CHECK(attempts==(collision<100?collision+1:100));
 CHECK(debug_calls==(unsigned)ingame);
 if(ingame) {
  char expected[1200];snprintf(expected,sizeof(expected),"Saved %s",last_path);
  CHECK(!strcmp(expected,debug_text));
 }
 FILE *file=fopen(last_path,"rb");int exists=file!=NULL;
 if(file)CHECK(!fclose(file));
 if(exists && strstr(last_path,".png")) {
  png_image image;memset(&image,0,sizeof(image));image.version=PNG_IMAGE_VERSION;
  CHECK(png_image_begin_read_from_file(&image,last_path));image.format=PNG_FORMAT_RGB;
  CHECK(image.width==(unsigned)width && image.height==(unsigned)height);
  size_t bytes=PNG_IMAGE_SIZE(image);unsigned char *rgb=malloc(bytes);CHECK(rgb);
  CHECK(png_image_finish_read(&image,NULL,rgb,0,NULL));png_image_free(&image);
  char path[1100];snprintf(path,sizeof(path),"%s.rgb",last_path);
  file=fopen(path,"wb");CHECK(file && fwrite(rgb,1,bytes,file)==bytes && !fclose(file));free(rgb);
 }
 printf("SHOT %u %u %d %d %d %u %d %d %s\n",obor_profile_build,scenario,format,width,pattern,collision,ingame,exists,last_path);
 ++scenario;
}
static void bounds(void) {
 s_screen *screen=calloc(1,sizeof(*screen)+4);CHECK(screen);
 screen->pixelformat=PIXEL_8;
 unsigned char palette[768]={0};
 savepng("invalid.pcx",NULL,palette);CHECK(access("invalid.pcx",F_OK)!=0);
 const int dimensions[4][2]={{0,1},{-1,1},{1,0},{1,-1}};
 for(unsigned i=0;i<4;++i) {
  screen->width=dimensions[i][0];screen->height=dimensions[i][1];
  savepng("invalid.pcx",screen,palette);CHECK(access("invalid.pcx",F_OK)!=0);
 }
 screen->width=screen->height=1;
 savepng("invalid.pcx",screen,NULL);CHECK(access("invalid.pcx",F_OK)!=0);
 free(screen);printf("BOUNDS %u 6\n",obor_profile_build);
}
static const struct {unsigned revision;int legacy;} revisions[]={@REVISIONS@};
int main(void) {
 CHECK(!mkdir("ScreenShots",0700));
 const int widths[]={1,2,3,63,64,65,4097};
 const int formats[]={PIXEL_8,PIXEL_x8,PIXEL_16,PIXEL_32};
 for(unsigned r=0;r<sizeof(revisions)/sizeof(revisions[0]);++r) {
  obor_profile_build=revisions[r].revision;scenario=0;
  for(unsigned f=0;f<sizeof(formats)/sizeof(formats[0]);++f)
  for(unsigned w=0;w<sizeof(widths)/sizeof(widths[0]);++w)
   shot(formats[f],widths[w],w==6,0,1);
  shot(PIXEL_32,3,0,3,0);shot(PIXEL_32,3,0,100,1);
  if(revisions[r].legacy)bounds();
 }
 return 0;
}
