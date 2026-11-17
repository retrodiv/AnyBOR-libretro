"""Execute native entity namespace and historical property consumers.

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
from test_historical_player import function, rename_identifiers, switch_cases
import test_forward_animation_properties as animation

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-entity-properties-contracts.json'


def program(data, engine):
    """Reuse bounded owner/storage providers; execute the native entity route."""
    source = (engine / 'openborscript.c').read_text()
    text = animation.program(load_contract_fixture(animation.FIXTURE), engine)
    text = text.replace('int main(void){', 'static int animation_contract_main(void){')
    symbols = {'unselected_openbor_getentityproperty': 'entity_query',
               'unselected_mapstrings_entityproperty': 'mapstrings_entityproperty'}
    for name in symbols:
        stub = 'static void ' + name + '(void){}'
        if text.count(stub) != 1:
            raise ValueError('One native entity registry reference required')
        text = text.replace(stub, '')
    text = rename_identifiers(text, symbols)
    text = text.replace('List theFunctionList;',
        'static HRESULT entity_query(ScriptVariant **,ScriptVariant **,int);\n'
        'int mapstrings_entityproperty(ScriptVariant **,int);\nList theFunctionList;')
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    selected = ['_ep_animation', '_ep_attack', '_ep_spritea', '_ep_aggression', '_ep_health',
                'obor_forward_ep_animation_handle', 'obor_forward_ep_attack_x',
                'obor_forward_ep_attack_y', 'obor_forward_ep_attack_width',
                'obor_forward_ep_attack_height', 'obor_forward_ep_attack_z_in',
                'obor_forward_ep_attack_z_out']
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){\n' +
              ''.join('case ' + name + ':' + cases[name]['body'] for name in selected) +
              'default:' + cases['default']['body'] + '}\nreturn S_OK;\n}\n')
    getter = rename_identifiers(getter, {'openbor_getentityproperty': 'entity_query'})
    namespace = source[source.index('enum _axis_enum'):source.index('typedef enum animationprop_enum')]
    helpers = source[source.index('enum obor_forward_entityproperty_enum'):
                     source.index('int mapstrings_entityproperty(')]
    rows = []
    for row in data['sources']:
        rows.append('{%d,%d,{%s},%d,%d,%d,%d,%d,%s,%s}' % (
            row['revision'], len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties']),
            row['coordinates'], row['legacy_attack'], row['current_animation'], row['model_animation'],
            row['sprite_offsets'],
            '{' + ','.join(json.dumps(error) for error in row['coordinate_errors']) + '}',
            json.dumps(row['get_reverse'])))
    template = Path(__file__).with_name('forward_entity_properties_contract.c.in').read_text()
    values = dict(NAMESPACE=namespace, HELPERS=helpers,
        MAPPER=function(source, 'mapstrings_entityproperty'), GETTER=getter,
        NAME_READER=function(source, 'obor_script_sprite_name_readable'), CONTEXTS=','.join(rows))
    for key, value in values.items():
        template = template.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', template):
        raise ValueError('Unresolved native entity property input')
    return text + '\n' + template


class ForwardEntityPropertyTests(unittest.TestCase):
    def test_native_namespace_and_consumed_entity_property_routes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_ENTITY_PROPERTIES_ENGINE', ROOT / 'src/engines' / data['engine']))
        raw = native_output(program(data, engine), data, engine_source=engine)
        self.assertEqual([json.loads(line) for line in raw.splitlines()],
                         [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
