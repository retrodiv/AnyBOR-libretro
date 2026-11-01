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
#undef inair
#undef kill
#define MIN_INT (int)0x80000000
uint32_t obor_profile_build;
static entity actor, support, companion, *self = &actor, *ent_list[2] = { &actor, &support };
static s_anim animation, support_animation;
static float geometry[2][1][8];
static int actor_sprite[1] = {1}, support_sprite[1] = {2}, shadowsprites[1] = {3};
static unsigned char palettes[2][256], *pal = palettes[0];
static s_level scene, *level = &scene;
static s_drawmethod plainmethod;
static unsigned time, bothnewkeys, sprites_loaded = 2;
static entity *smartbomber, *textbox;
static int ent_max = 2, current_palette;
static int gfx_x_offset, gfx_y_offset, shadowcolor, shadowalpha, light[2];
static int PLAYER_MIN_Z = 160, PLAYER_MAX_Z = 232;
static float advancex, scrolldx, scrolldy;
static int queued[4][6], queued_count, restored;
typedef struct { int colourmap, restored, count, draws[4][6]; } expected;
typedef struct {
 const char *name; float a, other_a;
 int other_exists, other_layer, self_height, actor_layer, owner, grabbing, shadow, wall;
 int updates, dying, health, colourmap, clock;
 expected results[4];
} scenario;
static const scenario cases[] = { @CASES@ };
static int current_wall;
static int palette_id(void *p) { if(!p) return -1; assert(p == palettes[0] || p == palettes[1]); return p == palettes[1]; }
static void queue(int x, int y, int z, int sprite, s_drawmethod *method, int sort) {
 assert(queued_count < 4 && method); int *row = queued[queued_count++];
 row[0]=x; row[1]=y; row[2]=z; row[3]=sprite; row[4]=palette_id(method->table); row[5]=sort;
}
static void restore(entity *e, int map) { assert(e == &actor && !map); e->colourmap = palettes[0]; restored++; }
static int wall_at(float x, float z) { (void)x; (void)z; return current_wall; }
static int wall_below(float x, float z, float a) { (void)a; return wall_at(x,z); }
static int hole_at(float x, float z) { (void)x; (void)z; return 0; }
#define spriteq_add_sprite queue
#define ent_set_colourmap restore
#define drawenemystatus(...) abort()
#define getDrawMethod(...) NULL
#define checkwall wall_at
#define checkwall_below wall_below
#define checkhole hole_at
#define ent_unlink(...) abort()
#define update_frame(...) abort()
#define kill(...) abort()
@FUNCTIONS@
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  const scenario *c=&cases[i]; const expected *want=&c->results[era];
  memset(&actor,0,sizeof(actor));memset(&support,0,sizeof(support));memset(&companion,0,sizeof(companion));
  memset(&animation,0,sizeof(animation));memset(&support_animation,0,sizeof(support_animation));
  memset(&scene,0,sizeof(scene));memset(&plainmethod,0,sizeof(plainmethod));memset(geometry,0,sizeof(geometry));
  actor.exists=1;actor.x=100;actor.z=200;actor.a=c->a;actor.animation=&animation;actor.sortid=7;actor.direction=1;
  actor.modeldata.type=TYPE_ENEMY;actor.modeldata.palette=palettes[0];actor.modeldata.colourmap[0]=palettes[1];
  actor.modeldata.shadow=c->shadow;actor.modeldata.setlayer=c->actor_layer;actor.modeldata.no_adjust_base=1;
  actor.dying=c->dying;actor.health=c->health;actor.per1=60;actor.per2=20;actor.colourmap=palettes[c->colourmap];
  if(c->owner) actor.owner=&companion;
  if(c->grabbing) {actor.grabbing=actor.link=&companion;}
  animation.sprite=actor_sprite;animation.numframes=1;
  time=c->clock;actor.nextanim=time+1;support.nextanim=time+1;
  support.exists=c->other_exists;support.x=100;support.z=205;support.a=c->other_a;
  support.animation=&support_animation;support.modeldata.setlayer=c->other_layer;support_animation.sprite=support_sprite;
  for(int k=0;k<2;k++) {
   float *g=geometry[k][0];g[1]=10;g[2]=g[3]=-20;g[4]=g[5]=20;g[6]=20;g[7]=k?10:c->self_height;
  }
  support_animation.platform=geometry[1];if(c->self_height) animation.platform=geometry[0];
  current_wall=c->wall?0:-1;scene.numwalls=1;scene.walls[0][7]=3;
  plainmethod.scalex=plainmethod.scaley=256;plainmethod.remap=plainmethod.alpha=-1;
  restored=queued_count=0;memset(queued,0,sizeof(queued));
  for(int k=0;k<c->updates;k++) update_animation();
  display_ents();
  if(palette_id(actor.colourmap)!=want->colourmap || restored!=want->restored || queued_count!=want->count) {
   fprintf(stderr,"%s revision=%u state={%d,%d,%d} expected={%d,%d,%d}\n",c->name,revision,palette_id(actor.colourmap),restored,queued_count,want->colourmap,want->restored,want->count);abort();
  }
  for(int k=0;k<queued_count;k++) for(int f=0;f<6;f++) if(queued[k][f]!=want->draws[k][f]) {
   fprintf(stderr,"%s revision=%u draw=%d field=%d got=%d expected=%d\n",c->name,revision,k,f,queued[k][f],want->draws[k][f]);abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_render=1"); return 0; }
