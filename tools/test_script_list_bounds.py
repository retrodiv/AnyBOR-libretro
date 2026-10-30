"""Compare script list lookup with defined original source observations.

The original index oracle marks out-of-table reads instead of accepting their
accidental result. These queries must have a defined bounded result in the core.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, rename_identifiers

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
FIXTURE = Path(__file__).parent / 'fixtures/script-list-contracts.json'


def mapper_program(script, lookup):
    """Retain real mapper/tables; stub variant storage/conversion and logging."""
    start = re.search(r'(?m)^enum (?:get)?entityproperty_enum\s*\{', script)
    entry = re.search(r'(?m)^(?:void|int) mapstrings_(?:getentityproperty|entityproperty)\(', script)
    if start is None or entry is None:
        raise ValueError('Entity mapper and own declarations required')
    name = re.search(r'mapstrings_\w+', entry[0])[0]
    declarations = script[start.start():entry.start()]
    axis = re.search(r'(?m)^enum _axis_enum\s*\{', script[:start.start()])
    if axis:
        declarations = script[axis.start():start.start()] + declarations
    # A distinct animation mapper can lie between the entity declarations and
    # entity mapper. It is outside this probe's calls and dependencies.
    animation = re.search(r'(?m)^int mapstrings_animationproperty\(', declarations)
    if animation:
        declarations = declarations[:animation.start()]
    macro = re.search(r'(?ms)^#define MAPSTRINGS\(.*?(?=\n\n)', script)
    if macro is None:
        raise ValueError('Own string mapping macro required')
    mapper = function(script, name)
    descriptor = support = ''
    if 'obor_get_property_namespace(' in mapper:
        from test_early_entity_namespaces import namespace_descriptor
        descriptor = namespace_descriptor(script, 'obor_property_namespace')
        support = '\n'.join(function(script, helper) for helper in (
            'obor_property_index', 'obor_get_property_namespace', 'obor_get_aiflag_namespace'))
        tables = re.findall(r'(?m)^static const [^\n]*\bobor_(?:get_property|get_aiflag)_namespace_\d+_(?:names|ids|table)\b[^\n]*;', script)
        referenced = set(re.findall(r'&([A-Za-z_]\w*_table)\b', support))
        if not referenced or any(sum(bool(re.search(r'\b' + re.escape(name) + r'\s*=', row)) for row in tables) != 1 for name in referenced):
            raise ValueError('Every selected namespace must retain its actual table')
        support = '\n'.join(tables) + '\n' + support
    prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
enum {VT_EMPTY=0,VT_INTEGER=1,VT_STR=6};
typedef struct {int vt;union {int32_t lVal,strVal;};} ScriptVariant;
static const char *strings[2];
static char *StrCache_Get(int32_t index) {assert(index>=0 && index<2);return (char*)strings[index];}
static void ScriptVariant_ChangeType(ScriptVariant *value,int type) {value->vt=type;}
static uint32_t obor_profile_build=3741;
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
#define stricmp strcasecmp
#define _is_not_a_known_subproperty_of_ "'%s' is not a known subproperty of '%s'.\n"
#define _is_not_supported_by_ "'%s' is not supported by '%s'.\n"
'''
    main = r'''
int main(void) {
 static const char *properties[]={"landframe","staydown"};
 static const char *queries[][6]={{"ent","frame","ENT","FRAME","ent_missing","z"},
  {"rise","riseattack","riseattack_stall","RISEATTACK_STALL","rise_missing","z"}};
 static const int expected[][6]={{0,1,0,1,-1,-1},{0,1,2,2,-1,-1}};
 for(int property=0;property<2;++property) for(int query=0;query<6;++query) {
  strings[0]=properties[property];strings[1]=queries[property][query];
  ScriptVariant values[3]={{0},{.vt=VT_STR,.strVal=0},{.vt=VT_STR,.strVal=1}};
  ScriptVariant *args[]={&values[0],&values[1],&values[2]};
  @MAPPER@(args,3);assert(values[1].vt==VT_INTEGER);
  if(expected[property][query]>=0) {
   assert(values[2].vt==VT_INTEGER && values[2].lVal==expected[property][query]);
   @MAPPER@(args,3);assert(values[2].lVal==expected[property][query]);
  } else assert(values[2].vt==VT_STR);
 }
 return 0;
}
'''
    return '\n'.join((prefix, descriptor, lookup, macro[0], declarations,
                       support, mapper, main.replace('@MAPPER@', name)))


def lookup_program(functions, cases, *, original=False):
    """Accept extracted lookup functions; original mode records source observations."""
    tables, data = [], []
    for index, case in enumerate(cases):
        names = 'table_' + str(index)
        tables.append('static const char *' + names + '[]={' +
                      ','.join(map(json.dumps, case['names'])) + '};')
        expected = case.get('original_result', -1)
        data.append('{%s,%d,%s,%d,%d},' % (names, len(case['names']),
                    json.dumps(case['query']), int(case.get('original_defined', False)), expected))
    definitions, calls = [], []
    for engine, source in functions.items():
        name = 'search_' + engine
        definitions.append(rename_identifiers(source, {'searchList': name}))
        calls.append('{"' + engine + '",' + name + '},')
    prefix = r'''
#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
static int invalid_index,actual_count;
static const char *source_at(const char **list,int length,int index) {
 if(index<0 || index>=length || index>=actual_count) {invalid_index=1;return "";}
 return list[index];
}
'''
    program = prefix + '\n'.join(definitions + tables) + r'''
struct query {const char **names;int count;const char *value;int defined,result;};
static const struct query queries[]={ @DATA@ };
struct engine {const char *name;int (*search)(const char **,const char *,int);};
static const struct engine engines[]={ @CALLS@ };
int main(void) {
@OPEN@
 for(unsigned e=0;e<sizeof(engines)/sizeof(*engines);++e) {
  for(unsigned q=0;q<sizeof(queries)/sizeof(*queries);++q) {
   const struct query *query=&queries[q];actual_count=query->count;invalid_index=0;
   int result=engines[e].search(query->names,query->value,query->count);
@CHECK@
  }
@EMPTY@
 }
@CLOSE@
 return 0;
}
'''
    if original:
        opening = ('char path[4096];assert(snprintf(path,sizeof(path),"%s/lookup-observations.json",'
                   'getenv("ANYBOR_NATIVE_ARTIFACTS"))<(int)sizeof(path));'
                   'FILE *output=fopen(path,"w");assert(output);fputs("[",output);int first=1;')
        check = r'''fprintf(output,"%s{\"engine\":\"%s\",\"query\":%u,\"defined\":%s,\"result\":%d}",
 first?"":",",engines[e].name,q,invalid_index?"false":"true",result);first=0;'''
        close = 'fputs("]\\n",output);assert(!fclose(output));puts(' + json.dumps(json.dumps({
            'status': 'PASS', 'engines': len(functions), 'queries': len(cases)})) + ');'
        empty = ''
    else:
        opening, close = '', ''
        check = r'''
   if(query->defined) assert(result==query->result);
   else if(result>=0) {assert(result<query->count);assert(!strcasecmp(query->names[result],query->value));}
   else assert(result==-1);
'''
        empty = r'''
  const char *one[]={"a"};
  assert(engines[e].search(NULL,"a",1)==-1);
  assert(engines[e].search(one,NULL,1)==-1);
  assert(engines[e].search(one,"a",0)==-1);
  assert(engines[e].search(one,"a",-1)==-1);
'''
    insertions = {'DATA': '\n'.join(data), 'CALLS': '\n'.join(calls),
                  'OPEN': opening, 'CHECK': check, 'EMPTY': empty, 'CLOSE': close}
    return re.sub(r'@(' + '|'.join(insertions) + r')@', lambda m: insertions[m[1]], program)


class ScriptListTests(unittest.TestCase):
    def test_actual_landframe_and_staydown_mappers_remain_in_their_tables(self):
        fixture = load_contract_fixture(FIXTURE)
        with tempfile.TemporaryDirectory(prefix='anybor-script-mapper-') as temporary:
            work = Path(temporary)
            for engine in fixture['engines']:
                with self.subTest(engine=engine):
                    root = SOURCE / 'src/engines' / engine
                    source = work / (engine + '.c'); executable = work / engine
                    source.write_text(mapper_program((root / 'openborscript.c').read_text(),
                        function((root / 'source/utils.c').read_text(), 'searchList')))
                    subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                        '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-error=deprecated-declarations', '-Wno-unused-function',
                        '-Wno-unused-variable', '-Wno-unused-const-variable',
                        '-g', '-fsanitize=address,undefined', str(source),
                        '-o', str(executable)], check=True, timeout=60)
                    subprocess.run([str(executable)], check=True, timeout=20,
                                   env=sanitizer_environment())

    def test_defined_original_results_and_bounded_missing_queries(self):
        fixture = load_contract_fixture(FIXTURE)
        functions = {}
        for engine in fixture['engines']:
            source = SOURCE / 'src/engines' / engine / 'source/utils.c'
            functions[engine] = function(source.read_text(), 'searchList')
        # Source observations are identical for these implementations. Keep the
        # engine identities in the fixture rather than assuming another version.
        self.assertEqual(set(functions), set(fixture['source_hashes']))
        with tempfile.TemporaryDirectory(prefix='anybor-script-list-') as temporary:
            work = Path(temporary); source = work / 'probe.c'; executable = work / 'probe'
            source.write_text(lookup_program(functions, fixture['queries']))
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                '-Wno-unused-variable', '-g', '-fsanitize=address,undefined',
                str(source), '-o', str(executable)], check=True, timeout=60)
            subprocess.run([str(executable)], check=True, timeout=20,
                           env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
