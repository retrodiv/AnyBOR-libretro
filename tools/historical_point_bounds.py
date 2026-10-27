"""Check finite point coordinates against a complete native drawing unit.

The expected changed pixel is authored independently; -1 means no change.
Allocation uses owned valid screens, not the engine arena.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_point_bounds(*, revision, entries, cases):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            not isinstance(entries, dict) or set(entries) != {'8', '16', '32'} or
            any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_]\w*', v) for v in entries.values()) or
            not isinstance(cases, list) or not 1 <= len(cases) <= 512):
        raise ValueError('Explicit native revision, point entries and bounded observations required')
    rows = []
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {'bits', 'x', 'y', 'expected_index'} or
                type(case['bits']) is not int or case['bits'] not in (8, 16, 32) or
                any(type(case[k]) is not int or not -2 <= case[k] <= 16 for k in ('x', 'y')) or
                type(case['expected_index']) is not int or not -1 <= case['expected_index'] < 48):
            raise ValueError('Finite coordinates and independent changed-pixel index required')
        rows.append('{' + ','.join(str(case[k]) for k in ('bits', 'x', 'y', 'expected_index')) + '}')
    code = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "draw.h"
#undef calloc
#undef free
#undef printf
#undef assert
#ifdef NDEBUG
#error Native point assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native point boundary mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
struct point_case {int bits,x,y,expected_index;};
static const struct point_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct point_case *test=tests+active_case;int bytes=test->bits/8;
  unsigned maximum=test->bits==8?255u:(test->bits==16?65535u:0xffffffu);
  unsigned color=test->bits==8?93u:(test->bits==16?0xb621u:0x1357b9u),expected[48];
  size_t size=offsetof(s_screen,data)+48u*(unsigned)bytes;
  if(size<sizeof(s_screen))size=sizeof(s_screen);
  s_screen *screen=calloc(1,size);assert(screen);
#ifdef screen_magic
  screen->magic=screen_magic;
#endif
  screen->width=8;screen->height=6;
  screen->pixelformat=test->bits==8?PIXEL_8:(test->bits==16?PIXEL_16:PIXEL_32);
  pixelformat=screen->pixelformat;
  for(unsigned p=0;p<48;++p){
   expected[p]=(p*47+13)&maximum;
   if(bytes==1)screen->data[p]=(unsigned char)expected[p];
   else if(bytes==2){uint16_t v=(uint16_t)expected[p];memcpy(screen->data+p*2,&v,2);}
   else {uint32_t v=expected[p];memcpy(screen->data+p*4,&v,4);}
  }
  if(test->bits==8)@ENTRY8@(test->x,test->y,(int)color,screen,0);
  else if(test->bits==16)@ENTRY16@(test->x,test->y,(unsigned short)color,screen,0);
  else @ENTRY32@(test->x,test->y,color,screen,0);
  if(test->expected_index>=0)expected[test->expected_index]=color;
  for(unsigned p=0;p<48;++p){
   unsigned value;
   if(bytes==1)value=screen->data[p];
   else if(bytes==2){uint16_t v;memcpy(&v,screen->data+p*2,2);value=v;}
   else {uint32_t v;memcpy(&v,screen->data+p*4,4);value=v;}
   assert(value==expected[p]);
  }
  free(screen);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    for key, value in dict(REVISION=str(revision) + 'u', CASES=',\n'.join(rows),
                           ENTRY8=entries['8'], ENTRY16=entries['16'], ENTRY32=entries['32']).items():
        code = code.replace('@' + key + '@', value)
    return code
