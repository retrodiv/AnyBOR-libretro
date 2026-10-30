"""Check source-owned model diagnostics before owned parser buffers close.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement, continued_macro


def render_model_errors(engine, port, fixture):
    rows, points, samples = fixture['sources'], fixture['points'], fixture['samples']
    if (not 1 <= len(rows) <= 128 or not 1 <= len(points) <= 64 or not 1 <= len(samples) <= 8 or
            len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique model diagnostic contexts required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                any(type(row[k]) is not bool for k in ('common_error', 'alias_arguments')) or
                type(row['buffer_capacity']) is not int or not 1 <= row['buffer_capacity'] <= 65536 or
                len(row['expected']) != len(points) or
                any(len(values) != len(samples) or
                    any(v is not None and (not isinstance(v, str) or len(v) > 65536) for v in values)
                    for values in row['expected'])):
            raise ValueError('Explicit bounded own diagnostic outcomes required')
    source = (engine / 'openbor.c').read_text()
    body = function(source, 'load_cached_model')
    calls = re.findall(r'\bshutdownmessage = (OBOR_MODEL_ERROR\([^\n]+\));', body)
    if len(calls) != len(points) or any(call != p['call'] for call, p in zip(calls, points)):
        raise ValueError('Every native diagnostic expression must match its source contract')
    declaration = re.search(r'char legacy_model_error\[(\d+)\][^;]*;', body)
    if declaration is None or any(r['buffer_capacity'] != int(declaration[1]) for r in rows):
        raise ValueError('Original shutdown and current capture capacities must agree')
    guard = braced_statement(body, 'if(!errorVal)')
    footer = body[body.rindex('lCleanup:'):]
    wrappers = []
    for i, call in enumerate(calls):
        if points[i]['id'] == 'colourmap-duplicate':
            wrappers.append('case %d:{%s}break;' % (i, guard))
        elif not points[i]['id'].startswith('colourmap-'):
            wrappers.append('case %d:shutdownmessage=%s;break;' % (i, call))
    entries = []
    for row in rows:
        entries.append('{%d,%d,{%s}}' % (
            row['revision'], row['alias_arguments'], ','.join(
                '{%s}' % ','.join('NULL' if v is None else json.dumps(v) for v in values)
                for values in row['expected'])))
    sample_data = ','.join('{%s,%s,%s,%d}' % (
        json.dumps(s['filename']), json.dumps(s['value']), json.dumps(s['value2']), s['line'])
        for s in samples)
    remap_point = next(i for i, p in enumerate(points) if p['id'] == 'colourmap-duplicate')
    code = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef shutdown
#undef time
#undef pause
#undef printf
#undef assert
#undef GET_ARG
#define assert(c) do{if(!(c)){fprintf(stderr,"model diagnostics revision=%u point=%u sample=%u line=%d: %s\n",obor_profile_build,active_point,active_sample,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;static unsigned active_point,active_sample;
static s_model dummy;
static uintptr_t owned[2];static unsigned freed;
static int engine_alive,engine_exit_status,stopped,frontend_token;
static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static char message[2048];
static void probe_free(void *p){
 unsigned bit=(uintptr_t)p==owned[0]?1u:(uintptr_t)p==owned[1]?2u:0u;
 assert(bit&&!(freed&bit));freed|=bit;free(p);
}
int obor_preload_active(void){return 0;}
void obor_wait_frame(void){abort();}
static void co_switch(void *target){assert(target==co_frontend&&!engine_alive&&engine_exit_status==1);++stopped;longjmp(frontend_return,1);}
@STOP@
static void probe_shutdown(int status,char *format,...){
 assert(freed==3);va_list args;va_start(args,format);
 int n=vsnprintf(message,sizeof(message),format,args);va_end(args);assert(n>=0&&(size_t)n<sizeof(message));borExit(status);
}
@HELPER@
@MACRO@
#define shutdown probe_shutdown
#define free probe_free
#define GET_ARG(z) ((z)==1?value:value2)
static s_model *error_window(unsigned point,char *filename,const char *a,const char *b,int line,int errorVal,int alias){
 char *buf=strdup(a),*scriptbuf=strdup(b);assert(buf&&scriptbuf);
 owned[0]=(uintptr_t)buf;owned[1]=(uintptr_t)scriptbuf;
 char *value=buf,*value2=alias?buf:scriptbuf,*shutdownmessage=NULL;s_model *newchar=&dummy;
 @DECLARATION@
 switch(point){@WRAPPERS@ default:abort();}
 @FOOTER@
#undef GET_ARG
#undef free
#undef shutdown
struct context {unsigned revision;int alias;const char *expected[@NPOINTS@][@NSAMPLES@];};
static const struct context contexts[]={@CONTEXTS@};
struct sample {char *filename,*a,*b;int line;};static const struct sample samples[]={@SAMPLES@};
static void check(const struct context *ctx,unsigned point,unsigned sample,int result_code,const char *expected){
 obor_profile_build=ctx->revision;active_point=point;active_sample=sample;
 engine_alive=1;engine_exit_status=-1;stopped=0;freed=0;message[0]=0;
 if(!setjmp(frontend_return)){
  const struct sample *s=&samples[sample];
  int alias=ctx->alias&&point==@REMAP@;const char *a=alias?s->b:s->a;
  s_model *r=error_window(point,s->filename,a,s->b,s->line,result_code,alias);
  assert(expected==NULL&&r==&dummy);
 }
 assert(freed==3);
 if(expected)assert(stopped==1&&!engine_alive&&engine_exit_status==1&&!strcmp(message,expected));
 else assert(!stopped&&engine_alive&&engine_exit_status==-1&&!message[0]);
}
int main(void){
 for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r){
  const struct context *ctx=&contexts[r];
  for(unsigned p=0;p<@NPOINTS@;++p)for(unsigned s=0;s<@NSAMPLES@;++s)
   if(ctx->expected[p][s])check(ctx,p,s,0,ctx->expected[p][s]);
  /* The original predicate continues for negative remap results. */
  for(int result=-4;result<0;++result)check(ctx,@REMAP@,0,result,NULL);
 }
 puts("model_errors=1");return 0;
}
'''
    values = dict(STOP=function(port.read_text(), 'borExit'),
                  HELPER=function(source, 'obor_model_error'),
                  MACRO=continued_macro(source, 'OBOR_MODEL_ERROR'),
                  DECLARATION=declaration.group(), WRAPPERS='\n'.join(wrappers), FOOTER=footer,
                  NPOINTS=str(len(points)), NSAMPLES=str(len(samples)),
                  CONTEXTS=',\n'.join(entries), SAMPLES=sample_data, REMAP=str(remap_point))
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
