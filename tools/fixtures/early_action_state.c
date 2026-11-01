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
#undef kill
uint32_t obor_profile_build;
static entity actor, other, *self = &actor;
static s_attack attack;
static unsigned time = 1000;
static int max_attack_types = 4;
static char trace[128];
static unsigned trace_at;
typedef struct { const char *trace; int stall, nextthink, blink, action, noaicontrol, type; } expected;
typedef struct {
 const char *name;
 int mode, health, weaploss, player, nodieblink, animating, falldie, linked, air, grabbing;
 int inpain, prethrow, expired, special, drop, no_pain, dead, toexplode, grab_allowed;
 expected results[4];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static void note(char c) { assert(trace_at + 1 < sizeof(trace)); trace[trace_at++] = c; trace[trace_at] = 0; }
static void unexpected(void) { abort(); }
static int probe_air(entity *e) { assert(e == self); note('A'); return current->air; }
static int probe_valid(entity *e, int animation) {
 assert(e == self && animation == ANI_SPECIAL); note('V'); return current->special;
}
static void probe_drop(int flag) { assert(flag == 1); note('W'); }
static int probe_death(entity *e, int type, int reset) {
 assert(e == self && type == self->damagetype && reset == 0); note('E'); return 1;
}
static int probe_rise(entity *e, int type, int reset) {
 assert(e == self && type == self->damagetype && reset == 0); note('R'); return 1;
}
static int probe_special(void) { note('S'); return 1; }
static void probe_grab_check(void) { note('G'); }
static int probe_attack(void) { note('X'); return 0; }
static int probe_move(void) { note('M'); return 1; }
static int probe_grab(entity *e, s_attack *a) { assert(e == &other && a == &attack); note('G'); return current->grab_allowed; }
static void probe_opponent(entity *e, entity *opponent) { assert(e == self && opponent == &other); note('O'); }
static void probe_drop_check(s_attack *a) { assert(a == &attack); note('D'); }
static void probe_effects(s_attack *a) { assert(a == &attack); note('F'); }
static void probe_flip(entity *e, s_attack *a) { assert(e == &other && a == &attack); note('I'); }
static void probe_mp(void) { note('M'); }
static void probe_score(entity *e, s_attack *a) { assert(e == &other && a == &attack); note('S'); }
static void probe_damage(entity *e, s_attack *a) { assert(e == &other && a == &attack); self->health = current->health; note('H'); }
static void probe_checkdeath(void) { note('K'); }
static void probe_unlink(entity *e) { assert(e == self); note('U'); }
static void probe_toss(entity *e, float velocity) { assert(e == self && velocity == 2); note('T'); }
static int probe_fall(void) { note('L'); return 1; }
void player_blink(void) { unexpected(); }
void suicide(void) { unexpected(); }
void player_die(void) { unexpected(); }
void common_prethrow(void) { unexpected(); }
void common_fall(void) { unexpected(); }
void common_pain(void) { unexpected(); }
void common_grabattack(void) { unexpected(); }
void npc_warp(void) { unexpected(); }
#define inair probe_air
#define validanim probe_valid
#define dropweapon probe_drop
#define set_death probe_death
#define set_rise probe_rise
#define check_special probe_special
#define common_grab_check probe_grab_check
#define common_attack probe_attack
#define common_move probe_move
#define rand32(...) (unexpected(),0U)
#define common_try_riseattack(...) unexpected()
#define check_costmove(...) unexpected()
#define checkgrab probe_grab
#define set_opponent probe_opponent
#define checkdamagedrop probe_drop_check
#define checkdamageeffects probe_effects
#define checkdamageflip probe_flip
#define checkmpadd probe_mp
#define checkhitscore probe_score
#define checkdamage probe_damage
#define checkdeath probe_checkdeath
#define control_rumble(...) unexpected()
#define kill(...) unexpected()
#define ent_unlink probe_unlink
#define toss probe_toss
#define set_fall(...) probe_fall()
#define set_pain(...) unexpected()
#pragma GCC diagnostic push
/* Original think compares the unsigned game clock with a signed script deadline. */
#pragma GCC diagnostic ignored "-Wsign-compare"
@FUNCTIONS@
#pragma GCC diagnostic pop
static int action(void) {
 if(actor.takeaction == suicide) return 1;
 if(actor.takeaction == player_blink) return 2;
 if(actor.takeaction == player_die) return 3;
 if(actor.takeaction == common_prethrow) return 4;
 if(actor.takeaction == common_fall) return 5;
 assert(!actor.takeaction); return 0;
}
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i]; const expected *want = &current->results[era];
  memset(&actor, 0, sizeof(actor)); memset(&other, 0, sizeof(other)); memset(&attack, 0, sizeof(attack));
  actor.health = current->health; actor.modeldata.weaploss[0] = current->weaploss;
  actor.modeldata.type = current->player ? TYPE_PLAYER : TYPE_ENEMY;
  actor.modeldata.nodieblink = current->nodieblink; actor.modeldata.falldie = current->falldie;
  actor.animating = current->animating; actor.link = current->linked ? &other : NULL;
  actor.grabbing = current->grabbing ? &other : NULL; actor.inpain = current->inpain;
  actor.takeaction = current->prethrow ? common_prethrow : NULL;
  actor.dead = current->dead; actor.toexplode = current->toexplode; actor.drop = current->drop;
  actor.stalltime = current->expired ? 900 : 1100; actor.nextthink = 777; actor.a = actor.base = 5;
  attack.no_pain = current->no_pain; attack.dropv[0] = 2;
  trace_at = 0; trace[0] = 0;
  if(current->mode == 0) common_lie();
  else if(current->mode == 1) common_think();
  else assert(common_takedamage(&other, &attack) == (!current->dead && current->toexplode != 2 && current->grab_allowed));
  int type = actor.modeldata.type == TYPE_NONE ? 0 : actor.modeldata.type == TYPE_PLAYER ? 1 : 2;
  if(strcmp(trace, want->trace) || actor.stalltime != (unsigned)want->stall ||
     actor.nextthink != (unsigned)want->nextthink || actor.blink != want->blink ||
     action() != want->action || actor.noaicontrol != want->noaicontrol || type != want->type) {
   fprintf(stderr, "%s revision=%u got={%s,%u,%u,%d,%d,%d,%d} expected={%s,%d,%d,%d,%d,%d,%d}\n",
    current->name, revision, trace, actor.stalltime, actor.nextthink, actor.blink, action(),actor.noaicontrol,type,
    want->trace,want->stall,want->nextthink,want->blink,want->action,want->noaicontrol,want->type); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_action_state=1"); return 0; }
