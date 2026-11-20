"""Check flash placement, defaults and profile-specific effect selection.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-flash-effects-contracts.json'
HIT_EFFECT_FIXTURE = FIXTURE.with_name('profile-hit-flash-and-charge.json')


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    declarations = []
    for name in ('emptyattack', 'empty_body', 'global_config'):
        match = re.search(r'(?m)^(?:const )?\w+ ' + name + r'\s*=\s*\{', core)
        if not match:
            raise ValueError('Missing native default object ' + name)
        declarations.append(core[match.start():core.index('\n};', match.end()) + 3])
    smart = re.findall(r'^[ \t]*spawn_attack_flash\([^;]+;',
                       function(core, 'smart_bomb'), re.M)
    shadow = re.findall(r'^[ \t]*shadowmethod\.flipx\s*=\s*obor_profile_build[^;]+;',
                        function(core, 'display_ents'), re.M)
    if len(smart) != 1 or len(shadow) != 1:
        raise ValueError('Expected the complete smartbomb and shadow effect expressions')
    initialization = re.findall(
        r'newchar->flash\.model_hit\s*=\s*newchar->flash\.model_block\s*=[^;]+;',
        function(core, 'init_model'))
    inheritance = re.findall(
        r'if\(newmodel->flash\.model_hit\s*<\s*0\).*?(?=if\(newmodel->dust\.fall_land)',
        function(core, 'set_model_ex'), re.S)
    if len(initialization) != 1 or len(inheritance) != 1:
        raise ValueError('Expected native model effect defaults and inheritance')
    parts = dict(
        DEFAULTS='\n'.join(declarations),
        FUNCTIONS='\n'.join(function(core, name) for name in
                             ('obor_profile_global_flash_layer_adjust',
                              'obor_profile_global_flash_layer_source',
                              'obor_profile_global_flash_z_source',
                              'attack_allocate_object', 'body_allocate_object',
                              'lcmHandleCommandSmartbomb', 'spawn_attack_flash',
                              'attack_dump_object', 'body_dump_object')),
        SMART_CALL=rename_identifiers(smart[0], {'spawn_attack_flash': 'record_smart_flash'}),
        SHADOW=shadow[0], MODEL_INITIALIZE=initialization[0], MODEL_INHERIT=inheritance[0],
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_flash_effects_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved flash effect contract input')
    return code


class ModernFlashEffectContracts(unittest.TestCase):
    def check_hit_flash_and_charge(self, physical):
        data = load_contract_fixture(HIT_EFFECT_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        attack = function(source, 'do_attack')
        gates = [match.start() for match in re.finditer(r'if\(!attack->no_flash\)', attack)]
        blocks = [braced_statement(attack[start:end], 'if(!attack->no_flash)')
                  for start, end in zip(gates, gates[1:] + [len(attack)], strict=True)]
        blocks = [block for block in blocks if 'execute_onspawn_script(flash);' in block]
        self.assertEqual(len(blocks), 4)
        values = {
            'FLASH_CASES': '\n'.join(f'case {i}: {block}\n    break;' for i, block in enumerate(blocks)),
            'CHARGE': braced_statement(attack, 'if(current_anim->energycost)'),
            'ROWS': ','.join('{%du,%d}' % (r['revision'], r['reason']) for r in rows),
        }
        template = Path(__file__).with_name('hit_flash_and_charge_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_hit_flash_and_charge(self):
        self.check_hit_flash_and_charge('4432')

    def test_6391_hit_flash_and_charge(self):
        self.check_hit_flash_and_charge('6391')

    def test_placement_defaults_inheritance_smartbomb_and_shadow(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
