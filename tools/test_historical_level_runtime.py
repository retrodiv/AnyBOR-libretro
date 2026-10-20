"""Probe literal and computed level properties with the actual variant union.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/3842'))
PROFILES = (3780, 3783, 3789, 3793, 3797, 3805, 3814, 3818,
            3819, 3820, 3821, 3822, 3824, 3829, 3831, 3837, 3839, 3842)


def level_runtime_program(script, header, variants, utils, profiles, original=False):
    """Use an engine's own API bodies; private oracles can supply upstream blobs.

    The cache has authored entries with controlled indices. Allocation ownership
    is observed through collect calls; no engine allocator or game is required.
    """
    records = []
    for name, alias in (('VariantType', 'VARTYPE'), ('ScriptVariant', 'ScriptVariant')):
        start = header.index('typedef ' + ('enum ' if name == 'VariantType' else 'struct ') + name)
        end = re.search(r'\}\s*' + alias + r'\s*;', header[start:])
        if end is None:
            raise AssertionError('Missing complete native type ' + name)
        records.append(header[start:start + end.end()])
    declarations = []
    for name in ('levelproperty_enum', 'drawmethod_enum'):
        start = script.index('enum ' + name)
        declarations.append(script[start:script.index('};', start) + 2])
    start = script.index('#define MAPSTRINGS(')
    macro = script[start:script.index('\n\n', start)]
    helpers = '' if original else function(script, 'obor_level_property_native')
    methods = '\n'.join(function(script, name) for name in (
        'mapstrings_levelproperty', 'mapstrings_drawmethodproperty',
        'openbor_getlevelproperty', 'openbor_changelevelproperty'))
    converters = '\n'.join(function(variants, name) for name in (
        'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue'))
    lowering = function(script, 'Script_GetStringMapFunction')
    for name in ('getlevelproperty', 'changelevelproperty'):
        if re.search(r'functionRef\s*==\s*\(\(void\*\)openbor_' + name +
                     r'\)\)\s*return\s*\(void\*\)mapstrings_levelproperty', lowering) is None:
            raise AssertionError('Compiler literal mapper changed for ' + name)
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef int32_t LONG;
typedef double DOUBLE;
typedef void VOID;
typedef int HRESULT;
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
#define stricmp strcasecmp
RECORDS
static uint32_t obor_profile_build;
static char *cache[64];
static int collects;
static char *StrCache_Get(int index) { assert(index>=0 && index<64 && cache[index]); return cache[index]; }
static void StrCache_Collect(int index) { assert(index>=0 && index<64 && cache[index]); ++collects; }
static int StrCache_Pop(void) { abort(); }
CONVERTERS
void ScriptVariant_ToString(ScriptVariant *v,char *out) {
    if(v->vt==VT_STR) snprintf(out,64,"%s",StrCache_Get(v->strVal));
    else snprintf(out,64,"<type %d>",v->vt);
}
SEARCH
MACRO
#define __reallocto(P,OLD,N) do { assert((N)>=(OLD) && (N)<=4); \
    (P)=realloc((P),(N)*sizeof(*(P))); assert(P); \
    memset((P)+(OLD),0,((N)-(OLD))*sizeof(*(P))); } while(0)
typedef struct { int rocking,type,cameraxoffset,camerazoffset,quake;
    float bgspeed,scrollspeed,gravity,maxfallspeed,maxtossspeed;
    int numholes,numwalls; float (*holes)[7],(*walls)[8]; } Level;
static Level storage,*level=&storage;
DECLARATIONS
HELPERS
METHODS
static ScriptVariant integer(int value) { ScriptVariant v={0};v.vt=VT_INTEGER;v.lVal=value;return v; }
static ScriptVariant string(int index,char *text) { ScriptVariant v={0};v.vt=VT_STR;v.strVal=index;cache[index]=text;return v; }
static void reset(void) {
    free(storage.holes);free(storage.walls);memset(&storage,0,sizeof(storage));
    storage.bgspeed=21;storage.cameraxoffset=22;storage.camerazoffset=23;
    storage.gravity=24.5f;storage.maxfallspeed=25.5f;storage.maxtossspeed=26.5f;
    storage.quake=27;storage.scrollspeed=28.5f;storage.rocking=29;storage.type=30;
    collects=0;
}
static void trace(const char *name,int hr,ScriptVariant *out,ScriptVariant *a) {
    printf("LEVEL_RUNTIME %u %s hr=%d out=%d type=%d value=%.2f quake=%d bg=%.2f a0=%d/%d a1=%d/%d collects=%d\n",
        obor_profile_build,name,hr,out!=NULL,out?(int)out->vt:-1,
        out?(out->vt==VT_DECIMAL?out->dblVal:(double)out->lVal):0,
        storage.quake,storage.bgspeed,(int)a[0].vt,a[0].lVal,(int)a[1].vt,a[1].lVal,collects);
}
static void exercise(unsigned profile) {
    obor_profile_build=profile;
    ScriptVariant a[10],result,*out,*v[10];
    for(int i=0;i<10;++i) {a[i]=integer(0);v[i]=a+i;}
    /* Compiler literals map property zero before runtime, in every build. */
    reset();a[0]=string(40,"quake");mapstrings_levelproperty(v,1);
    assert(a[0].vt==VT_INTEGER && a[0].lVal==7 && collects==1);
    result=integer(111);out=&result;
    int hr=openbor_getlevelproperty(v,&out,1);
    assert(hr==S_OK && out==&result && out->vt==VT_INTEGER && out->lVal==27);
    trace("literal_get",hr,out,a);
    /* A computed name retains its cache index before the getter repair. */
    reset();a[0]=string(0,"quake");result=integer(111);out=&result;
    hr=openbor_getlevelproperty(v,&out,1);
    assert(hr==S_OK && out==&result && out->lVal==(profile<3820?21:27));
    assert(a[0].vt==(profile<3820?VT_STR:VT_INTEGER));
    trace("computed_get_low_cache",hr,out,a);
    reset();a[0]=string(40,"quake");result=integer(111);out=&result;
    hr=openbor_getlevelproperty(v,&out,1);
    assert(profile<3820?(hr==E_FAIL && out==NULL):(hr==S_OK && out->lVal==27));
    trace("computed_get_high_cache",hr,out,a);
    /* Even the repaired mapper leaves unknown text in the union. Its safe
       scalar cache-index alias was observable in the original API. */
    reset();a[0]=string(0,"unknown");result=integer(111);out=&result;
    hr=openbor_getlevelproperty(v,&out,1);
    assert(hr==S_OK && out && out->lVal==21 && a[0].vt==VT_STR);
    trace("unmapped_get_low_cache",hr,out,a);
    reset();a[0]=string(40,"unknown");result=integer(111);out=&result;
    hr=openbor_getlevelproperty(v,&out,1);assert(hr==E_FAIL && out==NULL);
    trace("unmapped_get_high_cache",hr,out,a);
    /* The old drawmethod mapper consumes parameter ONE, not the selector.
       An extra getter argument is therefore mutated even when not used. */
    reset();a[0]=integer(7);a[1]=string(41,"alpha");result=integer(111);out=&result;
    hr=openbor_getlevelproperty(v,&out,2);
    assert(hr==S_OK && out && out->lVal==27);
    assert(a[1].vt==(profile<3820?VT_INTEGER:VT_STR));
    trace("getter_second_argument",hr,out,a);
    /* A literal selector remains valid, but a computed setter value can be
       converted by the wrong mapper until the distinct 3821 repair. */
    reset();a[0]=string(40,"quake");a[1]=string(41,"alpha");mapstrings_levelproperty(v,2);
    result=integer(111);out=&result;hr=openbor_changelevelproperty(v,&out,2);
    assert(profile<3821?(hr==S_OK && storage.quake==0):(hr==E_FAIL && storage.quake==27));
    assert(profile<3820?(out==&result && result.lVal==111):out==NULL);
    assert(a[1].vt==(profile<3821?VT_INTEGER:VT_STR));
    trace("literal_set_string_value",hr,out,a);
    reset();a[0]=string(0,"quake");a[1]=integer(17);result=integer(111);out=&result;
    hr=openbor_changelevelproperty(v,&out,2);
    assert(hr==S_OK && storage.bgspeed==(profile<3821?17:21) && storage.quake==(profile<3821?27:17));
    trace("computed_set_low_cache",hr,out,a);
    reset();a[0]=string(40,"quake");a[1]=integer(17);result=integer(111);out=&result;
    hr=openbor_changelevelproperty(v,&out,2);
    assert(profile<3821?(hr==E_FAIL && out==NULL):(hr==S_OK && storage.quake==17));
    trace("computed_set_high_cache",hr,out,a);
    reset();a[0]=integer(7);a[1]=integer(18);result=integer(111);out=&result;
    hr=openbor_changelevelproperty(v,&out,2);assert(hr==S_OK && storage.quake==18);
    assert(profile<3820?(out==&result && result.lVal==111):out==NULL);
    trace("numeric_set",hr,out,a);
    /* Original bulk setters read varlist[3] for every slot. Successful array
       getters fall through to E_FAIL; do not accidentally repair either. */
    const char *names[]={"hole","wall"};
    for(int k=0;k<2;++k) {
        reset();a[0]=string(40,(char*)names[k]);mapstrings_levelproperty(v,1);
        for(int i=1;i<10;++i)a[i]=integer(i+20);
        a[1]=integer(0);result=integer(111);out=&result;
        hr=openbor_changelevelproperty(v,&out,9+k);assert(hr==S_OK);
        for(int i=0;i<7+k;++i)assert((k?storage.walls[0][i]:storage.holes[0][i])==23);
        trace(k?"bulk_wall":"bulk_hole",hr,out,a);
        a[1]=integer(0);a[2]=integer(0);result=integer(111);out=&result;
        hr=openbor_getlevelproperty(v,&out,3);assert(hr==E_FAIL && out==NULL);
        trace(k?"get_wall_fallthrough":"get_hole_fallthrough",hr,out,a);
    }
    reset();free(storage.holes);free(storage.walls);
}
int main(void) {
    const unsigned profiles[]={PROFILES};
    for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);++i)exercise(profiles[i]);
    return 0;
}
'''.replace('RECORDS', '\n'.join(records)).replace('CONVERTERS', converters).replace(
        'SEARCH', function(utils, 'searchList')).replace('MACRO', macro).replace(
        'DECLARATIONS', '\n'.join(declarations)).replace('HELPERS', helpers).replace(
        'METHODS', methods).replace('PROFILES', ','.join(map(str, profiles)))


class HistoricalLevelRuntimeTests(unittest.TestCase):
    def test_literal_computed_and_numeric_level_property_contracts(self):
        program = level_runtime_program(
            (ENGINE/'openborscript.c').read_text(),
            (ENGINE/'source/scriptlib/ScriptVariant.h').read_text(),
            (ENGINE/'source/scriptlib/ScriptVariant.c').read_text(),
            (ENGINE/'source/utils.c').read_text(), PROFILES)
        with tempfile.TemporaryDirectory(prefix='historical-level-runtime-') as temp:
            work = Path(temp)
            source = work/'probe.c'
            source.write_text(program)
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-implicit-fallthrough',
                '-g', '-fsanitize=address,undefined', str(source), '-o', str(work/'probe')],
                check=True, timeout=45)
            subprocess.run([str(work/'probe')], check=True, timeout=20,
                           stdout=subprocess.DEVNULL,
                           env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                                    UBSAN_OPTIONS='halt_on_error=1'))


if __name__ == '__main__':
    unittest.main()
