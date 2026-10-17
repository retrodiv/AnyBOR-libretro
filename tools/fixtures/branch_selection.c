/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
#define Tr(x) (x)
#undef _menutextm
#undef _menutext
#define _menutextm(f,l,s,text,...) menu_label((f),(l),(text))
#define _menutext(f,c,l,text,...) menu_label((f),(l),(text))
uint32_t obor_profile_build;
int multihitcheat,escape_flag,goto_mainmenu_flag;
int cheats=1,forcecheatsoff,_pause,optionsMenu,livescheat,creditscheat,healthcheat;
int SAMPLE_BEEP=-1,SAMPLE_BEEP2=-1;
u64 bothnewkeys;
s_savedata savedata;
s_level *level;
s_videomodes videomodes;
float advancex;
static int calls;
static char menu_labels[4096];
static void menu_label(int selected,int row,const char *label) {
 (void)selected;(void)row;
 if(!strstr(menu_labels,label)) { assert(strlen(menu_labels)+strlen(label)+2<sizeof(menu_labels));strcat(menu_labels,label);strcat(menu_labels,"\n"); }
}
void savesettings(void) {}
void menu_options_video(void) {}
void menu_options_sound(void) {}
void menu_options_input(void) {}
void menu_options_system(void) {}
void update(int ingame,int usewait) {
 (void)ingame;(void)usewait;
 /* Four options, then the fourth cheat. Exit after one toggle. */
 bothnewkeys=++calls<=7?FLAG_MOVEDOWN:calls==8?FLAG_ATTACK:FLAG_ESC;
 assert(calls<11);
}
int sound_play_sample(int sample,unsigned priority,int left,int right,unsigned speed) {
 (void)sample;(void)priority;(void)left;(void)right;(void)speed;return 0;
}
void writeToLogFile(const char *text,...) { (void)text; }
METHODS
static int screen(entity *ent,float x) { SCREEN return 1; }
static int choice(u64 keys) {
 s_player player[1]={{0}};entity ent={0};entity *example[]={&ent};int i=0;
 player[0].newkeys=keys;
 if(0) return -1;
 else if(EARLY_CHOICE) return 1;
 else if(LATERAL_CHOICE) return 2;
 else if(CONFIRM_CHOICE) return 1;
 return 0;
}
static int escape_selection(void) { int escape=0; ESCAPE return escape; }
int main(void) {
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p) {
  obor_profile_build=profiles[p];entity target={0};multihitcheat=0;
  for(unsigned id=1;id<=5;++id)obor_remember_attack(&target,id);
  for(unsigned id=1;id<=6;++id) {
   int expected=id==5 || (profiles[p]==7123 && id>=2 && id<=4);
   assert(obor_attack_seen(&target,id,0)==expected && !obor_attack_seen(&target,id,1));
  }
  multihitcheat=1;assert(!obor_attack_seen(&target,4,0) && obor_attack_seen(&target,5,0));
  multihitcheat=0;goto_mainmenu_flag=escape_flag=0;goto_mainmenu(11);
  assert(goto_mainmenu_flag==23 && escape_flag==(profiles[p]==7123?11:0));
  bothnewkeys=0;assert(escape_selection()==(profiles[p]==7123));assert(escape_flag==0);
  bothnewkeys=FLAG_ESC;assert(escape_selection()==1);
  assert(choice(FLAG_ATTACK)==1 && choice(FLAG_MOVELEFT)==2);
  assert(choice(FLAG_ATTACK|FLAG_MOVELEFT)==(profiles[p]==7123?1:2));
  entity ent={0};ent.modeldata.subject_to_screen=1;advancex=100;videomodes.hRes=320;
  for(int x=100;x<=420;++x)assert(screen(&ent,x)==(x>=100+(p==1?5:10)&&x<=420-(p==1?5:10)));
  calls=0;bothnewkeys=0;menu_labels[0]=0;menu_options();
  assert(multihitcheat==(profiles[p]==7123));
  assert((strstr(menu_labels,"Multihit Glitch")!=NULL)==(profiles[p]==7123));
 }
}
