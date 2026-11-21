"""Execute native historical system-variable routing and changed field views.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-system-variables-contracts.json'
TEXT_FIXTURE = FIXTURE.with_name('profile-4432-system-text-queries.json')


def source_engine(data):
    return Path(os.environ.get('OBOR_SYSTEM_ENGINE', ROOT / 'src/engines' / data['engine']))


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(set(revisions)) != len(revisions) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own system sources and change-boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', value) for value in row['source_sha256'].values()) or
                len(row['properties']) != len(row['symbols']) or
                any(not re.fullmatch('_sv_[a-z0-9_]+', s) for s in row['symbols']) or
                any('_sv_' + name != symbol for name, symbol in zip(row['properties'], row['symbols'])) or
                row['properties'] != sorted(row['properties']) or
                set(row['features']) != set(data['feature_names'])):
            raise ValueError('Complete own namespace, field policy and source identity required')
    return data


def selected_fields(core, name, selected):
    body, cases = switch_cases(core, name, 'index', outermost=True)
    if not set(selected) <= set(cases):
        raise ValueError('All declared native field cases required')
    # Keep source order, including adjacent labels which share one body.
    arms = ''.join('case ' + key + ':' + value['body']
                   for key, value in cases.items() if key in selected)
    return (body[:body.index('switch(index)')] + 'switch(index){' + arms +
            'default:' + cases['default']['body'] + '}\nreturn 1;\n}\n')


def program(data):
    engine = source_engine(data)
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    at = script.index('static const char *svlist[]')
    declaration = script[at:script.index('// ===== openborvariant', at)]
    methods = '\n'.join(function(script, name) for name in
        ('obor_systemvariant_available', 'obor_systemvariant_native',
         'obor_systemvariant_logical', 'mapstrings_systemvariant',
         'openbor_systemvariant', 'openbor_changesystemvariant'))
    selected = data['selected_fields']
    # Read-only fields do not have a setter arm; render only actual setter cases.
    _, setter_cases = switch_cases(core, 'changesyspropertybyindex', 'index', outermost=True)
    callbacks = rename_identifiers(selected_fields(core, 'getsyspropertybyindex', selected),
                                  {'getsyspropertybyindex': 'probe_getsyspropertybyindex'}) + '\n'
    callbacks += rename_identifiers(selected_fields(core, 'changesyspropertybyindex',
        [key for key in selected if key in setter_cases]),
        {'changesyspropertybyindex': 'probe_changesyspropertybyindex'})
    dispatcher = function(script, 'Script_GetStringMapFunction')
    owned = {'openbor_systemvariant', 'openbor_changesystemvariant', 'mapstrings_systemvariant'}
    symbols = set(re.findall(r'\(void\s*\*\)\s*(\w+)', dispatcher))
    if not owned <= symbols:
        raise ValueError('Both actual system-variable mapper routes required')
    stubs = sorted(symbols - owned)
    dispatcher = rename_identifiers(dispatcher, {name: 'probe_symbol_' + name for name in stubs})
    fields = data['feature_names']
    if any(not re.fullmatch('[a-z_]+', key) for key in fields):
        raise ValueError('Explicit native field policies required')
    rows = ['{%du,%d,{%s},{%s},{%s}}' % (row['revision'], len(row['properties']),
            ','.join(row['symbols']), ','.join(json.dumps(s) for s in row['properties']),
            ','.join(str(row['features'][key]) for key in fields)) for row in data['sources']]
    _, getter_cases = switch_cases(core, 'getsyspropertybyindex', 'index', outermost=True)
    clones = []
    for index, config in enumerate(data['compiler_conditions']):
        if set(config['defined']) - set(data['platform_macros']):
            raise ValueError('Declared original preprocessor symbols required')
        prefix = '\n'.join('#undef %s\n#define %s %d' % (key, key, int(key in config['defined']))
                           for key in data['platform_macros'])
        clones.append(prefix + '\nstatic int probe_porting_%d(ScriptVariant *var){switch(_sv_porting){'
                      'case _sv_porting:%s default:return 0;}return 1;}\n' %
                      (index, getter_cases['_sv_porting']['body']))
    clones.append('\n'.join('#undef %s\n#define %s 0' % (key, key) for key in data['platform_macros']))
    hit = function(core, 'checkhit')
    at = hit.index('    lasthit.attack      = attack;')
    end = hit.index('    return 1;', at) + len('    return 1;')
    publication = ('static int probe_publish(entity *attacker,s_collision_attack *attack,'
                   's_collision_body *detect,float medy){\n' + hit[at:end] + '\n}\n')
    values = dict(
        DECLARATION=declaration, METHODS=methods, FIELDS=callbacks,
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        CHEATS=function(core, 'is_cheat_actived'), PUBLICATION=publication,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_ChangeType', 'ScriptVariant_Clear',
             'ScriptVariant_Copy', 'ScriptVariant_IntegerValue')),
        DISPATCH=dispatcher,
        STUBS='\n'.join('static void probe_symbol_%s(void){++unused_calls;}' % name for name in stubs),
        FEATURE_ENUM=','.join('FEATURE_' + name for name in fields),
        FEATURE_COUNT=str(len(fields)), CONTEXTS=','.join(rows), PORTING='\n'.join(clones),
        PORTING_FUNCTIONS=','.join('probe_porting_%d' % n for n in range(len(data['compiler_conditions']))),
        PORTING_EXPECTED=','.join('{%s,%d}' %
            ('NULL' if c['string'] is None else json.dumps(c['string']), c['integer'])
            for c in data['compiler_conditions']),
        ENUM_CHECKS='\n'.join('assert(%s==%d);' % (symbol, n)
                              for n, symbol in enumerate(data['platform_symbols'])),
        NUMBERS=','.join('{%d,%.17g,%d,%d}' %
            (v['tag'], v['value'], v['converted'], v['accepted']) for v in data['numeric_values']),
        PAUSE_VALUES=','.join(map(str, data['pause_values'])),
        MENU_FLAGS=','.join(map(str, data['menu_flags'])))
    values['GETTER_UNKNOWN'] = json.dumps(data['getter_unknown'])
    text = Path(__file__).with_name('system_variables_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native system-variable dependency')
    return text


class SystemVariableContracts(unittest.TestCase):
    def test_native_names_values_mutations_and_target_conditions(self):
        data = fixture_data()
        output = native_output(program(data), data, engine_source=source_engine(data))
        actual = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])

    def test_native_scene_branch_and_pak_text(self):
        data = load_contract_fixture(TEXT_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = source_engine(data)
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        cache = variant[variant.index('typedef struct'):variant.index('// find an existing constant')]
        symbols = ('_sv_current_scene', '_sv_branchname', '_sv_current_branch', '_sv_pakname')
        parts = dict(CACHE=cache + '\n' + function(variant, 'ScriptVariant_Copy'),
                     QUERIES=selected_fields(core, 'getsyspropertybyindex', symbols),
                     PROFILES=',\n'.join('{%du,%d}' % (row['revision'], row['pak_label_capacity'])
                                         for row in data['sources']))
        template = Path(__file__).with_name('system_text_queries_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)
        output = native_output(probe, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_6391_native_boss_music_and_pak_text(self):
        from test_early_jump_walkoff import braced_statement

        data = load_contract_fixture(FIXTURE.with_name('profile-6391-boss-music-and-pak-label.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = source_engine(data)
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        scripts = (engine / 'openborscript.c').read_text(encoding='latin-1')
        level = (engine / 'source/openborscript/level.c').read_text(encoding='latin-1')

        def arm(source, method, symbol):
            text = function(source, method)
            return re.search(r'(?ms)^\s*(case ' + symbol + r':.*?)(?=^\s*case )', text)[1]

        values = {
            'PARSE_MUSIC': arm(core, 'load_level', 'CMD_LEVEL_BOSSMUSIC'),
            'SET_MUSIC': arm(level, 'openbor_set_level_property', 'LEVEL_PROP_BOSS_MUSIC_NAME'),
            'GET_MUSIC': arm(level, 'openbor_get_level_property', 'LEVEL_PROP_BOSS_MUSIC_NAME'),
            'SET_COUNT': arm(level, 'openbor_set_level_property', 'LEVEL_PROP_BOSS_COUNT'),
            'GET_COUNT': arm(level, 'openbor_get_level_property', 'LEVEL_PROP_BOSS_COUNT'),
            'PLAY_MUSIC': braced_statement(function(core, 'smartspawn'),
                                            'if(props->boss && level != NULL && level->bossmusic[0])'),
            'GET_PAK_LABEL': arm(scripts, 'getsyspropertybyindex', '_sv_pakname'),
            'LABELS': ',\n'.join('{' + json.dumps(path) + ',' + json.dumps(label) + '}'
                                 for path, label in data['labels']),
            'PROFILES': ',\n'.join('{%du,%du,%du}' % (row['revision'], row['boss_music_capacity'],
                                                       row['pak_label_capacity']) for row in rows),
        }
        template = Path(__file__).with_name('boss_music_and_pak_label_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda item: values[item[1]], template)
        output = native_output(probe, data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)


if __name__ == '__main__':
    unittest.main()
