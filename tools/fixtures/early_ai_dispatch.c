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

uint32_t obor_profile_build;
static entity actor, hostile, item, parent, *self = &actor;
static s_anim actor_anim, item_anim;
static short vulnerable[1], altitude_offset[1];
static unsigned time = 1000;
static char trace[256];
static unsigned trace_at, draws;
static int walked_to;
struct result { const char *trace; int x, z, stall, direction, running, action, returned, walked_to; };
struct scenario {
 const char *name;
 int aimove, air, target, item, owner, noflip, running, turn, jump, blocked, follow;
 int item_here, vulnerable, altitude, seta, stall, aggression, subtype, npc, grab;
 unsigned r0, r1;
 int helper_wait, xdir, zdir, runupdown, direction, near;
 struct result expected[5];
};
static const struct scenario cases[] = { @CASES@ };
static const struct scenario *current;
static void note(char c) { assert(trace_at + 1 < sizeof(trace)); trace[trace_at++] = c; trace[trace_at] = 0; }
static void axes(char c, int x, int z) { note(c); note('0' + x); note('0' + z); }
static int probe_air(entity *e) { assert(e == self); note('A'); return current->air; }
static unsigned random_word(void) { note('R'); assert(draws < 2); return draws++ ? current->r1 : current->r0; }
static int valid(entity *e, int animation) { assert(e == self && animation == ANI_TURN); note('V'); return current->turn; }
static entity *probe_target(int type, int flags) { assert(type == -1 && flags == 0); note('N'); return current->target ? &hostile : NULL; }
static entity *find_item(void) { note('L'); return current->item ? &item : NULL; }
static entity *here(entity *e, float x, float z, int type) {
 assert(e == self && x == self->x && z == self->z && type == TYPE_ITEM); note('H');
 return current->item_here ? &item : NULL;
}
static void pickup(entity *e) { assert(e == &item); note('P'); }
static int jump(void) { note('J'); return current->jump; }
static int probe_blocked(void) { note('B'); return current->blocked; }
static int pick(entity *e) { assert(e == &item); note('K'); self->xdir = 10; self->zdir = 11; return 1; }
static void move_axes(char c, int x, int z, int vx, int vz) {
 axes(c, x, z); if(x) self->xdir = vx; if(z) self->zdir = vz;
 self->stalltime += current->helper_wait;
}
static int wander(entity *e, int x, int z) { assert(e == &hostile); move_axes('Q', x, z, 2, 3); return 1; }
static int free_wander(int x, int z) { move_axes('D', x, z, 4, 5); return 1; }
static int chase(entity *e, int x, int z) { assert(e == &hostile); move_axes('C', x, z, 6, 7); return 1; }
static int avoid(entity *e, int x, int z) { assert(e == &hostile); move_axes('E', x, z, 8, 9); return 1; }
static int follow(entity *e, int x, int z) {
 assert(e == (current->owner ? &parent : NULL) && x == 1 && z == 1); note('F');
 if(current->follow) { self->xdir = 12; self->zdir = 13; self->stalltime += current->helper_wait; }
 return current->follow;
}
static int idle(entity *e) { assert(e == self); note('I'); return 1; }
static void walk(entity *e) { walked_to = e == &hostile ? 1 : e == &item ? 2 : e == &parent ? 3 : 0; note('W'); }
static void animation(entity *e, int anim, int reset) { assert(e == self && anim == ANI_TURN && reset == 0); note('T'); }
static int route(char c) { note(c); return 1; }
static int normal(void) { return route('n'); }
static int old_avoid(void) { return route('v'); }
static int old_chase(void) { return route('c'); }
static int old_wander(void) { return route('w'); }
static int biker(void) { return route('b'); }
static int arrow(void) { return route('a'); }
static int star(void) { return route('s'); }
static int bomb(void) { return route('o'); }
void common_turn(void) { abort(); }
#define inair probe_air
#define rand32 random_word
#define validanim valid
#define normal_find_target probe_target
#define normal_find_item find_item
#define find_ent_here here
#define common_pickupitem pickup
#define common_try_jump jump
#define checkpathblocked probe_blocked
#define common_try_pick pick
#define common_try_wander wander
#define common_try_wandercompletely free_wander
#define common_try_chase chase
#define common_try_avoid avoid
#define common_try_follow follow
#define set_idle idle
#define adjust_walk_animation walk
#define ent_set_anim animation
#define normal_move normal
#define avoid_move old_avoid
#define chase_move old_chase
#define wander_move old_wander
#define biker_move biker
#define arrow_move arrow
#define star_move star
#define bomb_move bomb
#pragma GCC diagnostic push
/* The unchanged legacy dispatcher compares its unsigned mask with -1. */
#pragma GCC diagnostic ignored "-Wsign-compare"
@FUNCTIONS@
#pragma GCC diagnostic pop
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i]; const struct result *want = &current->expected[era];
  memset(&actor, 0, sizeof(actor)); memset(&hostile, 0, sizeof(hostile));
  memset(&item, 0, sizeof(item)); memset(&parent, 0, sizeof(parent));
  memset(&actor_anim, 0, sizeof(actor_anim)); memset(&item_anim, 0, sizeof(item_anim));
  self = &actor; actor.animation = &actor_anim; item.animation = &item_anim;
  actor.x = 100; actor.z = 200; hostile.x = current->near ? 101 : 200; hostile.z = 200;
  item.x = parent.x = 200; item.a = 0; actor.a = current->altitude;
  vulnerable[0] = current->vulnerable; item_anim.vulnerable = vulnerable;
  altitude_offset[0] = current->seta; if(current->seta >= 0) actor_anim.seta = altitude_offset;
  actor.parent = current->owner ? &parent : NULL;
  actor.modeldata.aimove = current->aimove; actor.modeldata.noflip = current->noflip;
  actor.modeldata.runupdown = current->runupdown; actor.modeldata.aggression = current->aggression;
  actor.modeldata.subtype = current->subtype; actor.modeldata.type = current->npc ? TYPE_NPC : TYPE_ENEMY;
  actor.modeldata.grabdistance = current->grab;
  actor.xdir = current->xdir; actor.zdir = current->zdir; actor.running = current->running;
  actor.direction = current->direction; actor.stalltime = current->stall;
  trace_at = draws = 0; trace[0] = 0; walked_to = -1;
  int returned = common_move();
  if(strcmp(trace, want->trace) || actor.xdir != want->x || actor.zdir != want->z ||
     actor.stalltime != (unsigned)want->stall || actor.direction != want->direction ||
     actor.running != want->running || (actor.takeaction == common_turn) != want->action || returned != want->returned || walked_to != want->walked_to) {
   fprintf(stderr, "%u %s: got {%s,%g,%g,%u,%d,%d,%d,%d}, expected {%s,%d,%d,%d,%d,%d,%d,%d}\n",
    revision, current->name, trace, actor.xdir, actor.zdir, actor.stalltime, actor.direction,
    actor.running, actor.takeaction == common_turn, returned, want->trace, want->x, want->z,
    want->stall, want->direction, want->running, want->action, want->returned); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_ai_dispatch=1"); return 0; }
