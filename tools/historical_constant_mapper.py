"""Render source-defined constant lookup and compile/runtime binding checks.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from test_historical_player import function


def constant_queries(fixture):
    names = sorted({name for row in fixture['sources'] for name in row['plain_names']})
    dynamic = []
    for call in fixture['sources'][-1]['suffix_calls']:
        prefix = re.fullmatch(r'ICMPSCONST[ABC]\((\w+)(?:, \w+)?\)', call)[1]
        dynamic += [prefix + str(n) for n in (1, 2, 11, 12)]
        if call.startswith('ICMPSCONSTC('):
            dynamic += [prefix.lower()+'1',prefix+'0',prefix+'01',prefix+'-1',prefix+'1tail']
    return sorted(set(names + [name.lower() for name in names] + dynamic +
                      ['', 'SYNTHETIC_UNKNOWN_CONSTANT', 'ANI_UNKNOWN17',
                       'ANI_ATTACK11tail', 'ANI_FALL12tail']))


def _number(text):
    match = re.match(r'[+-]?\d+', text)
    return int(match[0]) if match else 0


def _lookup(row, arrays, name, epoch, *, mapper):
    """Expected values come from the own-source name/path records, not the patch."""
    upper = name.upper()
    declared = {item.upper(): item for item in row['plain_names']}
    if upper in declared:
        value = row['assessed_values'].get(declared[upper], 0)
        if value is None:
            raise ValueError('Declared assessed constant lacks its own value')
        return 1, value
    if row['suffix_in_mapper']:
        for call in row['suffix_calls']:
            kind, prefix, array = re.fullmatch(r'ICMPSCONST([ABC])\((\w+)(?:, (\w+))?\)', call).groups()
            matched_prefix = row.get('expanded_suffix_prefixes', {}).get(prefix, prefix)
            matched_suffix = upper[len(matched_prefix):] if upper.startswith(matched_prefix) else ''
            if matched_suffix and '1' <= matched_suffix[0] <= '9':
                suffix = upper[len(prefix):]
                if kind == 'C':
                    return 1, _number(suffix) + row['special_slots'] - 1
                index = _number(suffix) - 1 + (row['special_slots'] if kind == 'B' else 0)
                if not 0 <= index < 64:
                    raise ValueError('Test query exceeds configured native table')
                return 1, epoch + arrays.index(array) * 128 + index
    if not mapper and row['legacy_paths']:
        for path in row['legacy_paths']:
            width, offset = path['compare_width'], path['read_offset']
            if (len(name) <= offset or upper[:width] != path['prefix'][:width] or
                    name[offset] < '1' or (path['digit_ceiling'] and name[offset] > '9')):
                continue
            number = _number(name[offset:])
            if path['minimum_extra']:
                number = max(number, row['base_slots'] - row['special_slots'] + 1)
            index = number - 1 + (row['special_slots'] if 'STA_ATKS' in path['index'] else 0)
            if 0 <= index < 64:
                return 1, epoch + arrays.index(path['array']) * 128 + index
            # The original would leave its table. The safe result is empty.
            return 0, 0
    return (4, 0) if mapper else ((0, 0) if row['unknown_empty_success'] else (-1, 0))


def render_constant_mapper(engine, fixture):
    script = (engine / 'openborscript.c').read_text()
    start = script.index('#define IICMPCONST(')
    mapper = function(script, 'mapstrings_transconst')
    macros = script[start:script.index(mapper.splitlines()[0], start)]
    entry = function(script, 'openbor_transconst')
    mapped = set(re.findall(r'(?:IICMPCONST|ICMPCONST|ICMPLEGACYCONST)\((\w+)\)', mapper))
    header = (engine / 'openbor.h').read_text()
    assessed = fixture['assessed_names']
    definitions = []
    for name in assessed:
        match = re.search(r'(?m)^#define\s+' + name + r'\s+(-?(?:0x[\dA-Fa-f]+|\d+))\b', header)
        if match is None:
            raise ValueError('Assessed physical constant missing: ' + name)
        definitions.append('#define ' + name + ' ' + match[1])
    for name in ['MAX_ATKS', 'STA_ATKS']:
        match = re.search(r'(?m)^#define\s+' + name + r'\s+([^\n]+)', header)
        if match is None:
            raise ValueError('Native attack-domain definition missing: ' + name)
        definitions.append('#define ' + name + ' ' + match[1])
    # Unchanged, unrelated numeric namespaces are controlled providers. This
    # probe checks their names, not their numeric contracts.
    definitions += ['#define ' + name + ' 0' for name in sorted(mapped - set(assessed))]
    arrays = fixture['arrays']
    definitions += ['static int ' + name + '_storage[64]; static int *' + name +
                    '=' + name + '_storage;' for name in arrays]
    definitions += ['int ' + name + '=64;' for name in
                    ['max_downs', 'max_ups', 'max_backwalks', 'max_walks', 'max_idles',
                     'max_attack_types', 'max_attacks', 'max_follows', 'max_freespecials']]
    engine_source = (engine / 'openbor.c').read_text()
    definitions += [function(engine_source, name) for name in
                    ('obor_attack_base', 'obor_attack_special')]
    definitions += ['#define OBOR_ATTACK_BASE (obor_attack_base())',
                    '#define OBOR_ATTACK_SPECIAL (obor_attack_special())']
    queries = constant_queries(fixture)
    checks = []
    case_tables = {}
    for row in fixture['sources']:
        cases = []
        for query in queries:
            direct = _lookup(row, arrays, query, 1000, mapper=False)
            mapped_result = _lookup(row, arrays, query, 1000, mapper=True)
            late = mapped_result if mapped_result[0] == 1 else _lookup(
                row, arrays, query, 5000, mapper=False)
            cases.append('{%s,%d,%d,%d,%d,%d,%d}' % (
                json.dumps(query), *direct, *mapped_result, *late))
        key = tuple(cases)
        table = case_tables.setdefault(key, 'source_cases_' + str(len(case_tables)))
        diagnostic = json.dumps(row.get('unknown_mapper_diagnostic', ''))
        checks.append('obor_profile_build=%d; check(%s,%d,%s,%d);' % (
            row['revision'], table, len(cases), diagnostic, row['unknown_empty_success']))
    tables = '\n'.join('static const Case ' + name + '[]={' + ','.join(cases) + '};'
                       for cases, name in case_tables.items())
    fills = ''.join('for(int i=0;i<64;++i)' + name + '[i]=epoch+' + str(a * 128) + '+i;'
                    for a, name in enumerate(arrays))
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
typedef long LONG;typedef int HRESULT;
enum {VT_EMPTY,VT_INTEGER,VT_DECIMAL,VT_PTR,VT_STR};
typedef struct {int vt;LONG lVal;int strVal;} ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define TRUE 1
#define FALSE 0
#define stricmp strcasecmp
#define strnicmp strncasecmp
static uint32_t obor_profile_build;
static const char *query_text;
static unsigned cases;
static char *StrCache_Get(int index){assert(index==7);return (char*)query_text;}
static void ScriptVariant_Init(ScriptVariant *v){memset(v,0,sizeof(*v));}
static void ScriptVariant_Clear(ScriptVariant *v){memset(v,0,sizeof(*v));}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){memset(v,0,sizeof(*v));v->vt=type;}
static void ScriptVariant_Copy(ScriptVariant *to,const ScriptVariant *from){*to=*from;}
static void ScriptVariant_ToString(ScriptVariant *v,char *buffer){
 snprintf(buffer,128,"%.100s",v->vt==VT_STR?query_text:"non-string");
}
static char trace[512];
static int quiet_printf(const char *format,...){
 size_t offset=strlen(trace);
 va_list args;va_start(args,format);
 int length=vsnprintf(trace+offset,sizeof(trace)-offset,format,args);
 va_end(args);
 assert(length>=0 && (size_t)length<sizeof(trace)-offset);
 return length;
}
@DEFINITIONS@
@MACROS@
#define printf quiet_printf
@MAPPER@
@ENTRY@
#undef printf
typedef struct {const char *name;int direct_kind;LONG direct_value;
 int map_kind;LONG map_value;int late_kind;LONG late_value;} Case;
@TABLES@
static void fill(int epoch){@FILLS@}
static void verify(const Case *c,int mode,int kind,LONG value,
                   HRESULT status,ScriptVariant *result,ScriptVariant *out){
 if((kind<0 && (status!=E_FAIL || out!=NULL)) ||
    (kind>=0 && (status!=S_OK || out!=result || result->vt!=kind ||
     (kind==VT_INTEGER && result->lVal!=value)))) {
  fprintf(stderr,"constant profile=%u query=%s phase=%d expected=%d:%ld actual=%d:%ld status=%d\n",
   obor_profile_build,c->name,mode,kind,value,result->vt,result->lVal,status);abort();
 }
}
static void check(const Case *rows,unsigned count,const char *mapper_diagnostic,int legacy_entry){
 for(unsigned i=0;i<count;++i)for(int mode=0;mode<2;++mode){
  const Case *c=&rows[i];++cases;query_text=c->name;fill(1000);
  ScriptVariant arg={VT_STR,0,7},result={VT_INTEGER,77,0},*out=&result,*args[]={&arg};
  char expected[512]={0};
  trace[0]=0;
  if(mode){
   mapstrings_transconst(args,1);
   if(arg.vt!=c->map_kind || (arg.vt==VT_INTEGER && arg.lVal!=c->map_value)){
    fprintf(stderr,"constant mapper profile=%u query=%s\n",obor_profile_build,c->name);abort();
   }
   if(arg.vt==VT_STR)assert(arg.strVal==7);
   if(arg.vt==VT_STR && *mapper_diagnostic)
    snprintf(expected,sizeof(expected),mapper_diagnostic,c->name);
   assert(!strcmp(trace,expected));
   trace[0]=0;
   fill(5000);
  }
  HRESULT status=openbor_transconst(args,&out,1);
  int expected_kind=mode?c->late_kind:c->direct_kind;
  expected[0]=0;
  if(expected_kind<0){
   if(*mapper_diagnostic)snprintf(expected,sizeof(expected),mapper_diagnostic,c->name);
   size_t used=strlen(expected);
   snprintf(expected+used,sizeof(expected)-used,"Can't translate constant %s\n",c->name);
  }
  assert(!strcmp(trace,expected));
  verify(c,mode,mode?c->late_kind:c->direct_kind,
         mode?c->late_value:c->direct_value,status,&result,out);
 }
 /* Numeric input bypasses the name mapper without losing its value. */
 ScriptVariant arg={VT_INTEGER,-17,0},result={0},*out=&result,*args[]={&arg};
 assert(openbor_transconst(args,&out,1)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==-17);
 ++cases;
 trace[0]=0;out=&result;
 assert(openbor_transconst(NULL,&out,0)==E_FAIL && !out && !trace[0]);
 ++cases;
 arg.vt=VT_DECIMAL;
 result=(ScriptVariant){VT_DECIMAL,77,0};
 out=&result;
 assert(openbor_transconst(args,&out,1)==E_FAIL && !out);
 assert(result.vt==(legacy_entry?VT_INTEGER:VT_DECIMAL));
 assert(!strcmp(trace,legacy_entry?"":"Can't translate constant non-string\n"));
 ++cases;
}
int main(void){@CHECKS@
 printf("{\"status\":\"PASS\",\"profiles\":%d,\"checks\":%u}\n",@PROFILES@,cases);return 0;
}
'''.replace('@DEFINITIONS@', '\n'.join(definitions)).replace('@MACROS@', macros).replace(
        '@MAPPER@', mapper).replace('@ENTRY@', entry).replace('@FILLS@', fills).replace(
        '@CHECKS@', '\n'.join(checks)).replace('@TABLES@', tables).replace(
        '@PROFILES@', str(len(fixture['sources'])))
