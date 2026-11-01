/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Actual model handlers and command cases; source-owned native controls
 * retain narrow-field assignment and floating arithmetic on the same host.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <setjmp.h>
#include <stdarg.h>
#include "openbor.h"
#include "commands.h"
#undef printf
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Model command revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static int blendfx[MAX_BLENDINGS];
static char diagnostic[256];
static jmp_buf stop;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
static int unexpected_warning(const char *format,...){(void)format;abort();}
void shutdown(int status,char *format,...){
 va_list args;va_start(args,format);vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);assert(status==1);longjmp(stop,1);
}
static int parsecolor(const char *value){assert(!strcmp(value,"0"));return 0;}
@MACROS@
#define printf unexpected_warning
@PARSERS@
#undef printf
@HANDLERS@
@ORIGINALS@
static s_drawmethod actual_draw(ArgList arglist,int blendfx_is_set){
 s_drawmethod drawmethod={0};char *filename="fixture.txt",*command="drawmethod";
 switch(CMD_MODEL_DRAWMETHOD){@DRAW_CASE@default:abort();}return drawmethod;
}
static void actual_map(ArgList arglist,s_model *newchar,s_attack *out,int newanim){
 s_attack attack=*out,*pattack;char *filename="fixture.txt",*command="forcemap";
 switch(CMD_MODEL_FORCEMAP){@MAP_CASE@default:abort();}*out=attack;
}
static ArgList arguments(const char *text,char *input,char *output){
 ArgList list;assert(strlen(text)<=MAX_ARG_LEN);strcpy(input,text);ParseArgs(&list,input,output);return list;
}
#define SAME(field) assert(actual.field==expected.field)
static void check(int revision,int obstacle,int notargetidle,int rotation,int fractional){
 obor_profile_build=revision;
 const char *types[]={"obstacle","enemy","none"};
 int moves[]={-1,0,AIMOVE1_CHASE},attacks[]={-1,0,AIATTACK1_NORMAL};
 for(unsigned t=0;t<3;t++)for(unsigned m=0;m<3;m++)for(unsigned a=0;a<3;a++){
  s_model model={0};char input[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1],line[64];
  model.aimove=moves[m];model.aiattack=attacks[a];snprintf(line,sizeof(line),"type %s",types[t]);ArgList list=arguments(line,input,output);
  lcmHandleCommandType(&list,&model,"fixture.txt");
  int expected=moves[m];if(!t && obstacle){if(expected==-1)expected=0;expected|=AIMOVE1_NOMOVE;expected|=AIATTACK1_NOATTACK;}
  assert(model.aimove==(unsigned)expected && model.aiattack==(unsigned)attacks[a]);
  assert(model.type==(t==0?TYPE_OBSTACLE:t==1?TYPE_ENEMY:TYPE_NONE));
 }
 const char *switches[]={"notargetidle","NoTaRgEtIdLe","ignoreholes",""};
 for(unsigned k=0;k<4;k++)for(int prior=0;prior<2;prior++){
  s_model model={0};model.aimove=AIMOVE1_CHASE;int set=prior;
  char input[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1],line[96];snprintf(line,sizeof(line),"aimove normal %s",switches[k]);ArgList list=arguments(line,input,output);
  int rejected=k<2 && !notargetidle;diagnostic[0]=0;
  if(!setjmp(stop)){lcmHandleCommandAimove(&list,&model,&set,"fixture.txt");assert(!rejected);}else assert(rejected);
  int expected=prior?AIMOVE1_CHASE:0;expected|=AIMOVE1_NORMAL;
  if(k<2 && notargetidle)expected|=AIMOVE2_NOTARGETIDLE;
  if(k==2)expected|=AIMOVE2_IGNOREHOLES;
  assert(model.aimove==(unsigned)expected && set==1);
  if(rejected){char want[256];snprintf(want,sizeof(want),"Model 'fixture.txt' has invalid A.I. move switch: '%s'",switches[k]);assert(!strcmp(diagnostic,want));}
 }
 const int angles[]={-1024,-1023,-721,-450,-360,-1,0,1,359,360,450,721,1023,1024,2047,2048,4097};
 const int flips[]={-721,-360,-1,0,1,360,721};
 for(unsigned a=0;a<sizeof(angles)/sizeof(*angles);a++)for(unsigned f=0;f<sizeof(flips)/sizeof(*flips);f++)
 for(int mark=0;mark<2;mark++){
  char input[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1],line[128];
  snprintf(line,sizeof(line),"drawmethod -256 512 0 1 7 3 2 0 %d %d",angles[a],flips[f]);ArgList list=arguments(line,input,output);
  memset(blendfx,0,sizeof(blendfx));s_drawmethod actual=actual_draw(list,mark);int marks[MAX_BLENDINGS];memcpy(marks,blendfx,sizeof(marks));
  memset(blendfx,0,sizeof(blendfx));reference_drawmethod expected=rotation?reference_draw_1(list,mark):reference_draw_0(list,mark);
  SAME(scalex);SAME(scaley);SAME(shiftx);SAME(alpha);SAME(remap);SAME(fillcolor);SAME(rotate);SAME(fliprotate);
  /* Published safety uses unsigned boolean fields; compare their drawing truth. */
  assert(!!actual.flag==!!expected.flag && !!actual.flipx==!!expected.flipx && !!actual.flipy==!!expected.flipy);
  assert(!memcmp(marks,blendfx,sizeof(marks)));
 }
 const char *durations[]={"0","0.25","-0.25","1.5","3","9999999"};
 for(unsigned d=0;d<sizeof(durations)/sizeof(*durations);d++)for(int has_smart=0;has_smart<2;has_smart++)for(int animation=0;animation<2;animation++){
  char input[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1],line[128];snprintf(line,sizeof(line),"forcemap 2 %s",durations[d]);ArgList list=arguments(line,input,output);
  s_attack actual={0},expected={0},smart_actual={0},smart_expected={0};s_model amodel={0},emodel={0};
  actual.maptime=expected.maptime=13;smart_actual.maptime=smart_expected.maptime=17;
  amodel.smartbomb=has_smart?&smart_actual:NULL;emodel.smartbomb=has_smart?&smart_expected:NULL;
  actual_map(list,&amodel,&actual,animation);
  if(fractional)reference_map_1(list,&emodel,&expected,animation);else reference_map_0(list,&emodel,&expected,animation);
  SAME(forcemap);SAME(maptime);assert(smart_actual.forcemap==smart_expected.forcemap && smart_actual.maptime==smart_expected.maptime);
 }
}
#undef SAME
int main(void){@CHECKS@return 0;}
