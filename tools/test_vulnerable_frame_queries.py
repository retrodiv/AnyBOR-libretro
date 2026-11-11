"""Check native vulnerability queries with explicit record/extent providers.

The selected dispatch retains its native prefix and query; numeric namespace,
string cache and allocation extents are bounded services. This is not arbitrary
entity-handle authentication or complete animation lifetime acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_early_entity_namespaces import selected_dispatch
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',HERE.parent))
FIXTURE=HERE/'fixtures/vulnerable-frame-native-baseline.json'


def program(engine,profiles,*,omit_frame_bound=False):
    core=(engine/'openborscript.c').read_text(encoding='latin1')
    oracle=load_contract_fixture(FIXTURE);data=oracle['engines'][engine.name]
    getter=selected_dispatch(core,'openbor_getentityproperty',['_ep_vulnerable'])
    if omit_frame_bound:
        bound='tempint >= selected_animation->numframes ||'
        if getter.count(bound)!=1:raise ValueError('One logical frame bound required')
        getter=getter.replace(bound,'',1)
    native=rename_identifiers(getter,{'obor_allocation_size':'fixture_allocation_size'})
    original=rename_identifiers(data['getter'],{'openbor_getentityproperty':'original_query'})
    variants=list((engine/'source').rglob('ScriptVariant.c'))
    if len(variants)!=1:raise ValueError('One native variant implementation required')
    variant=variants[0].read_text(encoding='latin1')
    header=variants[0].with_suffix('.h').read_text(encoding='latin1')
    if 'obor_animation_native(' in getter:
        mapper='obor_animation_native(value,obor_profile_build)'
    elif 'obor_animation_from_native(' in getter:
        mapper='obor_animation_from_native(value)'
    else:mapper='value'
    if 'original_mapper' in data and any(p['build'] not in data['mapper_limits'] for p in profiles):
        raise ValueError('Each native mapper context requires an explicit safe-original arithmetic domain')
    context=[]
    for p in profiles:
        own=oracle['profiles'][p['build']]
        limits=data.get('mapper_limits',{}).get(p['build'],[2147483647]*3)
        context.append('{%du,%d,{%s}}'%(int(p.get('revision',p['build'].split('-')[0])),own['clear_result_on_error'],','.join(map(str,limits))))
    values=dict(CONFIG='#include "config.h"' if (engine/'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine/'openborscript.h').is_file() else 'scriptcommon.h',
        PROFILE_HEADER='#include "source/openborscript/profile_ids.h"' if 'original_mapper' in data else '',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in header else 'void',
        MAPPER_TYPE='int' if re.search(r'(?m)^int mapstrings_entityproperty\(',core) else 'void',
        MAPPER_RETURN='return 1;' if re.search(r'(?m)^int mapstrings_entityproperty\(',core) else '',
        CONVERSIONS='\n'.join(function(variant,n) for n in ['ScriptVariant_ChangeType','ScriptVariant_Clear','ScriptVariant_IntegerValue']),
        NATIVE=native,ORIGINAL=original,MAPPER=mapper,
        ORIGINAL_MAPPER='\n'.join(rename_identifiers(data.get(key,''),{
            'obor_animation_from_native':'original_animation_map',
            'obor_animation_property_from_native':'original_property_map',
            'obor_attack_from_native':'original_attack_map'}) for key in
            ['original_mapper','original_property_mapper','original_attack_mapper']),
        HAS_MAPPER=str(int('original_mapper' in data)),CONTEXTS=','.join(context))
    text=(HERE/'vulnerable_frame_queries.c.in').read_text()
    for k,v in values.items():text=text.replace('@'+k+'@',v)
    if re.search(r'@[A-Z_]+@',text):raise ValueError('Unresolved vulnerability input')
    return text


class VulnerableFrameQueryTests(unittest.TestCase):
    def test_native_values_defaults_errors_and_extents_in_available_profiles(self):
        pin=json.loads((ROOT/'src/pin.json').read_text());oracle=load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['profiles']),{p['build'] for p in pin['profiles']})
        available=0
        for entry in pin['engines']:
            engine=ROOT/'src/engines'/entry['build']
            core=(engine/'openborscript.c').read_text(encoding='latin1')
            if engine.name not in oracle['engines']:
                self.assertIsNone(re.search(r'case _(?:g)?ep_vulnerable:',core));continue
            profiles=[p for p in pin['profiles'] if p['engine']==engine.name and oracle['profiles'][p['build']]['present']]
            self.assertTrue(profiles);available+=len(profiles)
            with self.subTest(engine=engine.name):
                result=run_native(engine,program(engine,profiles))
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                value=json.loads(result.stdout)
                self.assertEqual(value['profiles'],len(profiles));self.assertEqual(value['status'],'PASS')
                self.assertGreater(value['queries'],100*len(profiles))
        self.assertEqual(available,sum(x['present'] for x in oracle['profiles'].values()))

    def test_shared_id_translators_keep_defined_results_at_integer_boundaries(self):
        pin=json.loads((ROOT/'src/pin.json').read_text());oracle=load_contract_fixture(FIXTURE)
        entry=next(e for e in pin['engines'] if 'original_mapper' in oracle['engines'].get(e['build'],{}))
        engine=ROOT/'src/engines'/entry['build'];profiles=[p for p in pin['profiles'] if p['engine']==engine.name]
        result=run_native(engine,'#define MAPPER_ONLY 1\n'+program(engine,profiles))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['status'],'PASS')
        self.assertEqual(value['profiles'],len(profiles));self.assertGreater(value['queries'],100*len(profiles))

    def test_spare_storage_does_not_extend_the_declared_frame_range(self):
        pin=json.loads((ROOT/'src/pin.json').read_text());oracle=load_contract_fixture(FIXTURE)
        entry=next(e for e in pin['engines'] if e['build'] in oracle['engines'])
        engine=ROOT/'src/engines'/entry['build']
        profile=next(p for p in pin['profiles'] if p['engine']==engine.name and oracle['profiles'][p['build']]['present'])
        result=run_native(engine,'#define ENDPOINT_ONLY 1\n'+program(engine,[profile],omit_frame_bound=True))
        self.assertNotEqual(result.returncode,0);self.assertIn('result.vt==VT_EMPTY',result.stderr)
        self.assertNotIn('runtime error:',result.stderr);self.assertNotIn('ERROR: AddressSanitizer',result.stderr)


if __name__=='__main__':unittest.main()
