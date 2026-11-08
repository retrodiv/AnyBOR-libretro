"""Render native generator lifetime and engine-owned random-state controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import json
import re

from test_historical_player import function


def rng_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    main = function(source, 'openborMain')
    loop = main.index('while(!quit)')
    start = main.index('{', loop) + 1
    entry = main[start:main.index('if(skiptoset < 0)', start)]
    if 'srand32' not in entry:
        raise ValueError('Native outer-loop seed entry required')
    def vectors(bits):
        return ','.join('{%d,{%s},{%s}}' % (row['seed_argument_int'],
            ','.join(str(n)+'u' for n in row['expected_rand32_unsigned_outputs']),
            ','.join('UINT64_C(%d)' % n for n in row['expected_seed_after_each_call']))
            for row in data['lcg_vectors'] if row['unsigned_long_bits'] == bits)
    fields = dict(CONTEXTS=','.join('{%du,%d,%d}' %
            (row['revision'], row['clock_libc_generator'], bool(row['main_seed_calls']))
            for row in data['sources']),
        ENTRY=entry, VECTORS32=vectors(32), VECTORS64=vectors(64),
        OUTER_CLOCKS=','.join(str(n)+'u' for n in data['outer_clocks']))
    text = Path(__file__).with_name('classic_rng_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native generator control input')
    return text


def additive_program(data, *, provider_header=False):
    """Check the owned platform provider against independent source oracles."""
    rows = []
    for row in data['additive_vectors']:
        rows.append('{%du,%d,{%s}}' % (row['seed'], len(row['first']),
            ','.join(str(n)+'u' for n in row['first'])))
    default = next(row['first'] for row in data['additive_vectors'] if row['seed'] == 1)
    text = '''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obor_random_additive.h"
#define check(x) do {if(!(x)){fprintf(stderr,"Owned additive seed=%u draw=%u line=%d\\n",seed,draw,__LINE__);abort();}}while(0)
static const struct {unsigned seed,count,values[16];} vectors[]={'''+','.join(rows)+'''};
int main(void){
 unsigned seed=1,draw=0;
 const unsigned initial[]={@INITIAL@};
 for(draw=0;draw<sizeof(initial)/sizeof(initial[0]);++draw)check((unsigned)obor_rand()==initial[draw]);
 for(unsigned v=0;v<sizeof(vectors)/sizeof(vectors[0]);++v){
  seed=vectors[v].seed;obor_srand(seed);
  for(draw=0;draw<vectors[v].count;++draw)check((unsigned)obor_rand()==vectors[v].values[draw]);
 }
 obor_additive_random_state saved=obor_additive_random;
 unsigned values[64];for(draw=0;draw<64;++draw)values[draw]=(unsigned)obor_rand();
 obor_additive_random=saved;
 for(draw=0;draw<64;++draw)check(values[draw]==(unsigned)obor_rand());
 puts("owned_additive literal_vectors=PASS snapshot_replay=PASS");return 0;
}'''
    text = text.replace('@INITIAL@', ','.join(str(n)+'u' for n in default))
    if provider_header:
        text = text.replace('#include "obor_random_additive.h"',
            '#ifndef __ANDROID__\n#define __ANDROID__ 1\n#endif\n'
            '#include "obor_random.h"\n#ifndef OBOR_RANDOM_ADDITIVE_H\n'
            '#error Android engine provider must own additive state\n#endif')
    return text


def rng_script_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = '\n'.join(function(source, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods)))
    if not 8 <= len(symbols) <= 512 or 'system_srand' not in symbols:
        raise ValueError('Complete native registry and seed callback required')
    fields = dict(STUBS='\n'.join(
        'HRESULT %s(ScriptVariant **a,ScriptVariant **b,int n) '
        '{(void)a;(void)b;(void)n;++unused_calls[%d];return S_OK;}' % (name, i)
        for i, name in enumerate(symbols) if name != 'system_srand'),
        SYMBOL_COUNT=str(len(symbols)), METHODS=methods,
        CALLBACK=function(source, 'system_srand'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['registered']) for row in data['sources']),
        INPUTS=','.join('{%s,%.17g,%d,%d}' % (row['type'], row['value'], row['converts'], row['integer'])
                          for row in data['script_inputs']),
        RESULTS=','.join(str(n)+'u' for n in data['script_results']))
    text = Path(__file__).with_name('classic_rng_script_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native seed script control input')
    return text
