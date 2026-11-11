"""Check legacy attack queries with native records and variant conversions.

Numeric entity dispatch and unused string services are bounded providers. The
attack namespaces, selected getter and animation mapping retain native code.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_early_entity_namespaces import namespace_descriptor, selected_dispatch
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, remove_frame_guard=False):
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    enum = re.search(r'enum\s+gep_attack_enum\s*\{[^{}]+\}\s*;', source)
    if enum is None:
        raise ValueError('Native legacy attack selector enum required')
    outer = '_gep_attack' if engine.name == '3400' else '_ep_attack'
    prefix = '_gep_attack_' if engine.name in ('3400', '3741') else '_ep_attack_'
    getter = selected_dispatch(source, 'openbor_getentityproperty', [outer])
    if remove_frame_guard:
        guard = 'tempint >= ent->modeldata.animation[i]->numframes ||'
        if getter.count(guard) != 1:
            raise ValueError('One native logical frame guard required')
        getter = getter.replace(guard, '', 1)
    namespaces = ''
    if engine.name == '3400':
        first = source.index('/* Source-owned attack property namespaces. */')
        last = source.index('/* End source-owned attack property namespaces. */', first)
        namespaces = namespace_descriptor(source, 'obor_property_namespace')+'\n'+source[first:last]
        ordinal = '''const obor_property_namespace *space=obor_get_attack_namespace();
 for(int i=0;i<space->count;++i){if(space->ids[i]==id)return i;}abort();'''
    elif engine.name == '3842':
        namespaces = function(source, 'obor_attack_property_native')
        ordinal = 'for(int i=0;i<128;++i){if(obor_attack_property_native(i)==id)return i;}abort();'
    else:
        ordinal = 'return id;'
    axis = re.search(r'enum\s+_axis_enum\s*\{[^{}]+\}\s*;', source)
    values = dict(ENUM=enum[0], NAMESPACES=namespaces, ORDINAL=ordinal,
                  PREFIX_DEPENDENCY='enum {_gep_defense=2,_gep_the_end=3};' if engine.name == '3400' else
                      'enum {_ep_defense=2,_ep_the_end=3};',
                  AXIS=axis[0] if engine.name == '4086' and axis else '', GETTER=getter,
                  OUTER=outer, FORCE=prefix+'force', COORDS=prefix+'coords', DROPV=prefix+'dropv',
                  MAPPER_TYPE='int' if engine.name == '4086' else 'void',
                  MAPPER_RETURN='return 1;' if engine.name == '4086' else '',
                  POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in
                      (engine / 'source/scriptlib/ScriptVariant.h').read_text() else 'void',
                  CONVERSIONS='\n'.join(function(variant, name) for name in
                      ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']),
                  ANIMATION_ZERO='obor_animation_public(0,obor_profile_build)' if engine.name == '4086' else '0',
                  STRUCT_DROPV='1' if engine.name == '4086' else '0',
                  COORDINATE_LIMIT='(obor_profile_build<3729?5:6)' if engine.name == '3741' else
                      '5' if engine.name == '3400' else '6',
                  INITIALIZE_DROPV='attack.dropv.y=1.25;attack.dropv.x=2.5;attack.dropv.z=3.75;' if engine.name == '4086' else
                      'attack.dropv[0]=1.25;attack.dropv[1]=2.5;attack.dropv[2]=3.75;',
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                                    for p in profiles))
    text = (HERE / 'attack_query_bounds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved attack contract dependency')
    return text


class AttackQueryBoundsTests(unittest.TestCase):
    def test_legacy_native_arguments_frames_and_vectors_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for name in ('3400', '3741', '3842', '4086'):
            engine = ROOT / 'src/engines' / name
            profiles = [p for p in pin['profiles'] if p['engine'] == name]
            with self.subTest(engine=name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['queries'], 50*len(profiles))

    def test_inclusive_frame_endpoint_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3400'
        profile = next(p for p in pin['profiles'] if p['engine'] == '3400')
        text = program(engine, [profile], remove_frame_guard=True)
        # Only the endpoint case runs in this control. Physical spare backing
        # makes the missing logical bound an assertion, independent of a crash.
        text = '#define ENDPOINT_ONLY 1\n'+text
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('result.vt==VT_EMPTY', result.stderr)


if __name__ == '__main__':
    unittest.main()
