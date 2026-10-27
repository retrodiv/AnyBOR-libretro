"""Check complete entity mappers and their compiler/runtime selection.

Native property cases have separate tests. Here the actual callback prefix
stops after mapping and property selection, before reading entity fields.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture
import json
import os
from pathlib import Path
import re
import unittest

from test_historical_behavior import native
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))


class EntityMapperSplitTests(unittest.TestCase):
    def test_complete_mappers_and_call_routes_match_each_source_profile(self):
        fixture=load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-entity-mapper-contracts.json')
        rows=fixture['sources'];revisions={row['revision'] for row in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        properties=rows[0]['properties'];queries={name:['@missing'] for name in properties}
        layouts={name:(2,False) for name in properties}
        for row in rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(row['properties'],properties)
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
            for rules in row['mapping'].values():
                for rule in rules:
                    layouts[rule['property']]=(rule['argument'],rule['repeat'])
                    for word in rule['names']:
                        if word not in queries[rule['property']]:queries[rule['property']].append(word)
        arrays=[];serial=0
        def strings(values):
            nonlocal serial
            name='strings_'+str(serial);serial+=1
            arrays.append('static const char *const '+name+'[]={'+','.join(map(json.dumps,values))+'};')
            return name
        parent_array=strings(properties);query_rows=[]
        for prop in properties:
            query_rows.append('{%d,%d,%d,%s},' % (
                *map(int,layouts[prop]),len(queries[prop]),strings(queries[prop])))
        contracts=[]
        for row in rows:
            groups=[]
            for operation in ('get','set'):
                rules=row['mapping'][operation];name='rules_'+str(row['revision'])+'_'+operation
                definitions=[]
                for rule in rules:
                    definitions.append('{%d,%d,%d,%d,%s,%s},' % (
                        properties.index(rule['property']),rule['argument'],int(rule['repeat']),
                        len(rule['names']),strings(rule['names']),json.dumps(rule['diagnostic'])))
                arrays.append('static const struct rule '+name+'[]={'+''.join(definitions)+'};')
                groups.extend([len(rules),name])
            contracts.append('{%d,%d,%s,%d,%s,%s,%s},' % (
                row['revision'],*groups,json.dumps(row['main_diagnostic']['get']),
                json.dumps(row['main_diagnostic']['set'])))
        engine=SOURCE/'src/engines/3842';source=(engine/'openborscript.c').read_text()
        start=source.index('enum entityproperty_enum');stop=source.index('HRESULT openbor_getentityproperty(',start)
        declarations=source[start:stop]
        # Older prepared controls expose only the merged mapper. Keep those
        # compilable so this test detects their argument/diagnostic differences.
        if 'void mapstrings_getentityproperty(' not in declarations:
            declarations+='\n#define mapstrings_getentityproperty mapstrings_entityproperty\n'
            declarations+='#define mapstrings_changeentityproperty mapstrings_entityproperty\n'
        dispatcher=function(source,'Script_GetStringMapFunction')
        prefixes=[];actions=set()
        for name in ('openbor_getentityproperty','openbor_changeentityproperty'):
            body=function(source,name);self.assertEqual(body.count('switch(propind)'),1)
            prefix=body[:body.index('switch(propind)')]
            for array in re.findall(r'static const void\*\s*(?:actions|think)\[\]\s*=\s*\{([^}]*)\}',prefix):
                array=re.sub(r'//[^\n]*|/\*.*?\*/','',array,flags=re.S)
                actions.update(re.findall(r'\b[A-Za-z_]\w*\b',array))
            prefix+='last_property=propind;return S_OK;\n'
            if name=='openbor_changeentityproperty':prefix+='changeentityproperty_error:return E_FAIL;\n'
            prefixes.append(prefix+'}\n')
        owned={'openbor_getentityproperty','openbor_changeentityproperty','mapstrings_entityproperty',
               'mapstrings_getentityproperty','mapstrings_changeentityproperty'}
        references=set(re.findall(r'\(void\s*\*\)\s*([A-Za-z_]\w*)',dispatcher))
        stubs='\n'.join('static void '+name+'(void) {}' for name in sorted((references-owned)|actions))
        macro=source[source.index('#define MAPSTRINGS('):];macro=macro[:macro.index('\n\n')]
        variant=(engine/'source/scriptlib/ScriptVariant.c').read_text()
        conversions='\n'.join(function(variant,name) for name in
                              ('ScriptVariant_Clear','ScriptVariant_ChangeType'))
        lookup=function((engine/'source/utils.c').read_text(),'searchList')
        program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
typedef int32_t LONG,HRESULT;typedef double DOUBLE;
typedef enum {VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6} VARTYPE;
typedef struct {union {LONG lVal;DOUBLE dblVal;void *ptrVal;int strVal;};VARTYPE vt;} ScriptVariant;
typedef struct {int unused;} entity,s_model,s_sprite,s_attack;
enum {TYPE_ENEMY=1,TYPE_NPC,TYPE_OBSTACLE,TYPE_PLAYER,TYPE_SHOT};
#define S_OK 0
#define E_FAIL (-1)
#define stricmp strcasecmp
static uint32_t obor_profile_build;static unsigned test_case;
static int last_property;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Entity mapper revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
static char cache[32][128],diagnostics[4096];static int next_string;
static char *StrCache_Get(int index){assert(index>=0 && index<next_string);return cache[index];}
static int StrCache_Pop(void){assert(next_string<32);return next_string++;}
static void StrCache_Collect(int index){assert(index>=0 && index<next_string);}
static int report(const char *format,...) {
 size_t used=strlen(diagnostics);va_list args;va_start(args,format);
 int count=vsnprintf(diagnostics+used,sizeof(diagnostics)-used,format,args);va_end(args);
 assert(count>=0 && used+(size_t)count<sizeof(diagnostics));return count;
}
#define printf report
void ScriptVariant_ChangeType(ScriptVariant *var,VARTYPE type);
@CONVERSIONS@
@LOOKUP@
@MACRO@
@STUBS@
@DECLARATIONS@
@PREFIXES@
@DISPATCH@
struct rule {int property,argument,repeat,count;const char *const *names;const char *diagnostic;};
struct query_group {int argument,repeat,count;const char *const *names;};
struct contract {unsigned revision;int get_count;const struct rule *get;int set_count;const struct rule *set;const char *get_diagnostic,*set_diagnostic;};
@ARRAYS@
static const struct query_group queries[]={@QUERIES@};
static const struct contract contracts[]={@CONTRACTS@};
typedef void (*map_fn)(ScriptVariant**,int);
static ScriptVariant text(const char *word){
 ScriptVariant value={0};ScriptVariant_ChangeType(&value,VT_STR);
 assert(strlen(word)<sizeof(cache[0]));strcpy(StrCache_Get(value.strVal),word);return value;
}
static void check_main(const struct contract *c,int setter) {
 map_fn mapper=(map_fn)Script_GetStringMapFunction(setter?(void*)openbor_changeentityproperty:(void*)openbor_getentityproperty);
 next_string=0;diagnostics[0]=0;++test_case;mapper(NULL,0);assert(!diagnostics[0]);
 ScriptVariant *one[1]={NULL};++test_case;mapper(one,1);assert(!diagnostics[0]);
 ScriptVariant a={0},parent=text("aiflag"),child=text("@child");
 ScriptVariant *two[2]={&a,&parent};++test_case;mapper(two,2);
 assert(parent.vt==VT_INTEGER && parent.lVal==_ep_aiflag && !diagnostics[0]);
 parent=text("@missing-parent");ScriptVariant *args[3]={&a,&parent,&child};
 ++test_case;mapper(args,3);assert(parent.vt==VT_STR && child.vt==VT_STR);
 char expected[4096];snprintf(expected,sizeof(expected),setter?c->set_diagnostic:c->get_diagnostic,"@missing-parent");
 assert(!strcmp(diagnostics,expected));diagnostics[0]=0;
 parent=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=1.25};++test_case;mapper(args,3);
 assert(parent.vt==VT_DECIMAL && parent.dblVal==1.25 && child.vt==VT_STR && !diagnostics[0]);
 const int invalid[]={-1,_ep_the_end};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i){
  parent=(ScriptVariant){.vt=VT_INTEGER,.lVal=invalid[i]};++test_case;mapper(args,3);
  assert(parent.vt==VT_INTEGER && parent.lVal==invalid[i] && child.vt==VT_STR && !diagnostics[0]);
 }
}
static void check(const struct contract *c,int setter,int property,const char *query,
                  int parent_form,int child_form,int path) {
 const struct rule *rules=setter?c->set:c->get,*rule=NULL;
 int count=setter?c->set_count:c->get_count,index=-1;
 for(int i=0;i<count;++i)if(rules[i].property==property){assert(!rule);rule=&rules[i];}
 if(rule)for(int i=0;i<rule->count;++i)if(!strcasecmp(rule->names[i],query))index=i;
 char word[128],parent[128];strcpy(word,query);strcpy(parent,@PARENTS@[property]);
 if(child_form==1)for(unsigned i=0;i<strlen(word);++i)word[i]=(char)toupper((unsigned char)word[i]);
 if(parent_form==2)for(unsigned i=0;i<strlen(parent);++i)parent[i]=(char)toupper((unsigned char)parent[i]);
 next_string=0;diagnostics[0]=0;entity subject={0};ScriptVariant values[6],wanted[6],*args[6];
 for(int i=0;i<6;++i){values[i]=(ScriptVariant){.vt=VT_INTEGER,.lVal=98};args[i]=&values[i];}
 values[0]=(ScriptVariant){.vt=VT_PTR,.ptrVal=&subject};
 values[1]=parent_form?text(parent):(ScriptVariant){.vt=VT_INTEGER,.lVal=property};
 const struct query_group *q=&queries[property];
 for(int i=q->argument;i<(q->repeat?6:q->argument+1);++i)
  values[i]=child_form==2?(ScriptVariant){.vt=VT_INTEGER,.lVal=index<0?0:index}:text(word);
 memcpy(wanted,values,sizeof(wanted));wanted[1]=(ScriptVariant){.vt=VT_INTEGER,.lVal=property};
 int errors=0;
 if(rule && child_form!=2)for(int i=rule->argument;i<(rule->repeat?6:rule->argument+1);++i) {
  if(index>=0)wanted[i]=(ScriptVariant){.vt=VT_INTEGER,.lVal=index};else ++errors;
 }
 map_fn mapper=(map_fn)Script_GetStringMapFunction(setter?(void*)openbor_changeentityproperty:(void*)openbor_getentityproperty);
 assert(mapper==(obor_profile_build<3828?(setter?mapstrings_changeentityproperty:mapstrings_getentityproperty):mapstrings_entityproperty));
 assert(Script_GetStringMapFunction(NULL)==NULL);
 if(path!=1)mapper(args,6);
 if(path!=0) {
  ScriptVariant result={0},*output=&result;last_property=-1;
  assert((setter?openbor_changeentityproperty:openbor_getentityproperty)(args,&output,6)==S_OK);
  assert(last_property==property && (output==NULL)==setter);
 }
 for(int i=0;i<6;++i){
  assert(values[i].vt==wanted[i].vt);
  if(values[i].vt==VT_STR)assert(!strcmp(StrCache_Get(values[i].strVal),word));
  else if(values[i].vt==VT_PTR)assert(values[i].ptrVal==wanted[i].ptrVal);
  else assert(values[i].lVal==wanted[i].lVal);
 }
 char expected[4096]={0};
 if(errors)for(int i=0;i<errors*(path==2?2:1);++i) {
  size_t used=strlen(expected);int count=snprintf(expected+used,sizeof(expected)-used,rule->diagnostic,word);
  assert(count>=0 && used+(size_t)count<sizeof(expected));
 }
 assert(!strcmp(diagnostics,expected));
}
int main(void){
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i){
  const struct contract *c=&contracts[i];obor_profile_build=c->revision;test_case=0;
  check_main(c,0);check_main(c,1);
  for(int setter=0;setter<2;++setter)for(unsigned p=0;p<sizeof(queries)/sizeof(*queries);++p)
  for(int q=0;q<queries[p].count;++q)for(int parent=0;parent<3;++parent)
  for(int child=0;child<3;++child)for(int path=0;path<3;++path){
   ++test_case;check(c,setter,p,queries[p].names[q],parent,child,path);
  }
 }
 return 0;
}
'''
        values={'CONVERSIONS':conversions,'LOOKUP':lookup,'MACRO':macro,'STUBS':stubs,
                'DECLARATIONS':declarations,'PREFIXES':'\n'.join(prefixes),'DISPATCH':dispatcher,
                'ARRAYS':'\n'.join(arrays),'QUERIES':''.join(query_rows),
                'CONTRACTS':''.join(contracts),'PARENTS':parent_array}
        program=re.sub(r'@('+'|'.join(values)+')@',lambda match:values[match[1]],program)
        native(program,extra_flags=['-Wno-unused-variable','-Wno-unused-function',
                                    '-Wno-unused-const-variable'])


if __name__=='__main__':unittest.main()
