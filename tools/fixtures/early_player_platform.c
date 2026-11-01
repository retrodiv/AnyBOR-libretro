/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
uint32_t obor_profile_build;
static entity actor, support, *self = &actor, *ent_list[2] = { &actor, &support };
static s_anim animation, duck_animation, support_animation, *animations[MAX_ANIS];
static float geometry[2][1][8];
static s_level scene, *level;
static int ent_max = 2, queries, changed, fell_through;
typedef struct {
 const char *name;
 int flag, valid, scene, own_height, other_exists, other_a, other_height, model_height, animation_height;
 int results[2][2];
} scenario;
static const scenario cases[] = { @CASES@ };
@QUERIES@
static entity *between(float x, float z, float low, float high, entity *exclude) {
 assert(x == self->x && z == self->z && low == self->a && exclude == self && queries < 2);
 assert(high == self->a + (queries ? self->animation->height : self->modeldata.height));
 queries++; return native_between(x,z,low,high,exclude);
}
static void animate(entity *e, int animation_id, int reset) {
 assert(e == self && animation_id == ANI_DUCK && reset == 1 && !changed);changed++;
}
void common_stuck_underneath(void) { abort(); }
#define check_platform_between between
#define ent_set_anim animate
static void native_player_platform_gate(void) { @GATE@ fell_through++; }
static void check(unsigned revision, unsigned era) {
 obor_profile_build=revision;
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  const scenario *c=&cases[i];
  memset(&actor,0,sizeof(actor));memset(&support,0,sizeof(support));
  memset(&animation,0,sizeof(animation));memset(&duck_animation,0,sizeof(duck_animation));memset(&support_animation,0,sizeof(support_animation));
  memset(animations,0,sizeof(animations));memset(geometry,0,sizeof(geometry));
  level=c->scene?&scene:NULL;actor.exists=1;actor.x=100;actor.z=200;actor.animation=&animation;
  actor.modeldata.animation=animations;actor.modeldata.animation_capacity=MAX_ANIS;
  if(c->valid) { animations[ANI_DUCK]=&duck_animation;duck_animation.numframes=1; }
  actor.modeldata.subject_to_platform=c->flag;actor.modeldata.height=c->model_height;animation.height=c->animation_height;
  support.exists=c->other_exists;support.x=100;support.z=200;support.a=c->other_a;support.animation=&support_animation;
  for(int k=0;k<2;k++) {float *g=geometry[k][0];g[1]=10;g[2]=g[3]=-20;g[4]=g[5]=20;g[6]=20;g[7]=k?c->other_height:c->own_height;}
  if(c->own_height) animation.platform=geometry[0];
  support_animation.platform=geometry[1];
  queries=changed=fell_through=0;native_player_platform_gate();
  int want=c->results[era][0];
  if(changed!=want || fell_through!=!want || (actor.takeaction==common_stuck_underneath)!=want || queries!=c->results[era][1]) {
   fprintf(stderr,"%s revision=%u got={%d,%d,%d,%d} expected={%d,%d}\n",c->name,revision,changed,fell_through,actor.takeaction==common_stuck_underneath,queries,want,c->results[era][1]);abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_player_platform=1"); return 0; }
