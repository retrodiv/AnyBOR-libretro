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
static s_level instance, *level;
static entity platforms[2], *ent_list[2] = { &platforms[0], &platforms[1] };
static s_anim animations[2];
static float geometry[2][1][8];
static int ent_max = 2;
@FUNCTIONS@
typedef struct {
 const char *name; int kind; float first, second, altitude, x, z;
 int present, exists_first, exists_second, results[2];
} scenario;
static const scenario cases[] = { @CASES@ };
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  const scenario *row = &cases[i];
  memset(&instance, 0, sizeof(instance)); memset(platforms, 0, sizeof(platforms));
  memset(animations, 0, sizeof(animations)); memset(geometry, 0, sizeof(geometry));
  instance.numwalls = 2; level = row->present ? &instance : NULL;
  for(int k = 0; k < 2; k++) {
   float height = k ? row->second : row->first;
   float *wall = instance.walls[k], *plat = geometry[k][0];
   wall[2] = wall[3] = plat[2] = plat[3] = -10;
   wall[4] = wall[5] = plat[4] = plat[5] = 10;
   wall[6] = plat[6] = 10; wall[7] = height; plat[7] = 1;
   platforms[k].exists = k ? row->exists_second : row->exists_first;
   platforms[k].a = height - 1; platforms[k].animation = &animations[k]; animations[k].platform = geometry[k];
  }
  int got;
  if(!row->kind) got = checkwall_below(row->x, row->z, row->altitude);
  else {
   entity *selected = check_platform_below(row->x, row->z, row->altitude, NULL);
   got = selected == &platforms[0] ? 0 : selected == &platforms[1] ? 1 : -1;
  }
  if(got != row->results[era]) {
   fprintf(stderr, "%s revision=%u got=%d expected=%d\n", row->name, revision, got, row->results[era]); abort();
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_altitude=1"); return 0; }
