/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Actual input, pause predicate and menu dispatch with controlled services.
 * No replay file I/O or frontend startup is performed.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "openbor.h"
#undef printf
#undef _menutextm
#define CHECK(c) do{if(!(c)){fprintf(stderr,"Movie/menu revision=%u case=%d line=%d\n",obor_profile_build,case_id,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static int case_id;
static s_player player[MAX_PLAYERS];
static s_playercontrols controls[MAX_PLAYERS],*playercontrolpointers[MAX_PLAYERS];
static int current_set,maxplayers[MAX_DIFFICULTIES],pause,nopause;
static u32 interval,bothkeys,bothnewkeys;
static int movieplay,movielog,movieloglen=17,moviebufptr=11,movielen=40;
#define MOVIEBUF_LEN 2048
static unsigned supplied_interval;
static int updates,ticks,replays,saves,flushes,closes,texts;
static int order[8],order_used;
static void event(int n){CHECK(order_used<8);order[order_used++]=n;}
void control_update(s_playercontrols **p,int n){CHECK(p==playercontrolpointers && n==maxplayers[0]);++updates;event(1);}
unsigned timer_getinterval(unsigned rate){CHECK(rate==GAME_SPEED);++ticks;event(2);return supplied_interval;}
static void movie_update(s_playercontrols **p){CHECK(p==playercontrolpointers);++replays;event(3);}
static void movie_save(s_playercontrols **p){CHECK(p==playercontrolpointers);++saves;event(4);}
static void movie_flushbuf(void){++flushes;event(5);}
static void movie_closefile(void){++closes;movieplay=movielog=0;event(6);}
void font_printf(int x,int y,int font,int layer,char *format,...){
 CHECK(x==2 && y==2 && font==1 && layer==0);
 char text[128];va_list ap;va_start(ap,format);int n=vsnprintf(text,sizeof(text),format,ap);va_end(ap);
 CHECK(n>0 && (size_t)n<sizeof(text));
 CHECK(!strcmp(text,"Playing movie, frames: -2020/40") || !strcmp(text,"Recording movie, frames: 28"));++texts;
}
@INPUT@
static int can_pause(int ingame){@PAUSE@ {return 1;}return 0;}
static int rows,selected[6],positions[6];
static const char *labels[6];
static void menu_text(int active,int row,int shift,const char *text){
 CHECK(rows<6 && shift==0);selected[rows]=active;positions[rows]=row;labels[rows++]=text;
}
#define _menutextm(active,row,shift,text) menu_text(active,row,shift,text)
@HELPERS@
static int i,players[MAX_PLAYERS],relback,started,quit,cheats,forcecheatsoff;
static char tmpBuff[128],*custScenes;
static int action_id,choose_result;
int choose_mode(int *p){CHECK(p==players);action_id=1;return choose_result;}
static void movie_options(void){action_id=2;}
void options(void){action_id=3;}
void cheatoptions(void){action_id=4;}
void playscene(char *name){
 CHECK(!strcmp(name,custScenes?"fixture/howto.txt":"data/scenes/howto.txt"));action_id=5;
}
void hallfame(int add){CHECK(!add);action_id=6;}
static char *append_scene(char *out,const char *suffix,size_t count){
 CHECK(out==tmpBuff && !strcmp(out,"fixture/") && !strcmp(suffix,"howto.txt") && count==9);
 size_t used=strlen(out);CHECK(used+count<sizeof(tmpBuff));memcpy(out+used,suffix,count+1);return out;
}
#define strncat append_scene
static void dispatch(int selector){@SWITCH@}
#undef strncat
static void check(int revision,int has_movie,int removed){
 obor_profile_build=revision;case_id=0;
 /* Playback, recording and normal input: one controller sample, preserved
  * release/play masks, historical interval clamps and ordered callbacks. */
 const unsigned intervals[]={0,1,GAME_SPEED/4,GAME_SPEED/4+1,GAME_SPEED,GAME_SPEED+1};
 for(int count=1;count<=MAX_PLAYERS;count++)for(int mode=0;mode<3;mode++)
 for(int esc=0;esc<2;esc++)for(int paused=0;paused<2;paused++)
 for(unsigned v=0;v<sizeof(intervals)/sizeof(*intervals);v++){
  memset(player,0,sizeof(player));memset(controls,0,sizeof(controls));
  updates=ticks=replays=saves=flushes=closes=texts=order_used=0;
  maxplayers[0]=count;pause=paused;movieplay=mode==1;movielog=mode==2;
  supplied_interval=intervals[v];interval=37;
  u32 expected_keys=0,expected_new=0;
  for(int p=0;p<count;p++){
   controls[p].keyflags=FLAG_START | (p&1?FLAG_ATTACK:0);
   controls[p].newkeyflags=(p==count-1 && esc)?FLAG_ESC:FLAG_START;
   player[p].keys=FLAG_JUMP;player[p].playkeys=FLAG_ATTACK;
   expected_keys|=controls[p].keyflags;expected_new|=controls[p].newkeyflags;
  }
  inputrefresh();CHECK(updates==1 && order[0]==1);
  int playback=has_movie && mode==1;
  CHECK(ticks==!playback && replays==(playback && !esc));
  CHECK(saves==(has_movie && mode==2 && !paused));
  CHECK(flushes==(has_movie && mode==2 && esc && !paused));
  CHECK(closes==(has_movie && esc && (mode==1 || (mode==2 && !paused))));
  CHECK(texts==replays+saves);
  if(playback)CHECK(interval==37);
  else{unsigned value=intervals[v];if(value>GAME_SPEED)value=1;if(value>GAME_SPEED/4)value=GAME_SPEED/4;CHECK(interval==value && order[1]==2);}
  if(playback)CHECK(order[1]==(esc?6:3));
  if(saves)CHECK(order[2]==4);
  if(flushes)CHECK(order[order_used-2]==5 && order[order_used-1]==6);
  CHECK(bothkeys==expected_keys && bothnewkeys==expected_new);
  for(int p=0;p<count;p++){
   CHECK(player[p].keys==controls[p].keyflags && player[p].newkeys==controls[p].newkeyflags);
   CHECK(player[p].releasekeys==((controls[p].keyflags|FLAG_JUMP)-controls[p].keyflags));
   CHECK(player[p].playkeys==((FLAG_ATTACK|controls[p].newkeyflags)&controls[p].keyflags));
  }
  ++case_id;
 }
 /* The exact update predicate: any live player can pause, with replay
  * inhibiting pause only while that feature exists. */
 for(int who=-1;who<MAX_PLAYERS;who++)for(int key=0;key<2;key++)
 for(int ingame=0;ingame<3;ingame++)for(int paused=0;paused<2;paused++)
 for(int prohibited=0;prohibited<2;prohibited++)for(int playing=0;playing<2;playing++){
  memset(player,0,sizeof(player));if(who>=0){player[who].ent=(entity*)&player[who];player[who].newkeys=key?FLAG_START:FLAG_ATTACK;}
  pause=paused;nopause=prohibited;movieplay=playing;
  CHECK(can_pause(ingame)==(ingame==1 && !paused && !prohibited && who>=0 && key && !(has_movie && playing)));++case_id;
 }
 static const char *const old_labels[]={"Start Game","Movie Mode","Options","How To Play","Hall Of Fame","Quit"};
 static const char *const new_labels[]={"Start Game","Options","How To Play","Hall Of Fame","Quit"};
 for(int selector=-1;selector<=6;selector++){
  rows=0;obor_main_menu_choices(selector);CHECK(rows==(removed?5:6));
  for(int r=0;r<rows;r++){
   const char *expected=removed?new_labels[r]:old_labels[r];
   if(!removed && r==1 && !has_movie)expected="Movie Options(Disabled)";
   CHECK(!strcmp(labels[r],expected) && positions[r]==r+2 && selected[r]==(selector==r));
  }
  ++case_id;
  for(int cheat=0;cheat<2;cheat++)for(int forced=0;forced<2;forced++)
  for(int custom=0;custom<2;custom++)for(int accepted=0;accepted<2;accepted++){
   memset(player,0,sizeof(player));for(int p=0;p<MAX_PLAYERS;p++)player[p].newkeys=FLAG_START|FLAG_ATTACK;
   relback=quit=action_id=0;started=1;cheats=cheat;forcecheatsoff=forced;
   custScenes=custom?"fixture/":NULL;choose_result=accepted;
   dispatch(selector);
   int start=selector==0;
   int movie=!removed && selector==1;
   int option=selector==(removed?1:2),how=selector==(removed?2:3),hall=selector==(removed?3:4);
   int expected=start?1:movie?(has_movie?2:0):option?(cheat&&!forced?4:3):how?5:hall?6:0;
   CHECK(action_id==expected && quit==!(start||movie||option||how||hall));
   CHECK(relback==(start?accepted:(how||hall)) && started==!(start&&accepted));
   if(start)for(int p=0;p<MAX_PLAYERS;p++)CHECK(players[p]==(int)(player[p].newkeys&FLAG_ANYBUTTON));
   ++case_id;
  }
 }
}
int main(void){
 for(int p=0;p<MAX_PLAYERS;p++)playercontrolpointers[p]=controls+p;
 @CHECKS@
 return 0;
}
