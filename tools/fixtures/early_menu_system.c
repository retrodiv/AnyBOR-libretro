/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Actual system callbacks and selected menu lifecycle source windows.
 */
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"menu-system line=%d revision=%u\n",__LINE__,obor_profile_build);abort();}}while(0)
uint32_t obor_profile_build;
static int selectScreen,titleScreen,hallOfFame,gameOver,showComplete,menuScreen;
static char *currentScene;
static s_level instance,*level;
static char cache[1024][256],diagnostic[1024];
static int next_cache;
CHAR *StrCache_Get(int i){assert(i>=0 && i<1024);return cache[i];}
void StrCache_Collect(int i){assert(i>=0 && i<1024);}
int StrCache_Pop(void){assert(++next_cache<700);return next_cache;}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
@VARIANTS@
@CALLBACKS@
static ScriptVariant input,result,*args[]={&input},*out;
static void setup(void){memset(&input,0,sizeof(input));memset(&result,0,sizeof(result));out=&result;next_cache=0;diagnostic[0]=0;}
static int query(int index){setup();input.vt=VT_INTEGER;input.lVal=index;return openbor_systemvariant(args,&out,1);}
static int named(const char *name){setup();strcpy(cache[700],name);input.vt=VT_STR;input.strVal=700;return openbor_systemvariant(args,&out,1);}
static int io_success,events,seen_select[8],seen_title[8],seen_menu[8],seen_show,seen_hall;
static char trace[16];
int buffer_pakfile(char *filename,char **buf,size_t *size){assert(filename);*buf=(char*)"";*size=0;return io_success;}
static void observe(char event){assert(events<8);trace[events]=event;seen_select[events]=selectScreen;seen_title[events]=titleScreen;seen_menu[events]=menuScreen;++events;trace[events]=0;}
void kill_all(void){observe('K');}
static void reset_playable_list(int mode){assert(mode==1);observe('R');}
void sound_close_music(void){observe('S');}
void unload_background(void){seen_show=showComplete;seen_hall=hallOfFame;}
@WINDOWS@
struct context {int revision,count,scene_empty,menu_mode;const char *const *names;const int *canonical,*resolved;};
@ARRAYS@
static void clear_flags(void){selectScreen=titleScreen=hallOfFame=gameOver=showComplete=menuScreen=0;currentScene=NULL;level=NULL;}
static int value_for(const char *name){
 if(!strcmp(name,"in_gameoverscreen"))return gameOver;
 if(!strcmp(name,"in_halloffamescreen"))return hallOfFame;
 if(!strcmp(name,"in_selectscreen"))return selectScreen;
 if(!strcmp(name,"in_titlescreen"))return titleScreen;
 if(!strcmp(name,"in_showcomplete"))return showComplete;
 return -1;
}
static void check(const struct context *c){
 obor_profile_build=(uint32_t)c->revision;clear_flags();
 gameOver=17;hallOfFame=19;selectScreen=23;titleScreen=29;showComplete=31;menuScreen=37;currentScene=(char*)"scene";
 int menu_index=-1,scene_index=-1;
 for(int i=0;i<c->count;i++){
  assert(obor_system_property_index(i)==c->canonical[i]);
  setup();strcpy(cache[700],c->names[i]);input.vt=VT_STR;input.strVal=700;
  mapstrings_systemvariant(args,1);mapstrings_systemvariant(args,1);
  if(c->resolved[i]<0){assert(input.vt==VT_STR && diagnostic[0]);}
  else assert(input.vt==VT_INTEGER && input.lVal==c->resolved[i]);
  int expected=value_for(c->names[i]);
  if(expected>=0){
   assert(query(i)==S_OK && out && out->vt==VT_INTEGER && out->lVal==expected);
   assert(named(c->names[i])==S_OK && out && out->vt==VT_INTEGER && out->lVal==expected);
  }
  if(!strcmp(c->names[i],"in_menuscreen"))menu_index=i;
  if(!strcmp(c->names[i],"current_scene"))scene_index=i;
 }
 assert(menu_index>=0 && scene_index>=0);
 assert(obor_system_property_index(-1)==-1 && obor_system_property_index(c->count)==-1);
 assert(query(-1)==E_FAIL && !out);assert(query(c->count)==E_FAIL && !out);
 assert(query(scene_index)==S_OK && out && out->vt==VT_STR && !strcmp(StrCache_Get(out->strVal),"scene"));
 currentScene=NULL;int status=query(scene_index);
 assert(c->scene_empty ? (status==S_OK && out && out->vt==VT_EMPTY) : (status==E_FAIL && !out));
 if(!c->menu_mode)assert(named("in_showcomplete")==E_FAIL && !out);
 else assert(named("in_showcomplete")==S_OK && out && out->lVal==31);
 for(int mask=0;mask<128;mask++)for(int menu=0;menu<2;menu++){
  clear_flags();selectScreen=mask&1;titleScreen=mask&2;hallOfFame=mask&4;gameOver=mask&8;
  showComplete=mask&16;currentScene=mask&32?(char*)"scene":NULL;level=mask&64?&instance:NULL;
  menuScreen=menu?37:0;
  int hidden=c->menu_mode && ((mask&63)||(c->menu_mode==2 && (mask&64)));
  int expected=hidden?0:menuScreen;
  assert(query(menu_index)==S_OK && out && out->vt==VT_INTEGER && out->lVal==expected);
  assert(named("in_menuscreen")==S_OK && out && out->vt==VT_INTEGER && out->lVal==expected);
 }
 for(int title=0;title<2;title++)for(int menu=0;menu<2;menu++){
  int initial_title=title?19:0,initial_menu=menu?29:0;
  for(int loaded=0;loaded<2;loaded++){
   clear_flags();titleScreen=initial_title;menuScreen=initial_menu;io_success=loaded;scene_begin((char*)"scene");
   assert(titleScreen==(!loaded||c->menu_mode?initial_title:0));
   assert(menuScreen==(!loaded||c->menu_mode?initial_menu:0));
   assert(loaded?currentScene!=NULL:currentScene==NULL);
   if(loaded){scene_end();assert(!currentScene);}
  }
  clear_flags();titleScreen=initial_title;menuScreen=initial_menu;hall_begin();
  assert(hallOfFame==1 && titleScreen==(c->menu_mode?initial_title:0) && menuScreen==(c->menu_mode?initial_menu:0));
  hall_end();assert(seen_hall==1 && hallOfFame==0);
  clear_flags();titleScreen=initial_title;menuScreen=initial_menu;events=0;select_begin();select_end();
  assert(!strcmp(trace,"KRKS") && events==4 && selectScreen==0);
  for(int i=0;i<4;i++){
   assert(seen_select[i]==(i<2||c->menu_mode?1:0));
   assert(seen_title[i]==(c->menu_mode?initial_title:0) && seen_menu[i]==(c->menu_mode?initial_menu:0));
  }
  select_begin();assert(quick_select()==1 && selectScreen==0);
 }
 clear_flags();completion_begin();assert(showComplete==(c->menu_mode?1:0));
 completion_end();assert(seen_show==(c->menu_mode?1:0) && showComplete==0);
 printf("revision=%d names=%d menu_mode=%d masks=256 lifecycle=1\n",c->revision,c->count,c->menu_mode);
}
int main(void){@CHECKS@puts("early_menu_system=1");return 0;}
