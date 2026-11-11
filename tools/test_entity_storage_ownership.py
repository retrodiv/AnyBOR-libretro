"""Check native entity construction and release with bounded script services.

The retained source oracle runs on valid inputs only. Native constructor and
release bodies use real records; heap, script and variable services are explicit
providers. Allocation traces here do not establish whole-arena compatibility.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/entity-storage-native-baseline.json'


def program(engine, profiles, *, omit_release=False):
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    ctor, release = function(core, 'alloc_ent'), function(core, 'free_ent')
    baseline = load_contract_fixture(FIXTURE)['engines'][engine.name]
    owned_varlist = 'obor_varlist_register(ent->varlist);' in ctor
    expected_release = baseline['free_ent']
    if owned_varlist:
        expected_release = expected_release.replace(
            '        Varlist_Clear(e->varlist);\n        free(e->varlist);',
            '        obor_varlist_release(e->obor_varlist_owned, 1);', 1)
    if expected_release != release:
        raise ValueError('Unexpected change to native entity release')
    inline = 'defense_factors' in ctor
    varlist = 'Varlist_Init' in ctor
    modern = 'defense_allocate_object' in ctor
    if omit_release:
        call = 'free(e->defense);'
        if release.count(call) != 1:
            raise ValueError('One native defense release required for the control')
        release = release.replace(call, '(void)e->defense;', 1)
    providers = {
        'alloc_all_scripts': 'fixture_alloc_scripts',
        'clear_all_scripts': 'fixture_clear_scripts',
        'free_all_scripts': 'fixture_free_scripts',
        'obor_profile_callback_scripts': 'fixture_callback_scripts',
        'obor_colourmap_owner_release': 'fixture_colourmap_release',
        'Varlist_Init': 'fixture_varlist_init', 'Varlist_Clear': 'fixture_varlist_clear',
        'obor_varlist_register': 'fixture_varlist_register',
        'obor_varlist_release': 'fixture_varlist_release',
        'ScriptVariant_Clear': 'fixture_variant_clear',
        'free_recursive_list': 'fixture_empty_recursive_legacy',
        'recursive_damage_free_list': 'fixture_empty_recursive_modern',
    }
    helpers = ''
    diagnostic = ''
    if modern:
        helpers = '\n'.join(function(core, name) for name in (
            'defense_allocate_object', 'offense_allocate_object',
            'defense_free_object', 'offense_free_object'))
        helpers = rename_identifiers(helpers, {'borShutdown': 'fixture_stop', 'shutdown': 'fixture_stop_alias'})
        matches = re.findall(r'(?m)^(?:static\s+const\s+char\s*\*\s*E_OUT_OF_MEMORY|char\s+E_OUT_OF_MEMORY\[\])[^;]*;', core)
        if len(matches) != 1:
            raise ValueError('One native constructor diagnostic required')
        diagnostic = matches[0]
    if 'recursive_effect_free_collection(e)' in release:
        helpers += '\n'+function(core, 'recursive_effect_free_collection')
    enums = ''
    if 'OBOR_CALLBACK_FREE_ENT' in release:
        match = re.search(r'enum\s*\{\s*OBOR_CALLBACK_KILL\b[^}]+\};', core)
        if not match:
            raise ValueError('Native callback operation enum required')
        enums = match[0]
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        INLINE_SCRIPTS=str(int(inline)), HAS_VARLIST=str(int(varlist)), MODERN=str(int(modern)),
        OWNED_VARLIST=str(int(owned_varlist)),
        COLOURMAP_CHECK='CHECK(model && !model->maps_loaded);' if 'obor_colourmap_owner_release' in release else 'CHECK(!"unexpected model storage release");',
        DIRECT_COUNT='4' if varlist else ('9' if inline else '3')+'+(max_entity_vars>0)',
        CALLBACK_ENUM=enums, DIAGNOSTIC=diagnostic, HELPERS=helpers,
        ROUTINES='\n'.join([
            rename_identifiers(release, providers), rename_identifiers(ctor, providers),
            rename_identifiers(baseline['alloc_ent'], dict(providers, alloc_ent='original_alloc_ent'))]),
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'entity_storage_ownership.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return bind_named_allocation_support(text, engine, marker='@NAMED_ALLOCATION_SUPPORT@').replace('@NAMED_ALLOCATION_SUPPORT@', '')


class EntityStorageOwnershipTests(unittest.TestCase):
    def test_native_records_traces_and_partial_release_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['engines']), {e['build'] for e in pin['engines']})
        for entry in pin['engines']:
            build = entry['build']
            engine = ROOT / 'src/engines' / build
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            with self.subTest(engine=build):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['cases'], 8*len(profiles))

    def test_omitting_partial_field_release_fails_a_defined_owner_control(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3842'
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        text = '#define NEGATIVE_ONLY 1\n'+program(engine, [profile], omit_release=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('live_count()==0', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
