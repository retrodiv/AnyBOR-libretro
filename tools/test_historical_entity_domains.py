"""Check entity selector domains, mapper dispatch and callback case routing.

Case bodies are replaced by routing markers; their mutations and results have
separate probes. These checks retain actual callback validation, mapper bodies,
variant conversion and string lookup. They do not execute a full interpreter.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, rename_identifiers, switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = load_contract_fixture(Path(__file__).parent /
    'fixtures/profile-entity-domain-contracts.json')


def routing_entry(source, name):
    method, cases = switch_cases(source, name, 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['body_start'], reverse=True):
        if label != 'default':
            if not re.fullmatch(r'_ep_[a-z_0-9]+', label):
                raise ValueError('Reviewed entity case labels required')
            method = (method[:row['body_start']] +
                '{ last_case=' + json.dumps(label[4:]) + ';break; }\n' + method[row['end']:])
    actions = set()
    for body in re.findall(r'static const void\*\s*(?:actions|think)\[\]\s*=\s*\{([^}]*)\}', method):
        body = re.sub(r'//[^\n]*|/\*.*?\*/', '', body, flags=re.S)
        actions.update(re.findall(r'\b[A-Za-z_]\w*\b', body))
    return method, actions


def source_component(fragments, prefix=''):
    getter, get_actions = routing_entry(fragments['openbor_getentityproperty'],
                                      'openbor_getentityproperty')
    setter, set_actions = routing_entry(fragments['openbor_changeentityproperty'],
                                      'openbor_changeentityproperty')
    declarations = fragments['getter_domains'] + fragments['setter_subdomains']
    methods = '\n'.join(fragments[name] for name in
        ('mapstrings_getentityproperty', 'mapstrings_changeentityproperty'))
    dispatcher = fragments['compiler_dispatch']
    owned = {'openbor_getentityproperty', 'openbor_changeentityproperty',
        'mapstrings_getentityproperty', 'mapstrings_changeentityproperty',
        'Script_GetStringMapFunction'}
    text = declarations + methods + getter + setter + dispatcher
    names = set(re.findall(r'\b_(?:ep|gep|cep)_\w+', text)) | owned
    names.update(re.findall(r'\benum\s+(\w+)\s*\{', declarations))
    names.update(re.findall(r'static const char\s*\*\s*(\w+)\[\]', text))
    names.update(re.findall(r'\bobor_(?:entity|map_entity)_\w+', declarations))
    if prefix:
        text = rename_identifiers(text, {name: prefix + name for name in names})
    references = set(re.findall(r'\(void\s*\*\)\s*([A-Za-z_]\w*)', dispatcher))
    return {'definitions': text, 'stubs': sorted((references - owned) | get_actions | set_actions),
        'get': prefix + 'openbor_getentityproperty',
        'set': prefix + 'openbor_changeentityproperty',
        'dispatch': prefix + 'Script_GetStringMapFunction'}


def generated_fragments():
    engine = SOURCE / 'src/engines/3741'
    source = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    fragments = {}
    for label, pattern in (
        ('getter_domains', r'(?ms)^enum entityproperty_enum\s*\{.*?(?=^void mapstrings_getentityproperty\()'),
        ('setter_subdomains', r'(?ms)^enum cep_energycost_enum\s*\{.*?(?=^void mapstrings_changeentityproperty\()'),
        ('mapstrings_macro', r'(?ms)^#define MAPSTRINGS\(.*?(?=\n\n)')):
        match = re.search(pattern, source)
        if match is None:
            raise ValueError('Missing source region: ' + label)
        fragments[label] = match[0]
    for name in ('mapstrings_getentityproperty', 'mapstrings_changeentityproperty',
                 'openbor_getentityproperty', 'openbor_changeentityproperty'):
        fragments[name] = function(source, name)
    fragments['compiler_dispatch'] = function(source, 'Script_GetStringMapFunction')
    fragments['searchList'] = function((engine / 'source/utils.c').read_text(), 'searchList')
    for name in ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue'):
        fragments[name] = function(variants, name)
    return fragments


def domain_program(components=None, common=None, contracts=None, original=False):
    rows = CONTRACTS['sources'] if contracts is None else contracts
    if components is None:
        common = generated_fragments()
        component = source_component(common)
        components = {row['revision']: component for row in rows}
    if common is None:
        raise ValueError('Explicit common source functions required')
    parts, structs = [], []
    for row in rows:
        spec = CONTRACTS['contracts'][row['contract']]
        stem = 'contract_' + str(row['revision'])
        parts.append('static const char *const ' + stem + '_names[]={' +
                     ','.join(map(json.dumps, spec['properties'])) + '};')
        for operation in ('get', 'set'):
            parts.append('static const unsigned char ' + stem + '_' + operation + '[]={' +
                ','.join(str(int(name in spec[operation + '_cases']))
                         for name in spec['properties']) + '};')
        subs = []
        for setter, operation in enumerate(('get', 'set')):
            for sub in spec[operation + '_subproperties']:
                symbol = stem + '_sub_' + str(len(subs))
                parts.append('static const char *const ' + symbol + '[]={' +
                             ','.join(map(json.dumps, sub['names'])) + '};')
                subs.append('{%d,%d,%d,%d,%d,%s},' %
                    (setter, spec['properties'].index(sub['property']), sub['argument'],
                     sub['repeat'], len(sub['names']), symbol))
        parts.append('static const struct subproperty ' + stem + '_subs[]={' + ''.join(subs) + '};')
        component = components[row['revision']]
        structs.append('{%d,%d,%d,%s_names,%s_get,%s_set,%d,%s_subs,%s,%s,%s},' %
            (row['revision'], row['has_result'], len(spec['properties']), stem, stem, stem,
             len(subs), stem, component['get'], component['set'], component['dispatch']))
    definitions = '\n'.join(dict.fromkeys(component['definitions'] for component in components.values()))
    stubs = sorted({name for component in components.values() for name in component['stubs']})
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
typedef int32_t LONG,HRESULT;
typedef double DOUBLE;
typedef void VOID;
typedef enum { VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6 } VARTYPE;
typedef struct { union { LONG lVal; void *ptrVal; DOUBLE dblVal; int strVal; }; VARTYPE vt; } ScriptVariant;
typedef struct { int marker; } entity,s_model,s_sprite,s_attack;
enum { TYPE_ENEMY=1,TYPE_NPC,TYPE_OBSTACLE,TYPE_PLAYER,TYPE_SHOT };
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
#define stricmp strcasecmp
static uint32_t obor_profile_build;
static const char *last_case;
static int fixture_source_lookup_invalid;
static char strings[16][128];
static int next_string;
static char *StrCache_Get(int index) { assert(index>=0 && index<16);return strings[index]; }
static int StrCache_Pop(void) { assert(next_string<16);return next_string++; }
static void StrCache_Collect(int index) { assert(index>=0 && index<16); }
static int quiet_printf(const char *format,...) { (void)format;return 0; }
#define printf quiet_printf
@CONVERSIONS@
@LOOKUP@
@MACRO@
@STUBS@
@DEFINITIONS@
typedef HRESULT (*entry_fn)(ScriptVariant **,ScriptVariant **,int);
typedef void (*map_fn)(ScriptVariant **,int);
struct subproperty { int setter,property,argument,repeat,count; const char *const *names; };
struct contract {
 int revision,has_result,count;const char *const *names;
 const unsigned char *get_cases,*set_cases;int sub_count;
 const struct subproperty *subs;entry_fn get,set;void *(*dispatch)(void *);
};
@DATA@
static const struct contract contracts[]={ @CONTRACTS@ };
static ScriptVariant text(const char *value) {
 ScriptVariant result={0};ScriptVariant_ChangeType(&result,VT_STR);
 assert(strlen(value)<sizeof(strings[0]));strcpy(StrCache_Get(result.strVal),value);
 return result;
}
static map_fn mapper(const struct contract *c,int setter) {
 return (map_fn)c->dispatch((void*)(setter?c->set:c->get));
}
static void route(const struct contract *c,int setter,ScriptVariant *values,
                  int expected_status,const char *expected_case,int count) {
 ScriptVariant *args[4];assert(count>=2 && count<=4);
 for(int i=0;i<count;++i) args[i]=&values[i];
 ScriptVariant result={.vt=VT_INTEGER,.lVal=999},*output=&result;last_case=NULL;
 fixture_source_lookup_invalid=0;
 assert((setter?c->set:c->get)(args,&output,count)==expected_status);
 assert(!fixture_source_lookup_invalid);
 assert((output!=NULL)==(expected_status==S_OK && (!setter || c->has_result)));
 if(expected_case) assert(last_case && !strcmp(last_case,expected_case));
 else assert(last_case==NULL);
}
static void check(const struct contract *c) {
 obor_profile_build=c->revision;entity subject={0};
 assert(c->dispatch(NULL)==NULL);
 for(int setter=0;setter<2;++setter) {
  for(int property=0;property<c->count;++property) {
   for(int form=0;form<4;++form) {
    next_string=0;ScriptVariant values[3]={{.vt=VT_PTR,.ptrVal=&subject},
        {.vt=VT_INTEGER,.lVal=property},{.vt=VT_INTEGER,.lVal=0}};
    if(form) {
     char name[128];strcpy(name,c->names[property]);
     if(form==3) for(unsigned i=0;i<strlen(name);++i) name[i]=(char)toupper((unsigned char)name[i]);
     values[1]=text(name);
     if(form==2) {
      ScriptVariant *args[]={&values[0],&values[1],&values[2]};
      mapper(c,setter)(args,3);
      assert(values[1].vt==VT_INTEGER && values[1].lVal==property);
      mapper(c,setter)(args,3);
      assert(values[1].vt==VT_INTEGER && values[1].lVal==property);
     }
    }
    int available=(setter?c->set_cases:c->get_cases)[property];
    route(c,setter,values,available?S_OK:E_FAIL,available?c->names[property]:NULL,3);
    assert(values[1].vt==VT_INTEGER && values[1].lVal==property);
   }
  }
  for(int invalid=0;invalid<3;++invalid) {
   int property=invalid==0?-1:invalid==1?c->count:INT_MAX;
   ScriptVariant values[3]={{.vt=VT_PTR,.ptrVal=&subject},
    {.vt=VT_INTEGER,.lVal=property},{.vt=VT_INTEGER,.lVal=0}};
   route(c,setter,values,E_FAIL,NULL,3);
  }
  // A failed textual lookup retains its string-cache index. The original
  // getter still routes through that union member; the setter rejects it.
  next_string=0;ScriptVariant values[3]={{.vt=VT_PTR,.ptrVal=&subject},
    {.vt=VT_EMPTY},{.vt=VT_INTEGER,.lVal=0}};
  values[1]=text("@missing");assert(values[1].strVal==0);
  route(c,setter,values,setter?E_FAIL:S_OK,setter?NULL:c->names[0],3);
  values[0]=(ScriptVariant){.vt=VT_EMPTY};
  route(c,setter,values,S_OK,NULL,3);
  values[0]=(ScriptVariant){.vt=VT_INTEGER,.lVal=0};
  route(c,setter,values,E_FAIL,NULL,3);
 }
 for(int sub=0;sub<c->sub_count;++sub) {
  const struct subproperty *s=&c->subs[sub];
  for(int value=0;value<s->count;++value) for(int upper=0;upper<2;++upper) {
   next_string=0;ScriptVariant values[6]={0},*args[6];
   for(int i=0;i<6;++i) args[i]=&values[i];
   values[1]=text(c->names[s->property]);
   char name[128];strcpy(name,s->names[value]);
   if(upper) for(unsigned i=0;i<strlen(name);++i) name[i]=(char)toupper((unsigned char)name[i]);
   int count=s->repeat?6:s->argument+1;
   for(int arg=s->argument;arg<count;++arg) values[arg]=text(name);
   fixture_source_lookup_invalid=0;
   mapper(c,s->setter)(args,count);
#if !@GENERATED@
   if(fixture_source_lookup_invalid) {
    fprintf(stderr,"SOURCE_UNDEFINED_LOOKUP revision=%d setter=%d property=%s query=%s\n",
            c->revision,s->setter,c->names[s->property],name);
    continue;
   }
#endif
   assert(values[1].vt==VT_INTEGER && values[1].lVal==s->property);
   for(int arg=s->argument;arg<count;++arg)
    assert(values[arg].vt==VT_INTEGER && values[arg].lVal==value);
   mapper(c,s->setter)(args,count);
   for(int arg=s->argument;arg<count;++arg) assert(values[arg].lVal==value);
  }
#if @GENERATED@
  next_string=0;ScriptVariant values[6]={0},*args[6];
  for(int i=0;i<6;++i) args[i]=&values[i];
  values[1]=text(c->names[s->property]);
  int count=s->repeat?6:s->argument+1;
  for(int arg=s->argument;arg<count;++arg) values[arg]=text("@missing");
  mapper(c,s->setter)(args,count);
  for(int arg=s->argument;arg<count;++arg) assert(values[arg].vt==VT_STR);
#endif
 }
}
int main(int argc,char **argv) {
 assert(argc==2);int revision=atoi(argv[1]),matched=0;
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
  if(contracts[i].revision==revision) { check(&contracts[i]);++matched; }
 }
 assert(matched==1);return 0;
}
'''
    if original:
        observation = {'status': 'PASS', 'sources': len(rows),
                       'contracts': len({row['contract'] for row in rows})}
        program = program[:program.index('int main(int argc,char **argv)')] + (
            'int main(void) {for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)'
            'check(&contracts[i]);puts(' + json.dumps(json.dumps(observation)) + ');return 0;}\n')
    insertions = dict((
        ('CONVERSIONS', '\n'.join(common[name] for name in
            ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue'))),
        ('LOOKUP', common['searchList']), ('MACRO', common['mapstrings_macro']),
        ('STUBS', '\n'.join('static void '+name+'(void) {}' for name in stubs)),
        ('DEFINITIONS', definitions), ('DATA', '\n'.join(parts)),
        ('CONTRACTS', '\n'.join(structs)), ('GENERATED', str(int(not original)))))
    return re.sub(r'@(' + '|'.join(insertions) + r')@',
                  lambda match: insertions[match[1]], program)


class EntityDomainTests(unittest.TestCase):
    def test_registry_has_own_source_domains_and_registered_profiles(self):
        revisions = [row['revision'] for row in CONTRACTS['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        for key, contract in CONTRACTS['contracts'].items():
            raw = json.dumps(contract, sort_keys=True, separators=(',', ':')).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), key)
            self.assertEqual(len(contract['properties']), len(set(contract['properties'])))
        for row in CONTRACTS['sources']:
            self.assertIn(row['contract'], CONTRACTS['contracts'])
            spec = CONTRACTS['contracts'][row['contract']]
            for query in row['undefined_lookup_queries']:
                self.assertIn(query['operation'], ('get', 'set'))
                sub = next(value for value in spec[query['operation'] + '_subproperties']
                           if value['property'] == query['property'])
                self.assertEqual(sub['names'].index(query['query'].lower()),
                                 query['defined_core_index'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['has_result']), bool)
            for mapping in ('source_hashes', 'auxiliary_hashes'):
                for digest in row[mapping].values():
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-entity-domain-contracts.json', pin['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)

    def test_numeric_textual_compiler_mappers_and_case_routing_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-entity-domains-') as temporary:
            work=Path(temporary);source=work/'probe.c';exe=work/'probe'
            source.write_text(domain_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc')) + [
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-const-variable','-Wno-unused-function',
                '-g','-fsanitize=address,undefined',str(source),'-o',str(exe)],
                check=True,timeout=60)
            executed=[]
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe),str(row['revision'])],check=True,
                        timeout=20,env=sanitizer_environment())
                    executed.append(row['revision'])
            self.assertEqual(executed,[row['revision'] for row in CONTRACTS['sources']])
            print(json.dumps({'executed_sources':executed,
                'scope':'Main/subproperty mapping and transformed callback case routing; case bodies separate'}))


if __name__=='__main__':
    unittest.main()
