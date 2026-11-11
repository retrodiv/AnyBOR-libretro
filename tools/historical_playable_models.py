"""Exercise native playable-list validation and controlled engine stop.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from test_historical_player import function


def render_playable_models(engine, port, fixture):
    rows = fixture['sources']
    identities = [r.get('profile', r['revision']) for r in rows]
    if (not 1 <= len(rows) <= 128 or
            any(type(identity) not in (str, int) or isinstance(identity, str) and
                not 1 <= len(identity) <= 64 for identity in identities) or
            len(set(identities)) != len(rows) or
            any(type(r['revision']) is not int or not 0 < r['revision'] <= 0xffffffff or
                type(r.get('original_null_check', False)) is not bool for r in rows)):
        raise ValueError('Bounded unique own-source selection contexts required')
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    globals_header = engine / 'source/globals.h'
    if globals_header.is_file():
        header += '\n'+globals_header.read_text(encoding='latin1')
    if re.search(r'(?m)^void borShutdown\(', source):
        stop_source = function(source, 'borShutdown')
        mapped_stop = 'borExit(status);' in stop_source
    else:
        stop_source = function(source, 'shutdown')
        mapped_stop = (re.search(r'#define\s+shutdown\s+borShutdown', header) and
                       re.search(r'#define\s+exit\s+borExit', header) and
                       'exit(status);' in stop_source)
    if not mapped_stop:
        raise ValueError('Actual controlled engine exit mapping required')
    sequential_reader = 's_command_argument_reader reader;' in function(source, 'load_playable_list')
    stored_declarations = re.findall(
        r'(?m)^[ \t]*(?:static[ \t]+)?char[ \t]+(?:\*[ \t]*)?allowselect_args'
        r'(?:\[[^\]\n]+\])?(?:[ \t]*=[^;\n]+)?;', source)
    if len(stored_declarations) > 1:
        raise ValueError('One native stored-selection declaration required')
    stored_declaration = stored_declarations[0] if stored_declarations else ''
    stored_pointer = bool(re.search(r'\*[ \t]*allowselect_args', stored_declaration))
    reader_declarations = ''
    if sequential_reader:
        declarations = []
        for name in ['s_command_token', 's_command_token_reader', 's_command_argument_reader']:
            matches = re.findall(r'typedef struct '+name+r'\s*\{[^{}]*\}\s*'+name+r';', source)
            if len(matches) != 1:
                raise ValueError('Actual sequential argument-reader declaration required')
            declarations.append(matches[0])
        limit = re.search(r'(?m)^#define MAX_COMMAND_ARGUMENT_LEN\s+([0-9]+)', source)
        if limit is None or not 1 <= int(limit[1]) <= 4096:
            raise ValueError('Bounded actual command argument capacity required')
        reader_declarations = limit[0]+'\n'+'\n'.join(declarations)
        names = ['command_token_update_quote_state', 'command_token_reader_next',
                 'command_token_copy_value', 'command_argument_reader_initialize',
                 'command_argument_reader_next', 'append_command_argument']
    else:
        names = ['ParseArgs', 'findarg']
        if re.search(r'\bobor_legacy_arg\(', source):
            names.append('obor_legacy_arg')
    bodies = '\n'.join(function(source, name) for name in
                       names+['reset_playable_list', 'load_playable_list'])
    macro = re.search(r'(?m)^#define GET_ARG\(z\)[^\n]*', source+'\n'+header)
    if macro is None:
        raise ValueError('Actual profile argument accessor required')
    missing, cache = fixture['missing_message'], fixture['cache_message']
    for message in (missing, cache):
        if (not isinstance(message, str) or not 1 <= len(message) <= 256 or
                message.count('%s') != 1 or '%' in message.replace('%s', '')):
            raise ValueError('One bounded original model-name diagnostic required')
    limits = fixture.get('argument_limits')
    extra = ''
    if any(type(r.get('reset_all_on_zero', False)) is not bool for r in rows):
        raise ValueError('Explicit source-derived playable reset policy required')
    returning = fixture.get('returning_stop_control', False)
    if type(returning) is not bool:
        raise ValueError('Returning-stop control must be explicit')
    checks = '\n'.join('check(%d,%d);' % (r['revision'], r.get('reset_all_on_zero', False))
                       for r in rows)
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
    emit_counts = fixture.get('emit_counts', False)
    if type(emit_counts) is not bool:
        raise ValueError('Explicit observation output mode required')
    code = r'''
#include <assert.h>
#include <stdbool.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef exit
#undef shutdown
#undef time
#undef pause
#undef printf
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"playable models revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;
s_modelcache *model_cache;
@READER_GLOBALS@
static s_model models[3];static s_modelcache cache_slots[4];
static unsigned models_cached=4;
static int engine_alive,engine_exit_status,stopped,lookup_calls,cache_calls,uncached,return_stop;
static unsigned scenarios;
static int frontend_token;static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static char message[1024];
static void co_switch(void *target){assert(target==co_frontend&&!engine_alive&&engine_exit_status==1);++stopped;longjmp(frontend_return,1);}
@STOP@
static void probe_shutdown(int status,char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(message,sizeof(message),format,args);va_end(args);
 assert(n>=0&&(size_t)n<sizeof(message));
 if(return_stop){engine_alive=0;engine_exit_status=status;++stopped;return;}
 borExit(status);
}
s_model *findmodel(char *name){
 ++lookup_calls;for(int i=0;i<3;++i)if(!strcmp(name,models[i].name))return &models[i];return NULL;
}
int get_cached_model_index(@CACHE_CONST@char *name){
 ++cache_calls;if(uncached)return -1;
 for(int i=0;i<3;++i){
  if(name==models[i].name)return i;
 }
 abort();
}
#define shutdown probe_shutdown
#define borShutdown probe_shutdown
#undef stricmp
#define stricmp strcasecmp
@MACRO@
@READER_DECLARATIONS@
#if defined(__GNUC__) || defined(__clang__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"
#endif
@BODIES@
#if defined(__GNUC__) || defined(__clang__)
#pragma GCC diagnostic pop
#endif
#undef shutdown
#undef borShutdown
static void setup(void){
 @READER_SETUP@
 memset(models,0,sizeof(models));memset(cache_slots,0,sizeof(cache_slots));model_cache=cache_slots;
 static char names[3][16]={"available","second","enemy"};
 for(int i=0;i<3;++i){models[i].name=names[i];models[i].type=i<2?TYPE_PLAYER:TYPE_ENEMY;
  cache_slots[i].model=&models[i];cache_slots[i].selectable=i<2?9:8;}
 cache_slots[3].selectable=7;engine_alive=1;engine_exit_status=-1;stopped=lookup_calls=cache_calls=0;message[0]=0;
}
static void check(unsigned revision,int reset_all_on_zero){
 obor_profile_build=revision;
 const char *lines[]={"allowselect\n","allowselect available second\n","allowselect enemy\n",
                      "allowselect absent\n","allowselect available absent second\n","allowselect available\n"};
 for(volatile int mode=0;mode<@STOP_MODES@;++mode)for(volatile int c=0;c<6;++c){
  return_stop=mode;
  setup();uncached=c==5;char line[80];strcpy(line,lines[c]);
  if(!setjmp(frontend_return))load_playable_list(line);
  int fatal=c>=3;
  assert(stopped==fatal&&engine_alive==!fatal&&engine_exit_status==(fatal?1:-1));
  assert(cache_slots[0].selectable==(c==1||c==4)&&cache_slots[1].selectable==(c==1));
  assert(cache_slots[2].selectable==(c==2?1:reset_all_on_zero?0:8));
  assert(cache_slots[3].selectable==(reset_all_on_zero?0:7));
  const int lookups[]={0,2,1,1,2,1},cached[]={0,2,1,0,1,1};
  assert(lookup_calls==lookups[c]&&cache_calls==cached[c]);
  if(c==3||c==4){
   /* Defined original diagnostic before removal; candidate stability afterward. */
   assert(!strcmp(message,@MISSING@));
  }else if(c==5)assert(!strcmp(message,@CACHE@));else assert(!message[0]);
  ++scenarios;
 }
}
@LIMITS@int main(void){@CHECKS@ @READER_CLEANUP@ @OBSERVATION@ return 0;}
'''
    values = dict(STOP=function(port.read_text(), 'borExit'), MACRO=macro.group(), BODIES=bodies,
                  MISSING=json.dumps(missing.replace('%s', 'absent')),
                  CACHE=json.dumps(cache.replace('%s', 'available')),
                  CACHE_CONST='const ' if re.search(r'get_cached_model_index\(const\s+char',
                                                    function(source, 'get_cached_model_index')) else '',
                  STOP_MODES='2' if returning else '1',
                  READER_DECLARATIONS=reader_declarations,
                  READER_GLOBALS=stored_declaration,
                  READER_SETUP=('free(allowselect_args);allowselect_args=NULL;' if stored_pointer else
                                'memset(allowselect_args,0,sizeof(allowselect_args));' if stored_declaration else ''),
                  READER_CLEANUP='free(allowselect_args);allowselect_args=NULL;' if stored_pointer else '',
                  OBSERVATION=('printf("{\\"profiles\\":%u,\\"scenarios\\":%u}\\n",@COUNT@u,scenarios);'.replace('@COUNT@', str(len(rows)))
                               if emit_counts else 'puts("playable_models=1");'),
                  LIMITS=extra, CHECKS=checks)
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
