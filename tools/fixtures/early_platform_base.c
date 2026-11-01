/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#define MIN_INT (int)0x80000000
uint32_t obor_profile_build;
static entity actor, platform, obstacle, *ent_list[2] = { &actor, &platform };
static s_anim actor_anim, platform_anim, obstacle_anim;
static float geometry[3][1][8];
static s_level scene, *level = &scene;
static s_videomodes videomodes;
static float advancex = 50;
static int ent_max = 2, PLAYER_MIN_Z = 160, PLAYER_MAX_Z = 232, hole_calls, obstacle_calls;
typedef struct {
 const char *name;
 int mode, ent, wallflag, holeflag, platflag, obsflag, minz, maxz, screen, exit_blocked, width;
 int a, base, height, animheight, sx, sz, x, z, wall, wallheight, selfplat, otherplat, othera;
 int obs, obsplat, obsheight, hole;
 int result[3];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static int probe_wall(float x, float z) { assert(x == current->x && z == current->z); return current->wall; }
static int probe_wall_below(float x, float z, float a) {
 int selected = probe_wall(x, z); assert(selected < 0 || current->wallheight <= a); return selected;
}
static int probe_hole(float x, float z) { (void)probe_wall(x, z); hole_calls++; return current->hole; }
static entity *probe_obstacle(entity *e, float x, float z, int type) {
 assert(e == &actor && type == (TYPE_OBSTACLE | TYPE_TRAP)); (void)probe_wall(x, z);
 obstacle_calls++; return current->obs ? &obstacle : NULL;
}
#define checkwall probe_wall
#define checkwall_below probe_wall_below
#define checkhole probe_hole
#define find_ent_here probe_obstacle
@FUNCTIONS@
static void check(unsigned revision, int has_base, int has_move) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i]; if((current->mode == 0 && !has_base) || (current->mode == 1 && !has_move)) continue;
  memset(&actor, 0, sizeof(actor)); memset(&platform, 0, sizeof(platform)); memset(&obstacle, 0, sizeof(obstacle));
  memset(&actor_anim, 0, sizeof(actor_anim)); memset(&platform_anim, 0, sizeof(platform_anim));
  memset(&obstacle_anim, 0, sizeof(obstacle_anim)); memset(&scene, 0, sizeof(scene)); memset(geometry, 0, sizeof(geometry));
  videomodes.hRes = 320; videomodes.vRes = 240; scene.width = current->width; scene.exit_blocked = current->exit_blocked;
  scene.numwalls = 2; scene.walls[0][7] = scene.walls[1][7] = current->wallheight;
  actor.exists = 1; actor.x = 100; actor.z = 200; actor.a = current->a; actor.base = current->base;
  actor.animation = &actor_anim; actor_anim.height = current->animheight; actor.modeldata.height = current->height;
  actor.modeldata.subject_to_wall = current->wallflag; actor.modeldata.subject_to_hole = current->holeflag;
  actor.modeldata.subject_to_platform = current->platflag; actor.modeldata.subject_to_obstacle = current->obsflag;
  actor.modeldata.subject_to_minz = current->minz; actor.modeldata.subject_to_maxz = current->maxz;
  actor.modeldata.subject_to_screen = current->screen;
  platform.exists = current->otherplat; platform.x = 100; platform.z = 200; platform.a = current->othera;
  platform.animation = &platform_anim; obstacle.animation = &obstacle_anim;
  for(int k = 0; k < 3; k++) {
   float *g = geometry[k][0]; g[1] = 50; g[2] = g[3] = -100; g[4] = g[5] = 100; g[6] = 100; g[7] = 10;
  }
  if(current->selfplat) actor_anim.platform = geometry[0];
  platform_anim.platform = geometry[1];
  if(current->obsplat) obstacle_anim.platform = geometry[2];
  geometry[2][0][7] = current->obsheight;
  hole_calls = obstacle_calls = 0; float value;
  if(current->mode == 0) value = checkbase(current->ent ? &actor : NULL, current->x, current->z);
  else { assert(current->ent); value = testmove(&actor, current->sx, current->sz, current->x, current->z); }
  if(value != current->result[0] || hole_calls != current->result[1] || obstacle_calls != current->result[2]) {
   fprintf(stderr, "%s revision=%u got={%g,%d,%d} expected={%d,%d,%d}\n",current->name,revision,value,hole_calls,obstacle_calls,current->result[0],current->result[1],current->result[2]); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_base=1"); return 0; }
