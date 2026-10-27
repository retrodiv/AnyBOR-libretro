"""Render native model-defense command cases with actual records and parsing.

Expected updates are explicit data, not inferred from a build number or from
the candidate implementation. Model loading, allocation and disposal outside
the retained command branch remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import math
import re

from native_header_fixtures import graphics_refusals, inline_refusals

FIELDS = ('factor', 'pain', 'knockdown', 'blockpower', 'blockthreshold', 'blockratio', 'blocktype')
PARALLEL = ('defense_factors', 'defense_pain', 'defense_knockdown', 'defense_blockpower',
            'defense_blockthreshold', 'defense_blockratio', 'defense_blocktype')


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 3.4e38:
        raise ValueError('Finite native float expectations required')
    text = format(value, '.17g')
    return text + ('' if '.' in text or 'e' in text.lower() else '.0') + 'f'


def render_model_defense(parts, *, revision, representation, attack_types, seed, cases,
                         helpers='', unused_graphics_inlines=False,
                         unused_inline_declarations=None):
    names = {'parse_args', 'is_numeric', 'float_reader', 'argument_macros',
             'defense_case', 'default_defense'}
    if (not isinstance(parts, dict) or set(parts) != names or
            any(not isinstance(value, str) or len(value) > 65536 or
                (name != 'default_defense' and not value.strip())
                for name, value in parts.items())):
        raise ValueError('Bounded native parser, numeric reader, macros and command branch required')
    if not re.search(r'\bcase\s+CMD_MODEL_DEFENSE\s*:', parts['defense_case']):
        raise ValueError('Complete native model-defense case required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit native profile revision required')
    if representation not in ('parallel', 'record'):
        raise ValueError('Explicit native defense representation required')
    if representation == 'record' and not parts['default_defense'].strip():
        raise ValueError('The native record default is required')
    if type(attack_types) is not int or not 0 < attack_types <= 256:
        raise ValueError('Explicit bounded configured attack extent required')
    if not isinstance(seed, list) or len(seed) != 7:
        raise ValueError('Seven independently declared defense seed fields required')
    initial = ','.join(number(value) for value in seed)
    if not isinstance(helpers, str) or len(helpers) > 65536:
        raise ValueError('Bounded exact prepared helper definitions required')
    if not isinstance(cases, list) or not 0 < len(cases) <= 512:
        raise ValueError('A bounded explicit command-case list required')
    updates, entries = [], []
    for case in cases:
        keys = {'line', 'argc', 'reset', 'biker', 'numeric_warnings', 'range_warnings', 'updates'}
        if not isinstance(case, dict) or set(case) != keys:
            raise ValueError('Explicit parser, warning and update expectations required')
        line = case['line']
        if (not isinstance(line, str) or not line.isascii() or '\0' in line or
                not 0 < len(line) < 480 or '\n' in line or '\r' in line or
                not re.match(r'^\s*defense(?:\s|$)', line, re.I)):
            raise ValueError('One bounded ASCII defense command required')
        if (type(case['argc']) is not int or not 1 <= case['argc'] <= 128 or
                any(type(case[key]) is not bool for key in ('reset', 'biker')) or
                any(type(case[key]) is not int or not 0 <= case[key] <= 128
                    for key in ('numeric_warnings', 'range_warnings')) or
                not isinstance(case['updates'], list) or len(case['updates']) > 32):
            raise ValueError('Bounded native command expectations required')
        first = len(updates)
        for update in case['updates']:
            if not isinstance(update, dict) or set(update) != {'indices', 'values'}:
                raise ValueError('Each expected update needs explicit indices and seven values')
            indices, values = update['indices'], update['values']
            if indices == 'all':
                indices = list(range(attack_types))
            if (not isinstance(indices, list) or not indices or
                    any(type(index) is not int or not 0 <= index <= attack_types for index in indices) or
                    indices != sorted(set(indices)) or not isinstance(values, list) or len(values) != 7):
                raise ValueError('Unique allocated native slots and seven field expectations required')
            mask = sum(1 << index for index, value in enumerate(values) if value is not None)
            text = ','.join('0.0f' if value is None else number(value) for value in values)
            for index in indices:
                updates.append('{%d,%du,{%s}}' % (index, mask, text))
        entries.append('{%s,%d,%d,%d,%d,%d,%d,%d}' % (
            json.dumps(line), case['argc'], case['reset'], case['biker'],
            case['numeric_warnings'], case['range_warnings'], first, len(updates) - first))
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#ifndef stricmp
#define stricmp strcasecmp
#endif
#ifndef strnicmp
#define strnicmp strncasecmp
#endif
#undef assert
#undef printf
#undef malloc
#undef calloc
#undef free
#ifdef NDEBUG
#error Native command assertions must remain enabled
#endif
static const char *phase="initial";
#define assert(condition) do {if(!(condition)) { \
 fprintf(stderr,"Native model-defense contract mismatch: %s\n",phase);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@GRAPHICS@
@REFUSALS@
enum {TYPE_COUNT=@ATTACK_TYPES@,MODEL_CAPACITY=TYPE_COUNT+1};
static int fixture_attack_types=TYPE_COUNT;
#undef max_attack_types
#define max_attack_types fixture_attack_types
static s_model model;
static float expected[MODEL_CAPACITY][7];
@STORAGE@
static unsigned numeric_warnings,range_warnings;
static int observed_printf(const char *format,...) {(void)format;++numeric_warnings;return 0;}
static void observed_log(const char *format,...) {(void)format;++range_warnings;}
#define printf observed_printf
#undef writeToLogFile
#define writeToLogFile observed_log
@DEFAULT_DEFENSE@
@ARGUMENT_MACROS@
@IS_NUMERIC@
@FLOAT_READER@
@PARSE_ARGS@
@HELPERS@
static void command_under_test(ArgList arglist) {
 s_model *newchar=&model;
 char *filename="native-model",*command="defense",*value;
 int tempInt=0,i=0;
 @COMMAND_LOCAL@
 switch(CMD_MODEL_DEFENSE) {
 @DEFENSE_CASE@
 }
}
#undef printf
#undef writeToLogFile
struct update {unsigned index,mask;float values[7];};
struct command_case {const char *line;int argc,reset,biker,numeric_warnings,range_warnings;
 unsigned first,count;};
static const struct update updates[]={@UPDATES@};
static const struct command_case commands[]={@CASES@};
static const float initial[7]={@INITIAL@};
static void reset_model(void) {
 memset(&model,0,sizeof(model));
 @POINTERS@
 for(unsigned index=0;index<MODEL_CAPACITY;++index)for(unsigned field=0;field<7;++field) {
  expected[index][field]=initial[field];
  @SEED_FIELDS@
 }
}
static float read_field(unsigned index,unsigned field) {
 switch(field) {@READ_FIELDS@}
 abort();
}
int main(void) {
 unsigned cases=0,checks=0;
 reset_model();
 for(unsigned at=0;at<sizeof(commands)/sizeof(*commands);++at) {
  const struct command_case *test=&commands[at];
  if(test->reset)reset_model();
  model.subtype=test->biker?SUBTYPE_BIKER:0;
  char input[MAX_ARG_LEN],output[MAX_ARG_LEN];ArgList arguments;
  assert(strlen(test->line)<sizeof(input));strcpy(input,test->line);
  memset(output,0,sizeof(output));memset(&arguments,0,sizeof(arguments));
  numeric_warnings=range_warnings=0;phase="parse";
  ParseArgs(&arguments,input,output);assert(arguments.count==(size_t)test->argc);
  phase="command";command_under_test(arguments);
  for(unsigned n=test->first;n<test->first+test->count;++n) {
   assert(updates[n].index<MODEL_CAPACITY);
   for(unsigned field=0;field<7;++field)if(updates[n].mask&(1u<<field))
    expected[updates[n].index][field]=updates[n].values[field];
  }
  phase="values";
  for(unsigned index=0;index<MODEL_CAPACITY;++index)for(unsigned field=0;field<7;++field) {
   assert(read_field(index,field)==expected[index][field]);++checks;
  }
  phase="warnings";assert(numeric_warnings==(unsigned)test->numeric_warnings);
  assert(range_warnings==(unsigned)test->range_warnings);++cases;
 }
 printf("{\"status\":\"PASS\",\"cases\":%u,\"checks\":%u}\n",cases,checks);return 0;
}
'''
    if representation == 'parallel':
        storage = 'static float factors[7][MODEL_CAPACITY];'
        pointers = '\n'.join('model.%s=factors[%d];' % (name, index)
                             for index, name in enumerate(PARALLEL))
        seed_fields = 'factors[field][index]=initial[field];'
        read_fields = '\n'.join('case %d:return model.%s[index];' % (index, name)
                                for index, name in enumerate(PARALLEL))
        local = ''
    else:
        storage = 'static s_defense factors[MODEL_CAPACITY];'
        pointers = 'model.defense=factors;'
        seed_fields = 'switch(field) {' + ''.join(
            'case %d:model.defense[index].%s=initial[field];break;' % (index, name)
            for index, name in enumerate(FIELDS)) + '}'
        read_fields = '\n'.join('case %d:return model.defense[index].%s;' % (index, name)
                                for index, name in enumerate(FIELDS))
        local = 's_defense defense;'
    values = dict(REVISION=str(revision), ATTACK_TYPES=str(attack_types), STORAGE=storage,
        POINTERS=pointers, SEED_FIELDS=seed_fields, READ_FIELDS=read_fields, COMMAND_LOCAL=local,
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=('ParseArgs', 'getValidFloat', 'isNumeric', 'command_under_test')),
        DEFAULT_DEFENSE=parts['default_defense'], HELPERS=helpers,
        ARGUMENT_MACROS=parts['argument_macros'], IS_NUMERIC=parts['is_numeric'],
        FLOAT_READER=parts['float_reader'], PARSE_ARGS=parts['parse_args'],
        DEFENSE_CASE=parts['defense_case'], INITIAL=initial,
        UPDATES=','.join(updates) if updates else '{0,0,{0}}', CASES=',\n'.join(entries))
    for name, value in values.items():
        code = code.replace('@' + name + '@', value)
    return code
