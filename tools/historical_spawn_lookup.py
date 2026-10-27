"""Render native missing-model lookup, diagnostic and unchanged-state contracts.

The complete spawn function is retained. All supplied cache indices are valid;
the model lookup service explicitly reports an absent model. No allocation,
script execution or gameplay acceptance is inferred from this early return.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json

from historical_entity_spawn import render_entity_spawn


def render_spawn_lookup(parts, *, revision, factor_layout, scripts_pointer,
                        flag_member, cases, unused_graphics_inlines=False,
                        unused_inline_declarations=None):
    if not isinstance(cases,list) or not 1 <= len(cases) <= 64:
        raise ValueError('Bounded independent missing-model lookup cases required')
    rows=[]
    for c in cases:
        if (not isinstance(c,dict) or set(c)!={'index','name','find_calls','diagnostic'} or
                type(c['index']) is not int or not -2 <= c['index'] <= 0 or
                type(c['name']) is not int or c['name'] not in (0,1) or
                type(c['find_calls']) is not int or c['find_calls'] not in (0,1) or
                not isinstance(c['diagnostic'],str) or len(c['diagnostic']) > 256 or
                not c['diagnostic'].isascii() or '\0' in c['diagnostic']):
            raise ValueError('Explicit valid cache index, lookup and exact diagnostic required')
        rows.append('{%d,%d,%d,%s}' % (c['index'],c['name'],c['find_calls'],
                                      json.dumps(c['diagnostic'])))
    # Reuse the maintained native-record and callback scaffold. Its ordinary
    # spawn cases are not executed by this contract's replacement entry point.
    baseline=dict(type=0,flag=0,variables=0,route=0,occupied=0,expected_slot=0)
    base=render_entity_spawn(parts,revision=revision,factor_layout=factor_layout,
        scripts_pointer=scripts_pointer,flag_member=flag_member,
        contract=dict(zero_factors=False,priority_reuse=False,counter_updates=False),
        cases=[baseline],unused_graphics_inlines=unused_graphics_inlines,
        unused_inline_declarations=unused_inline_declarations)
    marker='int main(void){'
    if base.count(marker)!=1:
        raise ValueError('One authored native entity entry required')
    base=base[:base.index(marker)]
    original='static s_model *observed_find(char *name){assert(!strcmp(name,"actor"));return &model;}'
    if base.count(original)!=1:
        raise ValueError('One explicit authored lookup observer required')
    base=base.replace(original,'''static unsigned lookup_calls;
static s_model *observed_find(char *name){
 assert(name&&!strcmp(name,"actor"));++lookup_calls;return NULL;
}''')
    declarations=r'''
static char diagnostic[512];
static unsigned diagnostic_bytes,diagnostic_calls;
static int observed_diagnostic(const char *format,...){
 va_list ap;va_start(ap,format);
 int n=vsnprintf(diagnostic+diagnostic_bytes,sizeof(diagnostic)-diagnostic_bytes,format,ap);
 va_end(ap);assert(n>=0 && (size_t)n<sizeof(diagnostic)-diagnostic_bytes);
 diagnostic_bytes+=(unsigned)n;++diagnostic_calls;return n;
}
'''
    anchor='#define kill native_kill\n'
    if base.count(anchor)!=1:
        raise ValueError('One authored native function boundary required')
    base=base.replace('#include <stdio.h>','#include <stdio.h>\n#include <stdarg.h>')
    base=base.replace(anchor,declarations+'\n#define printf observed_diagnostic\n'+anchor)
    base=base.replace('#undef kill\n','#undef kill\n#undef printf\n')
    entry=r'''
struct lookup_case {int index,name,find_calls;const char *diagnostic;};
static const struct lookup_case lookups[]={@CASES@};
int main(void){
 for(unsigned i=0;i<sizeof(lookups)/sizeof(*lookups);++i){
  active_case=i;const struct lookup_case *c=&lookups[i];phase="missing model setup";
  memset(pool,0,sizeof(pool));pool[0].exists=1;pool[0].health=9;
  entity previous[3];memcpy(previous,pool,sizeof(pool));
  model_cache=fixture_cache;memset(fixture_cache,0,sizeof(fixture_cache));
  ent_count=2;ent_max=3;numPlatforms=7;numObstacles=9;fixture_clock=123;
  lookup_calls=diagnostic_bytes=diagnostic_calls=0;memset(diagnostic,0,sizeof(diagnostic));
  entity *result=spawn(3,4,5,1,c->name?"actor":NULL,c->index,NULL);
  phase="missing model return";assert(!result&&lookup_calls==(unsigned)c->find_calls);
  assert(ent_count==2&&ent_max==3&&numPlatforms==7&&numObstacles==9&&fixture_clock==123);
  assert(!memcmp(previous,pool,sizeof(pool)));
  phase="missing model diagnostic";
  assert(!strcmp(diagnostic,c->diagnostic));
  assert(diagnostic_calls==(unsigned)(c->diagnostic[0]!=0));
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",(unsigned)(sizeof(lookups)/sizeof(*lookups)));
 return 0;
}
'''
    return base+entry.replace('@CASES@',','.join(rows))
