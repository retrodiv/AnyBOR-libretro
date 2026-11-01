/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "ScriptVariant.h"
#undef exit
#define MIN_INT (int)0x80000000
uint32_t obor_profile_build;
static s_level instance, *level;
static entity platforms[2], *ent_list[2] = { &platforms[0], &platforms[1] };
static s_anim animations[2];
static float geometry[2][1][8];
static int ent_max = 2;
@FUNCTIONS@
static HRESULT probe_decimal(ScriptVariant *value, DOUBLE *out) {
 if(value->vt != VT_DECIMAL) return E_FAIL;
 *out = value->dblVal; return S_OK;
}
static void probe_type(ScriptVariant *value, VARTYPE type) { value->vt = type; }
#define ScriptVariant_DecimalValue probe_decimal
#define ScriptVariant_ChangeType probe_type
@SCRIPT@
typedef struct {
 const char *name; int exclude, present, first_exists, second_exists;
 int results[2][5];
} scenario;
static const scenario cases[] = { @CASES@ };
static int identity(entity *e) {
 if(!e) return -1;
 assert(e == &platforms[0] || e == &platforms[1]); return e == &platforms[0] ? 0 : 1;
}
static void check(unsigned revision, unsigned era) {
 obor_profile_build = revision;
 for(unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
  const scenario *row = &cases[i];
  memset(&instance, 0, sizeof(instance)); memset(platforms, 0, sizeof(platforms));
  memset(animations, 0, sizeof(animations)); memset(geometry, 0, sizeof(geometry));
  level = row->present ? &instance : NULL;
  for(int k = 0; k < 2; k++) {
   float *g = geometry[k][0]; g[2] = g[3] = -10; g[4] = g[5] = 10; g[6] = g[7] = 10;
   platforms[k].a = k ? 15 : 10; platforms[k].animation = &animations[k]; animations[k].platform = geometry[k];
   platforms[k].exists = k ? row->second_exists : row->first_exists;
  }
  entity *exclude = row->exclude < 0 ? NULL : &platforms[row->exclude];
  int got[] = {identity(check_platform(0, -5, exclude)),
   identity(check_platform_between(0, -5, 19, 15, exclude)),
   identity(check_platform_above(0, -5, 10, exclude)),
   identity(check_platform_below(0, -5, 30, exclude)), testplatform(&platforms[0], 0, -5, exclude)};
  for(int k = 0; k < 5; k++) if(got[k] != row->results[era][k]) {
   fprintf(stderr, "%s revision=%u query=%d got=%d expected=%d\n",row->name,revision,k,got[k],row->results[era][k]); abort();
  }
  /* The script query passes NULL, independently of the native exclusion above. */
  ScriptVariant args[3], output, *in[] = {&args[0], &args[1], &args[2]}, *out = &output;
  memset(args, 0, sizeof(args)); memset(&output, 0, sizeof(output));
  for(int k = 0; k < 3; k++) args[k].vt = VT_DECIMAL;
  args[0].dblVal = 0; args[1].dblVal = -5; args[2].dblVal = 30;
  assert(openbor_checkplatformbelow(in, &out, 3) == S_OK && out == &output && output.vt == VT_PTR);
  assert(output.ptrVal == check_platform_below(0, -5, 30, NULL));
  out = &output; assert(openbor_checkplatformbelow(in, &out, 2) == E_FAIL && !out);
  for(int k = 0; k < 3; k++) {
   args[k].vt = VT_EMPTY; out = &output;
   assert(openbor_checkplatformbelow(in, &out, 3) == S_OK && out == &output && output.vt == VT_DECIMAL && output.dblVal == 0);
   args[k].vt = VT_DECIMAL;
  }
 }
}
int main(void) { @CHECKS@ puts("early_platform_exclude=1"); return 0; }
