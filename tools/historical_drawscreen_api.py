"""Observe complete native drawscreen calls and their own plain-method default.

Typed queue services record transport, not rendering, VM or queue execution.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from native_header_fixtures import graphics_refusals, inline_refusals
from test_historical_player import function


def drawscreen_parts(script, variants, engine):
    match = re.search(r'(?ms)^const s_drawmethod plainmethod\s*=\s*\{.*?^\};', engine)
    if match is None:
        raise ValueError('Complete native plain-method declaration required')
    return dict(openbor_drawscreen=function(script, 'openbor_drawscreen'),
                ScriptVariant_IntegerValue=function(variants, 'ScriptVariant_IntegerValue'),
                plainmethod=match[0])


def render_drawscreen_api(parts, *, revision, cases, plain_expectations, signed_bitflags=False,
                          extra_members=None, unused_graphics_inlines=False,
                          unused_inline_declarations=None, perturb_observation=False):
    names = {'openbor_drawscreen', 'ScriptVariant_IntegerValue', 'plainmethod'}
    if (not isinstance(parts, dict) or set(parts) != names or
            any(not isinstance(v, str) or not v.strip() or len(v) > 16384 for v in parts.values()) or
            type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(signed_bitflags) is not bool or type(perturb_observation) is not bool or
            not isinstance(cases, list) or not 1 <= len(cases) <= 2048):
        raise ValueError('Complete native screen call, integer reader, default and bounded observations required')
    members = [] if extra_members is None else extra_members
    if (not isinstance(members, list) or len(members) > 32 or
            any(not isinstance(v, str) or not re.fullmatch(r'[a-z]+(?:\.[a-z]+)?', v) for v in members) or
            len(set(members)) != len(members)):
        raise ValueError('Explicit unique native additional method fields required')
    fields = ('table fp fillcolor flag alpha remap flipx flipy transbg fliprotate rotate scalex scaley '
              'shiftx centerx centery xrepeat yrepeat xspan yspan water.wavetime water.watermode '
              'water.beginsize water.endsize water.wavespeed').split()
    if set(fields) & set(members):
        raise ValueError('Additional fields must not duplicate common method fields')
    compare = ' && '.join('a->' + field + '==b->' + field for field in fields + members)
    if (not isinstance(plain_expectations, dict) or set(plain_expectations) != set(fields + members) or
            any(value is not None and type(value) not in (int, bool) or
                type(value) is int and not -1024 <= value <= 0xffffff
                for value in plain_expectations.values())):
        raise ValueError('Independent default value for every compared native method field required')
    defaults = []
    for field, value in plain_expectations.items():
        expression = '!!plainmethod.' + field if type(value) is bool else 'plainmethod.' + field
        expected = 'NULL' if value is None else str(int(value))
        defaults.append('assert(' + expression + '==' + expected + ');')
    failures = ('none', 'short', 'number', 'alpha', 'screen')
    rows = []
    for case in cases:
        expected_fields = {'format', 'active', 'decimal', 'alpha', 'has_alpha', 'failure',
                           'expected_alpha', 'expected_global', 'message'}
        if (not isinstance(case, dict) or set(case) != expected_fields or
                case['format'] not in ('PIXEL_8', 'PIXEL_16', 'PIXEL_32') or
                any(type(case[k]) is not bool for k in ('active', 'decimal', 'has_alpha', 'expected_global')) or
                any(type(case[k]) is not int or not -64 <= case[k] <= 64 for k in ('alpha', 'expected_alpha')) or
                case['failure'] not in failures or case['failure'] == 'alpha' and not case['has_alpha'] or
                not isinstance(case['message'], str) or len(case['message']) > 512 or
                not case['message'].isascii() or '\0' in case['message'] or
                bool(case['message']) != (case['failure'] != 'none')):
            raise ValueError('Explicit bounded call arguments, method transport and diagnostics required')
        rows.append('{' + ','.join([case['format'], str(int(case['active'])), str(int(case['decimal'])),
                    str(case['alpha']), str(int(case['has_alpha'])), str(failures.index(case['failure'])),
                    str(case['expected_alpha']), str(int(case['expected_global'])),
                    json.dumps(case['message'])]) + '}')
    code = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "openbor.h"
#undef calloc
#undef free
#undef printf
#undef assert
#ifdef NDEBUG
#error Native drawscreen assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native drawscreen API mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
@PLAINMETHOD@
s_drawmethod drawmethod,observed_method;
static s_screen *fixture_screen;
static int calls,diagnostics;
static char diagnostic[1024];
static int same_method(const s_drawmethod *a,const s_drawmethod *b){return @COMPARE@;}
static int observed_printf(const char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(n>=0 && (size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static void observed_queue_screen(int x,int y,int z,s_screen *screen,s_drawmethod *method,int sortid){
 assert(calls++==0 && x==3 && y==5 && z==2 && screen==fixture_screen && sortid==0 && method);
 memcpy(&observed_method,method,sizeof(observed_method));
 if(@PERTURB@)observed_method.alpha^=1;
}
#define spriteq_add_screen observed_queue_screen
#define printf observed_printf
@FUNCTIONS@
#undef printf
struct screen_case {int format,active,decimal,alpha,has_alpha,failure,expected_alpha,expected_global;const char *message;};
static const struct screen_case tests[]={@CASES@};
int main(void){
 @DEFAULTS@
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct screen_case *test=tests+active_case;
  memcpy(&drawmethod,&plainmethod,sizeof(drawmethod));drawmethod.flag=test->active;
  drawmethod.alpha=4;drawmethod.scalex=384;drawmethod.centerx=7;
  drawmethod.fillcolor=27;drawmethod.flipy=@TRUE_FLAG@;drawmethod.water.wavetime=17;
  unsigned char before_method[sizeof(drawmethod)];memcpy(before_method,&drawmethod,sizeof(drawmethod));
  size_t bytes=offsetof(s_screen,data)+8u*6u*4u;if(bytes<sizeof(s_screen))bytes=sizeof(s_screen);
  fixture_screen=calloc(1,bytes);assert(fixture_screen);fixture_screen->width=8;fixture_screen->height=6;
  fixture_screen->pixelformat=test->format;
#ifdef screen_magic
  fixture_screen->magic=screen_magic;
#endif
  ScriptVariant values[5],result,*args[5],*returned=&result;memset(values,0,sizeof(values));memset(&result,0,sizeof(result));
  for(int i=0;i<5;++i){args[i]=values+i;values[i].vt=VT_INTEGER;}
  values[0].vt=VT_PTR;values[0].ptrVal=fixture_screen;
  const int numbers[]={3,5,2,test->alpha};
  for(int i=1;i<5;++i){
   if(test->decimal){values[i].vt=VT_DECIMAL;values[i].dblVal=(DOUBLE)numbers[i-1]+(i==4?0:0.75);}
   else values[i].lVal=numbers[i-1];
  }
  int count=4+test->has_alpha;
  if(test->failure==1)count=3;
  if(test->failure==2)values[1].vt=VT_EMPTY;
  if(test->failure==3)values[4].vt=VT_EMPTY;
  if(test->failure==4)values[0].ptrVal=NULL;
  unsigned char before_args[sizeof(values)];memcpy(before_args,values,sizeof(values));
  calls=diagnostics=0;diagnostic[0]=0;
  HRESULT status=openbor_drawscreen(args,&returned,count);
  assert(status==(test->failure?E_FAIL:S_OK) && returned==NULL);
  assert(!memcmp(before_args,values,sizeof(values)) && !memcmp(before_method,&drawmethod,sizeof(drawmethod)));
  assert(calls==(test->failure==0) && diagnostics==(test->failure!=0) && !strcmp(diagnostic,test->message));
  if(!test->failure){
   s_drawmethod expected;memcpy(&expected,test->expected_global?&drawmethod:&plainmethod,sizeof(expected));
   expected.alpha=test->expected_alpha;if(!test->expected_global)expected.transbg=@TRUE_FLAG@;
   assert(same_method(&observed_method,&expected));
  }
  free(fixture_screen);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values = dict(REVISION=str(revision) + 'u', PLAINMETHOD=parts['plainmethod'], COMPARE=compare,
                  GRAPHICS=graphics_refusals(unused_graphics_inlines),
                  REFUSALS=inline_refusals(unused_inline_declarations, forbidden_names=tuple(names)),
                  FUNCTIONS=parts['ScriptVariant_IntegerValue'] + '\n' + parts['openbor_drawscreen'],
                  CASES=',\n'.join(rows), TRUE_FLAG='-1' if signed_bitflags else '1',
                  DEFAULTS='\n '.join(defaults),
                  PERTURB=str(int(perturb_observation)))
    return re.sub(r'@(' + '|'.join(values) + r')@', lambda match: values[match[1]], code)
