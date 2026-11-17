"""Check native level-property ordinals and speed conversion/representation.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-level-property-contracts.json'


def representation_program(fragments, decimal):
    """Run an own-source speed case, Variant record and type-change operation.

    This narrow original control observes initialized union bytes on the chosen
    host compiler. It does not supply a historical executable/ABI identity.
    """
    if type(decimal) is not bool:
        raise ValueError('Explicit original representation boundary required')
    header = fragments['whole_variant_header']
    records = []
    for kind, name, alias in [('enum', 'VariantType', 'VARTYPE'),
                              ('struct', 'ScriptVariant', 'ScriptVariant')]:
        match = re.search(r'typedef '+kind+' '+name+r'\s*\{[\s\S]*?\}\s*'+alias+r'\s*;', header)
        if match is None:
            raise ValueError('Own native Variant declaration required')
        records.append(match[0])
    if 'switch(varlist[0]->lVal)' not in fragments['openbor_getlevelproperty']:
        raise ValueError('Own speed case must keep its original root selector')
    body, cases = switch_cases(fragments['openbor_getlevelproperty'].replace(
        'switch(varlist[0]->lVal)', 'switch(root)'), 'openbor_getlevelproperty', 'root', outermost=True)
    case = cases['_lp_bgspeed']['body']
    if not re.search(r'\(\*pretvar\)->lVal\s*=\s*\((?:LONG|DOUBLE)\)level->bgspeed\s*;', case):
        raise ValueError('Own speed case must write the declared union member')
    if ('VT_DECIMAL' in case) != bool(decimal):
        raise ValueError('Own speed representation and expected boundary differ')
    dependencies = fragments['whole_depends']
    aliases = []
    for name in ['LONG', 'DOUBLE']:
        matches = re.findall(r'(?m)^typedef [^;\n]+\b'+name+r';', dependencies)
        if len(matches) != 1:
            raise ValueError('Own scalar typedef required')
        aliases.extend(matches)
    if '#pragma pack (4)' not in dependencies:
        raise ValueError('Original packing context needs its own declaration control')
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t s32;
typedef void VOID;
@ALIASES@
#pragma pack(push,4)
@RECORDS@
#pragma pack(pop)
static void StrCache_Collect(int index) {(void)index;abort();}
static int StrCache_Pop(void) {abort();}
@CHANGE@
enum {_lp_bgspeed};
static struct {float bgspeed;} scene,*level=&scene;
static void original_case(ScriptVariant **pretvar)
{switch(_lp_bgspeed){case _lp_bgspeed:@CASE@}}
int main(void)
{
 const float speeds[]={2.75f,-6.5f,0.0f,17.125f};
 const uint64_t seeds[]={0,UINT64_C(0x3ff0000000000000),UINT64_C(0x40080000ffffffff)};
 assert(sizeof(LONG)==4 && sizeof(DOUBLE)==8 && sizeof(ScriptVariant)==12);
 assert(offsetof(ScriptVariant,vt)==8);
 for(unsigned i=0;i<4;++i)for(unsigned j=0;j<3;++j)
 {
  ScriptVariant result;memset(&result,0,sizeof(result));
  result.vt=VT_EMPTY;memcpy(&result.dblVal,&seeds[j],8);level->bgspeed=speeds[i];
  ScriptVariant *out=&result;unsigned char expected[8];memcpy(expected,&result.dblVal,8);
  LONG truncated=(LONG)speeds[i];memcpy(expected,&truncated,sizeof(truncated));
  original_case(&out);assert(out==&result && result.vt==@TYPE@);
  assert(!memcmp(&result.dblVal,expected,8));
  if(@DECIMAL@){DOUBLE observed;memcpy(&observed,expected,8);assert(result.dblVal==observed);}
  else assert(result.lVal==truncated);
 }
 printf("{\"status\":\"PASS\",\"cases\":12,\"union_bytes\":8,\"long_bytes\":4,\"packed_variant_bytes\":12,\"tag\":%d}\n",@TYPE@);
 return 0;
}
'''
    for key, value in dict(ALIASES='\n'.join(aliases), RECORDS='\n'.join(records),
            CHANGE=fragments['ScriptVariant_ChangeType'], CASE=case,
            TYPE='VT_DECIMAL' if decimal else 'VT_INTEGER', DECIMAL=str(int(decimal))).items():
        code = code.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved own representation dependency')
    return code


def program(data, engine):
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    start = source.index('enum levelproperty_enum')
    declarations = source[start:source.index('HRESULT openbor_getlevelproperty(', start)]
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last+1])
    providers = Path(__file__).with_name('classic_terrain_contract.c.in').read_text().split('@VARIANTS@')[0]
    values = dict(PROVIDERS=providers,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue', 'ScriptVariant_ToString')),
        SEARCH=function(utils, 'searchList'), MACROS=macros, DECLARATIONS=declarations,
        METHODS='\n'.join(function(source, name) for name in
            ('openbor_getlevelproperty', 'openbor_changelevelproperty')),
        CONTEXTS=','.join('{%du,%d,{%s},%d}' % (row['revision'], len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties']), row['bgspeed_tag']) for row in data['sources']))
    code = Path(__file__).with_name('forward_level_properties_contract.c.in').read_text()
    for key, value in values.items():
        code = code.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native level property dependency')
    return code


class ForwardLevelPropertyTests(unittest.TestCase):
    def test_original_representation_refuses_incomplete_or_generated_source(self):
        with self.assertRaisesRegex(ValueError, 'Explicit original'):
            representation_program({}, 'decimal')
        with self.assertRaisesRegex(ValueError, 'Own native Variant declaration'):
            representation_program({'whole_variant_header': ''}, False)
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_LEVEL_PROPERTY_ENGINE', ROOT / 'src/engines' / data['engine']))
        fragments = dict(whole_variant_header=(engine / 'source/scriptlib/ScriptVariant.h').read_text(),
            openbor_getlevelproperty=function((engine / 'openborscript.c').read_text(), 'openbor_getlevelproperty'))
        with self.assertRaisesRegex(ValueError, 'Own speed case'):
            representation_program(fragments, True)

    def test_native_ordinals_speed_union_values_and_terrain_refusals(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_LEVEL_PROPERTY_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
