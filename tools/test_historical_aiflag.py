"""Check native AI-flag names, numerical selectors and rejected mutations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_historical_player import function
from native_sanitizers import sanitizer_environment

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', SOURCE / 'src/engines/3842'))


def aiflag_case(source, name):
    method = function(source, name)
    start = method.index('case _ep_aiflag:')
    return method[start:method.index('\n\tcase _ep_aimove:', start)]


class HistoricalAiflagTests(unittest.TestCase):
    def test_native_names_numeric_selectors_timers_and_rejected_writes(self):
        source = (ENGINE / 'openborscript.c').read_text()
        start = source.index('enum aiflag_enum {')
        stop = source.index('enum gep_attack_enum {', start)
        declarations = source[start:stop]
        macro = source[source.index('#define MAPSTRINGS('):]
        macro = macro[:macro.index('\n\n')]
        fixture = json.loads((Path(__file__).parent /
            'fixtures/profile-aiflag-contracts.json').read_text())
        rows = fixture['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertTrue(set(fixture['boundary_controls']) <= set(revisions))
        old_names = fixture['old_names']
        new_names = fixture['new_names']
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['names'], old_names if row['legacy'] else new_names)
            self.assertEqual(row['readonly'], ['freezetime', 'pain_time', 'walking']
                             if row['legacy'] else ['walking'])
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        conversion = function((ENGINE / 'source/scriptlib/ScriptVariant.c').read_text(),
                              'ScriptVariant_IntegerValue')
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
typedef int LONG, HRESULT;
typedef struct { int lVal; int vt; int strVal; double dblVal; } ScriptVariant;
enum { VT_EMPTY, VT_INTEGER, VT_STR, VT_DECIMAL };
enum { _ep_aiflag=1 };
#define E_FAIL (-1)
#define S_OK 0
#define SUCCEEDED(x) ((x)>=0)
static uint32_t obor_profile_build;
static char diagnostic[1024];
static int report(const char *format,...) {
    va_list args;va_start(args,format);
    int count=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
    va_end(args);assert(count>=0 && count<(int)sizeof(diagnostic));return count;
}
#define printf report
static char strings[2][32];
static char *StrCache_Get(int index) { assert(index>=0 && index<2); return strings[index]; }
static void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {
    ScriptVariant_Clear(v); v->vt=type;
}
CONVERSION
static int searchList(const char **names,const char *name,int count) {
    for(int i=0;i<count;++i) if(!strcasecmp(names[i],name)) return i;
    return -1;
}
typedef struct {
    int animating,attacking,autokill,blink,blocking,charging,dead,drop,falling;
    int frozen,getting,idlemode,idling,inpain,invincible,jumpid,jumping;
    int projectile,running,toexplode,turning,walking,walkmode,freezetime,pain_time;
} entity;
static entity subject;
MACRO
DECLARATIONS
static int read_flag(ScriptVariant *property,ScriptVariant *result,int count) {
    entity *ent=&subject;
    ScriptVariant *args[3]={NULL,NULL,property},**varlist=args;
    ScriptVariant *arg=NULL,**pretvar=&result;
    int paramCount=count,ltemp;
    switch(_ep_aiflag) { GET_CASE }
    return S_OK;
}
static int write_flag(ScriptVariant *property,ScriptVariant *value,int count) {
    entity *ent=&subject;
    ScriptVariant *args[4]={NULL,NULL,property,value},**varlist=args;
    int paramCount=count,ltemp;
    switch(_ep_aiflag) { SET_CASE }
    return S_OK;
changeentityproperty_error:
    return E_FAIL;
}
struct expected { const char *name; int *field; int readonly; };
#define FIELD(name) {#name,&subject.name,0}
static struct expected old_names[]={
    FIELD(animating),FIELD(attacking),FIELD(autokill),FIELD(blink),
    FIELD(blocking),FIELD(charging),FIELD(dead),FIELD(drop),FIELD(falling),
    {"freezetime",&subject.freezetime,1},FIELD(frozen),FIELD(getting),
    FIELD(idling),FIELD(inpain),FIELD(invincible),FIELD(jumpid),FIELD(jumping),
    {"pain_time",&subject.pain_time,1},FIELD(projectile),FIELD(running),
    FIELD(toexplode),FIELD(turning),{"walking",NULL,1},
};
static struct expected new_names[]={
    FIELD(animating),FIELD(attacking),FIELD(autokill),FIELD(blink),
    FIELD(blocking),FIELD(charging),FIELD(dead),FIELD(drop),FIELD(falling),
    FIELD(frozen),FIELD(getting),FIELD(idlemode),FIELD(idling),FIELD(inpain),
    FIELD(invincible),FIELD(jumpid),FIELD(jumping),FIELD(projectile),
    FIELD(running),FIELD(toexplode),FIELD(turning),{"walking",NULL,1},FIELD(walkmode),
};
static ScriptVariant integer(int value) { ScriptVariant v={.lVal=value,.vt=VT_INTEGER};return v; }
static ScriptVariant text(const char *name) {
    ScriptVariant v={.vt=VT_STR}; assert(strlen(name)<sizeof(strings[0]));
    strcpy(strings[0],name); return v;
}
int main(void) {
    const int builds[]={BUILDS};
    const int legacy_contracts[]={LEGACY};
    assert(sizeof(old_names)==sizeof(new_names));
    for(unsigned b=0;b<sizeof(builds)/sizeof(*builds);++b) {
        obor_profile_build=builds[b];
        int legacy=legacy_contracts[b];
        struct expected *expected=legacy?old_names:new_names;
        for(int i=0;i<23;++i) for(int named=0;named<2;++named) {
            memset(&subject,0,sizeof(subject));
            if(expected[i].field) *expected[i].field=101+i;
            ScriptVariant property=named?text(expected[i].name):integer(i);
            obor_map_aiflag_property(&property);
            assert(property.vt==VT_INTEGER && property.lVal==i);
            obor_map_aiflag_property(&property);
            assert(property.lVal==i);
            ScriptVariant result=integer(999);
            assert(read_flag(&property,&result,3)==S_OK);
            if(expected[i].field) assert(result.vt==VT_INTEGER && result.lVal==101+i);
            else assert(result.vt==(legacy?VT_EMPTY:VT_INTEGER) && result.lVal==0);
            entity before=subject;
            ScriptVariant value=integer(211);
            diagnostic[0]=0;
            int status=write_flag(&property,&value,4);
            int rejected=legacy && expected[i].readonly && expected[i].field;
            assert(status==(rejected?E_FAIL:S_OK));
            assert(!strcmp(diagnostic,rejected?"Unknown AI flag.\n":""));
            if(!expected[i].readonly) assert(*expected[i].field==211);
            else assert(!memcmp(&subject,&before,sizeof(subject)));
            before=subject; value.vt=VT_EMPTY;
            diagnostic[0]=0;
            assert(write_flag(&property,&value,4)==(rejected?E_FAIL:S_OK));
            assert(!strcmp(diagnostic,rejected?"Unknown AI flag.\n":""));
            assert(!memcmp(&subject,&before,sizeof(subject)));
            const double decimals[]={211.75,-211.75};
            for(unsigned d=0;d<sizeof(decimals)/sizeof(*decimals);++d) {
                before=subject;value.vt=VT_DECIMAL;value.dblVal=decimals[d];
                diagnostic[0]=0;
                assert(write_flag(&property,&value,4)==(rejected?E_FAIL:S_OK));
                assert(!strcmp(diagnostic,rejected?"Unknown AI flag.\n":""));
                if(!expected[i].readonly) assert(*expected[i].field==(int)decimals[d]);
                else assert(!memcmp(&subject,&before,sizeof(subject)));
            }
        }
        const char *absent_old[]={"idlemode","walkmode"};
        const char *absent_new[]={"freezetime","pain_time"};
        for(int i=0;i<2;++i) {
            ScriptVariant property=text(legacy?absent_old[i]:absent_new[i]);
            obor_map_aiflag_property(&property); assert(property.vt==VT_STR);
            ScriptVariant result=integer(999),value=integer(211);
            assert(read_flag(&property,&result,3)==E_FAIL);
            assert(write_flag(&property,&value,4)==E_FAIL);
        }
        const int invalid[]={-1,23,24,100,2147483647};
        for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
            ScriptVariant property=integer(invalid[i]),result=integer(999),value=integer(211);
            entity before=subject;
            assert(read_flag(&property,&result,3)==E_FAIL && result.vt==VT_EMPTY);
            diagnostic[0]=0;
            assert(write_flag(&property,&value,4)==E_FAIL);
            assert(!strcmp(diagnostic,"Unknown AI flag.\n"));
            value.vt=VT_EMPTY;
            diagnostic[0]=0;
            assert(write_flag(&property,&value,4)==(legacy?E_FAIL:S_OK));
            assert(!strcmp(diagnostic,legacy?"Unknown AI flag.\n":""));
            assert(!memcmp(&subject,&before,sizeof(subject)));
        }
        ScriptVariant property=integer(0),result=integer(999),value=integer(211);
        entity before=subject;
        assert(read_flag(&property,&result,2)==S_OK && result.lVal==999);
        assert(write_flag(&property,&value,3)==S_OK);
        assert(!memcmp(&subject,&before,sizeof(subject)));
    }
    puts("historical AI flag native contracts: OK");
    return 0;
}
'''
        for key, value in (('MACRO', macro), ('DECLARATIONS', declarations),
                           ('CONVERSION', conversion),
                           ('BUILDS', ','.join(str(row['revision']) for row in rows)),
                           ('LEGACY', ','.join(str(int(row['legacy'])) for row in rows)),
                           ('GET_CASE', aiflag_case(source, 'openbor_getentityproperty')),
                           ('SET_CASE', aiflag_case(source, 'openbor_changeentityproperty'))):
            program = program.replace(key, value)
        with tempfile.TemporaryDirectory(prefix='anybor-historical-aiflag-') as temporary:
            root = Path(temporary)
            native = root / 'flags.c'
            native.write_text(program)
            host = root / 'flags'
            subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
                '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations', '-g',
                '-fsanitize=address,undefined', str(native), '-o', str(host)],
                check=True, timeout=60)
            result = subprocess.run([str(host)], capture_output=True, text=True, timeout=10,
                                    env=sanitizer_environment())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('historical AI flag native contracts: OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
