"""Check historical binding APIs with allocated and embedded engine records.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement, continued_macro
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-binding-contracts.json'


def program(data, engine):
    binding = (engine / 'source/openborscript/binding.c').read_text()
    constants = (engine / 'source/openborscript/constants.c').read_text()
    index = function((engine / 'source/openborscript/index.c').read_text(), 'Script_GetStringMapFunction')
    binding_constants = re.findall(r'^\s*ICMPCONST_SINCE\(BIND_PROPERTY_\w+, 7468u\)$', constants, re.M)
    if len(binding_constants) != 12:
        raise ValueError('Expected the original binding constant family')
    core = (engine / 'openbor.c').read_text()
    initialize = function(core, 'ent_default_init')
    first_switch = re.search(r'(?m)^    switch\s*\(', initialize)
    if first_switch is None:
        raise ValueError('Expected the entity type initialization switch')
    initialize = initialize[:first_switch.start()] + '}\n'
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    parts = dict(HELPERS='\n'.join(function(binding, name) for name in
                                  ('mapstrings_bind_property', 'obor_profile_bind_get_property_map',
                                   'obor_profile_get_bind_property',
                                   'obor_profile_set_bind_property')),
                 ENTRIES='\n'.join(function(binding, name) for name in
                                   ('openbor_get_bind_property', 'openbor_set_bind_property',
                                    'openbor_update_bind')),
                 VARIANTS='\n'.join(function(variants, name) for name in
                                    ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                     'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
                 COMMON='\n'.join(function(common, name) for name in
                                  ('property_access_get_member', 'property_access_set_member')),
                 SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
                 MAPPER_ROUTE=braced_statement(index, 'if (obor_profile_build < 7468u &&'),
                 CONSTANT_SUPPORT=function(constants, 'obor_profile_property_constant') + '\n' +
                     continued_macro(constants, 'ICMPCONST_SINCE'),
                 BIND_CONSTANTS='\n'.join(binding_constants),
                 ALLOCATE=function(core, 'bind_allocate_object'), INITIALIZE=initialize,
                 PROFILES=','.join('{' + str(row['revision']) + 'u,' +
                                   str(row['signed_points']) + '}' for row in data['sources']),
                 CASES=',\n'.join('{' + ','.join(str(case[field]) for field in
                     data['case_fields']) + '}' for case in data['cases']))
    code = Path(__file__).with_name('modern_binding_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved binding contract input')
    return code


class ModernBindingContracts(unittest.TestCase):
    def test_binding_vertical_argument_uses_original_axis_selection(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        code = r'''
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static entity actor, target;
static unsigned adjustments;

void adjust_bind(entity *value)
{
    assert(value == &actor && value->binding.target == &target);
    ++adjustments;
}

@INTEGER@
@BIND@

int main(void)
{
    static const uint32_t builds[] = {7369, 7390, 7391, 7420, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        ScriptVariant ent = {.vt = VT_PTR, .ptrVal = &actor};
        ScriptVariant other = {.vt = VT_PTR, .ptrVal = &target};
        ScriptVariant x = {.vt = VT_INTEGER, .lVal = 3};
        ScriptVariant z = {.vt = VT_INTEGER, .lVal = -5};
        ScriptVariant y = {.vt = VT_INTEGER, .lVal = 7};
        ScriptVariant *args[] = {&ent, &other, &x, &z, &y};
        ScriptVariant result = {.vt = VT_EMPTY}, *out = &result;
        const e_bind_config lateral = BIND_CONFIG_AXIS_X_TARGET | BIND_CONFIG_AXIS_Z_TARGET;
        const e_bind_config axes = builds[i] < 7391u ? BIND_CONFIG_AXIS_Y_TARGET
                                                    : (lateral | BIND_CONFIG_AXIS_Y_TARGET);
        adjustments = 0;
        assert(openbor_bindentity(args, &out, 5) == S_OK && out == NULL && adjustments == 1);
        assert(actor.binding.config == axes);
        assert(actor.binding.offset.x == 3 && actor.binding.offset.z == -5 && actor.binding.offset.y == 7);
        y.vt = VT_EMPTY;
        assert(openbor_bindentity(args, &out, 5) == S_OK && adjustments == 2 && actor.binding.config == lateral);
    }
    return 0;
}
'''
        code = (code.replace('@INTEGER@', function(variant, 'ScriptVariant_IntegerValue'))
                    .replace('@BIND@', function(source, 'openbor_bindentity')))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_binding_position_uses_original_destination(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = function((engine / 'openbor.c').read_text(), 'adjust_bind')
        adjustment = source.split('acting_entity->direction = direction_get_adjustment_result(', 1)[1]
        position_updates = adjustment.split('\n', 1)[1].split('#undef ADJUST_BIND_SET_ANIM_RESETABLE', 1)[0]
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;

static void place(entity *acting_entity)
{
@POSITION_UPDATES@
}

static void check_position(const entity *object, float x, float y, float z)
{
    if(object->position.x != x || object->position.y != y || object->position.z != z)
    {
        fprintf(stderr, "Unexpected binding position for profile %u\n", obor_profile_build);
        abort();
    }
}

static void check_placement(e_bind_config config, e_direction direction,
                            float expected_x, float expected_y, float expected_z)
{
    entity actor = {0}, target = {0};
    actor.position = (s_axis_principal_float){.x = 44, .y = 55, .z = 66};
    target.position = (s_axis_principal_float){.x = 10, .y = 20, .z = 30};
    target.direction = direction;
    actor.binding.config = config;
    actor.binding.offset = (s_axis_principal_int){.x = 1, .y = 2, .z = 3};
    actor.binding.target = &target;

    place(&actor);

    if(config == 0)
    {
        check_position(&actor, 44, 55, 66);
        check_position(&target, 10, 20, 30);
    }
    else if(obor_profile_build < 7391u)
    {
        check_position(&actor, 44, 55, 66);
        check_position(&target, expected_x, expected_y, expected_z);
    }
    else
    {
        check_position(&actor, expected_x, expected_y, expected_z);
        check_position(&target, 10, 20, 30);
    }
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7390, 7391, 7420, 7530, 7533, 7555};
    const e_bind_config relative = BIND_CONFIG_AXIS_X_TARGET |
                                   BIND_CONFIG_AXIS_Y_TARGET | BIND_CONFIG_AXIS_Z_TARGET;
    const e_bind_config absolute = BIND_CONFIG_AXIS_X_LEVEL |
                                   BIND_CONFIG_AXIS_Y_LEVEL | BIND_CONFIG_AXIS_Z_LEVEL;
    for(size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        check_placement(relative, DIRECTION_LEFT, 9, 22, 33);
        check_placement(relative, DIRECTION_RIGHT, 11, 22, 33);
        check_placement(absolute, DIRECTION_LEFT, 1, 2, 3);
        check_placement(0, DIRECTION_RIGHT, 0, 0, 0);
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@POSITION_UPDATES@', position_updates),
                                       {'engine': '7533'}, engine_source=engine), '')

    def test_binding_animation_and_direction_at_original_boundaries(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        constants = (engine / 'source/openborscript/constants.c').read_text()
        chain = re.findall(r'^\s*ICMPCONST(?:_SINCE)?\(DIRECTION_ADJUST_.*\)$', constants, re.M)
        self.assertEqual(len(chain), 7)
        parts = {
            'ADJUST_BIND': function(core, 'adjust_bind'),
            'PARSE_DIRECTION': function(core, 'direction_get_adjustment_from_argument'),
            'RESOLVE_DIRECTION': function(core, 'direction_get_adjustment_result'),
            'ATTACK_DIRECTION': '\n'.join(function(core, name) for name in (
                'obor_profile_pain_flags', 'obor_profile_static_move_flags', 'checkdamageflip')),
            'CONSTANT_MACROS': '\n'.join(continued_macro(constants, name)
                                         for name in ('ICMPCONST', 'ICMPCONST_SINCE')),
            'CONSTANT_CHAIN': '\n'.join(chain),
        }
        code = Path(__file__).with_name('modern_binding_direction_contract.c.in').read_text()
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_binding_values_producers_admission_returns_and_argument_limits(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        observed = native_output(program(data, engine), data, engine_source=engine)
        self.assertEqual(json.loads(observed), expected)


if __name__ == '__main__':
    unittest.main()
