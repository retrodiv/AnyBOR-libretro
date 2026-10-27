"""Observe consecutive initializer calls in complete native drawing units.

Private inputs supply field availability and independent state observations.
This does not render pixels or run the engine allocator or game.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json


def render_draw_initialization(*, revision, draw_source, tint, clipping,
                               global_entry, initial_state, cases, perturb_state=False):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            not isinstance(draw_source, str) or not draw_source.startswith('/') or
            not draw_source.endswith('.c') or len(draw_source) > 4096 or
            any(c in draw_source for c in ('\0', '\n', '\r')) or
            any(type(v) is not bool for v in (tint, clipping, global_entry, perturb_state))):
        raise ValueError('Explicit native revision, complete drawing unit and field availability required')

    def state(values):
        return (isinstance(values, list) and len(values) == 11 and
                all(type(v) is int and -1024 <= v <= 0xffffff for v in values) and
                all(0 <= v <= 255 for v in values[:3]) and
                values[3] in (0, 1) and 0 <= values[4] <= 6 and
                0 <= values[5] <= 0xffffff and values[6] in (0, 1) and
                all(-1024 <= v <= 1024 for v in values[7:]))

    if not state(initial_state) or not isinstance(cases, list) or not 1 <= len(cases) <= 2048:
        raise ValueError('Bounded consecutive calls and complete independent initial state required')
    rows = []
    for case in cases:
        fields = {'format', 'entry', 'method', 'alpha', 'rgb', 'tint', 'clip',
                  'expected_alpha', 'expected_state'}
        if (not isinstance(case, dict) or set(case) != fields or
                case['format'] not in ('8', 'x8', '16', '32') or
                case['entry'] not in ('primitive', 'global') or
                case['entry'] == 'global' and not global_entry or
                type(case['method']) is not int or case['method'] not in (-1, 0, 1) or
                any(type(case[k]) is not int or not -2 <= case[k] <= 7
                    for k in ('alpha', 'expected_alpha')) or
                not isinstance(case['rgb'], list) or len(case['rgb']) != 3 or
                any(type(v) is not int or not 0 <= v <= 255 for v in case['rgb']) or
                not isinstance(case['tint'], list) or len(case['tint']) != 2 or
                any(type(v) is not int for v in case['tint']) or
                not 0 <= case['tint'][0] <= 6 or not 0 <= case['tint'][1] <= 0xffffff or
                not isinstance(case['clip'], list) or len(case['clip']) != 4 or
                any(type(v) is not int or not -32 <= v <= 32 for v in case['clip']) or
                not state(case['expected_state'])):
            raise ValueError('Complete bounded method, format and independent state observation required')
        scalar = [f'PIXEL_{case["format"]}', str(int(case['entry'] == 'global')),
                  str(case['method']), str(case['alpha'])]
        arrays = ['{' + ','.join(map(str, case[k])) + '}' for k in ('rgb', 'tint', 'clip')]
        rows.append('{' + ','.join(scalar + arrays + [str(case['expected_alpha']),
                    '{' + ','.join(map(str, case['expected_state'])) + '}']) + '}')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
/* Include the complete unit to call its actual file-local draw_init. */
#include @DRAW_SOURCE@
#ifdef NDEBUG
#error Native initialization assertions must remain enabled
#endif
#undef printf
#undef assert
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native draw initialization mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
extern unsigned channelr,channelg,channelb;
extern int usechannel;
#if @TINT@
extern unsigned tintmode,tintcolor;
#endif
#if @CLIPPING@
extern int useclip,clipx1,clipy1,clipx2,clipy2;
#endif
static const int initial[]={@INITIAL@};
struct initialization_case {
 int format,entry,method,alpha,rgb[3],tint[2],clip[4],expected_alpha,state[11];
};
static const struct initialization_case tests[]={@CASES@};
int main(void){
 channelr=(unsigned)initial[0];channelg=(unsigned)initial[1];channelb=(unsigned)initial[2];usechannel=initial[3];
#if @TINT@
 tintmode=(unsigned)initial[4];tintcolor=(unsigned)initial[5];
#endif
#if @CLIPPING@
 useclip=initial[6];clipx1=initial[7];clipy1=initial[8];clipx2=initial[9];clipy2=initial[10];
#endif
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct initialization_case *test=tests+active_case;
  s_drawmethod method;memset(&method,0,sizeof(method));
  method.flag=test->method==1;method.alpha=test->alpha;
  method.channelr=(unsigned)test->rgb[0];method.channelg=(unsigned)test->rgb[1];method.channelb=(unsigned)test->rgb[2];
#if @TINT@
  method.tintmode=(unsigned)test->tint[0];method.tintcolor=(unsigned)test->tint[1];
#endif
#if @CLIPPING@
  method.clipx=test->clip[0];method.clipy=test->clip[1];method.clipw=test->clip[2];method.cliph=test->clip[3];
#endif
  s_drawmethod before=method,*selected=test->method<0?NULL:&method;
  screenformat=test->format;int alpha=0;
#if @GLOBAL_ENTRY@
  if(test->entry)drawmethod_global_init(selected);else
#endif
  alpha=draw_init(selected);
  assert(alpha==test->expected_alpha && memcmp(&method,&before,sizeof(method))==0);
  if(@PERTURB@ && active_case==0)channelr^=1;
  assert(channelr==(unsigned)test->state[0] && channelg==(unsigned)test->state[1] &&
         channelb==(unsigned)test->state[2] && usechannel==test->state[3]);
#if @TINT@
  assert(tintmode==(unsigned)test->state[4] && tintcolor==(unsigned)test->state[5]);
#endif
#if @CLIPPING@
  assert(useclip==test->state[6] && clipx1==test->state[7] && clipy1==test->state[8] &&
         clipx2==test->state[9] && clipy2==test->state[10]);
#endif
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''.replace('@DRAW_SOURCE@', json.dumps(draw_source)).replace('@REVISION@', str(revision) + 'u').replace(
        '@TINT@', str(int(tint))).replace('@CLIPPING@', str(int(clipping))).replace(
        '@GLOBAL_ENTRY@', str(int(global_entry))).replace('@INITIAL@', ','.join(map(str, initial_state))).replace(
        '@CASES@', ',\n'.join(rows)).replace('@PERTURB@', str(int(perturb_state)))
