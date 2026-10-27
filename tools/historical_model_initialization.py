"""Render complete native model-constructor contracts with real records.

JSON supplies source-reviewed scalar expectations and allocation extents.
Script allocation and model-name lookup are explicit observations; neither
executes the VM or validates the native disposer.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from historical_model_defense import FIELDS, PARALLEL, number
from native_header_fixtures import graphics_refusals, inline_refusals


def render_model_initialization(parts, *, revision, representation, scripts_pointer,
                                attack_types, animation_count, freespecial_count,
                                special_elements, animation_capacity_field,
                                cases, lookup, helpers='', unused_graphics_inlines=False,
                                unused_inline_declarations=None, lazy_animation_storage=False):
    if (not isinstance(parts, dict) or set(parts) not in (
            {'init_model', 'default_defense'},
            {'init_model', 'default_defense', 'model_animation_reserve'}) or
            any(not isinstance(value, str) or len(value) > 65536 for value in parts.values())
            or not parts['init_model'].strip()):
        raise ValueError('Bounded complete native constructor and record default required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit native revision required')
    if representation not in ('parallel', 'record') or (
            representation == 'record' and not parts['default_defense'].strip()):
        raise ValueError('Explicit native factor representation and its default required')
    if any(type(flag) is not bool for flag in (scripts_pointer, animation_capacity_field,
                                               lazy_animation_storage)):
        raise ValueError('Explicit native script and animation-capacity layouts required')
    if lazy_animation_storage and not animation_capacity_field:
        raise ValueError('Lazy animation storage requires the tracked capacity field')
    if lazy_animation_storage and not parts.get('model_animation_reserve', '').strip():
        raise ValueError('Lazy animation storage requires its complete native reserve helper')
    if any(type(value) is not int or not 1 <= value <= 256 for value in (
            attack_types, animation_count, freespecial_count, special_elements)):
        raise ValueError('Bounded explicit constructor allocation extents required')
    if not isinstance(helpers, str) or len(helpers) > 65536:
        raise ValueError('Bounded exact prepared constructor helpers required')
    if not isinstance(lookup, list) or not 1 <= len(lookup) <= 32:
        raise ValueError('Bounded explicit native lookup sequence required')
    lookups = []
    for row in lookup:
        if (not isinstance(row, dict) or set(row) != {'name', 'result'} or
                not isinstance(row['name'], str) or not row['name'].isascii() or
                not 0 < len(row['name']) <= 128 or '\0' in row['name'] or
                type(row['result']) is not int or not -32768 <= row['result'] <= 32767):
            raise ValueError('Bounded lookup names and native index results required')
        lookups.append('{%s,%d}' % (json.dumps(row['name']), row['result']))
    if not isinstance(cases, list) or not 1 <= len(cases) <= 128:
        raise ValueError('Bounded independent constructor cases required')
    entries, checks = [], []
    for index, case in enumerate(cases):
        keys = {'cacheindex', 'unload', 'magic_type', 'jumpheight', 'jumpspeed',
                'grabdistance', 'noatk_duration', 'fields'}
        if (not isinstance(case, dict) or set(case) != keys or
                type(case['cacheindex']) is not int or case['cacheindex'] not in (0, 1) or
                any(type(case[key]) is not int or not 0 <= case[key] <= 3
                    for key in ('unload', 'magic_type')) or
                not isinstance(case['fields'], list) or not 1 <= len(case['fields']) <= 192):
            raise ValueError('Explicit bounded constructor inputs and field checks required')
        names, field_checks = set(), []
        for field in case['fields']:
            if (not isinstance(field, dict) or set(field) != {'field', 'kind', 'value'} or
                    not isinstance(field['field'], str) or len(field['field']) > 128 or
                    not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[(?:0|[1-9][0-9]{0,2})\])*',
                                     field['field']) or field['field'] in names):
                raise ValueError('Unique bounded native member paths required')
            names.add(field['field'])
            kind, value = field['kind'], field['value']
            if kind == 'float':
                expectation = '(float)model->%s==%s' % (field['field'], number(value))
            elif kind == 'integer' and type(value) is int and abs(value) < 1 << 63:
                expectation = '(long long)model->%s==(%dLL)' % (field['field'], value)
            else:
                raise ValueError('Explicit native integer or finite float field expectation required')
            field_checks.append('phase=%s;assert(%s);++checks;' % (
                json.dumps('field:' + field['field']), expectation))
        checks.append('case %d:{%s}break;' % (index, '\n'.join(field_checks)))
        entries.append('{%d,%d,%d,%s,%s,%s,%s}' % (
            case['cacheindex'], case['unload'], case['magic_type'],
            *(number(case[key]) for key in ('jumpheight', 'jumpspeed', 'grabdistance', 'noatk_duration'))))
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef malloc
#undef calloc
#undef free
#undef realloc
#ifdef NDEBUG
#error Native constructor assertions must remain enabled
#endif
static const char *phase="initial";
#define assert(condition) do {if(!(condition)) { \
 fprintf(stderr,"Native model initialization mismatch: %s\n",phase);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@GRAPHICS@
@REFUSALS@
enum {FACTOR_COUNT=@ATTACK_TYPES@,ANIMATION_COUNT=@ANIMATIONS@,
 FREESPECIAL_COUNT=@FREESPECIALS@,SPECIAL_ELEMENTS=@SPECIAL_ELEMENTS@,
 ANIMATION_STORAGE_COUNT=@ANIMATION_STORAGE@};
_Static_assert(FACTOR_COUNT>=MAX_ATKS,"Original constructor needs its native default attack extent");
static int fixture_attacks=FACTOR_COUNT,fixture_animations=ANIMATION_COUNT;
static int fixture_freespecials=FREESPECIAL_COUNT,fixture_magic;
static float fixture_jumpheight,fixture_jumpspeed,fixture_grabdistance,fixture_noatk_duration;
static s_modelcache cache[2],*fixture_model_cache=cache;
#undef max_attack_types
#define max_attack_types fixture_attacks
#undef max_animations
#define max_animations fixture_animations
#undef max_freespecials
#define max_freespecials fixture_freespecials
#define magic_type fixture_magic
#define default_model_jumpheight fixture_jumpheight
#define default_model_jumpspeed fixture_jumpspeed
#define default_model_grabdistance fixture_grabdistance
#define noatk_duration fixture_noatk_duration
#define model_cache fixture_model_cache
static void *allocations[64];static size_t allocation_sizes[64];
static unsigned allocated,script_calls,lookup_position;
static void *script_argument;
static void *observed_calloc(size_t count,size_t size) {
 assert(allocated<64 && size && count && count<=(1u<<20)/size);
 void *pointer=calloc(count,size);assert(pointer);
 allocations[allocated]=pointer;allocation_sizes[allocated++]=count*size;return pointer;
}
static size_t allocation_size(const void *pointer) {
 assert(pointer);
 for(unsigned index=0;index<allocated;++index)
  if(allocations[index]==pointer)return allocation_sizes[index];
 assert(!"Unowned constructor allocation");return 0;
}
static void *observed_realloc(void *pointer,size_t size) {
 assert(pointer && size && size<=(1u<<20));
 for(unsigned index=0;index<allocated;++index)if(allocations[index]==pointer) {
  void *resized=realloc(pointer,size);assert(resized);
  allocations[index]=resized;allocation_sizes[index]=size;return resized;
 }
 assert(!"Unowned animation allocation");return NULL;
}
static void observed_scripts(@SCRIPT_PARAMETER@) {
 ++script_calls;script_argument=scripts;@SCRIPT_ALLOCATION@
}
static const struct {const char *name;int result;} lookup_sequence[]={@LOOKUPS@};
static int observed_lookup(char *name) {
 assert(lookup_position<sizeof(lookup_sequence)/sizeof(*lookup_sequence));
 assert(!strcmp(name,lookup_sequence[lookup_position].name));
 return lookup_sequence[lookup_position++].result;
}
static void observed_shutdown(int status,const char *format,...) {
 (void)status;(void)format;fputs("Unexpected constructor shutdown\n",stderr);abort();
}
#undef E_OUT_OF_MEMORY
#define E_OUT_OF_MEMORY "native allocation failure"
#undef shutdown
#define shutdown observed_shutdown
#define calloc observed_calloc
#define realloc observed_realloc
#define alloc_all_scripts observed_scripts
#define get_cached_model_index observed_lookup
@DEFAULT@
@HELPERS@
@ANIMATION_RESERVE@
@CONSTRUCTOR@
#undef calloc
#undef realloc
#undef alloc_all_scripts
#undef get_cached_model_index
#undef shutdown
#undef max_attack_types
#undef max_animations
#undef max_freespecials
#undef magic_type
#undef default_model_jumpheight
#undef default_model_jumpspeed
#undef default_model_grabdistance
#undef noatk_duration
#undef model_cache
struct constructor_case {int cacheindex,unload,magic_type;float jumpheight,jumpspeed,grabdistance,duration;};
static const struct constructor_case cases[]={@CASES@};
int main(void) {
 unsigned checks=0;
 cache[0].name="model-a";cache[0].path="data/model-a.txt";
 cache[1].name="model-b";cache[1].path="data/model-b.txt";
 for(unsigned at=0;at<sizeof(cases)/sizeof(*cases);++at) {
  const struct constructor_case *test=&cases[at];
  allocated=script_calls=lookup_position=0;script_argument=NULL;fixture_magic=test->magic_type;
  fixture_jumpheight=test->jumpheight;fixture_jumpspeed=test->jumpspeed;
  fixture_grabdistance=test->grabdistance;fixture_noatk_duration=test->duration;
  phase="constructor";s_model *model=init_model(test->cacheindex,test->unload);
  assert(model && allocation_size(model)==sizeof(*model));
  phase="borrowed cache names";assert(model->name==cache[test->cacheindex].name);
  assert(model->path==cache[test->cacheindex].path && model->index==test->cacheindex);
  assert(model->unload==test->unload && model->freetypes==MF_ALL && !model->isSubclassed);
  phase="script allocation callback";assert(script_calls==1 && script_argument==@SCRIPT_ADDRESS@);
  phase="lookup callbacks";assert(lookup_position==sizeof(lookup_sequence)/sizeof(*lookup_sequence));
  phase="special storage";assert(allocation_size(model->special)==SPECIAL_ELEMENTS*sizeof(s_com));
  for(unsigned index=0;index<SPECIAL_ELEMENTS;++index) {
   const unsigned char *bytes=(const unsigned char *)(model->special+index);
   for(unsigned byte=0;byte<sizeof(s_com);++byte)assert(!bytes[byte]);
  }
  phase="animation storage";assert(allocation_size(model->animation)==ANIMATION_STORAGE_COUNT*sizeof(*model->animation));
  @ANIMATION_CAPACITY@
  for(unsigned index=0;index<ANIMATION_STORAGE_COUNT;++index)assert(!model->animation[index]);
  @ANIMATION_GROWTH@
  phase="factor storage";
  @FACTOR_ALLOCATION_CHECKS@
  for(unsigned index=0;index<=FACTOR_COUNT;++index) {
   assert(model->offense_factors[index]==(index<FACTOR_COUNT?1.0f:0.0f));++checks;
   @DEFENSE_CHECKS@
  }
  switch(at) {@FIELD_CHECKS@ default:abort();}
  for(unsigned index=0;index<allocated;++index)free(allocations[index]);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u,\"checks\":%u}\n",
        (unsigned)(sizeof(cases)/sizeof(*cases)),checks);return 0;
}
'''
    allocation_checks = ['assert(allocation_size(model->offense_factors)==(FACTOR_COUNT+1)*sizeof(float));']
    if representation == 'parallel':
        allocation_checks.extend('assert(allocation_size(model->%s)==(FACTOR_COUNT+1)*sizeof(float));'
                                 % name for name in PARALLEL)
        defense_checks = '\n'.join(
            'assert(model->%s[index]==%s);++checks;' % (
                name, '(index<FACTOR_COUNT?1.0f:0.0f)' if field in ('factor', 'knockdown') else '0.0f')
            for field, name in zip(FIELDS, PARALLEL))
    else:
        allocation_checks.append('assert(allocation_size(model->defense)==(FACTOR_COUNT+1)*sizeof(s_defense));')
        defense_checks = '\n'.join(
            'assert(model->defense[index].%s==%s);++checks;' % (
                field, '(index<FACTOR_COUNT?1.0f:0.0f)' if field in ('factor', 'knockdown') else '0.0f')
            for field in FIELDS)
    values = dict(REVISION=str(revision), ATTACK_TYPES=str(attack_types), ANIMATIONS=str(animation_count),
        FREESPECIALS=str(freespecial_count), SPECIAL_ELEMENTS=str(special_elements),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=('init_model', 'alloc_all_scripts', 'get_cached_model_index')),
        SCRIPT_PARAMETER='s_scripts **scripts' if scripts_pointer else 's_scripts *scripts',
        SCRIPT_ALLOCATION='*scripts=observed_calloc(1,sizeof(**scripts));' if scripts_pointer else '',
        SCRIPT_ADDRESS='&model->scripts', LOOKUPS=','.join(lookups),
        DEFAULT=parts['default_defense'], HELPERS=helpers,
        ANIMATION_RESERVE=parts.get('model_animation_reserve', '') if lazy_animation_storage else '',
        CONSTRUCTOR=parts['init_model'],
        CASES=',\n'.join(entries), FIELD_CHECKS='\n'.join(checks),
        FACTOR_ALLOCATION_CHECKS='\n'.join(allocation_checks), DEFENSE_CHECKS=defense_checks,
        ANIMATION_STORAGE='(ANIMATION_COUNT<MAX_ANIS?ANIMATION_COUNT:MAX_ANIS)' if lazy_animation_storage else 'ANIMATION_COUNT',
        ANIMATION_GROWTH='''phase="animation growth";
  s_anim retained_animation={0};
  model->animation[0]=&retained_animation;
  s_anim **initial_table=model->animation;
  assert(!model_animation_reserve(NULL,0));
  assert(!model_animation_reserve(model,-1));
  assert(!model_animation_reserve(model,ANIMATION_COUNT));
  assert(model->animation==initial_table && model->animation_capacity==ANIMATION_STORAGE_COUNT);
  assert(model_animation_reserve(model,ANIMATION_COUNT-1));
  assert(model->animation_capacity==ANIMATION_COUNT);
  assert(allocation_size(model->animation)==ANIMATION_COUNT*sizeof(*model->animation));
  assert(model->animation[0]==&retained_animation);model->animation[0]=NULL;
  for(unsigned index=0;index<ANIMATION_COUNT;++index)assert(!model->animation[index]);''' if lazy_animation_storage else '',
        ANIMATION_CAPACITY='assert(model->animation_capacity==ANIMATION_STORAGE_COUNT);' if animation_capacity_field else '')
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
