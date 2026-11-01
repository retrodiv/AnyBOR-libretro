/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Compile the entire renderer; observe its real vectors and projection lines.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct trig_point {int angle,x,y;double dx,dy;int expected[3][2];};
#include @RENDERER@
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"trig unit=@UNIT@ line=%d revision=%u\n",__LINE__,obor_profile_build);abort();}}while(0)
static void check_rotation(const uint64_t *expected,const struct trig_point *points,int count,int table){
 @ROT_POINTERS@
 assert(sizeof(double)==sizeof(uint64_t));
 for(int angle=0;angle<360;++angle){
  uint64_t sine,cosine;memcpy(&sine,obor_sin+angle,8);memcpy(&cosine,obor_cos+angle,8);
  assert(sine==expected[angle] && cosine==expected[360+angle]);
 }
 for(int i=0;i<count;++i){
  int angle=points[i].angle,x=points[i].x,y=points[i].y,rx,ry;
  double deltax=points[i].dx,deltay=points[i].dy;
  @ROT_PROJECT@
  assert(rx==points[i].expected[table][0] && ry==points[i].expected[table][1]);
 }
}
static void check_flip(const uint64_t *expected,const struct trig_point *points,int count,int table){
 @FLIP_POINTERS@
 for(int angle=0;angle<360;++angle){
  uint64_t sine,cosine;memcpy(&sine,obor_sin+angle,8);memcpy(&cosine,obor_cos+angle,8);
  assert(sine==expected[angle] && cosine==expected[360+angle]);
 }
 for(int i=0;i<count;++i){
  int angle=points[i].angle,x=points[i].x,y=points[i].y,rx,ry;
  double deltax=points[i].dx,deltay=points[i].dy;
  @FLIP_PROJECT@
  assert(rx==points[i].expected[table][0] && ry==points[i].expected[table][1]);
 }
}
void trig_unit_@UNIT@(const uint64_t *expected,const struct trig_point *points,int count,int table){
 check_rotation(expected,points,count,table);check_flip(expected,points,count,table);
}
