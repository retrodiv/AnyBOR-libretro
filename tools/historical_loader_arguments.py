"""Check historical text-loader argument callers against own source outcomes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from test_historical_player import function


def render_barstatus_arguments(engine, fixture):
    rows, samples, initial = fixture['sources'], fixture['samples'], fixture['initial']
    if (not 1 <= len(rows) <= 128 or not 1 <= len(samples) <= 64 or len(initial) != 9 or
            len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique bar-status contexts and samples required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                len(row['expected']) != len(samples) or
                any(len(v) != 9 or any(type(n) is not int or not -(1 << 31) <= n < (1 << 31)
                                      for n in v) for v in row['expected'])):
            raise ValueError('Explicit representable own member outcomes required')
    if any(not isinstance(s['line'], str) or len(s['line']) > 4096 for s in samples):
        raise ValueError('Bounded source argument lines required')
    source = (engine / 'openbor.c').read_text()
    fields = ('sizex', 'sizey', 'noborder', 'type', 'orientation',
              'borderlayer', 'shadowlayer', 'barlayer', 'backlayer')
    entries = ',\n'.join('{%d,{%s}}' % (r['revision'], ','.join(
        '{%s}' % ','.join(map(str, v)) for v in r['expected'])) for r in rows)
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef printf
#undef assert
static unsigned active_sample;uint32_t obor_profile_build;
static void fail(int line,const char *condition){
 fprintf(stderr,"loader arguments profile=%u sample=%u line=%d: %s\n",
         obor_profile_build,active_sample,line,condition);abort();
}
#define assert(c) do{if(!(c))fail(__LINE__,#c);}while(0)
@MACRO@
@FUNCTIONS@
static const char *samples[]={@SAMPLES@};
static const int initial[]={@INITIAL@};
struct context {uint32_t revision;int expected[@COUNT@][9];};
static const struct context contexts[]={@CONTEXTS@};
static int colours[2][11];
int main(void){
 for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r){
  const struct context *ctx=&contexts[r];obor_profile_build=ctx->revision;
  for(active_sample=0;active_sample<@COUNT@;++active_sample){
   s_barstatus status={0};char input[MAX_ARG_LEN+1];
   assert(strlen(samples[active_sample])<sizeof(input));strcpy(input,samples[active_sample]);
   @INITIALIZE@
   status.offsetx=-9;status.offsety=12;status.direction=1;status.colourtable=colours;
   _readbarstatus(input,&status);
   const int actual[]={@ACTUAL@};
   for(unsigned f=0;f<9;++f)assert(actual[f]==ctx->expected[active_sample][f]);
   assert(status.offsetx==-9&&status.offsety==12&&status.direction==1&&status.colourtable==colours);
   assert(!strcmp(input,samples[active_sample]));
  }
 }
 puts("loader_arguments=1");return 0;
}
'''
    macro = re.search(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
    if macro is None:
        raise ValueError('Actual profile argument accessor required')
    values = dict(MACRO=macro.group(), FUNCTIONS='\n'.join(function(source, n) for n in
                  ('ParseArgs', 'findarg', 'obor_legacy_arg', '_readbarstatus')),
                  SAMPLES=','.join(json.dumps(s['line']) for s in samples),
                  INITIAL=','.join(map(str, initial)), COUNT=str(len(samples)),
                  CONTEXTS=entries, INITIALIZE='\n'.join(
                      'status.%s=initial[%d];' % (f, i) for i, f in enumerate(fields)),
                  ACTUAL=','.join('status.' + f for f in fields))
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code


def render_query_windows(engine, fixture):
    rows, samples, sites = fixture['sources'], fixture['samples'], fixture['sites']
    if (not 1 <= len(rows) <= 128 or not 1 <= len(samples) <= 64 or
            not 1 <= len(sites) <= 32 or len(set(sites)) != len(sites) or
            len({r['revision'] for r in rows}) != len(rows) or
            any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z_]\w*', n) for n in sites)):
        raise ValueError('Bounded unique caller windows required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                row['model_query_sites'] not in (1, 2) or len(row['expected_tokens']) != len(samples) or
                any(not isinstance(v, str) or len(v) > 4096 for v in row['expected_tokens'])):
            raise ValueError('Own bounded query outcomes required')
    if any(not isinstance(s['line'], str) or len(s['line']) > 4096 for s in samples):
        raise ValueError('Bounded query lines required')
    source = (engine / 'openbor.c').read_text()
    windows = []
    for i, name in enumerate(sites):
        body = function(source, name)
        search_body = re.sub(
            r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*',
            lambda m: re.sub(r'[^\n]', ' ', m.group()), body, flags=re.S)
        if name == 'load_cached_model':
            match = re.search(
                r'ParseArgs\(&arglist,buf\+pos,argbuf\);\s*'
                r'if\((.*?)\)\{\s*command\s*=\s*GET_ARG\(0\);', search_body, re.S)
            if match is None:
                raise ValueError('Actual model command admission required')
            prefix = body[match.start():match.end()] + '\n}'
        else:
            match = re.search(
                r'ParseArgs\(&arglist,\s*buf\+pos,\s*argbuf\);\s*'
                r'command\s*=\s*GET_ARG\(0\);', search_body)
            if match is None:
                raise ValueError('Actual caller query prefix required')
            prefix = body[match.start():match.end()]
        windows.append('case %d:{%s}break;' % (i, prefix))
    entries = ',\n'.join('{%d,%d,{%s}}' % (
        r['revision'], r['model_query_sites'],
        ','.join(json.dumps(v) for v in r['expected_tokens'])) for r in rows)
    code = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef printf
#undef assert
static unsigned active_site,active_sample;uint32_t obor_profile_build;
static void fail(int line,const char *condition){
 fprintf(stderr,"query windows profile=%u site=%u sample=%u line=%d: %s\n",
         obor_profile_build,active_site,active_sample,line,condition);abort();
}
#define assert(c) do{if(!(c))fail(__LINE__,#c);}while(0)
@MACRO@
@FUNCTIONS@
static void query_window(unsigned site,char *buf,char *out){
 ptrdiff_t pos=0;ArgList arglist;char argbuf[MAX_ARG_LEN+1]="";char *command=NULL;
 switch(site){@WINDOWS@ default:abort();}
 if(command){assert(strlen(command)<MAX_ARG_LEN+1);strcpy(out,command);}
 else out[0]=0;
}
static const char *samples[]={@SAMPLES@};
static const char *sites[]={@SITES@};
struct context {uint32_t revision;int model_queries;const char *expected[@COUNT@];};
static const struct context contexts[]={@CONTEXTS@};
int main(void){
 for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r){
  const struct context *ctx=&contexts[r];obor_profile_build=ctx->revision;
  for(active_site=0;active_site<sizeof(sites)/sizeof(*sites);++active_site)
   for(active_sample=0;active_sample<@COUNT@;++active_sample){
    int repeats=!strcmp(sites[active_site],"load_models")?ctx->model_queries:1;
    for(int pass=0;pass<repeats;++pass){
     char seed[]= @SEED@;char input[MAX_ARG_LEN+1],out[MAX_ARG_LEN+1];
     assert(strlen(samples[active_sample])<sizeof(input));strcpy(input,samples[active_sample]);
     findarg(seed,MAX_ARG_LEN-1);
     query_window(active_site,input,out);
     assert(!strcmp(out,ctx->expected[active_sample]));
     assert(!strcmp(input,samples[active_sample]));
    }
   }
 }
 puts("query_windows=1");return 0;
}
'''
    macro = re.search(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
    if macro is None:
        raise ValueError('Actual profile argument accessor required')
    values = dict(MACRO=macro.group(), FUNCTIONS='\n'.join(function(source, n) for n in
                  ('ParseArgs', 'findarg', 'obor_legacy_arg')), WINDOWS='\n'.join(windows),
                  SAMPLES=','.join(json.dumps(s['line']) for s in samples),
                  SITES=','.join(json.dumps(s) for s in sites),
                  SEED=json.dumps(fixture['seed']), COUNT=str(len(samples)), CONTEXTS=entries)
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
