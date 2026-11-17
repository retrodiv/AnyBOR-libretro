"""Check native player-property tables, values and direction constant admission.

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
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-player-property-contracts.json'


def program(data, engine):
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    enum = re.search(r'enum playerproperty_enum\s*\{.*?\};', source, re.S)
    if enum is None:
        raise ValueError('Native player enum required')
    prefix = source[enum.start():source.index('int mapstrings_playerproperty(', enum.end())]
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    constants = function(source, 'mapstrings_transconst')
    # These seven newly introduced entries and the preceding native control are
    # the scope here. Preserve their real chain, conversion and diagnostic tail.
    cut = constants.index('        ICMPCONST(VT_EMPTY)')
    tail = constants.index('        else\n        {\n            found = FALSE;')
    constants = constants[:cut] + constants[tail:]
    macro = source[source.index('#define IICMPCONST('):source.index('static LONG obor_animation_constant_value')]
    providers = Path(__file__).with_name('classic_player_properties_contract.c.in').read_text().split('@VARIANTS@')[0]
    providers = providers.replace('int get_cached_model_index(char *name) { (void)name; abort(); }',
        'static int cache_result, cache_calls;\nint get_cached_model_index(char *name) '
        '{ assert(!strcmp(name,"Player")); ++cache_calls; return cache_result; }')
    values = dict(PROVIDERS=providers+'\nvoid StrCache_Grab(int i) { (void)i; abort(); }\n',
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_ToString', 'ScriptVariant_Copy')),
        SEARCH=function(utils, 'searchList'), MAP_MACRO=''.join(lines[first:last+1]),
        METHODS=prefix+'\n'+'\n'.join(function(source, name) for name in
            ('mapstrings_playerproperty', 'openbor_getplayerproperty', 'openbor_changeplayerproperty')),
        CONSTANTS=macro+'\n'+function(source, 'obor_animation_constant_value')+'\n'+constants,
        CONTEXTS=','.join('{%du,%d,{%s},{%s},%d}' % (row['revision'], len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties']),
            ','.join(str(int(name in row['settable'])) for name in row['properties']),
            int(row['direction_constants'])) for row in data['sources']),
        CONSTANT_NAMES=','.join(json.dumps(row['name']) for row in data['constants']),
        CONSTANT_VALUES=','.join(str(row['value']) for row in data['constants']))
    code = Path(__file__).with_name('forward_player_properties_contract.c.in').read_text()
    for key, value in values.items():
        code = code.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native player property dependency')
    return code


class ForwardPlayerPropertyTests(unittest.TestCase):
    def test_native_ordinals_getters_setters_arrays_and_direction_constants(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_PLAYER_PROPERTY_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
