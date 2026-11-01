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
#undef validanim
uint32_t obor_profile_build;
static entity actor, *self = &actor;
static unsigned time = 1000;
static char trace[16];
static unsigned trace_at;
static int air_xdir, air_nextthink;
typedef struct {
 const char *trace;
 int xdir, zdir, nextthink, tossv, no_adjust, base, wall, platform, hole, action, air_xdir, air_nextthink;
} expected;
typedef struct {
 const char *name;
 int air, toexplode, exploding, direction, diesound, attack1, attack2;
 expected results[2];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static void note(char c) { assert(trace_at + 1 < sizeof(trace)); trace[trace_at++] = c; trace[trace_at] = 0; }
static int probe_air(entity *e) {
 assert(e == self); note('A'); air_xdir = e->xdir; air_nextthink = e->nextthink; return current->air;
}
static int probe_valid(entity *e, int animation) {
 assert(e == self && (animation == ANI_ATTACK1 || animation == ANI_ATTACK2));
 note(animation == ANI_ATTACK1 ? '1' : '2'); return animation == ANI_ATTACK1 ? current->attack1 : current->attack2;
}
static void probe_animation(entity *e, int animation, int reset) {
 assert(e == self && reset == 0 && (animation == ANI_ATTACK1 || animation == ANI_ATTACK2));
 note(animation == ANI_ATTACK1 ? 'a' : 'b');
}
static int probe_sound(int sample, unsigned priority, int left, int right, unsigned speed) {
 assert(sample == current->diesound && priority == 0 && left == 37 && right == 37 && speed == 100); note('S'); return 1;
}
void bomb_explode(void) { abort(); }
#define inair probe_air
#define validanim probe_valid
#define ent_set_anim probe_animation
#define sound_play_sample probe_sound
@FUNCTION@
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision; assert(THINK_SPEED == 2); savedata.effectvol = 37;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i]; const expected *want = &current->results[era];
  memset(&actor, 0, sizeof(actor)); actor.xdir = 7; actor.zdir = 9; actor.nextthink = 777;
  actor.tossv = 3; actor.base = 2; actor.a = 5; actor.modeldata.speed = 4;
  actor.modeldata.subject_to_wall = actor.modeldata.subject_to_hole = 1;
  actor.modeldata.diesound = current->diesound; actor.toexplode = current->toexplode;
  actor.direction = current->direction; actor.takeaction = current->exploding ? bomb_explode : NULL;
  trace_at = 0; trace[0] = 0; air_xdir = air_nextthink = -1;
  int returned = bomb_move();
  if(returned != 1 || strcmp(trace, want->trace) || actor.xdir != want->xdir || actor.zdir != want->zdir ||
     actor.nextthink != (unsigned)want->nextthink || actor.tossv != want->tossv ||
     actor.modeldata.no_adjust_base != want->no_adjust || actor.base != want->base ||
     actor.modeldata.subject_to_wall != want->wall || actor.modeldata.subject_to_platform != want->platform ||
     actor.modeldata.subject_to_hole != want->hole || (actor.takeaction == bomb_explode) != want->action ||
     air_xdir != want->air_xdir || air_nextthink != want->air_nextthink) {
   fprintf(stderr, "%s revision=%u trace=%s x=%g z=%g next=%u toss=%g base=%g air_x=%d air_next=%d\n",
    current->name, revision, trace, actor.xdir, actor.zdir, actor.nextthink, actor.tossv, actor.base, air_xdir, air_nextthink);
   abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_ai_bomb=1"); return 0; }
