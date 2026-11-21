/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <math.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#include "anybor_endian.h"
#undef assert
#define assert(x) ((x)?(void)0:__builtin_trap())
uint32_t obor_profile_build;
s_savedata savedata;
s_playercontrols default_control;
int default_keys[MAX_BTN_NUM];
int PLAYER_MIN_Z=200;
unsigned long long obor_clock_us;
METHODS
int main(void) {
 for(unsigned value=0;value<65536;++value) {
  unsigned expected=(value>>8)|((value&255)<<8);
  assert(Swap16(value)==expected && Swap16(Swap16(value))==value);
 }
 static const struct { unsigned profile; const char *version; } cases[] = {
  {6997, "v3.0 Build 6997"},
  {7039, "v3.0 Build 7039 (commit hash: be46a55)"},
  {7086, "v3.0 Build 7086 (commit hash: 7a45a22)"},
  {7091, "v3.0 Build 7091 (commit hash: 8ad6874)"},
  {7123, "v3.0 Build 7123 (commit hash: f5261e7)"},
  {7142, VERSION}
 };
 for(unsigned p=0;p<sizeof(cases)/sizeof(cases[0]);++p) {
  obor_profile_build=cases[p].profile;memset(&savedata,0xa5,sizeof(savedata));clearsettings();
  assert(savedata.vsync==(obor_profile_build==7123?0:1));
  assert(savedata.compatibleversion==COMPATIBLEVERSION);
  int swapped_layers=obor_profile_build==7091||obor_profile_build==7123;
  assert(SHADOW_Z==PLAYER_MIN_Z-(swapped_layers?47:48));
  assert(NEONPANEL_Z==PLAYER_MIN_Z-(swapped_layers?48:47));
  assert(!strcmp(obor_profile_version_string(),cases[p].version));
  assert(strstr(obor_profile_shutdown_message(),cases[p].version));
  for(int player=0;player<4;++player)for(int button=0;button<SDID_ESC;++button) {
   assert(savedata.keys[player][button]==savedata.keys[0][button]+player*OBOR_KEYSPAN);
   assert(savedata.keys[player][button]!=CONTROL_NONE);
  }
  obor_clock_us=0;
  for(int frame=0;frame<256;++frame) { obor_clock_us+=16666;unsigned fps=getFPS();if(frame>=128)assert(fps==60); }
 }
}
