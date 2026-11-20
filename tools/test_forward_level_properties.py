"""Check native level-property ordinals and speed conversion/representation.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-level-property-contracts.json'
RUNTIME_FIXTURE = FIXTURE.with_name('profile-4432-stage-runtime-contracts.json')
SPAWN_FIXTURE = FIXTURE.with_name('profile-4432-stage-spawn-boundaries.json')
SETTER_FIXTURE = FIXTURE.with_name('profile-4432-level-setter-contracts.json')
TERRAIN_QUERY_FIXTURE = FIXTURE.with_name('profile-4432-terrain-script-queries.json')
GAMEOVER_FIXTURE = FIXTURE.with_name('profile-4432-level-gameover.json')
VALUE_QUERY_FIXTURE = FIXTURE.with_name('profile-4432-level-value-queries.json')


def typed_level_setter_program(data, engine=None, gameover=None):
    engine = engine or ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    start = script.index('/* Canonical property order from 4494.')
    end = script.index('static int obor_lookup_level_property(', start)
    definitions = []
    for index, case in enumerate(data['cases']):
        body = []
        for group in ('integers', 'decimals', 'names'):
            for selector, field in case[group]:
                if type(selector) is not int or not re.fullmatch(r'[a-z_]+', field):
                    raise ValueError('Explicit original setter selector and field required')
                body.append('SET_%s(%d, %s);' % (group.upper(), selector, field))
        for control in ('unknown_success', 'wall_collection', 'read_only', 'spawn_noop'):
            if control in case:
                body.append('check_%s(%d);' % (control, case[control]))
        definitions.append('static void check_case_%d(void) {\n    %s\n}' % (index, '\n    '.join(body)))
    views = []
    for index, view in enumerate(data['collection_views']):
        body = []
        if 'early_background' in view:
            body.append('check_early_background(%d, %d);' %
                        (view['early_background'], view['early_getter']))
        for selector, count, field in view.get('arrays', []):
            if not re.fullmatch(r'[a-z_]+', field) or type(selector) is not int or type(count) is not int:
                raise ValueError('Original collection and count fields required')
            body.append('CHECK_ARRAY(%d, %d, %s);' % (selector, count, field))
        if 'background' in view:
            body.append('check_background_handle(%d);' % view['background'])
            body.append('check_wall_count(%d, %d);' % (view['wall_count'], view['wall_collection']))
            body.append('check_collection_growth();')
        if 'player_spawn' in view:
            body.append('check_player_spawn(%d);' % view['player_spawn'])
        for selector, field in view.get('scripts', []):
            if type(selector) is not int or not re.fullmatch(r'[a-z_]+', field):
                raise ValueError('Original script slot selector and member required')
            body.append('check_script_slot(%d, &stage.%s);' % (selector, field))
        if body:
            body.insert(0, 'seed_arrays();')
        views.append('static void check_view_%d(void) {\n    %s\n}' % (index, '\n    '.join(body)))
    runner = []
    for row in data['sources']:
        if row['registered']:
            runner.append('check_level_setter(%du, check_case_%d, check_view_%d);' %
                          (row['revision'], row['case'], row['view']))
    arrays = core.index('/* All pointers and counts stay in their native fields for gameplay. */')
    release = core.index('void free_level(s_level *lv)', arrays)
    execution = script.index('/* A running script can replace the record through which it was entered. */')
    initialization = script.index('static void execute_init_method(', execution)
    parts = dict(SELECTORS=script[start:end], SETTER=function(script, 'openbor_set_level_property'),
                 LIFECYCLE=script[execution:initialization] + '\n'.join(function(script, name) for name in (
                     'execute_init_method', 'Script_Clear', 'Script_Execute')),
                 SCRIPT_SLOTS='\n'.join(function(script, name) for name in (
                     'obor_level_script_source', 'obor_assign_level_script')),
                 GETTER=function(script, 'obor_level_property_has_early_getter') +
                    function(script, 'openbor_get_level_property'),
                 SET_PROPERTY_NATIVE=function(script, 'obor_set_property_native'),
                 ARRAYS=core[arrays:release] + function(core, 'free_level'),
                 VARIANTS='\n'.join(function(variant, name) for name in
                                    ('ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue',
                                     'ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_Init')),
                 CASES='\n'.join(definitions), VIEWS='\n'.join(views), EXTRA='',
                 RUNNER='\n    '.join(runner))
    if gameover is not None:
        registry = function(script, 'Script_LoadSystemFunctions')
        reverse = function(script, 'Script_GetFunctionName')
        query = function(script, 'obor_lookup_level_property')
        rows = ',\n'.join('{%d,%d,%d,%d,%d}' % (row['revision'], row['gameover'],
            row['damage_enemy'], row['weapon'], row['all_players']) for row in gameover['sources'])
        values = dict(
            GAMEOVER=function(script, 'openbor_gameover'),
            LOOKUP=query,
            APPLY=function(core, 'obor_apply_level_gameover'),
            LOOP=braced_statement(function(core, 'playlevel'), 'while(!endgame)'),
            REGISTER=braced_statement(registry, f'if(obor_profile_build >= 4642 && obor_profile_build <= {gameover["range"][1]})'),
            REVERSE=braced_statement(reverse, f'if (obor_profile_build >= 4642 && obor_profile_build <= {gameover["range"][1]} &&'),
            ROWS=rows,
        )
        extra = Path(__file__).with_name('level_gameover_contract.c.in').read_text()
        parts['EXTRA'] = re.sub(r'@([A-Z_]+)@', lambda item: values[item[1]], extra)
        parts['RUNNER'] += '\n    check_gameover_profiles();'
    template = Path(__file__).with_name('level_property_setter_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)


def stage_runtime_program(data, engine=None):
    engine = engine or ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    loader, cases = switch_cases(source, 'load_level', 'cmd', outermost=True)
    defaults = loader[loader.index('    level->nohurt ='):loader.index('    level->setweap = 0;')]

    def guard(method, anchor):
        body = function(source, method)
        start = body.index(anchor)
        return body[start:body.index('{', start)].strip()

    commands = ('NOSLOW', 'TYPE', 'NOHIT', 'SPAWN1', 'SPAWN2', 'SPAWN3', 'SPAWN4')
    parts = dict(
        SPAWN_COUNT=function(source, 'obor_level_spawn_count'),
        ENTRY=braced_statement(function(source, 'ent_default_init'),
                               'else if(!e->animation)').removeprefix('else '),
        SCORE=function(source, 'addscore'),
        DEFAULTS=defaults,
        CASES='\n'.join('case CMD_LEVEL_' + name + ':' + cases['CMD_LEVEL_' + name]['body'] for name in commands),
        EXCLUDES=function(source, 'obor_spawn_excludes_player_targets'),
        SPAWN=guard('spawn', 'if((e->modeldata.type & TYPE_PLAYER) && (obor_spawn_excludes_player_targets'),
        KNIFE=guard('knife_spawn', 'if((self->modeldata.type & TYPE_PLAYER) && (obor_spawn_excludes_player_targets'),
        BLOCK=guard('do_attack', 'if(didblock && (obor_profile_build'),
        DAMAGE=guard('player_takedamage', 'if(healthcheat || ((obor_profile_build'),
        SLOW=guard('update', 'if((level_completed && !tospeedup &&'),
        CONTEXTS=',\n'.join('{%d,%d,%d,%d,%d}' % (
            row['revision'], row['spawn_extent'], row.get('flag_modes', -1),
            row.get('spawn_y_policy', row['spawn_extent']), row.get('configured_entry', 0))
                            for row in data['sources']))
    template = Path(__file__).with_name('stage_runtime_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)


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


def legacy_level_property_parts(engine):
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last+1])
    providers = Path(__file__).with_name('classic_terrain_contract.c.in').read_text().split('@VARIANTS@')[0]
    return source, dict(PROVIDERS=providers,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue', 'ScriptVariant_ToString')),
        SEARCH=function(utils, 'searchList'), MACROS=macros)


def program(data, engine):
    source, values = legacy_level_property_parts(engine)
    start = source.index('enum levelproperty_enum')
    declarations = source[start:source.index('HRESULT openbor_getlevelproperty(', start)]
    values.update(DECLARATIONS=declarations,
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
    def test_4432_typed_level_and_set_value_queries(self):
        data = load_contract_fixture(VALUE_QUERY_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        start = script.index('/* Canonical property order from 4494.')
        end = script.index('static int obor_lookup_level_property(', start)
        cache = variant[variant.index('typedef struct'):variant.index('// find an existing constant')]
        rows = ',\n'.join('{%du,%d,%d,%d,{%s},%d}' % (
            row['revision'], row['set_name'], row['level_name'], row['boss_music'],
            ','.join(map(str, row['scripts'])), row['spawn_players']) for row in data['sources'])
        parts = dict(CACHE=cache + '\n' + function(variant, 'ScriptVariant_Copy'),
                     SELECTORS=script[start:end] + function(script, 'obor_set_property_native'),
                     GETTERS='\n'.join(function(script, n) for n in (
                         'obor_script_set_handle', 'obor_level_property_has_early_getter',
                         'openbor_get_set_property', 'openbor_get_level_property')),
                     CONTEXTS=rows)
        template = Path(__file__).with_name('level_value_queries_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_level_gameover_request_and_ordinals(self):
        data = load_contract_fixture(GAMEOVER_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 4510 <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        existing = load_contract_fixture(SETTER_FIXTURE)
        code = typed_level_setter_program(existing, engine, gameover=data)
        results = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [dict(revision=row['revision'], status='PASS') for row in existing['sources']
                    if row['registered']]
        expected.extend(dict(revision=revision, gameover='PASS') for revision in revisions)
        self.assertEqual(results, expected)

    def test_4432_legacy_terrain_property_results(self):
        data = load_contract_fixture(TERRAIN_QUERY_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 4510 <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source, parts = legacy_level_property_parts(engine)
        start = source.index('enum levelproperty_enum')
        end = source.index('int mapstrings_levelproperty(', start)
        parts.update(
            SELECTORS=source[start:end],
            METHODS='\n'.join(function(source, name) for name in (
                'mapstrings_levelproperty', 'obor_terrain_query_selector',
                'openbor_getlevelproperty', 'obor_basemap_set_cell', 'openbor_changelevelproperty')),
            ROWS=',\n'.join('{%d,%d}' % (row['revision'], row['mapped_selectors']) for row in data['sources']),
        )
        code = Path(__file__).with_name('legacy_terrain_script_queries_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], code)
        results = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in results.splitlines()], revisions)

    def test_4432_typed_level_setter_scalars_and_results(self):
        data = load_contract_fixture(SETTER_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        results = [json.loads(line) for line in native_output(typed_level_setter_program(data), data).splitlines()]
        self.assertEqual(results, [dict(revision=row['revision'], status='PASS') for row in data['sources']
                                   if row['registered']])

    def test_4432_stage_spawn_and_flag_modes(self):
        data = load_contract_fixture(RUNTIME_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        results = [json.loads(line) for line in native_output(
            stage_runtime_program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(results, [dict(revision=revision, status='PASS') for revision in revisions])

    def test_4432_stage_spawn_boundaries_and_score_rewards(self):
        data = load_contract_fixture(SPAWN_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        results = [json.loads(line) for line in native_output(
            stage_runtime_program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(results, [dict(revision=revision, status='PASS') for revision in revisions])

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
