/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <math.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#include "obor_endian.h"
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
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p) {
  obor_profile_build=profiles[p];memset(&savedata,0xa5,sizeof(savedata));clearsettings();
  assert(savedata.vsync==(profiles[p]==7123?0:1));
  assert(savedata.compatibleversion==COMPATIBLEVERSION);
  assert(SHADOW_Z==PLAYER_MIN_Z-(profiles[p]==7123?47:48));
  assert(NEONPANEL_Z==PLAYER_MIN_Z-(profiles[p]==7123?48:47));
  const char *version=p==0?"v3.0 Build 7086 (commit hash: 7a45a22)":p==1?"v3.0 Build 7123 (commit hash: f5261e7)":VERSION;
  assert(!strcmp(obor_profile_version_string(),version));
  assert(strstr(obor_profile_shutdown_message(),version));
  for(int player=0;player<4;++player)for(int button=0;button<SDID_ESC;++button) {
   assert(savedata.keys[player][button]==savedata.keys[0][button]+player*OBOR_KEYSPAN);
   assert(savedata.keys[player][button]!=CONTROL_NONE);
  }
  obor_clock_us=0;
  for(int frame=0;frame<256;++frame) { obor_clock_us+=16666;unsigned fps=getFPS();if(frame>=128)assert(fps==60); }
 }
}
