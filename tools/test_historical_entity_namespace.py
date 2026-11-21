"""Check historical entity property selectors through native dispatch.

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
from test_historical_model_defaults import model_command_functions
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-namespace-contracts.json'
BOOLEAN_BINDING = FIXTURE.with_name('profile-6391-boolean-binding.json')
TYPED_ENTITY = FIXTURE.with_name('profile-6391-typed-entity.json')
TYPED_SCRIPT_IDS = FIXTURE.with_name('profile-6391-typed-script-ids.json')
LEGACY_ENTITY = FIXTURE.with_name('profile-legacy-entity-stats.json')
LEGACY_ENTITY_SELECTORS = ('obor_entityproperty_legacy_count', 'obor_entityproperty_legacy_index',
                           'obor_entityproperty')
ENTITY_COLLISION = FIXTURE.with_name('profile-6391-entity-collision.json')
AXIS_PROPERTIES = FIXTURE.with_name('profile-6391-axis-properties.json')
ENTITY_LINKS_AND_MODEL_UNLOAD = FIXTURE.with_name('profile-6391-entity-links-and-model-unload.json')
INTERMEDIATE_BINDING = FIXTURE.with_name('profile-6391-intermediate-binding.json')
ANIMATION_AND_MATCHING_IDS = FIXTURE.with_name('profile-6391-animation-and-matching-ids.json')
BINDING_ADJUSTMENT = FIXTURE.with_name('profile-6391-binding-adjustment.json')
LITERAL_CONSTANTS = FIXTURE.with_name('profile-6391-literal-constants.json')
ANIMATION_CONSTANTS = FIXTURE.with_name('profile-6391-animation-constants.json')
BACKGROUND_SPEEDS = FIXTURE.with_name('profile-6391-background-speeds.json')
SCRIPT_ACTIONS = FIXTURE.with_name('profile-script-entity-actions.json')
SCRIPT_STATUS = FIXTURE.with_name('profile-script-entity-status.json')


def declaration(source, pattern):
    match = re.search(pattern, source, re.M)
    if not match:
        raise ValueError('Missing native entity namespace declaration: ' + pattern)
    return match[0]


def entity_namespace(script):
    declarations = (
        r'^enum entityproperty_enum[^;]*;',
        r'^static const char \*eplist\[\][^;]*;',
        r'^static const struct \{[^\n]+\} obor_entity_property_additions\[\][\s\S]*?^};',
    )
    helpers = ('obor_entity_property_uses_history', 'obor_resolve_entity_property',
               'obor_entity_property_name', 'obor_map_entity_property_name')
    return '\n'.join([declaration(script, pattern) for pattern in declarations] +
                     [function(script, name) for name in helpers])


def program(data, engine):
    script = (engine / 'openborscript.c').read_text()
    mapper = function(script, 'mapstrings_entityproperty')
    getter = function(script, 'openbor_getentityproperty')
    setter = function(script, 'openbor_changeentityproperty')
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')
    branches = '\n'.join(f'    case {item}: observed = {item}; break;'
                         for item in data['physical_selectors'])
    getter_failure = 'default: *pretvar = NULL; return E_FAIL;'
    setter_failure = 'default: goto changeentityproperty_error;'
    values = {
        'NAMESPACE': entity_namespace(script),
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'VARIANTS': '\n'.join(function(variants, name) for name in methods),
        'MAPPER': mapper[:mapper.index('    static const')] +
                  mapper[mapper.index('    if(paramCount < 2)'):mapper.index('    switch (ep)')] +
                  '    (void)eps;\n    observed = ep;\n    return 1;\n}',
        'GETTER': getter[:getter.index('    switch(propind)')] +
                  f'    switch(propind) {{\n{branches}\n{getter_failure}\n    }}\n    return S_OK;\n}}',
        'SETTER': setter[:setter.index('    static const')] +
                  setter[setter.index('    *pretvar = NULL;\n\n'):setter.index('    switch(propind)')] +
                  f'    switch(propind) {{\n{branches}\n{setter_failure}\n    }}\n' +
                  setter[setter.rindex('    return S_OK;'):],
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'QUERIES': ',\n'.join('{%d,%d,%s}' % (query['missing'], query['ordinal'],
                                               json.dumps(query['name']) if query['name'] is not None else 'NULL')
                              for query in data['queries']),
    }
    template = Path(__file__).with_name('entity_namespace_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def expected(table, query, slots):
    """Use the original source table's admitted names and numeric selectors."""
    name = query['name']
    named = name is not None
    ordinal = table['lookup'].get(name.lower(), -1) if named else query['ordinal']
    converted = int(named and ordinal >= 0)
    missing_name = int(named and not converted)
    raw = 0 if missing_name else ordinal
    selector = table['physical'][raw] if 0 <= raw < len(table['physical']) else None
    route = slots.get(selector, -1)
    if query['missing']:
        # Observe the existing defense exception before executing property bodies.
        permitted = selector == '_ep_defense' and not missing_name
        if permitted:
            return [[0, 1, raw, route, 0, converted | 2, 0]]
        return [[-1, int(not named), 0 if named else query['ordinal'], -1, 0, 0, 1]]
    mapper = [1 - missing_name, int(not missing_name), raw, route if not missing_name else -1,
              missing_name, converted, 0]
    getter = [0 if route >= 0 else -1, int(not missing_name), raw, route,
              2 * missing_name, converted | 2, int(route < 0)]
    setter = [0 if route >= 0 and not missing_name else -1, int(not missing_name), raw,
              route if not missing_name else -1, missing_name, converted, 1]
    return [mapper, getter, setter]


