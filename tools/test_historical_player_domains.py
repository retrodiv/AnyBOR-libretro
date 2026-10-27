"""Check historical player property domains against their own source contracts.

The reduced native fixture tests API selectors, mapping, returns and mutations;
it does not establish full historical player layout or game acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
ENGINE = SOURCE / 'src/engines/3842'
CONTRACTS = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-player-domain-contracts.json')


def player_api_program(main, components=None, engine=None):
    if components is None:
        engine = ENGINE if engine is None else Path(engine)
        source = (engine / 'openborscript.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        enum = source[source.index('enum playerproperty_enum {'):]
        enum = enum[:enum.index('};') + 2]
        macro = source[source.index('#define MAPSTRINGS('):]
        macro = macro[:macro.index('\n\n')]
        names = ('obor_player_property_native', 'mapstrings_playerproperty',
                 'openbor_getplayerproperty', 'openbor_changeplayerproperty')
        if engine.name == '3741':
            names = ('obor_player_property_native',
                     'obor_player_get_property_native',
                     'obor_player_set_property_native',
                     'mapstrings_playerproperty',
                     'mapstrings_getplayerproperty',
                     'mapstrings_changeplayerproperty',
                     'openbor_getplayerproperty', 'openbor_changeplayerproperty')
        methods = '\n'.join(function(source, name) for name in names)
        conversion = '\n'.join(function(variants, name) for name in (
            'ScriptVariant_ChangeType', 'ScriptVariant_Clear',
            'ScriptVariant_IntegerValue', 'ScriptVariant_ToString'))
        dispatch = function(source, 'Script_GetStringMapFunction')
    else:
        enum,macro,methods,conversion,dispatch = (components[name] for name in (
            'enum','macro','methods','conversion','dispatch'))
        names=components['method_names']
    # Unrelated APIs are only compared by address, never called in this probe.
    references = set(re.findall(r'\(void\s*\*\)\s*([A-Za-z_]\w*)', dispatch))
    stubs = '\n'.join('static void ' + name + '(void) {}'
                      for name in sorted(references - set(names)))
    prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef int LONG, HRESULT;
typedef double DOUBLE;
typedef void VOID;
typedef char *LPSTR;
typedef enum { VT_EMPTY=0, VT_INTEGER=1, VT_DECIMAL=2, VT_PTR=5, VT_STR=6 } VARTYPE;
typedef struct {
    union { LONG lVal; VOID *ptrVal; DOUBLE dblVal; int strVal; };
    VARTYPE vt;
} ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(value) ((value)>=0)
#define FAILED(value) ((value)<0)
#define MAX_STR_VAR_LEN 255
static uint32_t obor_profile_build;
typedef struct { int marker; } entity;
typedef struct {
    entity *ent;
    char name[24];
    int colourmap, spawnhealth, spawnmp, lives, playkeys, keys, credits, weapnum;
    unsigned int score;
} player_state;
static player_state player[4];
static entity subject;
static int noshare, credits, weapon_calls, weapon_value, weapon_extra;
static char strings[64][512];
static unsigned next_string;
static char *StrCache_Get(int index) { assert(index>=0 && index<64); return strings[index]; }
static int StrCache_Pop(void) { assert(next_string<64); return next_string++; }
static void StrCache_Collect(int index) { (void)index; }
static void set_weapon(entity *ent, int value, int extra) {
    assert(ent==&subject); ++weapon_calls; weapon_value=value; weapon_extra=extra;
}
static int searchList(const char **names, const char *name, int count) {
    for(int i=0;i<count;++i) if(!strcasecmp(names[i],name)) return i;
    return -1;
}
CONVERSION
ENUM
MACRO
METHODS
static ScriptVariant integer(int value) {
    ScriptVariant v={0}; v.vt=VT_INTEGER; v.lVal=value; return v;
}
static ScriptVariant text(const char *value) {
    ScriptVariant v={0}; ScriptVariant_ChangeType(&v,VT_STR);
    strcpy(StrCache_Get(v.strVal),value); return v;
}
static void reset(void) {
    memset(player,0,sizeof(player)); next_string=0;
    player[0].ent=&subject; player[0].score=731; player[0].colourmap=13;
    player[0].lives=17; player[0].credits=19; player[0].playkeys=23;
    player[0].keys=29; player[0].spawnhealth=31; player[0].spawnmp=37;
    player[0].weapnum=41; strcpy(player[0].name,"before");
    credits=43; noshare=0; weapon_calls=0; weapon_value=weapon_extra=-99;
}
static int set(ScriptVariant *property, ScriptVariant *value,
               ScriptVariant *extra, ScriptVariant *result, int *has_result) {
    ScriptVariant index=integer(0), *args[]={&index,property,value,extra}, *p=result;
    int status=openbor_changeplayerproperty(args,&p,extra?4:3);
    *has_result=p!=NULL; return status;
}
static void expect_result(ScriptVariant *r,int has,int value) {
    assert(has==(obor_profile_build<3797));
    if(has) assert(r->vt==VT_INTEGER && r->lVal==value);
}
'''
    long_type = components.get('long_type','int') if components is not None else 'int'
    if long_type not in ('int','long'):
        raise ValueError('A reviewed native LONG type is required')
    prefix = prefix.replace('typedef int LONG, HRESULT;',
                            'typedef '+long_type+' LONG;\ntypedef int HRESULT;')
    prefix = prefix.replace('CONVERSION', conversion).replace('ENUM', enum)
    prefix = prefix.replace('MACRO', macro).replace('METHODS', methods)
    return prefix + stubs + '\n' + dispatch + '\n' + main


def early_player_api_case(profiles, original_error_results=False, contracts=None):
    profiles = list(profiles)
    if not profiles or len(profiles)>4096 or any(type(p) is not int or not 0<p<=0xffffffff for p in profiles):
        raise ValueError('Explicit bounded numeric profiles required')
    main = r'''static void expect_set_error(int status,int has) {
    assert(status==E_FAIL);
    if(ORIGINAL_ERROR_RESULTS && obor_profile_build<3797)assert(has);
    else assert(!has);
}

static void expect_get(const char *name,ScriptVariant *r,int empty) {
    if(empty || !strcmp(name,"weapon")) { assert(r->vt==VT_EMPTY);return; }
    if(!strcmp(name,"ent") || !strcmp(name,"entity")) {
        assert(r->vt==VT_PTR && r->ptrVal==&subject);return;
    }
    if(!strcmp(name,"name")) {
        assert(r->vt==VT_STR && !strcmp(StrCache_Get(r->strVal),"before"));return;
    }
    int value=-1;
    if(!strcmp(name,"colourmap"))value=13;
    else if(!strcmp(name,"credits"))value=43;
    else if(!strcmp(name,"keys"))value=29;
    else if(!strcmp(name,"lives"))value=17;
    else if(!strcmp(name,"playkeys"))value=23;
    else if(!strcmp(name,"score"))value=731;
    else if(!strcmp(name,"spawnhealth"))value=31;
    else if(!strcmp(name,"spawnmp"))value=37;
    else if(!strcmp(name,"weaponum") || !strcmp(name,"weapnum"))value=41;
    assert(value>=0 && r->vt==VT_INTEGER && r->lVal==value);
}
int main(int argc, char **argv) {
    unsigned requested = argc == 2 ? (unsigned)strtoul(argv[1], NULL, 10) : 0;
    int matched = 0;
    assert(argc == 1 || argc == 2);
    /* Independently transcribed from the original enums and string tables.
     * Every requested logical revision and both sides of each boundary run. */
    static const char *early_get[]={"credits","ent","entity","keys","lives",
        "name","playkeys","score","weaponum"};
    static const char *early_set[]={"credits","lives","name","playkeys","score","weapon"};
    static const char *merged[]={"credits","ent","entity","keys","lives",
        "name","playkeys","score","weapon","weaponum"};
    static const char *colour[]={"colourmap","credits","ent","entity","keys","lives",
        "name","playkeys","score","weapon","weaponum"};
    static const char *expanded[]={"colourmap","credits","ent","entity","keys","lives",
        "name","playkeys","score","spawnhealth","spawnmp","weapon","weaponum"};
    static const char *renamed[]={"colourmap","credits","ent","entity","keys","lives",
        "name","playkeys","score","spawnhealth","spawnmp","weapon","weapnum"};
    entity replacement={71};
    const unsigned profiles[]={PROFILES};
    for(unsigned at=0;at<sizeof(profiles)/sizeof(*profiles);++at) {
        unsigned profile=profiles[at];
        if(requested && requested != profile) continue;
        ++matched;
        obor_profile_build=profile;
        const char **get_names,**set_names;unsigned get_count,set_count;
        if(profile<3682) {
            get_names=early_get;get_count=9;set_names=early_set;set_count=6;
        } else {
            get_names=profile<3683?merged:profile<3797?colour:profile<3821?expanded:renamed;
            get_count=profile<3683?10:profile<3797?11:13;
            set_names=get_names;set_count=get_count;
        }
        void (*get_map)(ScriptVariant**,int)=Script_GetStringMapFunction((void*)openbor_getplayerproperty);
        void (*set_map)(ScriptVariant**,int)=Script_GetStringMapFunction((void*)openbor_changeplayerproperty);
        assert(get_map && set_map && Script_GetStringMapFunction(NULL)==NULL);
        for(unsigned id=0;id<get_count;++id) {
            for(int literal=0;literal<3;++literal) {
                reset();ScriptVariant index=integer(0),r={0},*out=&r;
                ScriptVariant prop=literal?text(get_names[id]):integer((int)id);
                ScriptVariant *args[]={&index,&prop};
                if(literal==2) {
                    get_map(args,2);assert(prop.vt==VT_INTEGER && prop.lVal==(int)id);
                    get_map(args,2);assert(prop.lVal==(int)id);
                }
                assert(openbor_getplayerproperty(args,&out,2)==S_OK && out==&r);
                assert(prop.vt==VT_INTEGER && prop.lVal==(int)id);
                expect_get(get_names[id],&r,0);
            }
        }
        for(unsigned id=0;id<set_count;++id) {
            const char *name=set_names[id];
            for(int literal=0;literal<3;++literal) {
                reset();player_state before=player[0];
                ScriptVariant prop=literal?text(name):integer((int)id),value=integer(59),r={0};
                if(!strcmp(name,"name"))value=text("after");
                if(!strcmp(name,"ent") || !strcmp(name,"entity")) {
                    value.vt=VT_PTR;value.ptrVal=&replacement;
                }
                if(literal==2) {
                    ScriptVariant index=integer(0),*args[]={&index,&prop,&value};
                    set_map(args,3);assert(prop.vt==VT_INTEGER && prop.lVal==(int)id);
                    set_map(args,3);assert(prop.lVal==(int)id);
                }
                int has,status=set(&prop,&value,NULL,&r,&has);
                int readonly=!strcmp(name,"keys")?profile<3798:
                    (!strcmp(name,"weaponum") || !strcmp(name,"weapnum"))?profile<3821:0;
                if(readonly) {
                    assert(!memcmp(&before,&player[0],sizeof(before)) && credits==43 && !weapon_calls);
                    if(profile<3797) { assert(status==S_OK);expect_result(&r,has,1); }
                    else assert(status==E_FAIL && !has);
                    continue;
                }
                assert(status==S_OK);expect_result(&r,has,1);
                if(!strcmp(name,"colourmap"))assert(player[0].colourmap==59);
                else if(!strcmp(name,"credits"))assert(credits==59 && player[0].credits==19);
                else if(!strcmp(name,"ent") || !strcmp(name,"entity"))assert(player[0].ent==&replacement);
                else if(!strcmp(name,"keys"))assert(player[0].keys==59);
                else if(!strcmp(name,"lives"))assert(player[0].lives==59);
                else if(!strcmp(name,"name"))assert(!strcmp(player[0].name,"after"));
                else if(!strcmp(name,"playkeys"))assert(player[0].playkeys==59);
                else if(!strcmp(name,"score"))assert(player[0].score==59);
                else if(!strcmp(name,"spawnhealth"))assert(player[0].spawnhealth==59);
                else if(!strcmp(name,"spawnmp"))assert(player[0].spawnmp==59);
                else if(!strcmp(name,"weapon"))assert(weapon_calls==1 && weapon_value==59 && weapon_extra==0);
                else assert(player[0].weapnum==59);
            }
        }
        for(int slot=0;slot<4;++slot) {
            reset();player[slot]=player[0];player[slot].ent=NULL;
            player_state before=player[slot];
            ScriptVariant index=integer(slot),prop=text("score"),value=integer(59),r={0},*out=&r;
            ScriptVariant *get_args[]={&index,&prop};get_map(get_args,2);
            assert(openbor_getplayerproperty(get_args,&out,2)==S_OK && out==&r);
            expect_get("score",&r,profile<3682);
            prop=text("score");ScriptVariant *set_args[]={&index,&prop,&value};
            set_map(set_args,3);out=&r;
            assert(openbor_changeplayerproperty(set_args,&out,3)==S_OK);
            expect_result(&r,out!=NULL,1);
            if(profile<3682)assert(!memcmp(&before,&player[slot],sizeof(before)));
            else assert(player[slot].score==59 && player[slot].ent==NULL);
            if(slot)assert(player[0].score==731);
            /* Invalid property values are ignored by the earlier empty-slot
             * guard, before the property-type failure in later sources. */
            prop=(ScriptVariant){0};out=&r;
            int status=openbor_getplayerproperty(get_args,&out,2);
            if(profile<3682)assert(status==S_OK && out==&r && r.vt==VT_EMPTY);
            else assert(status==E_FAIL && out==NULL);
        }
        /* A pointer index falls back to slot zero; it is not dereferenced. */
        reset();ScriptVariant index={.ptrVal=&player[2],.vt=VT_PTR},prop=text("score"),r={0},*out=&r;
        ScriptVariant *args[]={&index,&prop};
        assert(openbor_getplayerproperty(args,&out,2)==S_OK && out==&r);
        expect_get("score",&r,0);
        /* Supported/rejected spelling is checked separately from the tables
         * of successful calls, so additive aliases cannot pass unnoticed. */
        reset();index=integer(0);prop=text("weapon");out=&r;
        int status=openbor_getplayerproperty(args,&out,2);
        if(profile<3682)assert(status==E_FAIL && out==NULL);
        else assert(status==S_OK && out==&r && r.vt==VT_EMPTY);
        reset();prop=text("colourmap");out=&r;
        status=openbor_getplayerproperty(args,&out,2);
        if(profile<3683)assert(status==E_FAIL && out==NULL);
        else expect_get("colourmap",&r,0);
        reset();prop=text("colourmap");ScriptVariant colour_value=integer(59);int colour_has;
        status=set(&prop,&colour_value,NULL,&r,&colour_has);
        if(profile<3683) { expect_set_error(status,colour_has);assert(player[0].colourmap==13); }
        else { assert(status==S_OK && player[0].colourmap==59);expect_result(&r,colour_has,1); }
        reset();prop=text("keys");ScriptVariant keys_value=integer(59);int keys_has;
        status=set(&prop,&keys_value,NULL,&r,&keys_has);
        if(profile<3682 || profile==3797) { expect_set_error(status,keys_has);assert(player[0].keys==29); }
        else if(profile<3797) {
            assert(status==S_OK && player[0].keys==29);expect_result(&r,keys_has,1);
        } else assert(status==S_OK && !keys_has && player[0].keys==59);
        reset();prop=text("ent");ScriptVariant ent_value={.ptrVal=&replacement,.vt=VT_PTR};int ent_has;
        status=set(&prop,&ent_value,NULL,&r,&ent_has);
        if(profile<3682) { expect_set_error(status,ent_has);assert(player[0].ent==&subject); }
        else {
            assert(status==S_OK && player[0].ent==&replacement);expect_result(&r,ent_has,1);
        }
        /* The old setter's compiler mapper requires its value argument. */
        reset();index=integer(0);prop=text("score");
        ScriptVariant *short_args[]={&index,&prop};set_map(short_args,2);
        if(profile<3682)assert(prop.vt==VT_STR);
        else assert(prop.vt==VT_INTEGER);
        /* Repeated typed values use the logical selector without remapping. */
        reset();prop=text("credits");ScriptVariant value=integer(59);int has;
        noshare=1;assert(set(&prop,&value,NULL,&r,&has)==S_OK);
        assert(player[0].credits==59 && credits==43);expect_result(&r,has,1);
    }
    assert(matched > 0);
    return 0;
}
'''
    if contracts is not None:
        if {row['revision'] for row in contracts} != set(profiles):
            raise ValueError('Each tested profile needs its own original domain record')
        declarations, cases = [], []
        for row in contracts:
            revision = row['revision']
            for direction in ('get', 'change'):
                values = row['domains'][direction]['properties']
                names = [entry['name'] for entry in values]
                if not names or any(not re.fullmatch(r'[a-z_]+', name) for name in names):
                    raise ValueError('Bounded original ASCII property names required')
                declarations.append('    static const char *p%d_%s[]={%s};' %
                    (revision, direction, ','.join(json.dumps(name) for name in names)))
            cases.append('        case %d: get_names=p%d_get;set_names=p%d_change;'
                         'get_count=%d;set_count=%d;break;' %
                         (revision, revision, revision,
                          len(row['domains']['get']['properties']),
                          len(row['domains']['change']['properties'])))
        first = main.index('    static const char *early_get[]')
        last = main.index('    entity replacement={71};', first)
        main = main[:first] + '\n'.join(declarations) + '\n' + main[last:]
        first = main.index('        if(profile<3682) {')
        last = main.index('        void (*get_map)', first)
        main = main[:first] + '        switch(profile) {\n' + '\n'.join(cases) + \
            '\n        default: abort();\n        }\n' + main[last:]
    return main.replace('PROFILES', ','.join(map(str,profiles))).replace(
        'ORIGINAL_ERROR_RESULTS', '1' if original_error_results else '0')


class PlayerDomainTests(unittest.TestCase):
    def test_registry_covers_every_selectable_profile_on_the_affected_engines(self):
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        keys = [row['revision'] for row in CONTRACTS['sources']]
        self.assertEqual(len(keys), len(set(keys)))
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-player-domain-contracts.json', pin['profiles']):
            if profile['engine'] not in ('3741', '3842'):
                continue
            revision = int(profile.get('revision', profile['build']))
            with self.subTest(profile=profile['build']):
                self.assertIn(revision, keys)
                row = next(row for row in CONTRACTS['sources'] if row['revision'] == revision)
                self.assertEqual(row['engine'], profile['engine'])
        for row in CONTRACTS['sources']:
            with self.subTest(original=row['revision']):
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertTrue(row['fragments'])
                for fragment in row['fragments'].values():
                    self.assertEqual(fragment['path'], 'engine/openborscript.c')
                    self.assertRegex(fragment['sha256'], r'^[0-9a-f]{64}$')
                for direction in ('get', 'change'):
                    values = row['domains'][direction]['properties']
                    self.assertEqual([entry['id'] for entry in values], list(range(len(values))))

    def test_actual_api_per_profile_and_both_sides_of_the_boundaries(self):
        for engine in ('3741', '3842'):
            revisions = [row['revision'] for row in CONTRACTS['sources'] if row['engine'] == engine]
            self.assertTrue(revisions)
            main = early_player_api_case(revisions, original_error_results=engine == '3741',
                contracts=[row for row in CONTRACTS['sources'] if row['engine'] == engine])
            program = player_api_program(main, engine=SOURCE / 'src/engines' / engine)
            with tempfile.TemporaryDirectory(prefix='anybor-player-domains-') as temporary:
                work = Path(temporary)
                source, executable = work / 'probe.c', work / 'probe'
                source.write_text(program)
                subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                    '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-error=deprecated-declarations', '-g',
                    '-fsanitize=address,undefined', str(source), '-o', str(executable)],
                    check=True, timeout=60)
                completed = []
                for revision in revisions:
                    with self.subTest(engine=engine, profile=revision):
                        subprocess.run([str(executable), str(revision)],
                            check=True, timeout=20, env=sanitizer_environment(),
                            stdout=subprocess.DEVNULL)
                        completed.append(revision)
                self.assertEqual(completed, revisions)
                print(json.dumps({'engine': engine, 'executed_profiles': completed,
                    'scope': 'selectors, compiled/dynamic mapping, returns and mutation; reduced fixture'}))


if __name__ == '__main__':
    unittest.main()
