"""Check system-variable namespaces, selected fields and music handles.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import continued_macro
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-system-routing-contracts.json'


def system_layout_fragments(source):
    arrays = []
    for name in ('svlist', 'obor_profile_system_music_names'):
        match = re.search(r'static const char \*' + name + r'\[\]\s*=\s*\{[^}]+\};', source, re.S)
        if match is None:
            raise ValueError('Complete source-owned system name table required')
        arrays.append(match[0])
    state = re.search(r'static struct\s*\{[^}]+\}\s*obor_legacy_system_layout;', source, re.S)
    if state is None:
        raise ValueError('Historical system layout required')
    arrays.append(state[0])
    functions = ('obor_system_property_first_build', 'obor_profile_system_prepare_layout',
                 'obor_profile_system_property_count', 'obor_profile_system_native_index',
                 'mapstrings_systemvariant')
    return '\n'.join(arrays), '\n'.join(function(source, name) for name in functions)


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openborscript.c').read_text()
    mixer = (engine / 'source/gamelib/soundmix.c').read_text()
    header = (engine / 'source/openborscript/config.h').read_text()
    enum = re.search(r'enum systemvariant_enum\s*\{([^}]+)\}', header, re.S)
    labels = re.findall(r'\bSYSTEM_PROPERTY_\w+', enum[1]) if enum else []
    if not labels or labels[-1] != 'SYSTEM_PROPERTY_THE_END':
        raise ValueError('Complete system namespace enum required')
    arrays, helpers = system_layout_fragments(source)
    selected = ('SYSTEM_PROPERTY_MAX_WALL_HEIGHT', 'SYSTEM_PROPERTY_MUSICVOL',
                'SYSTEM_PROPERTY_SAMPLE_PLAY_ID', 'SYSTEM_PROPERTY_MUSIC_CHANNEL')
    callbacks = []
    for name in ('getsyspropertybyindex', 'changesyspropertybyindex'):
        body, cases = switch_cases(source, name, 'index', outermost=True)
        required = selected if name.startswith('get') else selected[:1]
        callbacks.append(body[:body.index('switch(index)')] + 'switch(index){' +
            ''.join('case ' + key + ':' + cases[key]['body'] for key in required) +
            'default:' + cases['default']['body'] + '}\nreturn 1;\n}\n')
    types = {m[1]: m[0] for m in re.finditer(
        r'(?ms)^typedef struct(?:\s+\w+)?\s*\{.*?^\}\s*(\w+)\s*;', mixer)}
    rows = []
    for row in data['sources']:
        names = row['names'] + data['extra_queries']
        rows.append('{%du,%d,{%s},{%s}}' % (row['revision'], len(names),
            ','.join(json.dumps(n) for n in names), ','.join(str(n) for n in row['field_ids'])))
    parts = dict(ARRAYS=arrays, TYPES='\n'.join(types[n] for n in
            ('samplestruct', 's_soundcache', 's_audio_global')),
        LABELS=','.join(json.dumps(n) for n in labels[:-1]),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        VARIANTS='\n'.join(function((engine / 'source/scriptlib/ScriptVariant.c').read_text(), n)
            for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        COUNTER=function(mixer, 'sound_profile_sample_play_id'),
        HELPERS=helpers,
        FIELDS='\n'.join(callbacks), METHODS='\n'.join(function(source, n) for n in
            ('openbor_systemvariant', 'openbor_setsystemvariant')), CONTEXTS=','.join(rows))
    code = Path(__file__).with_name('modern_system_routing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved system routing contract input')
    return code


class ModernSystemRoutingContracts(unittest.TestCase):
    def test_legacy_names_indices_waiting_and_geometry_constants(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openborscript.c').read_text()
        constants = (engine / 'source/openborscript/constants.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        fixture = json.loads(FIXTURE.with_name('modern-legacy-system-layout.json').read_text())
        queries = fixture['names'] + ['music_channel', 'healthcheat', 'hud_load']
        profiles = {7369, 7391, 7420, 7472, 7533}
        profiles.update(build for row in fixture['layouts'][1:] for build in (row['build'] - 1, row['build']))
        names, ordinals = [], []
        for build in sorted(profiles, reverse=True):
            layout = next(row for row in reversed(fixture['layouts']) if row['build'] <= build)
            visible = [name for name in fixture['names'] if name not in layout['missing']]
            unsearchable = layout.get('unsearchable', [])
            indices = {name: i for i, name in enumerate(visible) if name not in unsearchable}
            names.extend(f'{{{build}, {json.dumps(name)}, {indices.get(name, -1)}}}' for name in queries)
            native = ['SYSTEM_PROPERTY_' + ('HUD_LOAD' if name == 'hud_loading' else name.upper())
                      for name in visible]
            if 'unhandled_index' in layout:
                native.insert(layout['unhandled_index'], '-1')
            ordinals.extend(f'{{{build}, {i}, {value}}}' for i, value in enumerate(native))
            ordinals.extend([f'{{{build}, -1, -1}}', f'{{{build}, {len(native)}, -1}}'])
        arrays, helpers = system_layout_fragments(source)
        getter, routes = switch_cases(source, 'getsyspropertybyindex', 'index', outermost=True)
        selected = ('SYSTEM_PROPERTY_MAXATTACKTYPES', 'SYSTEM_PROPERTY_WAITING',
                    'SYSTEM_PROPERTY_PAKNAME', 'SYSTEM_PROPERTY_SAMPLE_PLAY_ID', 'SYSTEM_PROPERTY_SHADOWALPHA')
        get_body = (getter[:getter.index('switch(index)')] + 'switch(index){' +
                    ''.join('case ' + key + ':' + routes[key]['body'] for key in selected) +
                    'default:' + routes['default']['body'] + '}\nreturn 1;\n}\n')
        setter, routes = switch_cases(source, 'changesyspropertybyindex', 'index', outermost=True)
        set_body = (setter[:setter.index('switch(index)')] + 'switch(index){case SYSTEM_PROPERTY_SHADOWALPHA:' +
                    routes['SYSTEM_PROPERTY_SHADOWALPHA']['body'] +
                    'default:' + routes['default']['body'] + '}\nreturn 1;\n}\n')
        mixer = (engine / 'source/gamelib/soundmix.c').read_text()
        geometry = ('BGHEIGHT', 'MAX_WALL_HEIGHT', 'FRONTPANEL_Z', 'HOLE_Z', 'HUD_Z',
                    'NEONPANEL_Z', 'SHADOW_Z', 'SCREENPANEL_Z', 'PANEL_Z', 'MIRROR_Z',
                    'PLAYER_MIN_Z', 'PLAYER_MAX_Z')
        chain = [line for line in function(constants, 'mapstrings_transconst').splitlines()
                 if re.search(r'\bICMPCONST(?:_BEFORE)?\((' + '|'.join(geometry) + r')\b', line)]
        self.assertEqual(len(chain), len(geometry))
        parts = dict(ARRAYS=arrays, HELPERS=helpers, GETTER=get_body, SETTER=set_body,
                     COUNTER=function(mixer, 'sound_profile_sample_play_id'),
                     SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
                     VARIANTS='\n'.join(function(variant, name) for name in
                                       ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
                     CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
                     CONSTANT_MACROS='\n'.join(continued_macro(constants, name) for name in
                                              ('ICMPCONST', 'ICMPCONST_BEFORE')),
                     CONSTANT_CHAIN='\n'.join(chain), NAMES=',\n'.join(names), ORDINALS=',\n'.join(ordinals))
        code = Path(__file__).with_name('modern_legacy_system_layout_contract.c.in').read_text()
        for key, part in parts.items():
            code = code.replace('@' + key + '@', part)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_names_numeric_ids_music_pointer_counter_and_wall_setter(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', integer_bytes=4, profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
