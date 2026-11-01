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
#undef kill
#define MIN_INT (int)0x80000000
uint32_t obor_profile_build;
static entity actor, support, grabbed, *self = &actor, *ent_list[2] = { &actor, &support };
static s_anim animation, support_animation, *animations[MAX_ANIS];
static float geometry[2][2][8];
static short dx[2], dz[2], heights[2];
static s_level scene, *level = &scene;
static unsigned time = 1000, bothnewkeys;
static int ent_max = 2, endgame;
static float scrolldx, scrolldy;
static char trace[8];
static unsigned trace_at;
typedef struct { float x, z, a, base; int landed; const char *trace; } expected;
typedef struct {
 const char *name;
 int mode; float a, base, other_a;
 int landed, self_platform_height, platform_flag, other_exists, footprint;
 float xdir, zdir;
 int think_due, mark, movement, nextanim_due, animating, animpos, direction;
 int dx0, dx1, dz0, dz1, noadjust, seta, altbase;
 expected results[3];
} scenario;
static const scenario cases[] = { @CASES@ };
static void emit(char c) { assert(trace_at + 1 < sizeof(trace)); trace[trace_at++] = c; trace[trace_at] = 0; }
static int moved(float x, float z) { emit('M'); self->x += x; self->z += z; return 1; }
static void linked(float x, float z) { emit('L'); self->x += x; self->z += z; }
#define check_link_move linked
#define execute_think_script(...) abort()
#define set_idle(...) abort()
#define ent_set_colourmap(...) abort()
#define kill(...) abort()
#define update_frame(...) abort()
#define checkwall_below(...) (-1)
#define checkhole(...) 0
#define ent_unlink(...) abort()
@FUNCTIONS@
static int identity(entity *e) { if(!e) return -1; assert(e == &actor || e == &support); return e == &actor ? 0 : 1; }
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  const scenario *c = &cases[i]; const expected *want = &c->results[era];
  memset(&actor,0,sizeof(actor)); memset(&support,0,sizeof(support)); memset(&grabbed,0,sizeof(grabbed));
  memset(&animation,0,sizeof(animation)); memset(&support_animation,0,sizeof(support_animation));
  memset(animations,0,sizeof(animations)); memset(geometry,0,sizeof(geometry)); memset(&scene,0,sizeof(scene));
  actor.exists = 1; actor.x = 100; actor.z = 200; actor.a = c->a; actor.base = c->base;
  actor.animation = &animation; actor.nextthink = actor.nextanim = 1001;
  actor.modeldata.animation = animations; actor.modeldata.animation_capacity = MAX_ANIS;
  actor.modeldata.subject_to_platform = c->platform_flag; actor.modeldata.no_adjust_base = c->noadjust;
  actor.altbase = c->altbase; heights[0] = heights[1] = c->seta; animation.seta = heights;
  actor.landed_on_platform = c->landed < 0 ? NULL : c->landed == 0 ? &actor : &support;
  support.exists = c->other_exists; support.x = 100; support.z = 200; support.a = c->other_a;
  support.animation = &support_animation; support.xdir = c->xdir; support.zdir = c->zdir;
  support.nextthink = c->think_due ? 1000 : 1001; support.update_mark = c->mark;
  support.nextanim = c->nextanim_due ? 1000 : 1001; support.animating = c->animating;
  support.animpos = c->animpos; support.direction = c->direction; support_animation.numframes = 2;
  dx[0] = c->dx0; dx[1] = c->dx1; dz[0] = c->dz0; dz[1] = c->dz1;
  support_animation.move = dx; support_animation.movez = dz;
  for(int k = 0; k < 2; k++) for(int f = 0; f < 2; f++) {
   float *g = geometry[k][f]; g[1] = 10; g[2] = g[3] = -20; g[4] = g[5] = 20; g[6] = 20; g[7] = k ? 10 : c->self_platform_height;
  }
  if(c->self_platform_height) animation.platform = geometry[0];
  support_animation.platform = geometry[1]; if(!c->footprint) support.x = 1000;
  if(c->movement) actor.trymove = moved;
  if(c->movement == 2) { actor.grabbing = &grabbed; actor.grabwalking = 1; grabbed.trymove = moved; }
  if(!c->mode && c->landed == 0) { actor.xdir = c->xdir; actor.zdir = c->zdir; actor.update_mark = c->mark; }
  trace_at = 0; trace[0] = 0;
  if(c->mode) update_animation(); else check_ai();
  if(actor.x != want->x || actor.z != want->z || actor.a != want->a || actor.base != want->base ||
     identity(actor.landed_on_platform) != want->landed || strcmp(trace,want->trace)) {
   fprintf(stderr,"%s revision=%u got={%g,%g,%g,%g,%d,%s} expected={%g,%g,%g,%g,%d,%s}\n",c->name,revision,actor.x,actor.z,actor.a,actor.base,identity(actor.landed_on_platform),trace,want->x,want->z,want->a,want->base,want->landed,want->trace); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_follow=1"); return 0; }
