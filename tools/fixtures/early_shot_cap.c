/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Filename-search and final-call controls; no filesystem or encoder runs.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "types.h"
#define CHECK(c) do{if(!(c)){fprintf(stderr,"Screenshot cap revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static unsigned collisions,attempts,encoded,messages;
static char last_path[1024],debug_text[1200];
static s_screen *image;
static unsigned char palette[768];
static void getPakName(char *out,size_t capacity,int kind){CHECK(capacity>=8 && kind==99);strcpy(out,"fixture");}
static int fileExists(char *name){
 char expected[1024];snprintf(expected,sizeof(expected),"./ScreenShots/fixture - %04u.png",attempts);
 CHECK(!strcmp(name,expected));strcpy(last_path,name);++attempts;return attempts<=collisions;
}
static void savepng(const char *name,s_screen *screen,unsigned char *pal){
 CHECK(!strcmp(name,last_path) && screen==image && pal==palette);++encoded;
}
static void debug_printf(char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(debug_text,sizeof(debug_text),format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(debug_text));++messages;
}
@SCREENSHOT@
static const unsigned counts[]={@COLLISIONS@};
static void check(int revision,unsigned limit){
 obor_profile_build=revision;
 for(unsigned i=0;i<sizeof(counts)/sizeof(*counts);i++)for(int ingame=0;ingame<2;ingame++){
  collisions=counts[i];attempts=encoded=messages=0;last_path[0]=debug_text[0]=0;
  screenshot(image,palette,ingame);
  unsigned expected=collisions<limit?collisions+1:limit;
  CHECK(attempts==expected);CHECK(encoded==(expected<10000));CHECK(messages==(unsigned)ingame);
  if(ingame){char text[1200];snprintf(text,sizeof(text),"Saved %s",last_path);CHECK(!strcmp(text,debug_text));}
 }
}
int main(void){
 image=calloc(1,sizeof(*image)+4);CHECK(image);image->width=image->height=2;image->pixelformat=PIXEL_8;
 @CHECKS@
 free(image);return 0;
}
