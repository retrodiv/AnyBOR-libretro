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
static entity first, second;
static s_level scene, *level = &scene;
static s_videomodes videomodes;
static float advancex;
static char trace[64];
static unsigned trace_at, wall_calls, hole_calls, base_calls, move_calls;
typedef struct { int returned; float positions[4]; const char *trace; } expected;
typedef struct {
 const char *name;
 float initial[8], targets[4], distance;
 int grabin, screen[2], walls[2]; float wall_heights[2]; int holes[2]; float bases[2]; int moves[2];
 expected results[3];
} scenario;
static const scenario cases[] = { @CASES@ };
static const scenario *current;
static void emit(char kind, unsigned slot) {
 assert(trace_at + 2 < sizeof(trace) && slot < 2); trace[trace_at++] = kind; trace[trace_at++] = '1' + slot; trace[trace_at] = 0;
}
static void original_positions(void) {
 assert(first.x == current->initial[0] && first.z == current->initial[1]);
 assert(second.x == current->initial[4] && second.z == current->initial[5]);
}
static void target(unsigned slot, float x, float z) {
 original_positions(); assert(x == current->targets[slot * 2] && z == current->targets[slot * 2 + 1]);
}
static int probe_wall(float x, float z, float a) {
 assert(wall_calls < 2 && a == 9999999); unsigned slot = wall_calls++;
 target(slot, x, z); emit('W', slot); return current->walls[slot];
}
static int probe_hole(float x, float z) {
 assert(hole_calls < 2); unsigned slot = hole_calls++;
 target(slot, x, z); emit('H', slot); return current->holes[slot];
}
static float probe_base(entity *e, float x, float z) {
 assert(base_calls < 2); unsigned slot = base_calls++;
 assert(e == (slot ? &second : &first)); target(slot, x, z); emit('B', slot); return current->bases[slot];
}
static int probe_move(entity *e, float sx, float sz, float x, float z) {
 assert(move_calls < 2); unsigned slot = move_calls++;
 assert(e == (slot ? &second : &first) && sx == current->initial[slot * 4] && sz == current->initial[slot * 4 + 1]);
 target(slot, x, z); emit('M', slot); return current->moves[slot];
}
#define checkwall_below probe_wall
#define checkhole probe_hole
#define checkbase probe_base
#define testmove probe_move
@FUNCTION@
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  current = &cases[i]; const expected *want = &current->results[era];
  memset(&first, 0, sizeof(first)); memset(&second, 0, sizeof(second)); memset(&scene, 0, sizeof(scene));
  first.x = current->initial[0]; first.z = current->initial[1]; first.a = current->initial[2]; first.base = current->initial[3];
  second.x = current->initial[4]; second.z = current->initial[5]; second.a = current->initial[6]; second.base = current->initial[7];
  first.modeldata.subject_to_screen = current->screen[0]; second.modeldata.subject_to_screen = current->screen[1];
  first.modeldata.subject_to_wall = second.modeldata.subject_to_wall = 1;
  first.modeldata.subject_to_hole = second.modeldata.subject_to_hole = 1;
  first.modeldata.subject_to_platform = second.modeldata.subject_to_platform = 1;
  scene.numwalls = 2; scene.walls[0][7] = current->wall_heights[0]; scene.walls[1][7] = current->wall_heights[1];
  advancex = 0; videomodes.hRes = 320;
  trace_at = wall_calls = hole_calls = base_calls = move_calls = 0; trace[0] = 0;
  int got = adjust_grabposition(&first, &second, current->distance, current->grabin);
  float positions[] = {first.x, first.z, second.x, second.z};
  if(got != want->returned || strcmp(trace, want->trace)) {
   fprintf(stderr, "%s revision=%u returned=%d trace=%s expected=%d %s\n",current->name,revision,got,trace,want->returned,want->trace); abort();
  }
  for(int k = 0; k < 4; k++) if(positions[k] != want->positions[k]) {
   fprintf(stderr, "%s revision=%u position=%d got=%g expected=%g\n",current->name,revision,k,positions[k],want->positions[k]); abort();
  }
  assert(first.a == current->initial[2] && first.base == current->initial[3]);
  assert(second.a == current->initial[6] && second.base == current->initial[7]);
 }
}
int main(void) { @CHECKS@ puts("early_grab_position=1"); return 0; }
