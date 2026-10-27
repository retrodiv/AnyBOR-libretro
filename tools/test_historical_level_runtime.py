"""Probe literal and computed level properties with the actual variant union.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function
from native_sanitizers import sanitizer_environment

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
    helper_names = ('obor_level_property_native', 'obor_getlevelproperty_before_mapper',
                    'obor_changelevelproperty_before_mapper')
    helpers = '' if original else '\n'.join(function(script, name) for name in helper_names
        if re.search(r'(?m)^static[^\n]*\b' + name + r'\(', script))
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
    def test_each_own_source_level_property_domain_and_runtime(self):
        from test_historical_behavior import native
        fixture = json.loads((Path(__file__).parent /
            'fixtures/profile-level-property-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for control in fixture['namespace_only_boundary_sources']:
            self.assertEqual(control['revision'], 3739)
            self.assertTrue({'hole', 'wall'} <= set(control['property_names']))
            self.assertRegex(control['commit'], r'^[0-9a-f]{40}$')
        for profile in json.loads((ROOT / 'src/pin.json').read_text())['profiles']:
            revision = int(profile.get('revision', profile['build']))
            if any(span['engine'] == profile['engine'] and span['first'] <= revision <= span['last']
                   for span in fixture['coverage']):
                self.assertIn(revision, revisions)
        groups = {}
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertTrue(row['getter_and_setter_registered'])
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            groups.setdefault(row['engine'], []).append(row)
        for engine, contexts in groups.items():
            with self.subTest(engine=engine):
                root = ROOT / 'src/engines' / engine
                script = (root / 'openborscript.c').read_text()
                registry = function(script, 'Script_LoadSystemFunctions')
                self.assertIn('openbor_getlevelproperty', registry)
                self.assertIn('openbor_changelevelproperty', registry)
                base = level_runtime_program(script,
                    (root / 'source/scriptlib/ScriptVariant.h').read_text(),
                    (root / 'source/scriptlib/ScriptVariant.c').read_text(),
                    (root / 'source/utils.c').read_text(), ())
                prefix = base[:base.index('static void exercise(')]
                diagnostics = r'''
#include <stdarg.h>
static char diagnostic[2048];
static int record_diagnostic(const char *format,...) {
    size_t n=strlen(diagnostic);va_list args;va_start(args,format);
    int result=vsnprintf(diagnostic+n,sizeof(diagnostic)-n,format,args);va_end(args);
    assert(result>=0 && (size_t)result<sizeof(diagnostic)-n);return result;
}
#define printf record_diagnostic
'''
                prefix = prefix.replace('#include <strings.h>', '#include <strings.h>' + diagnostics, 1)
                router = function(script, 'Script_GetStringMapFunction')
                branches = re.findall(r'else if[^\n]*openbor_(?:getlevelproperty|changelevelproperty)[^\n]*;', router)
                self.assertEqual(len(branches), 2)
                branches[0] = branches[0].replace('else if', 'if', 1)
                route = 'static void *compiler_mapper(void *functionRef) {\n' + '\n'.join(branches) + '\nreturn NULL;\n}\n'
                tables, checks = {}, []
                total = 0
                for row in contexts:
                    names = tuple(row['property_names'])
                    if names not in tables:
                        tables[names] = 'names_%d' % len(tables)
                    checks.append('obor_profile_build=%d;check(%d,%s,%d,%d);' % (
                        row['revision'], row['legacy_string_only_api'], tables[names],
                        len(names), row['draw_enabled_index']))
                    total += 600 + 4 * (len(names) + 3) + 3 + (4 if len(names) == 11 else 0)
                definitions = '\n'.join('static const char *%s[]={%s};' % (
                    name, ','.join(json.dumps(s) for s in values)) for values, name in tables.items())
                if engine == '3842':
                    for control in fixture['diagnostic_boundary_controls']:
                        self.assertRegex(control['commit'], r'^[0-9a-f]{40}$')
                        message = ('Property is not supported by function getlevelproperty yet. 99\n'
                            if control['message_includes_property_id'] else
                            'Property is not supported by function getlevelproperty yet.\n')
                        checks.append('obor_profile_build=%d;diagnostic_boundary(%s,%s);' % (
                            control['revision'], json.dumps(message), json.dumps(control['setter_message'])))
                        total += 1
                program = prefix + route + r'''
static unsigned cases;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Level property: revision=%u case=%u line=%d\n",obor_profile_build,cases,__LINE__);abort();}}while(0)
enum {F_BG,F_CAMX,F_CAMZ,F_GRAVITY,F_FALL,F_TOSS,F_QUAKE,F_ROCK,F_SCROLL,F_TYPE,F_HOLE,F_WALL,F_INVALID};
static const char *queries[]={"bgspeed","BGSPEED","cameraxoffset","camerazoffset","gravity",
 "maxfallspeed","maxtossspeed","quake","rock","rocking","scrollspeed","hole","wall","invalid","ROCK"};
static int field(const char *name) {
 const char *names[]={"bgspeed","cameraxoffset","camerazoffset","gravity","maxfallspeed",
  "maxtossspeed","quake","rocking","scrollspeed","type","hole","wall"};
 for(int i=0;i<F_INVALID;++i)if(!strcmp(name,names[i]))return i;
 return F_INVALID;
}
static int logical(const char *name,const char **names,int count) {
 for(int i=0;i<count;++i)if(!strcasecmp(name,names[i]))return i;
 return -1;
}
static double scalar(const Level *v,int key) {
 switch(key) {
 case F_BG:return v->bgspeed;case F_CAMX:return v->cameraxoffset;case F_CAMZ:return v->camerazoffset;
 case F_GRAVITY:return v->gravity;case F_FALL:return v->maxfallspeed;case F_TOSS:return v->maxtossspeed;
 case F_QUAKE:return v->quake;case F_ROCK:return v->rocking;case F_SCROLL:return v->scrollspeed;case F_TYPE:return v->type;
 default:abort();
 }
}
static void assign(Level *v,int key,double value) {
 switch(key) {
 case F_BG:v->bgspeed=value;break;case F_CAMX:v->cameraxoffset=(int)value;break;case F_CAMZ:v->camerazoffset=(int)value;break;
 case F_GRAVITY:v->gravity=value;break;case F_FALL:v->maxfallspeed=value;break;case F_TOSS:v->maxtossspeed=value;break;
 case F_QUAKE:v->quake=(int)value;break;case F_ROCK:v->rocking=(int)value;break;case F_SCROLL:v->scrollspeed=value;break;
 default:abort();
 }
}
static void same_fields(const Level *expected) {
 for(int f=0;f<=F_TYPE;++f)assert(scalar(&storage,f)==scalar(expected,f));
 assert(storage.numholes==expected->numholes && storage.numwalls==expected->numwalls);
}
static void level_warning(char *out,const char *name) {
 snprintf(out+strlen(out),512-strlen(out),"Level property '%s' is not supported.\n",name);
}
static ScriptVariant selector(int mode,const char *name,int index) {
 return mode==2?integer(index):string(index,(char*)name);
}
static void map_literal(ScriptVariant **args,int mode,int count,void *function) {
 if(!mode) {
  void (*mapper)(ScriptVariant**,int)=(void(*)(ScriptVariant**,int))compiler_mapper(function);
  if(mapper)mapper(args,count);
 }
}
static void getter(int legacy,const char **names,int count,const char *name,int mode,int index) {
 ++cases;reset();*diagnostic=0;Level expected=storage;
 ScriptVariant result=integer(911),*out=&result,a=selector(mode,name,index),*v[]={&a};
 int named=logical(name,names,count),mapped=!legacy && mode==0 && named>=0;
 int property=mapped?named:index,key=F_INVALID;
 if(legacy && mode!=2)key=named>=0?field(names[named]):F_INVALID;
 if(!legacy && property>=0 && property<count)key=field(names[property]);
 int good=key!=F_INVALID && key!=F_ROCK && key!=F_HOLE && key!=F_WALL;
 if(legacy && mode==2)good=0;
 char wanted[512]={0};
 if(!legacy && mode==0 && named<0)level_warning(wanted,name);
 if(legacy && mode==2)strcat(wanted,"Function getlevelproperty must have a string property name.\n");
 else if(legacy && key==F_INVALID)snprintf(wanted,sizeof(wanted),"Property name '%s' is not supported by function getlevelproperty.\n",name);
 else if(!legacy && (key==F_INVALID || key==F_ROCK))strcat(wanted,"Property is not supported by function getlevelproperty yet.\n");
 map_literal(v,mode,1,(void*)openbor_getlevelproperty);
 assert(openbor_getlevelproperty(v,&out,1)==(good?S_OK:E_FAIL));
 assert(out==(good?&result:NULL));
 if(good) {
  int decimal=key==F_GRAVITY || key==F_FALL || key==F_TOSS || key==F_SCROLL;
  assert(result.vt==(decimal?VT_DECIMAL:VT_INTEGER));
  assert((decimal?result.dblVal:(double)result.lVal)==scalar(&expected,key));
 } else assert(result.vt==VT_INTEGER && result.lVal==911);
 assert(a.vt==((mode==2 || mapped)?VT_INTEGER:VT_STR));
 assert(a.lVal==(mapped?named:index) && collects==mapped && !strcmp(diagnostic,wanted));
 same_fields(&expected);
}
static void setter(int legacy,const char **names,int count,int enabled,const char *name,int mode,int index,int value_kind) {
 ++cases;reset();*diagnostic=0;Level expected=storage;
 ScriptVariant result=integer(911),*out=&result,a=selector(mode,name,index),value=integer(2);
 if(value_kind==1){value.vt=VT_DECIMAL;value.dblVal=2.5;}
 if(value_kind>=2)value=string(61,value_kind==3?"enabled":"invalid_value");
 ScriptVariant *v[]={&a,&value};int named=logical(name,names,count),mapped=!legacy && mode==0 && named>=0;
 int property=mapped?named:index,key=F_INVALID;
 if(!legacy && property>=0 && property<count)key=field(names[property]);
 if(legacy && mode!=2) {
  if(!strcmp(name,"rock"))key=F_ROCK;
  else if(!strcmp(name,"bgspeed") || !strcmp(name,"scrollspeed") || !strcmp(name,"cameraxoffset") || !strcmp(name,"camerazoffset"))key=field(name);
 }
 int mapped_value=!legacy && value_kind==3;
 int convertible=value_kind<2 || mapped_value;
 double number=value_kind==1?2.5:mapped_value?enabled:2;
 int good=legacy?mode!=2:key!=F_INVALID;
 int rv=legacy?1:911;
 if(!good)rv=911;
 else if(key==F_HOLE || key==F_WALL) {
  if(convertible){if(key==F_HOLE)expected.numholes=(int)number+1;else expected.numwalls=(int)number+1;}
  rv=0;
 } else if(key!=F_INVALID) {
  if(convertible)assign(&expected,key,(key==F_GRAVITY || key==F_FALL || key==F_TOSS)?number:(int)number);
  else rv=0;
 }
 char wanted[512]={0};
 if(!legacy && mode==0 && named<0)level_warning(wanted,name);
 if(!legacy && value_kind==2)strcat(wanted,"Property name 'invalid_value' is not supported by drawmethod.\n");
 if(!legacy && !good)strcat(wanted,"The level property is read-only.\n");
 map_literal(v,mode,2,(void*)openbor_changelevelproperty);
 assert(openbor_changelevelproperty(v,&out,2)==(good?S_OK:E_FAIL));
 assert(out==(good?&result:NULL) && result.vt==VT_INTEGER && result.lVal==rv);
 assert(a.vt==((mode==2 || mapped)?VT_INTEGER:VT_STR) && a.lVal==(mapped?named:index));
 assert(collects==mapped+mapped_value && !strcmp(diagnostic,wanted));
 if(value_kind==3)assert(value.vt==(legacy?VT_STR:VT_INTEGER) && value.lVal==(legacy?61:enabled));
 same_fields(&expected);
 for(int i=0;i<storage.numholes;++i)for(int j=0;j<7;++j)assert(!storage.holes[i][j]);
 for(int i=0;i<storage.numwalls;++i)for(int j=0;j<8;++j)assert(!storage.walls[i][j]);
}
static void table_roundtrip(int wall,int bulk) {
 ++cases;reset();*diagnostic=0;
 const char *name=wall?"wall":"hole";int fields=wall?8:7;
 ScriptVariant a[10],*v[10],result=integer(911),*out=&result;
 for(int i=0;i<10;++i){a[i]=integer(i);v[i]=&a[i];}
 a[0]=string(40,(char*)name);a[1]=integer(1);a[2]=integer(2);a[3].vt=VT_DECIMAL;a[3].dblVal=4.5;
 int params=bulk?(wall?10:9):4;
 map_literal(v,0,params,(void*)openbor_changelevelproperty);
 assert(openbor_changelevelproperty(v,&out,params)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==911);
 assert(collects==1 && !*diagnostic && (wall?storage.numwalls:storage.numholes)==2);
 for(int j=0;j<fields;++j)assert((wall?storage.walls[1][j]:storage.holes[1][j])==(bulk || j==2?4.5f:0));
 result=integer(911);out=&result;collects=0;*diagnostic=0;
 assert(openbor_getlevelproperty(v,&out,3)==E_FAIL && !out && result.vt==VT_DECIMAL && result.dblVal==4.5);
 assert(!strcmp(diagnostic,wall?"Property is not supported by function getlevelproperty yet.\n":"") && !collects);
 a[1]=integer(-1);result=integer(911);out=&result;*diagnostic=0;
 assert(openbor_getlevelproperty(v,&out,3)==E_FAIL && !out && result.vt==VT_INTEGER && result.lVal==911 && !*diagnostic);
 a[1]=integer(1);a[2]=integer(fields);result=integer(911);out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==S_OK && out==&result && result.lVal==0 && !*diagnostic);
 for(int j=0;j<fields;++j)assert((wall?storage.walls[1][j]:storage.holes[1][j])==(bulk || j==2?4.5f:0));
}
static void check(int legacy,const char **names,int count,int enabled) {
 assert((compiler_mapper((void*)openbor_getlevelproperty)!=NULL)==!legacy);
 assert((compiler_mapper((void*)openbor_changelevelproperty)!=NULL)==!legacy);
 const int indices[]={0,3,8,10,13};
 for(unsigned q=0;q<sizeof(queries)/sizeof(*queries);++q)for(int mode=0;mode<2;++mode)
 for(unsigned k=0;k<sizeof(indices)/sizeof(*indices);++k) {
  getter(legacy,names,count,queries[q],mode,indices[k]);
  for(int value=0;value<3;++value)setter(legacy,names,count,enabled,queries[q],mode,indices[k],value);
 }
 for(int index=-1;index<=count+1;++index) {
  getter(legacy,names,count,"",2,index);
  for(int value=0;value<3;++value)setter(legacy,names,count,enabled,"",2,index,value);
 }
 setter(legacy,names,count,enabled,"bgspeed",0,0,3);
 if(count==11)for(int wall=0;wall<2;++wall)for(int bulk=0;bulk<2;++bulk)table_roundtrip(wall,bulk);
 for(int params=0;params<2;++params) {
  ++cases;reset();*diagnostic=0;
  ScriptVariant property=integer(0),result=integer(911),*out=&result,*v[]={&property};
  assert(openbor_changelevelproperty(v,&out,params)==E_FAIL && !out);
  assert(result.vt==VT_INTEGER && result.lVal==911 && !*diagnostic);
 }
 reset();
}
static void diagnostic_boundary(const char *message,const char *setter_message) {
 ++cases;reset();*diagnostic=0;
 ScriptVariant property=integer(99),result=integer(911),*out=&result,*v[]={&property};
 assert(openbor_getlevelproperty(v,&out,1)==E_FAIL && !out);
 assert(result.vt==VT_INTEGER && result.lVal==911 && !strcmp(diagnostic,message));
 ScriptVariant value=integer(2),*args[]={&property,&value};result=integer(911);out=&result;*diagnostic=0;
 assert(openbor_changelevelproperty(args,&out,2)==E_FAIL && !out);
 assert(result.vt==VT_INTEGER && result.lVal==911 && !strcmp(diagnostic,setter_message));
}
@DEFINITIONS@
int main(void) {@CHECKS@assert(cases==@TOTAL@);return 0;}
'''
                program = program.replace('@DEFINITIONS@', definitions).replace('@CHECKS@', '\n'.join(checks)).replace('@TOTAL@', str(total))
                program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4),
                                 program, flags=re.MULTILINE)
                native(program, extra_flags=('-Wno-unused-variable', '-Wno-unused-function',
                       '-Wno-unused-parameter', '-Wno-unused-local-typedefs', '-Wno-implicit-fallthrough'))

    def test_initial_level_physics_matches_each_source_profile(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' /
            'profile-level-initial-physics-contracts.json').read_text())
        rows, cases = fixture['sources'], fixture['cases']
        self.assertEqual(len({row['revision'] for row in rows}), len(rows))
        known = {row['revision']: row for row in rows}
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            revision = int(profile.get('revision', profile['build']))
            for span in fixture['coverage']:
                if profile['engine'] == span['engine'] and span['first'] <= revision <= span['last']:
                    self.assertEqual(known[revision]['engine'], profile['engine'])
        fields = ('maxtossspeed', 'maxfallspeed', 'gravity')
        definitions = []
        for engine in sorted({row['engine'] for row in rows}):
            self.assertRegex(engine, r'^[0-9]+$')
            root = ROOT / 'src/engines' / engine
            text = (root / 'openbor.c').read_bytes().decode('utf-8', 'surrogateescape')
            body = function(text, 'load_level')
            assignments = re.findall(
                r'(?m)^[ \t]*level->maxtossspeed[^\r\n]*;\r?\n'
                r'[ \t]*level->maxfallspeed[^\r\n]*;\r?\n'
                r'[ \t]*level->gravity[^\r\n]*;', body)
            self.assertEqual(len(assignments), 1)
            header = (root / 'openbor.h').read_bytes().decode('utf-8', 'surrogateescape')
            for field in fields:
                self.assertRegex(header, r'(?m)^\s*float\s+' + field + r'\s*;')
            definitions.append('static void initialize_' + engine + '(void) {\n' +
                               assignments[0] + '\n}\n')
        profiles = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['assignments_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(row['field_types'], dict.fromkeys(fields, 'float'))
            self.assertIn(row['contract'], ('fixed', 'configured'))
            profiles.append('{%d,initialize_%s,%d}' %
                            (row['revision'], row['engine'], row['contract'] == 'configured'))
        def floats(values):
            self.assertEqual(len(values), 3)
            return '{' + ','.join('(float)' + repr(value) for value in values) + '}'
        case_rows = ['{' + floats(case['configured_values']) + ',{' +
                     floats(case['expected']['fixed']) + ',' +
                     floats(case['expected']['configured']) + '}}' for case in cases]
        program = r'''
#include <stdint.h>
#include <stdio.h>
static uint32_t obor_profile_build;
static float default_level_maxtossspeed,default_level_maxfallspeed,default_level_gravity;
static struct {float maxtossspeed,maxfallspeed,gravity;} storage,*level=&storage;
@DEFINITIONS@
static const struct {uint32_t revision;void (*initialize)(void);unsigned contract;} profiles[]={@PROFILES@};
static const struct {float configured[3],expected[2][3];} cases[]={@CASES@};
int main(void) {
 for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
  obor_profile_build=profiles[p].revision;
  for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);++c) {
   default_level_maxtossspeed=cases[c].configured[0];
   default_level_maxfallspeed=cases[c].configured[1];
   default_level_gravity=cases[c].configured[2];
   storage.maxtossspeed=storage.maxfallspeed=storage.gravity=1234.0f;
   profiles[p].initialize();
   const float actual[]={storage.maxtossspeed,storage.maxfallspeed,storage.gravity};
   for(unsigned f=0;f<3;++f) if(actual[f]!=cases[c].expected[profiles[p].contract][f]) {
    fprintf(stderr,"Level defaults differ: profile=%u case=%u field=%u\n",obor_profile_build,c,f);
    return 1;
   }
  }
 }
 return 0;
}
'''.replace('@DEFINITIONS@', '\n'.join(definitions)).replace(
            '@PROFILES@', ','.join(profiles)).replace('@CASES@', ','.join(case_rows))
        with tempfile.TemporaryDirectory(prefix='historical-level-defaults-') as temp:
            source = Path(temp) / 'probe.c'
            executable = Path(temp) / 'probe'
            source.write_text(program)
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-g',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                str(source), '-o', str(executable)], check=True, timeout=45)
            subprocess.run([str(executable)], check=True, timeout=20,
                           env=sanitizer_environment())

    def test_literal_computed_and_numeric_level_property_contracts(self):
        program = level_runtime_program(
            (ENGINE/'openborscript.c').read_text(),
            (ENGINE/'source/scriptlib/ScriptVariant.h').read_text(),
            (ENGINE/'source/scriptlib/ScriptVariant.c').read_text(),
            (ENGINE/'source/utils.c').read_text(), PROFILES)
        # Imported historical bodies mix tabs and spaces. Normalize only
        # leading indentation so compiler diagnostics see the same columns;
        # retain every C token and all warning checks.
        program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4),
                         program, flags=re.MULTILINE)
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
                           env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
