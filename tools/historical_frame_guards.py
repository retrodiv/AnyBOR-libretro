"""Render native drawing/frame guard contracts with explicit source expectations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from historical_frame_events import render_frame_services
from test_historical_player import function


def render_frame_guards(engine, port, fixture):
    rows = fixture['sources']
    if (not 1 <= len(rows) <= 128 or
            len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique frame contexts required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                len(row['lines']) != 8 or len(row['expressions']) != 8 or
                any(type(v) is not int or not 0 <= v < 1000000 for v in row['lines']) or
                any(not isinstance(v, str) or len(v) > 256 for v in row['expressions']) or
                [bool(v) for v in row['lines']] != [bool(v) for v in row['expressions']]):
            raise ValueError('Explicit own assertion coordinates and expressions required')
    source = (engine / 'openbor.c').read_text()
    macros = re.findall(r'(?m)^#define assert\(value\)[^\n]*', source)
    if len(macros) != 2 or len(set(macros)) != 1:
        raise ValueError('Actual paired production frame assertion hooks required')
    display = function(source, 'display_ents')
    masked = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\r\n]*|/\*.*?\*/',
                    lambda m: re.sub(r'[^\r\n]', ' ', m.group()), display, flags=re.S)
    matches = list(re.finditer(
        r'drawmethod\s*=\s*e->animation->drawmethods\s*\?[^;]*;', masked))
    if len(matches) != 1:
        raise ValueError('One actual active drawing lookup required')
    lookup = display[matches[0].start():matches[0].end()]
    code = render_frame_services(revision=int(fixture['engine']), require_assertions=False)
    code += r'''
#include <setjmp.h>
#include <stdarg.h>
#define CHECK(c) do{if(!(c)){fprintf(stderr,"Frame guard profile=%u case=%u line=%d: %s\n",obor_profile_build,active_case,__LINE__,#c);abort();}}while(0)
static int engine_alive,engine_exit_status,frontend_token;
static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static unsigned stopped,diagnostics,flushes;
static char diagnostic[512];
void co_switch(void *target){
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==1);
 ++stopped;longjmp(frontend_return,1);
}
static int capture_fprintf(FILE *file,const char *format,...){
 CHECK(file==stderr);va_list ap;va_start(ap,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static int capture_fflush(FILE *file){CHECK(file==stderr);++flushes;return 0;}
#define fprintf capture_fprintf
#define fflush capture_fflush
@STOP@
@ASSERT@
#undef fprintf
#undef fflush
#include "obor_frame_assert.h"
#pragma push_macro("assert")
#undef assert
@HOOK@
@SET@
@GET@
@FRAME@
#pragma pop_macro("assert")
static s_drawmethod *display_method(entity *e){s_drawmethod *drawmethod;@LOOKUP@return drawmethod;}
struct context {uint32_t revision;unsigned line[8];const char *expression[8];};
static const struct context contexts[]={@CONTEXTS@};
static s_drawmethod methods[3],baseline[3],*slots[3];
static void setup(void){
 memset(&subject,0,sizeof(subject));memset(&other,0,sizeof(other));
 memset(&animation,0,sizeof(animation));memset(&replacement,0,sizeof(replacement));
 memset(methods,0,sizeof(methods));
 for(unsigned i=0;i<3;++i){methods[i].flag=i+1;slots[i]=&methods[i];}
 memcpy(baseline,methods,sizeof(methods));animation.numframes=3;animation.drawmethods=slots;
 animation.flipframe=animation.jumpframe.f=animation.throwframe=animation.shootframe=animation.tossframe=-1;
 animation.quakeframe.framestart=-2;animation.unsummonframe=-1;
 subject.animation=&animation;subject.animpos=1;subject.nextanim=77;
 replacement.numframes=1;other.animation=&replacement;other.animpos=77;self=&other;level=NULL;
 trace_count=0;engine_alive=1;engine_exit_status=0;stopped=diagnostics=flushes=0;diagnostic[0]=0;
}
static int site_for_case(unsigned which){
 switch(which){
 case 4:case 18:return 0;case 5:return 1;case 6:case 19:return 2;case 7:return 3;
 case 9:case 20:return 4;case 10:return 5;case 11:return 6;case 14:return 7;
 default:return -1;
 }
}
static void execute_case(void){
 switch(active_case){
 case 0:CHECK(getDrawMethod(&animation,0)==&methods[0]);break;
 case 1:setDrawMethod(&animation,1,&methods[2]);CHECK(slots[1]==&methods[2]);break;
 case 2:slots[1]=NULL;CHECK(getDrawMethod(&animation,1)==NULL);break;
 case 3:CHECK(display_method(&subject)==&methods[1]);break;
 case 4:setDrawMethod(&animation,-1,&methods[1]);break;
 case 5:setDrawMethod(NULL,0,&methods[1]);break;
 case 6:setDrawMethod(&animation,1,NULL);CHECK(slots[1]==NULL);break;
 case 7:setDrawMethod(&animation,3,&methods[1]);break;
 case 8:animation.drawmethods=NULL;setDrawMethod(&animation,0,&methods[1]);break;
 case 9:CHECK(getDrawMethod(&animation,-1)==NULL);break;
 case 10:CHECK(getDrawMethod(NULL,0)==NULL);break;
 case 11:CHECK(getDrawMethod(&animation,3)==NULL);break;
 case 12:animation.drawmethods=NULL;CHECK(getDrawMethod(&animation,0)==NULL);break;
 case 13:update_frame(&subject,2);CHECK(subject.animpos==2&&subject.nextanim==77&&!trace_count);break;
 case 14:update_frame(&subject,3);CHECK(subject.animpos==1);break;
 case 15:update_frame(&subject,-1);CHECK(subject.animpos==1);break;
 case 16:update_frame(NULL,0);break;
 case 17:subject.animation=NULL;update_frame(&subject,0);CHECK(subject.animpos==1);break;
 case 18:setDrawMethod(NULL,-1,NULL);break;
 case 19:setDrawMethod(&animation,3,NULL);break;
 case 20:CHECK(getDrawMethod(NULL,-1)==NULL);break;
 case 21:animation.drawmethods=NULL;CHECK(display_method(&subject)==NULL);break;
 default:abort();
 }
}
int main(void){
 for(volatile unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r){
  const struct context *ctx=&contexts[r];obor_profile_build=ctx->revision;
  for(active_case=0;active_case<22;++active_case){
   setup();volatile int site=site_for_case(active_case),expected_stop=0;
#ifndef NDEBUG
   expected_stop=site>=0&&ctx->line[site]!=0;
#endif
   if(!setjmp(frontend_return)){
    execute_case();CHECK(!expected_stop&&!stopped&&!diagnostics&&!flushes);
    CHECK(engine_alive&&self==&other);
   }else{
    CHECK(expected_stop&&stopped==1&&!engine_alive&&engine_exit_status==1);
    const char *name=site<4?"setDrawMethod":site<7?"getDrawMethod":"update_frame";
    char expected[512];snprintf(expected,sizeof(expected),"openbor.c:%u: %s: Assertion `%s' failed.\n",
                              ctx->line[site],name,ctx->expression[site]);
    CHECK(diagnostics==1&&flushes==1&&!strcmp(diagnostic,expected));
    CHECK(self==(site==7?&subject:&other));
   }
   CHECK(slots[0]==&methods[0]&&slots[2]==&methods[2]);
   CHECK(!memcmp(methods,baseline,sizeof(methods))&&other.animpos==77);
  }
 }
 puts("early_frame_guards=1");return 0;
}
'''
    values = dict(STOP=function(port.read_text(), 'borExit'),
                  ASSERT=function(port.read_text(), 'obor_port_assert'), HOOK=macros[0],
                  SET=function(source, 'setDrawMethod'), GET=function(source, 'getDrawMethod'),
                  FRAME=function(source, 'update_frame'), LOOKUP=lookup,
                  CONTEXTS=',\n'.join('{%d,{%s},{%s}}' % (
                      r['revision'], ','.join(map(str, r['lines'])),
                      ','.join(map(json.dumps, r['expressions']))) for r in rows))
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
