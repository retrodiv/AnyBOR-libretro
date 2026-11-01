/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Full current session/level callers with controlled engine and save services.
 * Oracles specify save order and flag lifetime, without file or game I/O.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"New-session revision=%u case=%d line=%d\n",obor_profile_build,case_id,__LINE__);abort();}}while(0)
#undef time
#define time test_time
uint32_t obor_profile_build;
static int case_id;
static int new_game;
static int current_level,current_stage,current_set,endgame,level_completed;
static int allow_secret_chars,PLAYER_LIVES,musicoverlap,fade,CONTINUES,magic_type,sameplayer,credits,bonus;
int PLAYER_MIN_Z,PLAYER_MAX_Z;
static int BGHEIGHT,nomaxrushreset[5],maxplayers[MAX_DIFFICULTIES];
static unsigned num_levels[MAX_DIFFICULTIES],ifcomplete[MAX_DIFFICULTIES],num_difficulties=1;
static unsigned difflives[MAX_DIFFICULTIES],diffoverlap[MAX_DIFFICULTIES],custfade[MAX_DIFFICULTIES];
static unsigned diffcreds[MAX_DIFFICULTIES],typemp[MAX_DIFFICULTIES],same[MAX_DIFFICULTIES],noshowhof[MAX_DIFFICULTIES];
static s_level_entry entries[2],*levelorder[MAX_DIFFICULTIES][MAX_LEVELS];
static s_player player[4];
static entity bodies[4];
static s_level room,*level=&room;
static Script level_script,endlevel_script,caller_script;
Script *pcurrentscript=&caller_script;
ScriptVariant *indexed_var_list;
int max_indexed_vars,max_global_var_index;
static char branch_name[MAX_NAME_LEN+1];
static u32 time;
static int suppress,initial_skip,loads,select_ok,select_calls,script_loads;
static int entry_counts[4],order[4],order_used,completion_saves;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
void ScriptVariant_Clear(ScriptVariant *p){(void)p;abort();}
int Script_IsInitialized(Script *p){assert(p);return 0;}
int Script_Execute(Script *p){(void)p;abort();}
void kill_all(void){}
static void saved(int kind){
 ++entry_counts[kind];if(kind==0 || order_used){assert(order_used<4);order[order_used++]=kind;}
 else ++completion_saves;
}
void savelevelinfo(void){saved(0);}
void saveGameFile(void){saved(1);}
void saveHighScoreFile(void){saved(2);}
void saveScriptFile(void){saved(3);}
void loadScriptFile(void){++script_loads;}
void load_level(char *filename){
 assert(filename && !strncmp(filename,"fixture",7));
 int count=!(suppress && !loads && initial_skip);
 for(int i=0;i<4;i++)assert(entry_counts[i]==count);
 assert(order_used==4*count);
 for(int i=0;i<order_used;i++)assert(order[i]==i);
 memset(entry_counts,0,sizeof(entry_counts));order_used=0;
 if(suppress)assert(!new_game);
 ++loads;level=&room;endgame=0;level_completed=0;level->setweap=7;
}
void spawnplayer(int index){
 assert(index==0);player[index].ent=bodies+index;
 bodies[index].rush[1]=9;bodies[index].health=12;bodies[index].mp=4;
}
void update(int ingame,int wait){assert(ingame==1 && !wait);endgame=1;}
entity *findent(int types){(void)types;abort();}
void fade_out(int type,int speed){assert(!type && !speed);}
void sound_close_music(void){}
void unload_level(void){assert(level==&room);level=NULL;}
int selectplayer(int *players,char *filename){
 (void)players;(void)filename;++select_calls;
 if(select_ok){player[0].lives=3;strcpy(player[0].name,"fixture");}
 return select_ok;
}
void playscene(char *filename){assert(filename && !strncmp(filename,"fixture",7));}
void gameover(void){abort();}
void hallfame(int add){assert(add==1);}
void showcomplete(int stage){(void)stage;abort();}
@FUNCTIONS@
static void reset(void){
 memset(player,0,sizeof(player));memset(&room,0,sizeof(room));memset(savelevel,0,sizeof(savelevel));
 memset(entries,0,sizeof(entries));memset(entry_counts,0,sizeof(entry_counts));
 memset(num_levels,0,sizeof(num_levels));memset(maxplayers,0,sizeof(maxplayers));
 level=&room;endgame=level_completed=0;loads=select_calls=script_loads=order_used=completion_saves=0;
 branch_name[0]=0;current_level=current_set=0;current_stage=1;maxplayers[0]=1;
 max_indexed_vars=0;max_global_var_index=11;select_ok=1;pcurrentscript=&caller_script;
 for(int i=0;i<2;i++){entries[i].filename=i?"fixture1":"fixture0";levelorder[0][i]=entries+i;}
}
static void check(int revision,int has_flag){
 obor_profile_build=revision;suppress=has_flag;case_id=0;
 /* Direct level entry, followed by another level, including a carried flag. */
 for(int seed=0;seed<2;seed++){
  reset();new_game=seed;initial_skip=seed;player[0].lives=3;strcpy(player[0].name,"fixture");
  assert(playlevel("fixture0"));assert(playlevel("fixture1"));
  assert(loads==2 && new_game==(has_flag?0:seed) && pcurrentscript==&caller_script);
  ++case_id;
 }
 for(int resume=0;resume<2;resume++)for(int flag=1;flag<=2;flag++)for(int accepted=0;accepted<2;accepted++)
 for(int count=0;count<=2;count++)for(int scene=0;scene<2;scene++)for(int seed=0;seed<2;seed++){
  reset();new_game=seed;select_ok=accepted;num_levels[0]=count;
  if(scene && count)entries[0].type=cut_scene;
  savelevel[0].flag=flag;savelevel[0].pLives[0]=3;strcpy(savelevel[0].pName[0],"fixture");
  savelevel[0].stage=1;
  initial_skip=has_flag?(!resume || seed):0;
  int joined=(resume && flag==2) || accepted;
  int want_loads=joined?(count-(scene && count)):0;
  int players[4]={1,0,0,0};playgame(players,0,resume);
  assert(loads==want_loads && script_loads==resume);
  assert(select_calls==!(resume && flag==2));
  int want_flag=has_flag?(!resume?1:seed):seed;
  if(has_flag && want_loads)want_flag=0;
  assert(new_game==want_flag && pcurrentscript==&caller_script);
  for(int i=0;i<4;i++)assert(entry_counts[i]==(joined && i>=1 && i<=2));
  ++case_id;
 }
}
int main(void){@CHECKS@return 0;}
