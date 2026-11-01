/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <stdio.h>
struct trig_point {int angle,x,y;double dx,dy;int expected[3][2];};
uint32_t obor_profile_build;
void trig_unit_0(const uint64_t*,const struct trig_point*,int,int);
void trig_unit_1(const uint64_t*,const struct trig_point*,int,int);
void trig_unit_2(const uint64_t*,const struct trig_point*,int,int);
static void (*const units[])(const uint64_t*,const struct trig_point*,int,int)={trig_unit_0,trig_unit_1,trig_unit_2};
static const uint64_t vectors[3][720]={@VECTORS@};
static const struct trig_point points[]={@POINTS@};
static void check(int revision,int table8,int table16,int table32){
 obor_profile_build=(uint32_t)revision;const int tables[]={table8,table16,table32};
 for(int unit=0;unit<3;++unit)units[unit](vectors[tables[unit]],points,sizeof(points)/sizeof(*points),tables[unit]);
 printf("revision=%d vectors=2160 projections=%zu\n",revision,6*sizeof(points)/sizeof(*points));
}
int main(void){@CHECKS@puts("early_sprite_trig=1");return 0;}
