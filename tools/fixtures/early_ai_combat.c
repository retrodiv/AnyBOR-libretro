/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@SPEED@
enum {TYPE_PLAYER=1,TYPE_ENEMY=2,TYPE_ITEM=3,SUBTYPE_WEAPON=1,SUBTYPE_PROJECTILE=2,
      SUBTYPE_TOUCH=3,ANI_SPECIAL=1,ANI_ATTACK,ANI_RUNATTACK,ANI_JUMPATTACK,
      ANI_JUMPATTACK2,ANI_THROWATTACK,ANI_GET};
typedef struct {int vulnerable[1];} animation;
typedef struct entity {
 float x,z,a,base,xdir,zdir;
 int exists,blink,health,drop,attacking,jumping,idling,running,direction,animpos,autokill;
 uint32_t stalltime,combotime;int combostep[1];
 struct {int type,subtype,health,noflip,nomove,aggression,weapnum,dust[3];
         float speed,jumpheight;int (*weapon)[8];struct {int hide,detect;} stealth;} modeldata;
 struct entity *weapent,*opponent;
 animation *animation;
 void (*takeaction)(void);
} entity;
static uint32_t obor_profile_build,time=1000;
static entity actor,target,second,weapon,dust,*self=&actor,*found_target,*ent_list[2];
static animation target_animation,second_animation;
static struct {int hRes,vRes;} videomodes={320,240};
static int ent_max,max_freespecials=1,max_attacks=1;
static int specials[1]={ANI_SPECIAL},attacks[1]={ANI_ATTACK},*animspecials=specials,*animattacks=attacks;
static unsigned valid_mask,rng_at,target_calls,idles,attacks_set,animations,tosses,spawn_calls,spawn_scripts,walks;
static uint32_t random_values[4];
static int energy[2],last_animation,last_target_animation,dust_available,damage_allowed;
static char trace[32];static unsigned trace_at;
static void mark(char c){assert(trace_at+1<sizeof(trace));trace[trace_at++]=c;trace[trace_at]=0;}
static void initial_action(void){abort();}
static void common_attack_proc(void){abort();}
static void normal_prepare(void){abort();}
static void common_jump(void){abort();}
void common_runoff(void);
static int validanim(entity *e,int animation_id){assert(e==self && animation_id>=1 && animation_id<=ANI_GET);return (valid_mask&(1u<<animation_id))!=0;}
static entity *normal_find_target(int animation_id,int subtype){assert(!subtype);target_calls++;last_target_animation=animation_id;mark('T');return found_target;}
static int set_attacking(entity *e){assert(e==self);attacks_set++;mark('A');return 1;}
static int set_idle(entity *e){assert(e==self);idles++;mark('I');return 1;}
static int ent_set_anim(entity *e,int animation_id,int reset){assert(e==self && !reset);animations++;last_animation=animation_id;mark('N');return 1;}
static int check_energy(int mode,int animation_id){assert((mode==0 || mode==1) && animation_id==ANI_SPECIAL);mark('E');return energy[mode];}
static uint32_t rand32(void){assert(rng_at<4);mark('R');return random_values[rng_at++];}
static void toss(entity *e,float height){assert(e==self && height==self->modeldata.jumpheight);tosses++;mark('J');}
static entity *spawn(float x,float z,float a,int direction,char *name,int model,char *owner){
 assert(x==self->x && z==self->z && a==self->a && direction==self->direction && !name && !owner && model==0);
 spawn_calls++;mark('S');return dust_available?&dust:NULL;
}
static void execute_onspawn_script(entity *e){assert(e==&dust && e->base==self->a && e->autokill==1);spawn_scripts++;mark('O');}
static void adjust_walk_animation(entity *e){assert(e==found_target);walks++;mark('W');}
static int common_walk_anim(entity *e){assert(e==self);walks++;mark('W');return 1;}
static int isItem(entity *e){return e->modeldata.type==TYPE_ITEM;}
static int isSubtypeTouch(entity *e){return e->modeldata.subtype==SUBTYPE_TOUCH;}
static int isSubtypeWeapon(entity *e){return e->modeldata.subtype==SUBTYPE_WEAPON;}
static int isSubtypeProjectile(entity *e){return e->modeldata.subtype==SUBTYPE_PROJECTILE;}
static int canBeDamaged(entity *e,entity *other){assert(e && other==self);return damage_allowed;}
@FUNCTIONS@
static void reset(void){
 memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));memset(&second,0,sizeof(second));
 memset(&weapon,0,sizeof(weapon));memset(&dust,0,sizeof(dust));
 target_animation.vulnerable[0]=second_animation.vulnerable[0]=1;
 actor.modeldata.type=TYPE_ENEMY;actor.modeldata.health=20;actor.health=10;
 actor.modeldata.speed=2.5f;actor.modeldata.jumpheight=4;actor.modeldata.aggression=20;actor.modeldata.dust[2]=-1;
 actor.a=7;actor.xdir=5;actor.zdir=6;actor.running=1;actor.stalltime=1500;actor.takeaction=initial_action;
 target.exists=second.exists=1;target.health=second.health=3;target.x=30;second.x=40;
 target.animation=&target_animation;second.animation=&second_animation;
 target.modeldata.type=second.modeldata.type=TYPE_ENEMY;
 actor.opponent=&target;found_target=&target;ent_list[0]=&target;ent_list[1]=&second;ent_max=1;
 rng_at=target_calls=idles=attacks_set=animations=tosses=spawn_calls=spawn_scripts=walks=0;
 last_animation=last_target_animation=-99;valid_mask=0;energy[0]=energy[1]=1;
 random_values[0]=random_values[1]=random_values[2]=random_values[3]=3;
 dust_available=damage_allowed=1;trace_at=0;trace[0]=0;videomodes.hRes=320;
}
static void run_checks(int modern){
 for(int vulnerable=0;vulnerable<2;vulnerable++)for(int falling=0;falling<2;falling++)
 for(int striking=0;striking<2;striking++)for(int supplied=0;supplied<2;supplied++){
  reset();valid_mask=1u<<ANI_RUNATTACK;target_animation.vulnerable[0]=vulnerable;target.drop=falling;target.attacking=striking;
  int allowed=!modern || vulnerable || (!falling && !striking);
  assert(common_try_runattack(supplied?&target:NULL)==allowed);
  assert(target_calls==(unsigned)!supplied && !rng_at);
  assert(attacks_set==(unsigned)allowed && animations==(unsigned)allowed);
  assert(actor.xdir==(allowed?0:5) && actor.zdir==(allowed?0:6));
  assert(actor.takeaction==(allowed?common_attack_proc:initial_action));
  assert(!strcmp(trace,allowed?(supplied?"AN":"TAN"):(supplied?"":"T")));
  if(allowed)assert(last_animation==ANI_RUNATTACK);
 }
 for(int reason=0;reason<3;reason++){
  reset();valid_mask=reason==0?0:1u<<ANI_RUNATTACK;actor.running=reason==1?0:1;found_target=NULL;
  assert(!common_try_runattack(NULL));assert(!attacks_set && !animations && !rng_at);
  assert(target_calls==(unsigned)(reason==2));
 }
}
static void normal_checks(int modern){
 for(int mode=0;mode<3;mode++)for(int vulnerable=0;vulnerable<2;vulnerable++)
 for(int falling=0;falling<2;falling++)for(int striking=0;striking<2;striking++)for(int combo=0;combo<3;combo++){
  reset();valid_mask=1u<<(mode==0?ANI_ATTACK:mode==1?ANI_SPECIAL:ANI_THROWATTACK);
  if(mode==2){weapon.modeldata.subtype=SUBTYPE_PROJECTILE;actor.weapent=&weapon;}
  target_animation.vulnerable[0]=vulnerable;target.drop=falling;target.attacking=striking;
  actor.combostep[0]=combo!=0;actor.combotime=time+(combo==1?1:0);
  int allowed=!modern || vulnerable || (!falling && !striking);
  assert(common_try_normalattack(mode==2?NULL:&target)==allowed);
  unsigned randoms=(mode==1)+(allowed && combo!=1);
  assert(rng_at==randoms && target_calls==(unsigned)(mode==2));
  assert(idles==(unsigned)allowed && !animations && !attacks_set);
  assert(actor.takeaction==(allowed?normal_prepare:initial_action));
  char expected_trace[16]="";
  if(mode==1)strcat(expected_trace,"ER");
  if(mode==2)strcat(expected_trace,"T");
  if(allowed){strcat(expected_trace,"I");if(combo!=1)strcat(expected_trace,"R");}
  assert(!strcmp(trace,expected_trace));
  if(allowed){
   assert(!actor.xdir && !actor.zdir && actor.idling==0 && actor.attacking==-1);
   assert(actor.stalltime==(combo==1?time+1:time+33));
  }else assert(actor.xdir==5 && actor.zdir==6 && actor.stalltime==1500);
 }
 reset();valid_mask=1u<<ANI_SPECIAL;energy[1]=0;actor.combostep[0]=1;actor.combotime=time+1;
 assert(common_try_normalattack(&target)==1 && !strcmp(trace,"EERI"));
 reset();valid_mask=1u<<ANI_ATTACK;found_target=NULL;assert(!common_try_normalattack(NULL));
 assert(target_calls==1 && !rng_at && !idles);
 reset();assert(!common_try_normalattack(NULL) && !target_calls && !rng_at && !idles);
}
static void jump_checks(int modern){
 for(int mask=1;mask<=3;mask++)for(int roll=0;roll<2;roll++)for(int vulnerable=0;vulnerable<2;vulnerable++)
 for(int falling=0;falling<2;falling++)for(int striking=0;striking<2;striking++)for(int direction=0;direction<2;direction++)
 for(int supplied=0;supplied<2;supplied++)for(int dust_mode=0;dust_mode<3;dust_mode++){
  reset();valid_mask=((mask&1)?1u<<ANI_JUMPATTACK:0)|((mask&2)?1u<<ANI_JUMPATTACK2:0);
  random_values[0]=(uint32_t)roll;actor.direction=direction;actor.modeldata.dust[2]=dust_mode?0:-1;dust_available=dust_mode!=2;
  target_animation.vulnerable[0]=vulnerable;target.drop=falling;target.attacking=striking;
  int selected=mask==2 || (mask==3 && roll)?ANI_JUMPATTACK2:ANI_JUMPATTACK;
  int allowed=!modern || vulnerable || (!falling && !striking);
  assert(common_try_jumpattack(supplied?&target:NULL)==allowed);
  assert(rng_at==(unsigned)(mask==3) && target_calls==(unsigned)!supplied);
  assert(animations==(unsigned)allowed && attacks_set==(unsigned)allowed && tosses==(unsigned)allowed);
  assert(spawn_calls==(unsigned)(allowed && dust_mode) && spawn_scripts==(unsigned)(allowed && dust_mode==1));
  assert(actor.takeaction==(allowed?common_jump:initial_action));
  char expected_trace[16]="";
  if(mask==3)strcat(expected_trace,"R");
  if(!supplied)strcat(expected_trace,"T");
  if(allowed){strcat(expected_trace,"NAJ");if(dust_mode)strcat(expected_trace,dust_mode==1?"SO":"S");}
  assert(!strcmp(trace,expected_trace));
  if(allowed){
   assert(actor.jumping==1 && last_animation==selected);
   assert(actor.xdir==(selected==ANI_JUMPATTACK?(direction?1.3f:-1.3f):0) && !actor.zdir);
  }else assert(!actor.jumping && actor.xdir==5 && actor.zdir==6);
 }
 reset();assert(!common_try_jumpattack(NULL) && !rng_at && !target_calls);
 reset();valid_mask=1u<<ANI_JUMPATTACK;found_target=NULL;
 assert(!common_try_jumpattack(NULL) && target_calls==1 && !animations && !tosses);
}
static void runoff_checks(int modern){
 reset();found_target=NULL;common_runoff();assert(target_calls==1 && last_target_animation==-1 && !rng_at);
 assert(idles==(unsigned)modern && actor.xdir==(modern?0:5) && actor.zdir==(modern?0:6));
 assert(actor.takeaction==(modern?NULL:initial_action));
 assert(!strcmp(trace,modern?"TI":"T"));
 for(int noflip=0;noflip<2;noflip++)for(int direction=0;direction<2;direction++)for(int side=0;side<2;side++)
 for(int expires=-1;expires<=1;expires++){
  reset();actor.modeldata.noflip=noflip;actor.direction=direction;target.x=side?30:-30;
  actor.stalltime=time+expires;common_runoff();int facing=noflip?direction:side;
  assert(actor.direction==facing && actor.xdir==(facing?-1.25f:1.25f) && !actor.zdir);
  assert(actor.takeaction==(expires<0?NULL:initial_action) && walks==1 && target_calls==1 && !rng_at);
  assert(!strcmp(trace,"TW"));
 }
}
static const struct {int aggression,old,modern;} delays[]={@DELAYS@};
static void finish_checks(int modern){
 for(unsigned i=0;i<sizeof(delays)/sizeof(*delays);i++)for(int pattern=0;pattern<6;pattern++)for(int roll=0;roll<2;roll++){
  reset();actor.modeldata.aggression=delays[i].aggression;random_values[0]=roll?3:0;
  if(pattern==0)found_target=NULL;
  if(pattern==1)actor.opponent=NULL;
  if(pattern==2)target.x=80;
  if(pattern==3)actor.modeldata.nomove=1;
  if(pattern==4){actor.opponent=&second;second.x=200;}
  entity *chosen=modern?actor.opponent:found_target;
  int near=chosen && !actor.modeldata.nomove && chosen->x<80;
  int walking=near && roll;
  common_attack_finish();
  assert(!actor.xdir && !actor.zdir && target_calls==(unsigned)!modern && rng_at==(unsigned)near);
  assert(walks==(unsigned)walking && idles==(unsigned)!walking);
  assert(actor.takeaction==(walking?common_runoff:NULL));
  char expected_trace[8]="";if(!modern)strcat(expected_trace,"T");
  if(near)strcat(expected_trace,"R");
  strcat(expected_trace,walking?"W":"I");
  assert(!strcmp(trace,expected_trace));
  if(walking)assert(actor.idling==1);
  int delay=modern?delays[i].modern:delays[i].old;assert(actor.stalltime==(uint32_t)(time+delay));
 }
 reset();actor.modeldata.type=TYPE_PLAYER;common_attack_finish();
 assert(!actor.xdir && !actor.zdir && !actor.takeaction && idles==1 && !target_calls && !rng_at && actor.stalltime==1500);
}
static const struct {int width;float distance;int old,modern;} ranges[]={@RANGES@};
static void item_setup(void){reset();valid_mask=1u<<ANI_GET;target.modeldata.type=second.modeldata.type=TYPE_ITEM;}
static void item_checks(int modern){
 for(unsigned i=0;i<sizeof(ranges)/sizeof(*ranges);i++){
  item_setup();videomodes.hRes=ranges[i].width;target.x=ranges[i].distance;
  assert(normal_find_item()==((modern?ranges[i].modern:ranges[i].old)?&target:NULL));
 }
 item_setup();target.blink=1;assert(normal_find_item()==(modern?NULL:&target));
 item_setup();target_animation.vulnerable[0]=0;assert(!normal_find_item());
 item_setup();target.modeldata.stealth.hide=4;actor.modeldata.stealth.detect=3;assert(!normal_find_item());
 item_setup();target.modeldata.stealth.hide=3;actor.modeldata.stealth.detect=3;assert(normal_find_item()==&target);
 item_setup();target.exists=0;assert(!normal_find_item());
 item_setup();target.modeldata.type=TYPE_ENEMY;assert(!normal_find_item());
 item_setup();actor.health=actor.modeldata.health;assert(!normal_find_item());
 item_setup();valid_mask=0;target.modeldata.subtype=SUBTYPE_TOUCH;assert(normal_find_item()==&target);
 damage_allowed=0;assert(!normal_find_item());
 int equipment[8]={0};
 for(int subtype=SUBTYPE_WEAPON;subtype<=SUBTYPE_PROJECTILE;subtype++){
  item_setup();target.modeldata.subtype=subtype;target.modeldata.weapnum=1;actor.modeldata.weapon=&equipment;
  assert(normal_find_item()==&target);actor.weapent=&weapon;assert(!normal_find_item());
 }
 item_setup();ent_max=2;target.x=second.x=10;assert(normal_find_item()==&target);
 target.blink=1;assert(normal_find_item()==(modern?&second:&target));
}
static void check(unsigned revision,int modern,int speed){
 obor_profile_build=revision;assert(speed==GAME_SPEED && speed==200);
 run_checks(modern);normal_checks(modern);jump_checks(modern);runoff_checks(modern);finish_checks(modern);item_checks(modern);
}
int main(void){@CHECKS@puts("early_ai_combat=1");return 0;}
