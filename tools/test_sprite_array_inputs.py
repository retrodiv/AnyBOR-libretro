"""Check sprite-array bounds and stored names with native record types.

Callbacks retain their native prologues and sprite-array cases. Numeric property
mapping, the string cache and allocation extents are bounded providers. Native
filename copies retain shared buffers/nodes. Full loading is a separate control.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_early_entity_namespaces import selected_dispatch
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles):
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    enums = '\n'.join(m[0] for m in re.finditer(r'enum\s+\w+\s*\{[^{}]+\}\s*;', source)
                      if any(s in m[0] for s in ('_ep_spritea', '_gep_spritea', '_cep_spritea')))
    if not enums:
        raise ValueError('Native sprite-array selectors required')
    get_label = '_gep_spritea' if engine.name == '3400' else '_ep_spritea'
    set_label = '_cep_spritea' if engine.name == '3400' else '_ep_spritea'
    flat = engine.name == '3400'
    old_offsets = flat or engine.name == '3741'
    headers = '\n'.join(p.read_text(encoding='latin1') for p in
        [engine / 'openborscript.h', engine / 'source/openborscript/config.h'] if p.is_file())
    mapper = re.search(r'(void|int)\s+mapstrings_entityproperty\s*\(', headers)
    mapper_type = mapper[1] if mapper else 'void'
    values = dict(MAPPER_TYPE=mapper_type, MAPPER_RETURN='return 1;' if mapper_type == 'int' else '', CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        PROFILE_HEADER='#include "source/openborscript/profile_ids.h"' if engine.name == '6391' else '',
        ANIMATION_ZERO='obor_animation_public(0,obor_profile_build)' if engine.name == '4086' else 'obor_animation_to_native(0)' if engine.name == '6391' else '0',
        ENUMS=enums,
        CONVERSIONS='\n'.join(function(variant, n) for n in
            ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue')),
        HELPERS='\n'.join(function(source, n) for n in
            ['obor_script_sprite_name_readable', 'obor_script_sprite_name_store'] +
            (['obor_script_sprite_filename'] if engine.name == '3741' else [])),
        FIXED_CACHE='1' if engine.name in ['3400', '3741', '3842'] else '0',
        REPLACES_NAME='1' if engine.name == '3741' else '0',
        GET_FILE='_gep_spritea_file' if old_offsets else '_ep_spritea_file',
        MAP_NAME='maps[0].filename' if flat else 'maps[0].node->filename',
        OTHER_NAME='maps[1].filename' if flat else 'maps[1].node->filename',
        NULL_NODE_CONTROL='' if flat else 'maps[0].node=NULL;empty_name_get();',
        GETTER=selected_dispatch(source, 'openbor_getentityproperty', [get_label]),
        SETTER=selected_dispatch(source, 'openbor_changeentityproperty', [set_label]),
        GET_PROPERTY=get_label, SET_PROPERTY=set_label,
        GET_CENTER='_gep_spritea_centerx' if old_offsets else '_ep_spritea_centerx',
        SET_CENTER='_cep_spritea_centerx' if old_offsets else '_ep_spritea_centerx',
        SET_CENTERY='_cep_spritea_centery' if old_offsets else '_ep_spritea_centery',
        SET_FILE='_cep_spritea_file' if old_offsets else '_ep_spritea_file',
        SET_OFFSETX='_cep_spritea_offsetx' if old_offsets else '_ep_spritea_offsetx',
        GET_SPRITE='_gep_spritea_sprite' if old_offsets else '_ep_spritea_sprite',
        SET_SPRITE='_cep_spritea_sprite' if old_offsets else '_ep_spritea_sprite',
        SET_OFFSETY='_cep_spritea_offsety' if old_offsets else '_ep_spritea_offsety',
        LOADED_TYPE='uint64_t' if engine.name == '8023' else 'unsigned int',
        NODE_DECL='' if flat else 'static s_sprite_list node;',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in (engine / 'source/scriptlib/ScriptVariant.h').read_text() else 'void',
        OFFSET_FIELDS='1' if old_offsets else '0',
        MAP_INIT='maps[i].sprite=&images[i];maps[i].filename=name;' if flat else
                 'maps[i].node=&node;',
        NODE_INIT='' if flat else 'node=(s_sprite_list){0};node.sprite=&images[0];node.filename=name;',
        LEGACY_INIT='maps[i].profile_sprite=&images[i];' if engine.name == '3741' else '',
        OLD_OFFSETS='1' if flat else 'obor_profile_build<3609' if engine.name == '3741' else '0',
        RETURNS_VALUE='1' if flat else 'obor_profile_build<3710' if engine.name == '3741' else '0',
        GET_X_IS_Y='1',
        SPRITE_POINTER='maps[0].sprite' if flat else
            '(obor_profile_build<3609?maps[0].profile_sprite:maps[0].node->sprite)' if engine.name == '3741' else
            'maps[0].node->sprite',
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'sprite_array_inputs.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native sprite-array dependency')
    return text


class SpriteArrayInputsTests(unittest.TestCase):
    def test_native_callbacks_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 40*len(profiles))

    def test_ignoring_name_capacity_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / pin['engines'][0]['build']
        profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
        profile = max(profiles, key=lambda p: int(p.get('revision', p['build'].split('-')[0])))
        text = program(engine, [profile])
        guard = 'if(length >= capacity) return 0;'
        self.assertEqual(text.count(guard), 1)
        result = run_native(engine, text.replace(guard, 'if(0) return 0;'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stored name changed after capacity refusal', result.stderr)

    def test_inclusive_frame_endpoint_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / pin['engines'][0]['build']
        profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
        profile = max(profiles, key=lambda p: int(p.get('revision', p['build'].split('-')[0])))
        text = program(engine, [profile])
        guard = '(arg1->lVal >= ent->modeldata.animation[arg->lVal]->numframes)'
        self.assertEqual(text.count(guard), 1)
        result = run_native(engine, text.replace(guard, guard.replace('>=', '>')))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('result.vt==VT_EMPTY', result.stderr)


if __name__ == '__main__':
    unittest.main()
