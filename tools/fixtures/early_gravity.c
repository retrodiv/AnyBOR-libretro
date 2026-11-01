/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <float.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef inair
#undef validanim
#undef is_frozen
#undef kill
uint32_t obor_profile_build;
static entity actor, platform, dust[3], *self = &actor, *ent_list[2] = { &actor, &platform };
static s_anim animation, alternate, platform_animation;
static float geometry[2][4][8];
static s_level scene, *level = &scene;
static s_attack emptyattack;
static unsigned time = 1000;
static int ent_max = 2, SAMPLE_FALL = -1, autoland;
static char trace[64];
static unsigned trace_at, model_count, frame_count;
static int models[3], frames[3], observed_damage;
typedef struct {
 const char *trace; float a, velocity;
 int head, toss_time, damage_type, health, damage_left;
 int models[3], model_count, frames[3], frame_count;
} expected;
typedef struct {
 const char *name; float a, base, velocity, other_a;
 int other_exists, self_platform, platform_flag, height, anim_height, frozen, expired, falling, initial_head;
 int land_frame, land_model, drop, fall_model, missing, frame_switch, spawn_switch;
 int damage, callback, damage_type, frame_changes_type;
 expected results[4];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static void emit(char c) { assert(trace_at + 1 < sizeof(trace)); trace[trace_at++] = c; trace[trace_at] = 0; }
static int frozen(entity *e) { assert(e == self); return current->frozen; }
static int valid(entity *e, int animation_id) { assert(e == self && animation_id == ANI_WALKOFF); return 0; }
static void blocked(entity *e, entity *ceiling) { assert(e == self && e->hithead == ceiling && !e->tossv); emit('B'); }
static void moved(entity *e) { assert(e == self && e->tossv); emit('M'); }
static void frame(entity *e, int index) {
 assert(e == self && frame_count < 3); frames[frame_count++] = index; emit('F'); e->animpos = index;
 if(current->frame_switch) e->animation = &alternate;
 if(current->frame_changes_type) e->damagetype = 2;
}
static entity *spawned(float x, float z, float a, int direction, void *name, int model, void *owner) {
 assert(x == 100 && z == 200 && a == self->a && direction == 1 && !name && !owner && model_count < 3);
 unsigned slot = model_count++; models[slot] = model; emit('S');
 return current->missing == (int)slot + 1 ? NULL : &dust[slot];
}
static void spawn_callback(entity *e) {
 assert(e >= dust && e < dust + 3 && e->base == self->a && e->autokill == 1); emit('C');
 if(current->spawn_switch) self->animation = &alternate;
}
static int damage_callback(entity *e, s_attack *attack) {
 assert(e == self && attack->attack_force == current->damage); emit('D'); observed_damage = attack->attack_type; return 1;
}
#define is_frozen frozen
#define validanim valid
#define execute_onblocka_script blocked
#define execute_onmovea_script moved
#define update_frame frame
#define spawn spawned
#define execute_onspawn_script spawn_callback
#define toss(...) abort()
#define sound_play_sample(...) abort()
#define control_rumble(...) abort()
#define ent_set_anim(...) abort()
#define kill(...) abort()
void common_walkoff(void) { abort(); }
@FUNCTIONS@
static int identity(entity *e) { if(!e) return -1; assert(e == &actor || e == &platform); return e == &actor ? 0 : 1; }
static void check(unsigned revision, unsigned era) {
 assert(sizeof(float) == 4 && FLT_MANT_DIG == 24 && FLT_EVAL_METHOD == 0 && GAME_SPEED == 200);
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i]; const expected *want = &current->results[era];
  memset(&actor, 0, sizeof(actor)); memset(&platform, 0, sizeof(platform)); memset(dust, 0, sizeof(dust));
  memset(&animation, 0, sizeof(animation)); memset(&alternate, 0, sizeof(alternate));
  memset(&platform_animation, 0, sizeof(platform_animation)); memset(&scene, 0, sizeof(scene)); memset(geometry, 0, sizeof(geometry));
  memset(&emptyattack, 0, sizeof(emptyattack)); scene.maxfallspeed = -100; scene.maxtossspeed = 100;
  actor.exists = 1; actor.x = 100; actor.z = 200; actor.a = current->a; actor.base = current->base;
  actor.tossv = current->velocity; actor.toss_time = current->expired ? 0 : 1001; actor.falling = current->falling;
  actor.animation = &animation; actor.direction = 1; actor.health = 50; actor.modeldata.type = TYPE_ENEMY;
  actor.modeldata.subject_to_platform = current->platform_flag; actor.modeldata.height = current->height;
  actor.modeldata.dust[0] = current->fall_model; actor.drop = current->drop;
  actor.damage_on_landing = current->damage; actor.damagetype = current->damage_type;
  if(current->callback) actor.takedamage = damage_callback;
  if(current->initial_head) actor.hithead = &platform;
  animation.height = current->anim_height; animation.dropframe = -1; animation.numframes = 3;
  animation.landframe.frame = current->land_frame; animation.landframe.ent = current->land_model;
  alternate.height = current->anim_height; alternate.dropframe = -1; alternate.numframes = 3;
  alternate.landframe.frame = 2; alternate.landframe.ent = 9;
  platform.exists = current->other_exists; platform.x = 100; platform.z = 200; platform.a = current->other_a;
  platform.animation = &platform_animation;
  for(int k = 0; k < 2; k++) for(int f = 0; f < 4; f++) {
   float *g = geometry[k][f]; g[1] = 10; g[2] = g[3] = -20; g[4] = g[5] = 20; g[6] = 20; g[7] = 10;
  }
  if(current->self_platform) animation.platform = alternate.platform = geometry[0];
  platform_animation.platform = geometry[1]; trace_at = model_count = frame_count = 0; trace[0] = 0;
  observed_damage = -1; check_gravity();
  if(strcmp(trace, want->trace) || actor.a != want->a || actor.tossv != want->velocity ||
     identity(actor.hithead) != want->head || actor.toss_time != (unsigned)want->toss_time ||
     observed_damage != want->damage_type || actor.health != want->health || actor.damage_on_landing != want->damage_left ||
     model_count != (unsigned)want->model_count || frame_count != (unsigned)want->frame_count) {
   fprintf(stderr, "%s revision=%u got={%s,%g,%g,%d,%u,%d,%d,%d,models=%u,frames=%u}\n",current->name,revision,trace,actor.a,actor.tossv,identity(actor.hithead),actor.toss_time,observed_damage,actor.health,actor.damage_on_landing,model_count,frame_count); abort();
  }
  for(unsigned k = 0; k < model_count; k++) assert(models[k] == want->models[k]);
  for(unsigned k = 0; k < frame_count; k++) assert(frames[k] == want->frames[k]);
 }
}
int main(void) { @CHECKS@ puts("early_gravity=1"); return 0; }