def animation_property_program(engine, profiles, *, legacy_source):
    if legacy_source:
        source = (engine / 'openborscript.c').read_text()
        helpers = ('obor_uses_early_animation_properties', 'obor_native_animation_property')
        prelude = '#include "openbor.h"\n' + '\n'.join(function(source, name) for name in helpers)
        cache_start = 'typedef struct'
    else:
        source = (engine / 'source/openborscript/animation.c').read_text()
        prelude = '#include "scriptcommon.h"\n#include "profile_ids.h"'
        cache_start = '#define STRCACHE_INC'
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    core = (engine / 'openbor.c').read_text(encoding='utf-8', errors='surrogateescape')
    methods = ('openbor_get_animation_property', 'openbor_set_animation_property')
    values = {
        'HEADERS': prelude,
        'CACHE': variants[variants.index(cache_start):variants.index('BOOL ScriptVariant_IsTrue(')],
        'METHODS': '\n'.join(function(source, name) for name in methods),
        'PARSERS': '\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat')),
        'CHARGE_COMMAND': declaration(core, r'^[ \t]*case CMD_MODEL_CHARGETIME:[\s\S]*?^[ \t]*break;'),
        'PROFILES': ',\n'.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['bounce'], row['charge'],
                              row['frames'], row['entity_collision']) for row in profiles),
    }
    template = Path(__file__).with_name('animation_property_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def original_entity_name_lookup(table, name):
    """The original searchList uses a case-insensitive binary search."""
    low, high = 0, len(table) - 1
    folded = name.lower()
    while low <= high:
        middle = (low + high) // 2
        candidate = table[middle][0].lower()
        if candidate == folded:
            return middle
        if candidate < folded:
            low = middle + 1
        else:
            high = middle - 1
    return -1


def legacy_boomerang_program(engine, rows, tables, controls):
    script = (engine / 'openborscript.c').read_text()
    game = (engine / 'openbor.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    arrays = ('obor_entityproperty6330', 'obor_entityproperty6330lns', 'eplist',
              'obor_eplist6330', 'obor_eplist6330lns', 'eplist_boomerang')
    declarations = [declaration(script, rf'^enum {name}[^;]+;')
                    for name in ('entityproperty_enum', 'boomerang_enum')]
    declarations.extend(declaration(script, rf'^static const (?:int|char \*)\s*{name}\[\][^;]+;')
                        for name in arrays)
    declarations.append(declaration(script, r'^enum\s*\{\s*OBOR_6330_ENTITY_EDGE_ORDINAL[^;]+;'))
    mapper, cases = switch_cases(script, 'mapstrings_entityproperty', 'ep')
    mapping = (mapper[:mapper.index('    static const')] +
               mapper[mapper.index('    if(paramCount < 2)'):cases['_ep_a']['label_start']] +
               'case _ep_boomerang:' + cases['_ep_boomerang']['body'] + '\n    default: break;\n    }\n    return 1;\n}')
    method_parts = []
    for name in ('openbor_getentityproperty', 'openbor_changeentityproperty'):
        method, cases = switch_cases(script, name, 'propind')
        properties = ('_ep_boomerang', '_ep_damage_on_landing', '_ep_prevanimationid',
                      '_ep_collidedentity', '_ep_movex', '_ep_movez', '_ep_entitypushing',
                      '_ep_pushingfactor', '_ep_direction', 'default')
        if name == 'openbor_changeentityproperty':
            properties += ('_ep_defense', '_ep_offense')
        for label, case in reversed(tuple(cases.items())):
            if label not in properties:
                method = method[:case['label_start']] + method[case['end']:]
        if name == 'openbor_changeentityproperty':
            method = method[:method.index('    static const')] + method[method.index('    *pretvar = NULL;\n\n'):]
        method_parts.append(method)
    values = {
        'DECLARATIONS': '\n'.join(declarations),
        'CACHE': variants[variants.index('#define STRCACHE_INC'):variants.index('BOOL ScriptVariant_IsTrue(')],
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'METHODS': '\n'.join([*(function(script, name) for name in LEGACY_ENTITY_SELECTORS), mapping, *method_parts]),
        'SELECTOR': function(game, 'ent_set_anim'),
        'TABLES': '\n'.join(f'static const property_entry table_{key}[] = {{' +
                           ',\n'.join('{%s,%s,%d}' % (json.dumps(name), selector, original_entity_name_lookup(items, name))
                                      for name, selector in items) + '};'
                           for key, items in tables.items() if key in {row['table'] for row in rows}),
        'PROFILES': ',\n'.join('{%du, table_%s, sizeof(table_%s) / sizeof(*table_%s), %d}' %
                              (row['revision'], row['table'], row['table'], row['table'], row['boomerang'])
                              for row in rows),
        'CONTROLS': ','.join(json.dumps(name) for name in controls),
    }
    template = Path(__file__).with_name('legacy_boomerang_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def binding_property_methods(engine):
    source = (engine / 'source/openborscript/binding.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = ('mapstrings_binding', 'obor_profile_boolean_binding_axes', 'profile_binding_property',
               'openbor_get_binding_property', 'openbor_set_binding_property')
    return {
        'CACHE': variants[variants.index('#define STRCACHE_INC'):
                          variants.index('HRESULT ScriptVariant_DecimalValue(')],
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'METHODS': '\n'.join(function(source, name) for name in methods),
    }


def axis_property_program(data, rows, engine):
    modules = engine / 'source/openborscript'
    index = (modules / 'index.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    utility = (engine / 'source/utils.c').read_text(encoding='latin-1')
    loader = function(index, 'Script_LoadSystemFunctions')
    first = loader.index('    // Axis\n')
    names = data['registry_names']
    symbols = '|'.join(re.escape('openbor_' + name) for name in names)
    branches = re.compile(r'else if\s*\([^\n]*(?:' + symbols + r')\)\)\s*\{[^{}]*\}')
    values = {
        'FORWARD': loader[first:loader.index('    // Binding\n', first)],
        'NAMES': ','.join(json.dumps(name) for name in names),
        'FUNCTIONS': ','.join('openbor_' + name for name in names),
        'SEARCH': function(utility, 'searchList'),
        'VARIANTS': '\n'.join(function(variant, name) for name in ('ScriptVariant_Init', 'ScriptVariant_Clear',
                                  'ScriptVariant_ChangeType', 'ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue')),
        'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['axis_properties'],
                                         row.get('principal_int_y', 0)) for row in rows),
    }
    for key, method in (('REVERSE', 'Script_GetFunctionName'), ('MAPPER', 'Script_GetStringMapFunction')):
        body = function(index, method)
        cases = branches.findall(body)
        if len(cases) != len(names):
            raise ValueError('Complete axis property dispatcher required for ' + method)
        begin = body.index('{') + 1
        first_branch = re.search(r'(?m)^    if\s*\(', body).start()
        fallback = re.search(r'(return [^;]+;)\s*}\s*}\s*$', body)[1]
        values[key] = body[begin:first_branch] + cases[0].removeprefix('else ') + '\n'
        values[key] += '\n'.join(cases[1:]) + '\n' + fallback
    template = Path(__file__).with_name('axis_property_registry_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def constant_mapper_parts(engine):
    constants = (engine / 'source/openborscript/constants.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    mapper = function(constants, 'mapstrings_transconst')
    macros = constants[constants.index('#define IICMPCONST('):constants.index('int mapstrings_transconst(')]
    arrays = set(re.findall(r'(?m)^\s*ICMPSCONST(?:A(?:_IF)?|B)\(\w+,\s*(\w+)', mapper))
    reaction_arrays = set(re.findall(r'(?m)^\s*ICMPREACTION_SERIES\(\w+,\s*(\w+)', mapper))
    table_declarations = ['int max_attack_types = sizeof(dynamic_animations) / sizeof(*dynamic_animations);']
    table_declarations += [f'int *{name} = dynamic_animations;' for name in sorted(arrays)]
    table_declarations += [f'int *{name} = reaction_animations;' for name in sorted(reaction_arrays)]
    return {
        'ANIMATION_TABLES': '\n'.join(table_declarations),
        'VARIANTS': variants[variants.index('#define STRCACHE_INC'):variants.index('BOOL ScriptVariant_IsTrue(')] +
                    '\n' + function(variants, 'ScriptVariant_Copy'),
        'MAPPER': macros + '\n' + mapper,
    }


def typed_script_ids_program(data, engine):
    parts = constant_mapper_parts(engine) | {
        'PROFILES': ','.join('{%du,%d}' % (row['revision'], row['early_ids']) for row in data['sources']),
    }
    for key in ('early', 'base'):
        parts[key.upper()] = ',\n'.join(
            '{%s,%s}' % (json.dumps(name), 'INT_MIN' if value is None else int(value))
            for name, value in data['cases'][key].items())
    for domain, prefix, limit in (('animation', 'ANI_', 'MAX_ANIS'), ('attack', 'ATK_', 'MAX_ATKS')):
        layouts = []
        for key in ('base', 'early'):
            layout = data.get(domain + '_layouts', {}).get(key, [])
            if any(not re.fullmatch(prefix + r'[A-Z0-9_]+', name) for name in layout):
                raise ValueError('Expected native enum entries for ' + domain)
            layouts.append('{(const int[]){%s}, %d}' % (','.join([*layout, limit]), len(layout)))
        parts[domain.upper() + '_ENUM_LAYOUTS'] = ',\n'.join(layouts)
    template = Path(__file__).with_name('typed_script_ids_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)


def constant_level_methods(engine):
    source = (engine / 'source/openborscript/level.c').read_text()
    selected = {'LEVEL_PROP_BOSS_COUNT', 'LEVEL_PROP_MIRROR', 'LEVEL_PROP_NUM_BOSSES',
                'LEVEL_PROP_POSITION_X', 'LEVEL_PROP_WEAPON'}
    result = []
    for name in ('openbor_get_level_property', 'openbor_set_level_property'):
        body = function(source, name)
        labels = list(re.finditer(r'(?m)^        case (LEVEL_PROP_\w+):', body))
        first = labels[0].start()
        end = re.search(r'(?m)^        default:|^    }$', body[first:]).start() + first
        offsets = [label.start() for label in labels] + [end]
        slices = [body[label.start():stop] for label, stop in zip(labels, offsets[1:], strict=True)
                  if label[1] in selected]
        if len(slices) != len(selected):
            raise ValueError('Complete level selector boundary cases required')
        result.append(body[:first] + ''.join(slices) + body[end:])
    return '\n'.join(result)


def background_speed_level_methods(engine):
    source = (engine / 'source/openborscript/level.c').read_text()
    start = source.index('enum levelproperty_enum')
    end = source.index('HRESULT openbor_getlevelproperty(', start)
    getter = function(source, 'openbor_getlevelproperty')
    other_properties = getter.index('    case _lp_cameraxoffset:')
    fallback = re.search(r'^    default:', getter, re.M).start()
    search = function((engine / 'source/utils.c').read_text(), 'searchList')
    return '\n'.join((search, source[start:end], getter[:other_properties] + getter[fallback:]))


class EntityNamespaceContracts(unittest.TestCase):
    def test_6391_original_player_defaults_and_script_queries(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-script-query-defaults.json'))
        rows = data['sources']
        revisions = [r['revision'] for r in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        ids = (engine / 'source/openborscript/profile_ids.h').read_text()
        native_switch = 'switch(obor_player_property_native(prop))'
        plain_switch = 'switch(prop)'
        getter = function(script, 'openbor_getplayerproperty')
        self.assertEqual(getter.count(native_switch), 1)
        player, cases = switch_cases(getter.replace(native_switch, plain_switch), 'openbor_getplayerproperty', 'prop')
        for label, case in reversed(tuple(cases.items())):
            if label not in ('_pp_ent', '_pp_entity', '_pp_lives', 'default'):
                player = player[:case['label_start']] + player[case['end']:]
        _, direction = switch_cases(script, 'openbor_changeentityproperty', 'propind')
        values = {
            'PLAYER_ENUM': declaration(script, r'^enum playerproperty_enum\s*\{[^}]+\};'),
            'PROFILE': '\n'.join(function(ids, name) for name in ('obor_profile_uses_5134_script_ids',
                                 'obor_profile_has_player_status', 'obor_profile_has_player_status_property'))
                + function(script, 'obor_player_property_native'),
            'VARIANTS': '\n'.join(function(variants, name) for name in ('ScriptVariant_ChangeType',
                'ScriptVariant_Clear', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
            'PLAYER': player.replace(plain_switch, native_switch),
            'DIRECTION': 'case _ep_direction:' + direction['_ep_direction']['body'],
            'RANGE': function(script, 'openbor_checkrange'),
            'PROFILES': ',\n'.join('{%du,%d,%d}' % (r['revision'], r['unknown_numeric_is_empty'],
                r['direction_conversion'] == 'Decimal') for r in rows),
            'LNS': '{6330u,%d,%d}' % (data['lns_control']['unknown_numeric_is_empty'],
                    data['lns_control']['direction_conversion'] == 'Decimal'),
        }
        template = Path(__file__).with_name('script_query_defaults_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        result = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in result.splitlines()], [*revisions, 6330])

    def test_6391_original_ai_flags_and_delay_readback(self):
        from test_early_jump_walkoff import continued_macro
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-script-posture-ids.json'))
        rows = data['sources']
        revisions = [r['revision'] for r in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        profiles = (engine / 'source/openborscript/profile_ids.h').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        macros = (engine / 'source/openborscript/scriptcommon.h').read_text()
        utils = (engine / 'source/utils.c').read_text()
        _, mapping = switch_cases(script, 'mapstrings_entityproperty', 'ep')
        _, getters = switch_cases(script, 'openbor_getentityproperty', 'propind')
        _, setters = switch_cases(script, 'openbor_changeentityproperty', 'propind')

        def cases(source, labels):
            return '\n'.join('case ' + label + ':' + source[label]['body'] for label in labels)

        def expected(r):
            return '{%du,%d,{%s},%d,%d,%d}' % (r['revision'], len(r['names']),
                ','.join(map(json.dumps, r['names'])), r['decimal_factor'], len(r['edge_names']),
                r['clears_recovery'])

        fields = sorted({name for row in rows for name in row['names']} - {'jumpid'})
        flags = ('_ep_aiflag', '_ep_edgerange')
        decls = [declaration(script, rf'^enum {name}\s*\{{[^}}]+\}};') for name in
                 ('entityproperty_enum', 'aiflag_enum', 'edgerange_enum', 'gep_edelay_enum')]
        decls.extend(declaration(script, rf'^static const (?:int|char \*)\s*{name}\[\][^;]+;') for name in
                     ('obor_entityproperty6330', 'obor_entityproperty6330lns', 'eplist_aiflag', 'eplist_edgerange'))
        decls.append(declaration(script, r'^enum\s*\{\s*OBOR_6330_ENTITY_EDGE_ORDINAL[^;]+;'))
        values = {
            'DECLARATIONS': '\n'.join(decls),
            'MACRO': continued_macro(macros, 'MAPSTRINGS'),
            'HELPERS': function(profiles, 'obor_profile_uses_5134_script_ids') + '\n'
                + function((engine / 'openbor.h').read_text(), 'obor_profile_has_classic_boomerang') + '\n'
                + '\n'.join(function(script, name) for name in ('obor_aiflag_count',
                    'obor_aiflag_from_native', *LEGACY_ENTITY_SELECTORS)),
            'VARIANTS': '\n'.join(function(variants, name) for name in ('ScriptVariant_ChangeType',
                'ScriptVariant_Clear', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
            'SEARCH': function(utils, 'searchList'),
            'MEMBERS': 'int ' + ','.join(fields) + ';',
            'FIELDS': ',\n'.join('{"%s", &subject.%s}' % (name, name) for name in fields),
            'MAP': cases(mapping, flags), 'GET': cases(getters, (*flags, '_ep_edelay', '_ep_edge')),
            'SET': cases(setters, (*flags, '_ep_edge')), 'PROFILES': ',\n'.join(map(expected, rows)),
            'LNS': expected(data['lns_control'] | {'revision': 6330}),
        }
        template = Path(__file__).with_name('script_posture_ids_contract.c.in').read_text()
        code = re.sub(r'@([A-Z]+)@', lambda match: values[match[1]], template)
        result = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in result.splitlines()], [*revisions, 6330])

    def test_6391_axis_property_registry_and_values(self):
        data = load_contract_fixture(AXIS_PROPERTIES)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        result = native_output(axis_property_program(data, rows, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in result.splitlines()], revisions)

    def test_6391_entity_links_and_model_unload(self):
        data = load_contract_fixture(ENTITY_LINKS_AND_MODEL_UNLOAD)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        modules = engine / 'source/openborscript'
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        index = (modules / 'index.c').read_text()
        registry = function(index, 'Script_LoadSystemFunctions')
        insertion = re.search(r'(?m)^    if[^\n]*\n        List_InsertAfter\(&theFunctionList,\s*'
                              r'\(void \*\)openbor_unload_model, "unload_model"\);', registry)
        reverse = re.search(r'else if\s*\(functionRef == \(\(void \*\)openbor_unload_model\)\)'
                            r'\s*\{[^{}]*\}', function(index, 'Script_GetFunctionName'))
        self.assertIsNotNone(insertion)
        self.assertIsNotNone(reverse)
        sources = {
            modules / 'binding.c': ('mapstrings_binding',),
            modules / 'entity.c': ('obor_profile_scalar_entity_positions', 'mapstrings_entity_property',
                                   'profile_entity_property', 'openbor_get_entity_property',
                                   'openbor_set_entity_property'),
            engine / 'openbor.c': ('obor_remember_attack',),
            engine / 'openborscript.c': ('openbor_unload_model',),
        }
        methods = []
        for path, symbols in sources.items():
            source = path.read_text()
            methods.extend(function(source, name) for name in symbols)
        values = {
            'CACHE': variants[variants.index('#define STRCACHE_INC'):variants.index('BOOL ScriptVariant_IsTrue(')],
            'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
            'METHODS': '\n'.join(methods),
            'REGISTRY': insertion[0],
            'REVERSE': reverse[0].removeprefix('else '),
            'ROWS': ','.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['opponent'], row['owner'],
                                                  row['player_index'], row['unload_model']) for row in rows),
        }
        template = Path(__file__).with_name('entity_links_and_model_unload_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        result = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(re.findall(r'(?m)^PASS \d+$', result), [f'PASS {revision}' for revision in revisions])

    def check_script_entity_status(self, physical):
        data = load_contract_fixture(SCRIPT_STATUS)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        if physical == '4432':
            namespace = entity_namespace(script)
            macros = script
        else:
            declarations = [declaration(script, r'^enum entityproperty_enum[^;]+;')]
            declarations.extend(declaration(script, rf'^static const (?:int|char \*)\s*{name}\[\][^;]+;')
                                for name in ('obor_entityproperty6330', 'obor_entityproperty6330lns', 'eplist',
                                             'obor_eplist6330', 'obor_eplist6330lns'))
            declarations.append(declaration(script, r'^enum\s*\{\s*OBOR_6330_ENTITY_EDGE_ORDINAL[^;]+;'))
            namespace = '\n'.join(declarations + [function(script, name) for name in
                                                   LEGACY_ENTITY_SELECTORS])
            macros = (engine / 'source/openborscript/scriptcommon.h').read_text()
        mapper, cases = switch_cases(script, 'mapstrings_entityproperty', 'ep')
        mapping = (mapper[:mapper.index('    static const')] +
                   declaration(mapper, r'^    static const char \*proplist_landframe\[\][^;]+;') + '\n' +
                   mapper[mapper.index('    if(paramCount < 2)'):cases['_ep_a']['label_start']] +
                   'case _ep_landframe:' + cases['_ep_landframe']['body'] + '\n    default: break;\n    }\n    return 1;\n}')
        methods = []
        for name, fields in (('openbor_getentityproperty', ('_ep_health', '_ep_mp', '_ep_landframe',
                                                          '_ep_boss', '_ep_exists')),
                             ('openbor_changeentityproperty', ('_ep_health', '_ep_mp', '_ep_boss'))):
            method, cases = switch_cases(script, name, 'propind')
            for label, case in reversed(tuple(cases.items())):
                if label not in (*fields, 'default'):
                    method = method[:case['label_start']] + method[case['end']:]
            if name == 'openbor_changeentityproperty':
                method = method[:method.index('    static const')] + method[method.index('    *pretvar = NULL;\n\n'):]
            methods.append(method)
        flags = ('attacking', 'blocking', 'charging', 'blink')
        legacy_flag_cases = {}
        for kind, name in (('READ', 'openbor_getentityproperty'), ('WRITE', 'openbor_changeentityproperty')):
            method = function(script, name)
            legacy_flag_cases[kind] = '\n'.join(
                f'case {flag.upper()}: ' +
                re.search(rf'case _ep_aiflag_{flag}:\s*([^;]+;)', method)[1] + ' break;'
                for flag in flags)
        values = {
            'NAMESPACE': namespace + '\n' + declaration(script, r'^enum gep_landframe_enum[^;]+;'),
            'MACROS': declaration(macros, r'^#define _is_not_a_known_subproperty_of_[^\n]+') + '\n' +
                      re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', macros)[0],
            'VARIANTS': '\n'.join(function(variants, name) for name in
                                  ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
            'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
            'METHODS': '\n'.join([mapping, *methods, function(script, 'openbor_damageentity')]),
            'FLAG_GETTERS': legacy_flag_cases['READ'],
            'FLAG_SETTERS': legacy_flag_cases['WRITE'],
            'DEFAULT': re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', core)[0],
            'LAND_INIT': re.search(r'(?m)^\s*(newanim->landframe(?:\.frame)?\s*=\s*(?:-1|NULL);)',
                                   function(core, 'load_cached_model'))[1],
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['absent_land_is_empty']) for row in rows),
        }
        template = Path(__file__).with_name('script_entity_status_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_script_entity_status(self):
        self.check_script_entity_status('4432')

    def test_6391_script_entity_status(self):
        self.check_script_entity_status('6391')

    def check_script_entity_actions(self, physical):
        data = load_contract_fixture(SCRIPT_ACTIONS)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        values = {
            'METHODS': '\n'.join(function(script, name) for name in
                                 ('openbor_executeanimation', 'openbor_performattack', 'openbor_setidle')),
            'INTEGER': function(variants, 'ScriptVariant_IntegerValue'),
            'ROWS': ','.join('{%du,%d,%d,%d,%s,%d}' % (row['revision'], row['active'], row['keep_flags'], row['keep_duck'],
                                                   row['port_animation'], row['native_animation']) for row in rows),
        }
        template = Path(__file__).with_name('script_entity_actions_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_script_entity_actions(self):
        self.check_script_entity_actions('4432')

    def test_6391_script_entity_actions(self):
        self.check_script_entity_actions('6391')

    def test_6391_entity_collision_availability(self):
        data = load_contract_fixture(ENTITY_COLLISION)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
        utility = (engine / 'source/utils.c').read_text()
        modules = engine / 'source/openborscript'
        commands = (modules / 'commands.c').read_text()
        index = (modules / 'index.c').read_text()
        constants = (modules / 'constants.c').read_text()
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        reverse = function(index, 'Script_GetFunctionName')
        forward = function(index, 'Script_LoadSystemFunctions')
        debug = function(source, 'menu_options_debug')
        draw = function(source, 'predrawstatus')
        overlay = function(source, 'draw_visual_debug')
        reverse_start = reverse.index('    // Entity collision (ebox)')
        forward_start = forward.index('    // Entity collision (ebox) properties.')
        collision = (modules / 'collision_entity.c').read_text()
        values = {
            'COMMANDS': model_command_functions(commands, utility),
            'COLLECTION_API': '\n'.join(function(collision, f'openbor_{name}_entity_collision_{part}')
                for name, part in (('get', 'collection'), ('get', 'instance'),
                                   ('get', 'property'), ('set', 'property'))),
            'MODEL_CASES': ''.join('case ' + name + ':' + cases[name]['body'] for name in cases
                                   if name.startswith('CMD_MODEL_EBOX') or name in
                                   ('CMD_MODEL_ENTITYPUSHING', 'CMD_MODEL_PUSHINGFACTOR',
                                    'CMD_MODEL_ONENTITYCOLLISIONSCRIPT')),
            'REVERSE_DECLARATIONS': reverse[reverse.index('{') + 1:reverse.index('    if (functionRef')],
            'REVERSE': reverse[reverse_start:reverse.index('    else if (functionRef == ((void *)openbor_tossentity))')],
            'FORWARD': forward[forward_start:forward.index('    // Energy status', forward_start)],
            'CONSTANTS': '\n'.join(re.findall(r'(?m)^\s*(else if[^\n]*"ENTITY_COLLISION_PROP_[A-Z]+"[^\n]*)',
                                              constants)),
            'DEBUG_DISPLAY': re.search(r'if\(([^\n]+)\)\s*\{\s*_menutext\(\(selector == ITEM_COL_ENTITY\)', debug)[1],
            'DEBUG_SKIP': re.search(r'(?m)^\s*(if\([^\n]+selector == ITEM_COL_ENTITY\)[^\n]*\n\s*selector \+= [^;]+;)', debug)[1],
            'DEBUG_TOGGLE': re.search(r'(?ms)^\s*(case ITEM_COL_ENTITY:.*?break;)', debug)[1],
            'DEBUG_ENTRY': re.search(r'(?ms)^    if\((savedata.debug_position.*?)(?=\)\s*\{)', draw)[1],
            'DEBUG_ENTITY_BOXES': re.search(r'(?m)^\s*if\(([^\n]*savedata\.debug_collision_entity)\)', overlay)[1],
            'VARIANTS': '\n'.join(function(variant, name) for name in
                                  ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                   'ScriptVariant_IntegerValue')),
            'METHODS': '\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat',
                                  'diff', 'execute_onentitycollision_script', 'check_entity_collision',
                                  'check_entity_collision_for', 'ent_post_update')),
            'ROWS': ','.join('{%du,%d,%d,%d}' % (row['revision'], row['entity_collision'],
                                                row['pushing'], row['collection_api']) for row in rows),
        }
        template = Path(__file__).with_name('entity_collision_availability_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        actual = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_6391_entity_collision_frame_construction(self):
        data = load_contract_fixture(ENTITY_COLLISION)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        properties = (engine / 'source/openborscript/animation.c').read_text()
        getter = function(properties, 'openbor_get_animation_property')
        initializer = re.search(r'(?ms)^const s_collision_entity empty_entity_collision =\s*\{[^{}]*\};', source)[0]
        _, loader = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        animation = loader['CMD_MODEL_ANIM']['body']
        reset = '\n'.join(re.search(r'(?m)^\s*' + code + r'[^;]*;', animation)[0]
                          for code in (r'memset\(&ebox,', r'ebox_con\s*='))
        frame = loader['CMD_MODEL_FRAME']['body']
        first_coordinate = frame.index('entity_coords.x')
        transform = frame[first_coordinate:frame.index('attack_coords.x', first_coordinate)]
        methods = ('alloc_frames', 'free_frames', 'collision_alloc_coords',
                   'collision_alloc_attack_instance', 'collision_alloc_attack_list',
                   'collision_alloc_body_instance', 'collision_alloc_body_list',
                   'collision_alloc_entity_instance', 'collision_alloc_entity_list', 'addframe')
        values = {
            'INITIALIZER': initializer,
            'RESET': reset,
            'TRANSFORM': transform,
            'METHODS': '\n'.join(function(source, name) for name in methods),
            'COLLISION_PROPERTY': re.search(r'(?ms)^\s*(case ANI_PROP_ENTITY_COLLISION:.*?)(?=^\s*case )', getter)[1],
            'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['entity_collision'],
                                             row['getter']) for row in rows),
        }
        template = Path(__file__).with_name('entity_collision_frames_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        actual = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_native_entity_property_name_and_ordinal_dispatch(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        slots = {name: index for index, name in enumerate(data['physical_selectors'])}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        results = iter(native_output(program(data, engine), data, engine_source=engine).splitlines())
        for row in data['sources']:
            table = data['tables'][row['table']]
            for index, query in enumerate(data['queries']):
                want = [row['revision'], index, *expected(table, query, slots)]
                self.assertEqual(json.loads(next(results)), want, (row['revision'], query))
        self.assertIsNone(next(results, None))

    def test_4905_scalar_binding_results_and_writes(self):
        data = load_contract_fixture(FIXTURE)
        binding = data['binding']
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        script = (engine / 'openborscript.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        getter = function(script, 'openbor_getentityproperty')
        template = Path(__file__).with_name('scalar_binding_contract.c.in').read_text()
        methods = ('mapstrings_binding', 'obor_binding_handle', 'openbor_get_binding_property',
                   'openbor_set_binding_property')
        values = {
            'CACHE': variants[variants.index('typedef struct'):
                              variants.index('HRESULT ScriptVariant_DecimalValue(')],
            'PROPERTIES': declaration(script, r'^enum obor_binding_property[^;]*;'),
            'SELECTORS': declaration(script, r'^enum entityproperty_enum[^;]*;'),
            'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
            'METHODS': '\n'.join(function(script, name) for name in methods),
            'HANDLE_CASES': getter[getter.index('    case _ep_binding:'):getter.index('    case _ep_candamage:')],
            'NAMES': ','.join(json.dumps(name) for name in binding['properties']),
            'REVISION': str(binding['revision']),
        }
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        actual = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(actual.splitlines(), binding['diagnostics'] + ['scalar_binding_4905'])

    def test_6391_boolean_binding_selectors_and_diagnostics(self):
        data = load_contract_fixture(BOOLEAN_BINDING)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        values = {
            **binding_property_methods(engine),
            'NAMES': ','.join(json.dumps(name) for name in data['names']),
            'PROFILES': ','.join('{%du,%d}' % (row['revision'], row['boolean_axes']) for row in rows),
        }
        template = Path(__file__).with_name('boolean_binding_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        actual = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        sizes, _, actual = actual.partition('\n')
        width, entity_bytes, binding_bytes = map(int, sizes.split())
        refused = "Property name 'entity' is not supported by binding.\n\n Available properties:\n"
        refused += ''.join('\n\t' + name for name in data['names']) + '\n\n'
        expected = []
        for row in rows:
            entity_size, binding_size = (data['diagnostic_sizes'][str(width)] if row['boolean_axes']
                                         else (entity_bytes, binding_bytes))
            diagnostic = f'\n\n Size entity: {entity_size}\n Size bind: {binding_size}'
            expected.append(diagnostic * (len(data['names']) * 2 + 1) + refused + f'PASS {row["revision"]}\n')
        self.assertEqual(actual, ''.join(expected))

    def test_4905_precedes_typed_entity_and_energy_names(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / '4432'))
        script = (engine / 'openborscript.c').read_text()
        registry = function(script, 'Script_LoadSystemFunctions')
        names = set(re.findall(r',\s*"([^"]+)"\);', registry))
        self.assertIn('getentityproperty', names)
        self.assertTrue(names.isdisjoint(load_contract_fixture(TYPED_ENTITY)['registry_names']))

    def test_6391_intermediate_binding_properties(self):
        data = load_contract_fixture(INTERMEDIATE_BINDING)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))

        def profile(row):
            entries = row['properties']
            return '{%du,%d,{%s},{%s}}' % (
                row['revision'], len(entries),
                ','.join(json.dumps(name) for name, _ in entries),
                ','.join('_BINDING_' + field for _, field in entries))

        values = {**binding_property_methods(engine), 'ROWS': ',\n'.join(map(profile, rows))}
        template = Path(__file__).with_name('intermediate_binding_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        result = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        contexts = re.findall(r'(?ms)^BEGIN (\d+)\n(.*?)^PASS \1$', result)
        self.assertEqual([int(revision) for revision, _ in contexts], revisions)
        for row, (_, output) in zip(rows, contexts, strict=True):
            if 'diagnostics' in row:
                with self.subTest(revision=row['revision']):
                    self.assertEqual(' Size entity:' in output, bool(row['diagnostics']))
                    self.assertEqual(' Size bind:' in output, bool(row['diagnostics']))

    def test_6391_binding_adjustment_callbacks_and_model_commands(self):
        data = load_contract_fixture(BINDING_ADJUSTMENT)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        commands = (engine / 'source/openborscript/commands.c').read_text()
        registry = function(commands, 'createModelCommandList')
        guard = re.search(r'(?m)^    if[^\n]*\n    \{\n'
                          r'        LIST_ADD\(CMD_MODEL_ON_BIND_UPDATE_OTHER_TO_SELF_SCRIPT[^\n]*\n'
                          r'        LIST_ADD\(CMD_MODEL_ON_BIND_UPDATE_SELF_TO_OTHER_SCRIPT[^\n]*\n    \}', registry)
        dispatch = re.search(r'(?m)^    if[^\n]*\n    \{\n        adjust_bind_6453\(e\);\n'
                             r'        return;\n    \}', function(source, 'adjust_bind'))
        self.assertIsNotNone(guard)
        self.assertIsNotNone(dispatch)
        methods = ['execute_on_bind_update_other_to_self', 'execute_on_bind_update_self_to_other',
                   'adjust_bind_6453', 'obor_profile_script_container_offset']
        layout = data['script_layout']
        self.assertTrue(all(re.fullmatch(r'\w+_script', name) for name in layout))
        parts = {
            'METHODS': '\n'.join(function(source, name) for name in methods),
            'REGISTRY': guard[0], 'DISPATCH': dispatch[0],
            'SCRIPT_LAYOUT': ',\n'.join('offsetof(s_scripts, ' + name + ')' for name in layout),
            'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['callbacks'], row['target_relative_axes'])
                             for row in rows),
        }
        for side in ('other_to_self', 'self_to_other'):
            loader_call = f'newchar->scripts->on_bind_update_{side}_script, "on_bind_update_{side}_script"'
            self.assertEqual(function(source, 'load_cached_model').count(loader_call), 1)
        template = Path(__file__).with_name('binding_adjustment_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(output.splitlines(), [f'PASS {revision}' for revision in revisions])

    def test_6391_typed_entity_and_energy(self):
        data = load_contract_fixture(TYPED_ENTITY)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        modules = engine / 'source/openborscript'
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        index = (modules / 'index.c').read_text()
        registry = function(index, 'Script_LoadSystemFunctions')
        names = '|'.join(re.escape(name) for name in data['registry_names'])
        registrations = re.findall(
            r'List_InsertAfter\(&theFunctionList,\s*\(void \*\)\w+,\s*"(?:' + names + r')"\);',
            registry)
        self.assertEqual(len(registrations), len(data['registry_names']))
        callbacks = '|'.join('openbor_' + re.escape(name) for name in data['registry_names'])
        branch = (r'else if\s*\(functionRef\s*==\s*\(\(void \*\)(?:' + callbacks +
                  r')\)\)\s*\{[^{}]*\}')
        parts = {}
        for key, name in (('REVERSE', 'Script_GetFunctionName'), ('MAPPERS', 'Script_GetStringMapFunction')):
            branches = re.findall(branch, function(index, name))
            self.assertEqual(len(branches), len(data['registry_names']))
            parts[key] = '\n    '.join(item.removeprefix('else ') for item in branches)
        sources = {
            modules / 'binding.c': ('mapstrings_binding',),
            modules / 'energy_status.c': ('mapstrings_energy_status_property',
                         'openbor_get_energy_status_property', 'openbor_set_energy_status_property'),
            engine / 'openbor.c': ('obor_remember_attack',),
            modules / 'entity.c': ('obor_profile_scalar_entity_positions', 'mapstrings_entity_property',
                         'profile_entity_property', 'openbor_get_entity_property', 'openbor_set_entity_property'),
        }
        methods = []
        for path, symbols in sources.items():
            source = path.read_text()
            methods.extend(function(source, name) for name in symbols)
        parts.update({
            'CACHE': variants[variants.index('#define STRCACHE_INC'):variants.index('BOOL ScriptVariant_IsTrue(')],
            'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
            'METHODS': '\n'.join(methods),
            'REGISTRY': '\n    '.join(registrations),
            'ANIMATION_IDS': ','.join(str(int(value)) for value in data['animation_ids']),
            'REVISIONS': ','.join('{%du,%s}' % (row['revision'], row['selector_table']) for row in rows),
        })
        for tag, key in (('HISTORICAL', '5134'), ('WITH_LOOP', '6175'), ('CONTROL', '6391')):
            refused = data['rejected_names'][key]
            parts[tag] = ',\n'.join('{%s,%s,%d}' % (json.dumps(name), enum, name not in refused)
                                   for name, enum in data['selector_tables'][key])
        template = Path(__file__).with_name('typed_entity_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        result = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(re.findall(r'(?m)^PASS \d+$', result), [f'PASS {revision}' for revision in revisions])
        selector_tables = {'SCALAR_POSITIONS': '5134', 'COORDINATES_WITH_LOOP': '6175', 'COORDINATES': '6391'}
        diagnostics = []
        for row in rows:
            family = selector_tables[row['selector_table']]
            diagnostics.extend(name for name in data['rejected_names'][family] for _ in range(2))
            if family == '6391':
                diagnostics.append('boomerang_loop')
        self.assertEqual(re.findall(r"(?m)^ Error: '([^']+)' is not a known entity property\.$", result),
                         diagnostics)

    def test_4905_precedes_typed_script_flags(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / '4432'))
        mapper = function((engine / 'openborscript.c').read_text(), 'mapstrings_transconst')
        names = set(re.findall(r'\bI?ICMPCONST\((\w+)\)', mapper))
        flags = set(load_contract_fixture(TYPED_SCRIPT_IDS)['flag_names'])
        self.assertTrue(names.isdisjoint(flags))

    def test_4905_native_animation_properties(self):
        data = load_contract_fixture(TYPED_SCRIPT_IDS)['preceding_animation_property_control']
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        code = animation_property_program(engine, [data], legacy_source=True)
        result = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(result.splitlines(), [f'PASS {data["revision"]}'])

    def test_6391_native_animation_properties(self):
        data = load_contract_fixture(TYPED_SCRIPT_IDS)
        rows = data['animation_property_profiles']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['animation_property_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        code = animation_property_program(engine, rows, legacy_source=False)
        result = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(result.splitlines(), [f'PASS {revision}' for revision in revisions])

    def test_6391_native_animation_and_typed_script_ids(self):
        data = load_contract_fixture(TYPED_SCRIPT_IDS)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        code = typed_script_ids_program(data, engine)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(re.findall(r'(?m)^PASS \d+$', output), [f'PASS {revision}' for revision in revisions])
        self.assertEqual(re.findall(r"(?m)^Can't find openbor constant '([^']+)' $", output),
                         [name for row in rows
                          for name, value in data['cases']['early' if row['early_ids'] else 'base'].items()
                          if value is None])

    def test_6391_native_animation_and_binding_matching_ids(self):
        data = load_contract_fixture(ANIMATION_AND_MATCHING_IDS)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        code = typed_script_ids_program(data, engine)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(re.findall(r'(?m)^PASS \d+$', output), [f'PASS {revision}' for revision in revisions])

    def check_6391_literal_constants(self, fixture, *, background_fixture=None):
        data = load_contract_fixture(fixture)
        rows = data['sources']
        self.assertEqual([r['revision'] for r in rows], sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        names = data['names']
        tables = list(data['values'].values())
        self.assertLessEqual(len(tables), 32)
        self.assertTrue(all(len(t) == len(names) for t in tables))
        cases = []
        for name, values in zip(names, zip(*tables, strict=True), strict=True):
            mask = sum(1 << i for i, value in enumerate(values) if value is not None)
            cases.append('{%s,%du,{%s}}' % (json.dumps(name), mask,
                                          ','.join(str(value if value is not None else 0) for value in values)))
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        script = (engine / 'source/openborscript/constants.c').read_text()
        background_rows = []
        if background_fixture is not None:
            background = load_contract_fixture(background_fixture)
            background_rows = background['sources']
            self.assertEqual([row['revision'] for row in background_rows],
                             sorted(contract_revisions(background, background['expected_revisions'])))
        parts = constant_mapper_parts(engine) | {
            'WRAPPER': function(variants, 'ScriptVariant_ToString') + '\n' + function(script, 'openbor_transconst'),
            'LEVEL_METHODS': constant_level_methods(engine),
            'BACKGROUND_SPEED_METHODS': background_speed_level_methods(engine),
            'RUNTIME_GLOBALS': '\n'.join('int %s = %d;' % (name, value)
                                        for name, value in data['runtime_globals'].items()),
            'CASES': ',\n'.join(cases),
            'TABLE_COUNT': str(len(tables)),
            'CHECK_LEVELS': str(int(data.get('check_levels', True))),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['table']) for row in rows),
            'BACKGROUND_ROWS': ''.join('{%du,%d},\n' % (row['revision'], row['legacy_background_speed'])
                                       for row in background_rows),
        }
        template = Path(__file__).with_name('literal_constant_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(output.splitlines(),
                         [line for row in rows
                          for line in [*(f"Can't find openbor constant '{name}' "
                                         for name, value in zip(names, tables[row['table']], strict=True)
                                         if value is None), f'PASS {row["revision"]}']])

    def test_6391_original_literal_constants(self):
        self.check_6391_literal_constants(LITERAL_CONSTANTS, background_fixture=BACKGROUND_SPEEDS)

    def test_6391_original_animation_constants(self):
        self.check_6391_literal_constants(ANIMATION_CONSTANTS)

    def test_6391_legacy_entity_names_ordinals_and_boomerang(self):
        data = load_contract_fixture(LEGACY_ENTITY)
        rows = [row for row in data['sources'] if row['engine'] == '6391']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']['6391']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/6391'))
        commands = (engine / 'source/openborscript/commands.c').read_text()
        core = (engine / 'openbor.c').read_text()
        self.assertNotIn('CMD_MODEL_STATS', function(commands, 'createModelCommandList'))
        self.assertNotIn('case CMD_MODEL_STATS:', function(core, 'load_cached_model'))
        names = [{entry[0] for entry in table} for table in data['tables'].values()]
        controls = sorted((set.union(*names) - set.intersection(*names)) | {'stats'})
        output = native_output(legacy_boomerang_program(engine, rows, data['tables'], controls),
                               {'engine': '6391'}, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        expected = []
        for row in rows:
            table = data['tables'][row['table']]
            for name in [entry[0] for entry in table] + controls:
                if original_entity_name_lookup(table, name) < 0:
                    expected.append(f"Property name '{name}' is not supported by function getentityproperty.\n")
                    expected.append('\n Available properties:\n' + ''.join('\n\t' + item[0] for item in table) + '\n\n')
            if row['boomerang'] == 1:
                expected.append('You must specify a flag value for boomerang property (0 = acceleration, 1 = distance_x).\n')
                expected.append('You must specify 2 float values to change boomerang property (acceleration anddistance_x).\n')
            expected.append(f'PASS {row["revision"]}\n')
        self.assertEqual(output, ''.join(expected))


if __name__ == '__main__':
    unittest.main()
