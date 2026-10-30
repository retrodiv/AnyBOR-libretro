"""Exercise native playable-list validation and controlled engine stop.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from test_historical_player import function


def render_playable_models(engine, port, fixture):
    rows = fixture['sources']
    if (not 1 <= len(rows) <= 128 or len({r['revision'] for r in rows}) != len(rows) or
            any(type(r['revision']) is not int or not 0 < r['revision'] <= 0xffffffff or
                type(r['original_null_check']) is not bool for r in rows)):
        raise ValueError('Bounded unique own-source selection contexts required')
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    if (not re.search(r'#define\s+shutdown\s+borShutdown', header) or
            not re.search(r'#define\s+exit\s+borExit', header) or
            'exit(status);' not in function(source, 'shutdown')):
        raise ValueError('Actual controlled engine exit mapping required')
    bodies = '\n'.join(function(source, name) for name in
                       ('ParseArgs', 'findarg', 'obor_legacy_arg',
                        'reset_playable_list', 'load_playable_list'))
    macro = re.search(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
    if macro is None:
        raise ValueError('Actual profile argument accessor required')
    missing, cache = fixture['missing_message'], fixture['cache_message']
    for message in (missing, cache):
        if (not isinstance(message, str) or not 1 <= len(message) <= 256 or
                message.count('%s') != 1 or '%' in message.replace('%s', '')):
            raise ValueError('One bounded original model-name diagnostic required')
    limits = fixture.get('argument_limits')
    extra = ''
    checks = '\n'.join('check(%d,%d);' % (r['revision'], r['original_null_check']) for r in rows)
    if limits is not None:
        if not 1 <= len(limits) <= 64:
            raise ValueError('Bounded playable argument samples required')
        tokens = []
        for sample in limits:
            line = sample.get('line')
            if (not isinstance(line, str) or len(line) > 4096 or
                    not re.fullmatch(r'allowselect(?: (?:available|second|enemy))*\n', line)):
                raise ValueError('Terminated valid provider model names required')
            tokens.append(line.split()[1:])
        contexts = []
        for row in rows:
            values = row.get('expected_lookups')
            if (not isinstance(values, list) or len(values) != len(limits) or
                    any(type(n) is not int or not 0 <= n <= len(t)
                        for n, t in zip(values, tokens))):
                raise ValueError('Explicit own lookup counts required')
            outcomes = []
            for n, names in zip(values, tokens):
                selected = set(names[:n])
                outcomes.append('{%d,%d,%d,%d}' % (
                    n, 'available' in selected, 'second' in selected,
                    1 if 'enemy' in selected else 8))
            contexts.append('{%d,{%s}}' % (row['revision'], ','.join(outcomes)))
        extra = r'''
static const char *limit_lines[]={@LINES@};
struct limit_outcome {int calls,available,second,enemy;};
struct limit_context {unsigned revision;struct limit_outcome expected[@COUNT@];};
static const struct limit_context limit_contexts[]={@CONTEXTS@};
static void check_limits(const struct limit_context *ctx){
 obor_profile_build=ctx->revision;
 for(volatile unsigned c=0;c<@COUNT@;++c){
  setup();uncached=0;char line[MAX_ARG_LEN+1];
  assert(strlen(limit_lines[c])<sizeof(line));strcpy(line,limit_lines[c]);
  if(!setjmp(frontend_return))load_playable_list(line);
  const struct limit_outcome *wanted=&ctx->expected[c];
  assert(!stopped&&engine_alive&&engine_exit_status==-1&&!message[0]);
  assert(lookup_calls==wanted->calls&&cache_calls==wanted->calls);
  assert(cache_slots[0].selectable==wanted->available&&cache_slots[1].selectable==wanted->second);
  assert(cache_slots[2].selectable==wanted->enemy&&cache_slots[3].selectable==7);
 }
}
'''.replace('@LINES@', ','.join(json.dumps(s['line']) for s in limits)).replace(
                '@COUNT@', str(len(limits))).replace('@CONTEXTS@', ',\n'.join(contexts))
        checks = 'for(unsigned r=0;r<sizeof(limit_contexts)/sizeof(*limit_contexts);++r)check_limits(&limit_contexts[r]);'
    code = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
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
#define assert(c) do{if(!(c)){fprintf(stderr,"playable models revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;
static s_model models[3];static s_modelcache cache_slots[4];
static unsigned models_cached=4;
static int engine_alive,engine_exit_status,stopped,lookup_calls,cache_calls,uncached;
static int frontend_token;static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static char message[256];
static void co_switch(void *target){assert(target==co_frontend&&!engine_alive&&engine_exit_status==1);++stopped;longjmp(frontend_return,1);}
@STOP@
static void probe_shutdown(int status,char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(message,sizeof(message),format,args);va_end(args);
 assert(n>=0&&(size_t)n<sizeof(message));borExit(status);
}
s_model *findmodel(char *name){
 ++lookup_calls;for(int i=0;i<3;++i)if(!strcmp(name,models[i].name))return &models[i];return NULL;
}
int get_cached_model_index(char *name){
 ++cache_calls;if(uncached)return -1;
 for(int i=0;i<3;++i)if(name==models[i].name)return i;abort();
}
#define shutdown probe_shutdown
@MACRO@
@BODIES@
#undef shutdown
static void setup(void){
 memset(models,0,sizeof(models));memset(cache_slots,0,sizeof(cache_slots));model_cache=cache_slots;
 static char names[3][16]={"available","second","enemy"};
 for(int i=0;i<3;++i){models[i].name=names[i];models[i].type=i<2?TYPE_PLAYER:TYPE_ENEMY;
  cache_slots[i].model=&models[i];cache_slots[i].selectable=i<2?9:8;}
 cache_slots[3].selectable=7;engine_alive=1;engine_exit_status=-1;stopped=lookup_calls=cache_calls=0;message[0]=0;
}
static void check(unsigned revision,int original_null_check){
 obor_profile_build=revision;
 const char *lines[]={"allowselect\n","allowselect available second\n","allowselect enemy\n",
                      "allowselect absent\n","allowselect available absent second\n","allowselect available\n"};
 for(volatile int c=0;c<6;++c){
  setup();uncached=c==5;char line[80];strcpy(line,lines[c]);
  if(!setjmp(frontend_return))load_playable_list(line);
  int fatal=c>=3;
  assert(stopped==fatal&&engine_alive==!fatal&&engine_exit_status==(fatal?1:-1));
  assert(cache_slots[0].selectable==(c==1||c==4)&&cache_slots[1].selectable==(c==1));
  assert(cache_slots[2].selectable==(c==2?1:8)&&cache_slots[3].selectable==7);
  const int lookups[]={0,2,1,1,2,1},cached[]={0,2,1,0,1,1};
  assert(lookup_calls==lookups[c]&&cache_calls==cached[c]);
  if(c==3||c==4){
   /* Defined original diagnostic before removal; candidate stability afterward. */
   assert(!strcmp(message,@MISSING@));
  }else if(c==5)assert(!strcmp(message,@CACHE@));else assert(!message[0]);
 }
}
@LIMITS@int main(void){@CHECKS@ puts("playable_models=1");return 0;}
'''
    values = dict(STOP=function(port.read_text(), 'borExit'), MACRO=macro.group(), BODIES=bodies,
                  MISSING=json.dumps(missing.replace('%s', 'absent')),
                  CACHE=json.dumps(cache.replace('%s', 'available')),
                  LIMITS=extra, CHECKS=checks)
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
