"""Render complete primitive script calls with native variant/graphics records.

Typed observers record alpha or method transport and unchanged arguments.
They do not execute the queue, rasterizer, script VM or a game.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from native_header_fixtures import graphics_refusals, inline_refusals

OPERATIONS=('drawbox','drawboxtoscreen','drawline','drawlinetoscreen','drawdot','drawdottoscreen')


def render_primitive_api(parts, *, revision, method_arguments, cases,
                         signed_bitflags=False, unused_graphics_inlines=False,
                         unused_inline_declarations=None):
    names={'openbor_'+name for name in OPERATIONS}|{'ScriptVariant_IntegerValue'}
    if (not isinstance(parts,dict) or set(parts)!=names or
            any(not isinstance(v,str) or not v.strip() or len(v)>16384 for v in parts.values())):
        raise ValueError('Complete bounded primitive calls and native integer reader required')
    if (type(revision) is not int or not 0<revision<=0xffffffff or
            type(method_arguments) is not bool or type(signed_bitflags) is not bool):
        raise ValueError('Explicit native revision and alpha/method signature required')
    if not isinstance(cases,list) or not 1<=len(cases)<=2048:
        raise ValueError('Bounded independent primitive call expectations required')
    rows=[]
    failures=('none','short','number','alpha','screen')
    for case in cases:
        fields={'operation','format','active','decimal','alpha','has_alpha','failure',
                'expected_alpha','expected_method','expected_flag','message'}
        if not isinstance(case,dict) or set(case)!=fields:
            raise ValueError('Complete native arguments, method and diagnostic observations required')
        if (case['operation'] not in OPERATIONS or case['format'] not in ('PIXEL_8','PIXEL_16','PIXEL_32') or
                any(type(case[k]) is not bool for k in ('active','decimal','has_alpha','expected_method','expected_flag')) or
                any(type(case[k]) is not int or not -64<=case[k]<=64 for k in ('alpha','expected_alpha')) or
                case['failure'] not in failures or (case['failure']=='screen' and not case['operation'].endswith('toscreen')) or
                (case['failure']=='alpha' and not case['has_alpha']) or
                not isinstance(case['message'],str) or len(case['message'])>512 or not case['message'].isascii() or
                '\0' in case['message'] or bool(case['message'])!=(case['failure']!='none')):
            raise ValueError('Bounded valid native call and independently expected transport required')
        values=[str(OPERATIONS.index(case['operation'])),case['format'],
                str(int(case['active'])),str(int(case['decimal'])),str(case['alpha']),
                str(int(case['has_alpha'])),str(failures.index(case['failure'])),str(case['expected_alpha']),
                str(int(case['expected_method'])),str(int(case['expected_flag'])),json.dumps(case['message'])]
        rows.append('{'+','.join(values)+'}')
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#ifdef NDEBUG
#error Native primitive assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native primitive API mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
#define METHOD_ARGUMENTS @METHOD_ARGUMENTS@
const s_drawmethod plainmethod={.flag=@TRUE_FLAG@,.alpha=-1,.scalex=256,.scaley=256,
 .fillcolor=0,.centerx=0,.centery=0,.flipx=0,.flipy=0};
s_drawmethod drawmethod;
static s_screen fixture_screen;
static int calls,observed_operation,observed[6],observed_alpha,observed_global,observed_flag;
static unsigned diagnostics;
static char diagnostic[1024];
static int observed_printf(const char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(n>=0 && (size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static void observe(int operation,int x,int y,int a,int b,int z,int color,int alpha,const s_drawmethod *method){
 assert(calls++==0);observed_operation=operation;
 observed[0]=x;observed[1]=y;observed[2]=a;observed[3]=b;observed[4]=z;observed[5]=color;
 if(method){
  observed_alpha=method->alpha;observed_flag=!!method->flag;
  observed_global=(method->scalex==384 && method->centerx==7 && method->fillcolor==27 && method->flipy);
  if(!observed_global)assert(method->scalex==256 && method->centerx==0 && method->fillcolor==0 && !method->flipy);
 }else{
  observed_alpha=alpha;observed_flag=alpha>0;observed_global=0;
 }
}
#if METHOD_ARGUMENTS
static void queue_box(int x,int y,int w,int h,int z,int c,s_drawmethod *m){observe(0,x,y,w,h,z,c,0,m);}
static void queue_line(int x,int y,int a,int b,int z,int c,s_drawmethod *m){observe(2,x,y,a,b,z,c,0,m);}
static void queue_dot(int x,int y,int z,int c,s_drawmethod *m){observe(4,x,y,0,0,z,c,0,m);}
static void screen_box(int x,int y,int w,int h,int c,s_screen *s,s_drawmethod *m){assert(s==&fixture_screen);observe(1,x,y,w,h,0,c,0,m);}
static void screen_line(int x,int y,int a,int b,int c,s_screen *s,s_drawmethod *m){assert(s==&fixture_screen);observe(3,x,y,a,b,0,c,0,m);}
static void screen_dot(unsigned x,unsigned y,int c,s_screen *s,s_drawmethod *m){assert(s==&fixture_screen);observe(5,(int)x,(int)y,0,0,0,c,0,m);}
#else
static void queue_box(int x,int y,int w,int h,int z,int c,int alpha){observe(0,x,y,w,h,z,c,alpha,NULL);}
static void queue_line(int x,int y,int a,int b,int z,int c,int alpha){observe(2,x,y,a,b,z,c,alpha,NULL);}
static void queue_dot(int x,int y,int z,int c,int alpha){observe(4,x,y,0,0,z,c,alpha,NULL);}
#define SCREEN_METHODS(suffix,type,format) \
 static void screen_box##suffix(int x,int y,int w,int h,type c,s_screen *s,int alpha){assert(s==&fixture_screen && s->pixelformat==format);observe(1,x,y,w,h,0,c,alpha,NULL);} \
 static void screen_line##suffix(int x,int y,int a,int b,type c,s_screen *s,int alpha){assert(s==&fixture_screen && s->pixelformat==format);observe(3,x,y,a,b,0,c,alpha,NULL);} \
 static void screen_dot##suffix(unsigned x,unsigned y,type c,s_screen *s,int alpha){assert(s==&fixture_screen && s->pixelformat==format);observe(5,(int)x,(int)y,0,0,0,c,alpha,NULL);}
SCREEN_METHODS(8,int,PIXEL_8)
SCREEN_METHODS(16,unsigned short,PIXEL_16)
SCREEN_METHODS(32,unsigned,PIXEL_32)
#undef SCREEN_METHODS
#endif
#define spriteq_add_box queue_box
#define spriteq_add_line queue_line
#define spriteq_add_dot queue_dot
#if METHOD_ARGUMENTS
#define putbox screen_box
#define putline screen_line
#define putpixel screen_dot
#else
#define drawbox screen_box8
#define drawbox16 screen_box16
#define drawbox32 screen_box32
#define line screen_line8
#define line16 screen_line16
#define line32 screen_line32
#define putpixel screen_dot8
#define putpixel16 screen_dot16
#define putpixel32 screen_dot32
#endif
#define printf observed_printf
@FUNCTIONS@
#undef printf
typedef HRESULT (*entry_fn)(ScriptVariant**,ScriptVariant**,int);
static entry_fn entries[]={openbor_drawbox,openbor_drawboxtoscreen,openbor_drawline,
 openbor_drawlinetoscreen,openbor_drawdot,openbor_drawdottoscreen};
struct primitive_case {int operation,format,active,decimal,alpha,has_alpha,failure,expected_alpha,expected_global,expected_flag;const char *message;};
static const struct primitive_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct primitive_case *test=tests+active_case;int screen=test->operation&1,dot=test->operation>=4;
  int minimum=dot?4:6,count=minimum+test->has_alpha;
  memset(&drawmethod,0,sizeof(drawmethod));drawmethod.flag=test->active;
  drawmethod.scalex=384;drawmethod.centerx=7;drawmethod.fillcolor=27;drawmethod.flipy=@TRUE_FLAG@;
  unsigned char before_method[sizeof(drawmethod)];memcpy(before_method,&drawmethod,sizeof(drawmethod));
  memset(&fixture_screen,0,sizeof(fixture_screen));fixture_screen.pixelformat=test->format;
  ScriptVariant values[7],result,*arguments[7],*returned=&result;
  memset(values,0,sizeof(values));memset(&result,0,sizeof(result));
  const int full[6]={3,5,4,6,2,27},single[4]={3,5,2,27};
  int expected[6]={3,5,dot?0:4,dot?0:6,screen?0:2,27};
  for(int i=0;i<7;++i){arguments[i]=values+i;values[i].vt=VT_INTEGER;}
  int number=0;
  for(int i=0;i<minimum;++i){
   if(i==0 && screen){values[i].vt=VT_PTR;values[i].ptrVal=&fixture_screen;continue;}
   int value=dot?single[number++]:full[number++];
   if(screen && i==minimum-1)value=27;
   if(test->decimal){values[i].vt=VT_DECIMAL;values[i].dblVal=(DOUBLE)value+0.75;}
   else values[i].lVal=value;
  }
  values[minimum].lVal=test->alpha;
  if(test->decimal){values[minimum].vt=VT_DECIMAL;values[minimum].dblVal=(DOUBLE)test->alpha;}
  if(test->failure==1)count=minimum-1;
  if(test->failure==2)values[screen?1:0].vt=VT_EMPTY;
  if(test->failure==3)values[minimum].vt=VT_EMPTY;
  if(test->failure==4)values[0].ptrVal=NULL;
  unsigned char before[sizeof(values)];memcpy(before,values,sizeof(values));
  calls=0;diagnostics=0;diagnostic[0]='\0';
  HRESULT status=entries[test->operation](arguments,&returned,count);
  assert(status==(test->failure?E_FAIL:S_OK) && returned==NULL);
  assert(!memcmp(before,values,sizeof(values)) && !memcmp(before_method,&drawmethod,sizeof(drawmethod)));
  assert(diagnostics==(unsigned)(test->failure!=0) && !strcmp(diagnostic,test->message));
  assert(calls==(test->failure==0));
  if(!test->failure){
   assert(observed_operation==test->operation && !memcmp(observed,expected,sizeof(expected)));
   assert(observed_alpha==test->expected_alpha && observed_global==test->expected_global && observed_flag==test->expected_flag);
  }
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values=dict(REVISION=str(revision)+'u',METHOD_ARGUMENTS=str(int(method_arguments)),
                TRUE_FLAG='-1' if signed_bitflags else '1',CASES=',\n'.join(rows),
                GRAPHICS=graphics_refusals(unused_graphics_inlines),
                REFUSALS=inline_refusals(unused_inline_declarations,forbidden_names=tuple(names)),
                FUNCTIONS='\n'.join(parts[name] for name in sorted(parts)))
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
