"""Check source-owned level diagnostics through bounded cleanup and core stop.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement, continued_macro


def render_level_errors(engine, port, fixture):
    rows, points, samples = fixture['sources'], fixture['points'], fixture['samples']
    if (not 1 <= len(rows) <= 128 or not 1 <= len(points) <= 64 or not 1 <= len(samples) <= 8 or
            len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique level diagnostic contexts required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                any(type(row[k]) is not bool for k in ('common_error', 'grouped_scripts')) or
                type(row['buffer_capacity']) is not int or not 1 <= row['buffer_capacity'] <= 65536 or
                len(row['expected']) != len(points) or
                any(len(values) != len(samples) or
                    any(v is not None and (not isinstance(v, str) or len(v) > 65536) for v in values)
                    for values in row['expected'])):
            raise ValueError('Explicit bounded own diagnostic outcomes required')
    source = (engine / 'openbor.c').read_text()
    body = function(source, 'load_level')
    calls = re.findall(r'\berrormessage = (OBOR_LEVEL_ERROR\([^\n]+\));', body)
    literals = [p for p in points if p['kind'] == 'literal']
    if len(calls) != len(literals) or sorted(calls) != sorted(p['call'] for p in literals):
        raise ValueError('Every literal diagnostic must match its actual source call')
    declaration = re.search(r'char legacy_level_error\[(\d+)\][^;]*;', body)
    if declaration is None or any(r['buffer_capacity'] != int(declaration[1]) for r in rows):
        raise ValueError('Original and current diagnostic capacities must agree')
    spawn_start = body.index('errormessage = llHandleCommandSpawnscript(&arglist, &next);')
    spawn_guard = braced_statement(body[spawn_start:], 'if (errormessage)')
    spawn_body = function(source, 'llHandleCommandSpawnscript')
    spawn_messages = re.findall(r'\bresult = ("[^"\n]+");', spawn_body)
    if spawn_messages != [json.dumps(p['modern']) for p in points if p['kind'] == 'spawn']:
        raise ValueError('Native spawn helper failure results must be complete')
    wrappers = []
    for i, p in enumerate(points):
        if p['kind'] == 'literal':
            action = 'errormessage=' + p['call'] + ';'
        elif p['kind'] == 'script':
            if p['call'] not in body or not re.fullmatch(r'CMD_LEVEL_[A-Z]+SCRIPT', p['command']):
                raise ValueError('Script error calls must use actual command dispatch')
            action = 'cmd=' + p['command'] + ';errormessage=' + p['call'] + ';'
        elif p['kind'] == 'spawn':
            if p['call'] not in spawn_guard:
                raise ValueError('Actual spawn failure forwarding required')
            action = 'errormessage=' + json.dumps(p['modern']) + ';' + spawn_guard
        else:
            raise ValueError('Unknown diagnostic source kind')
        wrappers.append('case %d:{%s}break;' % (i, action))
    entries = []
    for row in rows:
        entries.append('{%d,{%s}}' % (row['revision'], ','.join(
            '{%s}' % ','.join(('NULL' if v is None else json.dumps(v)) for v in values) for values in row['expected'])))
    sample_data = ','.join('{%s,%s,%d,%d,%d}' % (
        json.dumps(s['filename']), json.dumps(s['value']), s['line'], s['j'], s['panels'])
        for s in samples)
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
#include "source/gamelib/commands.h"
#undef exit
#undef shutdown
#undef time
#undef pause
#undef printf
#undef assert
#undef GET_ARG
#define assert(c) do{if(!(c)){fprintf(stderr,"level diagnostics revision=%u point=%u sample=%u line=%d: %s\n",obor_profile_build,active_point,active_sample,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;static unsigned active_point,active_sample;
static uintptr_t owned;static unsigned freed,preload_ends;
static int engine_alive,engine_exit_status,stopped,frontend_token;
static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static char message[2048];
static void probe_free(void *p){assert((uintptr_t)p==owned&&!freed);++freed;free(p);}
void obor_preload_end(void){++preload_ends;}
static void co_switch(void *target){assert(target==co_frontend&&!engine_alive&&engine_exit_status==1);++stopped;longjmp(frontend_return,1);}
@STOP@
static void probe_shutdown(int status,char *format,...){
 assert(freed==1);va_list args;va_start(args,format);
 int n=vsnprintf(message,sizeof(message),format,args);va_end(args);assert(n>=0&&(size_t)n<sizeof(message));borExit(status);
}
@HELPERS@
/* The panel assertion branch has its separate complete-route contract. */
void obor_port_assert(int value,const char *assertion,const char *func,const char *file,int line){abort();}
@IMAGE_ASSERT@
@MACRO@
#define shutdown probe_shutdown
#define free probe_free
#define GET_ARG(z) (value)
static void error_window(unsigned point,char *filename,const char *input,int line,int j,int panels_loaded){
 char *buf=strdup(input);assert(buf);owned=(uintptr_t)buf;
 char *value=buf,*errormessage=NULL;int cmd=0;unsigned obor_panel_assert=0;
 @DECLARATION@
 switch(point){@WRAPPERS@ default:break;}
 @FOOTER@
#undef GET_ARG
#undef free
#undef shutdown
struct context {unsigned revision;const char *expected[@NPOINTS@][@NSAMPLES@];};
static const struct context contexts[]={@CONTEXTS@};
struct sample {char *filename,*value;int line,j,panels;};static const struct sample samples[]={@SAMPLES@};
static void check(const struct context *ctx,unsigned point,unsigned sample,const char *expected){
 obor_profile_build=ctx->revision;active_point=point;active_sample=sample;
 engine_alive=1;engine_exit_status=-1;stopped=0;freed=0;preload_ends=0;message[0]=0;
 if(!setjmp(frontend_return)){
  const struct sample *s=&samples[sample];
  error_window(point,s->filename,s->value,s->line,s->j,s->panels);
  assert(expected==NULL);
 }
 assert(freed==1);
 if(expected)assert(stopped==1&&!engine_alive&&engine_exit_status==1&&!strcmp(message,expected)&&!preload_ends);
 else assert(!stopped&&engine_alive&&engine_exit_status==-1&&!message[0]&&preload_ends==1);
}
int main(void){
 for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r){
  const struct context *ctx=&contexts[r];
  for(unsigned p=0;p<@NPOINTS@;++p)for(unsigned s=0;s<@NSAMPLES@;++s)
   if(ctx->expected[p][s])check(ctx,p,s,ctx->expected[p][s]);
  check(ctx,@NPOINTS@,0,NULL);
 }
 puts("level_errors=1");return 0;
}
'''
    values = dict(STOP=function(port.read_text(), 'borExit'),
                  IMAGE_ASSERT=(engine / 'source/gamelib/obor_image_assert.h').read_text(),
                  HELPERS='\n'.join(function(source, n) for n in
                                    ('obor_level_error', 'obor_level_script_error', 'obor_level_spawn_error')),
                  MACRO=continued_macro(source, 'OBOR_LEVEL_ERROR'),
                  DECLARATION=declaration.group(), WRAPPERS='\n'.join(wrappers),
                  FOOTER=body[body.rindex('lCleanup:'):], NPOINTS=str(len(points)),
                  NSAMPLES=str(len(samples)), CONTEXTS=',\n'.join(entries), SAMPLES=sample_data)
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
