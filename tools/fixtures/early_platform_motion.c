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
#undef inair
#undef cangrab
uint32_t obor_profile_build;
static entity actor, platform, dust, *self = &actor, *ent_list[2] = { &actor, &platform };
static s_anim actor_anim, platform_anim, jump_anim, run_anim, *animation_table[MAX_ANIS];
static float geometry[2][1][8];
static s_level scene, *level = &scene;
static s_videomodes videomodes;
static s_player player[4];
static int ent_max = 2, PLAYER_MIN_Z = 160, PLAYER_MAX_Z = 232, SAMPLE_JUMP;
static float advancex;
static unsigned time = 1000;
static int moved, idle_calls, jump_class, near_calls, far_calls, sound_calls, spawn_calls, spawn_callbacks;
typedef struct {
 const char *name;
 int mode, self_platform, other_platform, other_x, other_z, other_a, holes, solid;
 int direction, jump, runjump, forwardjump, running, jumpmovez, far_hole;
 int sound, effect, effect_exists, dx, dz;
 int results[2][4];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static unsigned era;
static int probe_air(entity *e) { assert(e == self); return 0; }
static int probe_valid(entity *e, int animation) {
 assert(e == self);
 if(animation == ANI_JUMP) return current->jump;
 if(animation == ANI_RUNJUMP) return current->runjump;
 if(animation == ANI_FORWARDJUMP) return current->forwardjump;
 assert(animation == ANI_THROW || animation == ANI_GRAB); return 0;
}
static int probe_wall(float x, float z) { (void)x; (void)z; return -1; }
static int probe_wall_below(float x, float z, float a) { (void)a; return probe_wall(x, z); }
static int probe_hole(float x, float z) {
 if(current->mode != 2) return current->holes;
 assert(z == self->z + (current->jumpmovez ? self->zdir : 0));
 float distance = x - self->x; if(distance < 0) distance = -distance;
 if(distance == 2) { near_calls++; return current->holes; }
 assert(distance == 20); far_calls++; return current->far_hole;
}
static void moved_axis(entity *e, int mask) { assert(e == self); moved |= mask; }
static int probe_idle(entity *e) { assert(e == self); idle_calls++; return 1; }
static void probe_jump(float height, float speed, float zspeed, int animation) {
 jump_class = animation == ANI_JUMP ? 1 : animation == ANI_RUNJUMP ? 2 : animation == ANI_FORWARDJUMP ? 3 : 0;
 assert(jump_class && jump_class == current->results[era][1]);
 int running = jump_class == 2 || current->running;
 assert(height == (running ? 4 : 3) && speed == (running ? 6 : 2));
 assert(zspeed == (current->jumpmovez ? self->zdir : 0));
}
static int probe_sound(int sample, unsigned priority, int left, int right, unsigned speed) {
 assert(sample == 7 && priority == 0 && left == 37 && right == 37 && speed == 100); sound_calls++; return 1;
}
static entity *probe_spawn(float x, float z, float a, int direction, void *name, int model, void *owner) {
 assert(x == 100 && z == 200 && a == 5 && direction == self->direction && !name && !owner && model == 6);
 spawn_calls++; return current->effect_exists ? &dust : NULL;
}
static void probe_spawned(entity *e) { assert(e == &dust && e->base == self->a && e->autokill == 1); spawn_callbacks++; }
static void probe_animation(entity *e, int animation, int reset) { assert(e == self && animation == ANI_JUMP && reset == 0); }
static void probe_toss(entity *e, float velocity) { assert(e == self && velocity == 3); e->tossv = velocity; }
#define inair probe_air
#define validanim probe_valid
#define checkwall probe_wall
#define checkwall_below probe_wall_below
#define checkhole probe_hole
#define execute_onmovex_script(e) moved_axis(e, 1)
#define execute_onmovez_script(e) moved_axis(e, 2)
#define execute_onblockz_script(...) abort()
#define execute_onblocks_script(...) abort()
#define execute_onblocko_script(...) abort()
#define execute_onblockw_script(...) abort()
#define find_ent_here(...) (abort(),(entity*)NULL)
#define cangrab(...) (abort(),0)
#define adjust_grabposition(...) (abort(),0)
#define set_opponent(...) abort()
#define ents_link(...) abort()
#define set_pain(...) abort()
#define dothrow(...) abort()
#define set_idle probe_idle
#define ent_set_anim probe_animation
#define tryjump probe_jump
#define sound_play_sample probe_sound
#define spawn probe_spawn
#define execute_onspawn_script probe_spawned
#define toss probe_toss
void common_grabbed(void) { abort(); }
void common_grab(void) { abort(); }
void common_prethrow(void) { abort(); }
void common_throw_wait(void) { abort(); }
void common_attack_proc(void) { abort(); }
void common_jump(void) { abort(); }
@FUNCTIONS@
static void check(unsigned revision, unsigned modern) {
 obor_profile_build = revision; era = modern;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i];
  memset(&actor, 0, sizeof(actor)); memset(&platform, 0, sizeof(platform)); memset(&dust, 0, sizeof(dust));
  memset(&actor_anim, 0, sizeof(actor_anim)); memset(&platform_anim, 0, sizeof(platform_anim));
  memset(&jump_anim, 0, sizeof(jump_anim)); memset(&run_anim, 0, sizeof(run_anim));
  memset(animation_table, 0, sizeof(animation_table)); memset(player, 0, sizeof(player));
  memset(&scene, 0, sizeof(scene)); memset(geometry, 0, sizeof(geometry));
  videomodes.hRes = 320; videomodes.vRes = 240; scene.width = 1000;
  actor.exists = 1; actor.x = 100; actor.z = 200; actor.a = actor.base = 5;
  actor.animation = &actor_anim; actor.direction = current->direction; actor.idling = 1;
  actor.modeldata.type = TYPE_ENEMY; actor.modeldata.height = 3;
  actor.modeldata.subject_to_hole = current->holes; actor.modeldata.subject_to_platform = current->solid;
  actor.modeldata.jumpheight = 3; actor.modeldata.runjumpheight = 4; actor.modeldata.jumpspeed = 2;
  actor.modeldata.runjumpdist = 3; actor.modeldata.jumpmovez = current->jumpmovez;
  actor.running = current->running;
  jump_anim.range.xmin = run_anim.range.xmin = 4; jump_anim.range.xmax = run_anim.range.xmax = 20;
  animation_table[ANI_JUMP] = &jump_anim; animation_table[ANI_RUNJUMP] = &run_anim; actor.modeldata.animation = animation_table; actor.modeldata.animation_capacity = MAX_ANIS;
  platform.exists = current->other_platform; platform.x = current->other_x; platform.z = current->other_z;
  platform.a = current->other_a; platform.animation = &platform_anim;
  for(int k = 0; k < 2; k++) {
   float *g = geometry[k][0]; g[1] = 10; g[2] = g[3] = -20; g[4] = g[5] = 20; g[6] = 20; g[7] = 10;
  }
  if(current->self_platform) actor_anim.platform = geometry[0];
  platform_anim.platform = geometry[1];
  moved = idle_calls = jump_class = near_calls = far_calls = sound_calls = spawn_calls = spawn_callbacks = 0;
  int got[4] = {0};
  if(current->mode == 0) {
   got[0] = common_trymove(current->dx, current->dz); got[1] = actor.x; got[2] = actor.z; got[3] = moved;
  } else if(current->mode == 1) {
   actor.takeaction = common_stuck_underneath; common_stuck_underneath();
   got[0] = idle_calls; got[1] = actor.takeaction != NULL; got[2] = actor.direction; got[3] = actor.running;
  } else if(current->mode == 2) {
   actor.zdir = 1; got[0] = common_try_jump(); got[1] = jump_class; got[2] = near_calls; got[3] = far_calls;
  } else {
   SAMPLE_JUMP = current->sound ? 7 : -1; savedata.effectvol = 37; actor.modeldata.dust[2] = current->effect ? 6 : -1;
   dojump(3, 2, 1, ANI_JUMP);
   assert(actor.jumping && !actor.idling && actor.tossv == 3 && actor.zdir == 1 && actor.takeaction == common_jump);
   got[0] = sound_calls; got[1] = spawn_calls; got[2] = spawn_callbacks; got[3] = actor.xdir;
  }
  for(int k = 0; k < 4; k++) if(got[k] != current->results[era][k]) {
   fprintf(stderr, "%s revision=%u field=%d got=%d expected=%d\n",current->name,revision,k,got[k],current->results[era][k]); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_motion=1"); return 0; }
