/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef validanim
#undef set_weapon
#define MIN_INT (int)0x80000000
uint32_t obor_profile_build;
static entity subject, weapon, support, unrelated, *self;
static entity *ent_list[3] = { &subject, &weapon, &support };
static s_anim subject_anim, weapon_anim, support_anim, *weapon_animations[MAX_ANIS];
static float geometry[3][1][8];
static s_level scene, *level = &scene;
static s_player player[4];
static unsigned time = 1000;
static int ent_max = 3, set_calls;
typedef struct {
 const char *name;
 int mode, subject_flag, subject_height, support_top, self_platform, weapon_platform, other_platform, wall;
 int flag, counter, animal, respawn, spawn;
 int results[3][4];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static int probe_wall(float x, float z) { assert(x == 100 && z == 200); return current->wall ? 0 : -1; }
static int probe_wall_below(float x, float z, float a) { assert(a == 9999999); return probe_wall(x, z); }
static int probe_valid(entity *e, int animation) {
 assert(e == &weapon && (animation == ANI_RESPAWN || animation == ANI_SPAWN));
 return animation == ANI_RESPAWN ? current->respawn : current->spawn;
}
static void probe_animation(entity *e, int animation, int reset) {
 assert(e == &weapon && reset == 0);
 assert(animation == (current->respawn ? ANI_RESPAWN : current->spawn ? ANI_SPAWN : ANI_IDLE));
}
static int probe_set_weapon(entity *e, int slot, int force) {
 assert(e == &subject && !e->weapent && slot == 0 && force == 0); set_calls++; return 1;
}
void common_lie(void) { abort(); }
void runanimal(void) { abort(); }
#define checkwall probe_wall
#define checkwall_below probe_wall_below
#define validanim probe_valid
#define ent_set_anim probe_animation
#define set_weapon probe_set_weapon
@QUERIES@
static void native_default_base(entity *e) { entity *other = NULL; int wall; @DEFAULT_TAIL@ }
@DROP@
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i];
  memset(&subject, 0, sizeof(subject)); memset(&weapon, 0, sizeof(weapon));
  memset(&support, 0, sizeof(support)); memset(&unrelated, 0, sizeof(unrelated));
  memset(&subject_anim, 0, sizeof(subject_anim)); memset(&weapon_anim, 0, sizeof(weapon_anim));
  memset(&support_anim, 0, sizeof(support_anim)); memset(&scene, 0, sizeof(scene)); memset(geometry, 0, sizeof(geometry));
  subject.exists = 1; subject.x = 100; subject.z = 200; subject.a = 5; subject.direction = 1;
  subject.animation = &subject_anim; subject.modeldata.type = current->mode ? TYPE_ENEMY : TYPE_ITEM;
  subject.modeldata.subject_to_platform = current->subject_flag; subject.modeldata.subject_to_wall = 1;
  subject.modeldata.animal = current->animal;
  weapon.exists = current->mode == 1; weapon.animation = &weapon_anim;
  memset(weapon_animations, 0, sizeof(weapon_animations));
  weapon.modeldata.animation = weapon_animations; weapon.modeldata.animation_capacity = MAX_ANIS;
  weapon_animations[ANI_IDLE] = &weapon_anim;
  if(current->respawn) weapon_animations[ANI_RESPAWN] = &weapon_anim;
  if(current->spawn) weapon_animations[ANI_SPAWN] = &weapon_anim;
  weapon.modeldata.typeshot = 1; weapon.modeldata.counter = current->counter; weapon.nextthink = 777;
  support.exists = current->other_platform; support.x = 100; support.z = 200; support.a = current->support_top - 10; support.animation = &support_anim;
  for(int k = 0; k < 3; k++) {
   float *g = geometry[k][0]; g[1] = 10; g[2] = g[3] = -20; g[4] = g[5] = 20; g[6] = 20; g[7] = 10;
  }
  geometry[0][0][7] = current->subject_height; geometry[1][0][7] = 1;
  if(current->self_platform) subject_anim.platform = geometry[0];
  if(current->weapon_platform) weapon_anim.platform = geometry[1];
  support_anim.platform = geometry[2]; scene.numwalls = 1; scene.walls[0][7] = 3; set_calls = 0;
  int got[4] = {0};
  if(!current->mode) {
   self = &unrelated; native_default_base(&subject); got[0] = subject.base;
  } else {
   self = &subject; subject.weapent = &weapon; dropweapon(current->flag);
   assert(!subject.weapent && weapon.x == subject.x && weapon.z == subject.z && weapon.a == subject.a && weapon.direction == subject.direction);
   assert(set_calls == (current->flag < 2));
   if(!weapon.modeldata.counter) {
    if(current->animal) assert(weapon.modeldata.type == TYPE_NONE && weapon.think == runanimal);
    else assert(weapon.takeaction == common_lie);
   }
   got[0] = weapon.base; got[1] = weapon.modeldata.counter; got[2] = weapon.blink; got[3] = weapon.nextthink;
  }
  for(int k = 0; k < 4; k++) if(got[k] != current->results[era][k]) {
   fprintf(stderr, "%s revision=%u field=%d got=%d expected=%d\n",current->name,revision,k,got[k],current->results[era][k]); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_owners=1"); return 0; }
