"""Render native spawn-score and model-AI sentinel clauses.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_unsigned_scalars(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    loader = function(source, 'load_level')
    score = loader[loader.index('case CMD_LEVEL_SCORE:'):loader.index('case CMD_LEVEL_NOLIFE:')]
    copy = function(source, 'ent_copy_uninit')
    first = re.search(r'(?m)^[ \t]*if\([^\n]*ent->modeldata\.aimove', copy).start()
    ai = copy[first:copy.index('\tif(ent->modeldata.hostile', first)]
    model = '\n'.join(re.search(r'(?m)^\s*(unsigned(?:\s+int)?\s+' + name + r'\s*;)', header)[1]
                      for name in ('aimove', 'aiattack'))
    spawn = re.search(r'typedef struct\s*\{[^{}]*\}s_spawn_entry;', header)[0]
    fields = '\n'.join(re.search(r'(?m)^\s*((?:unsigned(?:\s+int)?|int)\s+' + name + r'\s*;)', spawn)[1]
                       for name in ('score', 'multiple'))
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (
        row['revision'], row['sentinel_equality']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#ifndef PROBE_FOCUS
#define PROBE_FOCUS 0
#endif
static uint32_t obor_profile_build;
static unsigned cases;
static int a,b;
typedef struct {@MODEL@} Model;
typedef struct {Model modeldata;} Entity;
typedef struct {@FIELDS@} Spawn;
_Static_assert(sizeof(unsigned)==4 && sizeof(int)==4,"source integer domains");
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"unsigned scalar profile=%u focus=%d a=%d b=%d line=%d\n",obor_profile_build,PROBE_FOCUS,a,b,__LINE__);abort();}}while(0)
enum {CMD_LEVEL_SCORE};
#define GET_INT_ARG(i) (args[(i)-1])
static Spawn parse_score(int x,int y){int args[]={x,y};Spawn next={0};switch(0){@SCORE@}return next;}
static void inherit(Entity *ent,Model *oldmodel){@AI@}
static void check(int equality){
    const int values[]={0,1,-1,-2,INT_MIN,INT_MAX};
    if(PROBE_FOCUS!=2)for(a=0;a<6;++a)for(b=0;b<6;++b){
        Spawn result=parse_score(values[a],values[b]);
        unsigned score=equality && values[a]==-1?0:(unsigned)values[a];
        int multiple=(equality?values[b]==-1:values[b]<0)?0:values[b];
        assert(result.score==score && result.multiple==multiple);++cases;
    }
    const unsigned flags[]={0,1,UINT_MAX,UINT_MAX-1,0x80000000u};
    if(PROBE_FOCUS!=1)for(a=0;a<5;++a)for(b=0;b<5;++b){
        Entity ent={{flags[a],flags[b]}};Model parent={7,9};inherit(&ent,&parent);
        assert(ent.modeldata.aimove==(equality && a==2?7:flags[a]));
        assert(ent.modeldata.aiattack==(equality && b==2?9:flags[b]));
        assert(parent.aimove==7 && parent.aiattack==9);++cases;
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@MODEL@', model).replace('@FIELDS@', fields).replace('@SCORE@', score).replace(
        '@AI@', ai).replace('@CHECKS@', checks)
