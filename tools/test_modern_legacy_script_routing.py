"""Check runtime entity-property names and legacy projectile flag targets.

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
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-legacy-script-routing-contracts.json'
SPAWN_SCRIPT_FIXTURE = FIXTURE.with_name('profile-script-spawn-entry.json')


def combat_snapshot_support(core, additional=()):
    declarations = re.search(r'(?s)typedef struct s_model_collection_snapshot\s*\{.*?\}\s*s_model_collection_snapshot;\s*'
                             r'static s_model_collection_snapshot \*model_collection_snapshots;', core)
    if declarations is None:
        raise ValueError('Expected the native model-copy collection storage')
    return '\n'.join([declarations[0], *(function(core, name) for name in (
        'obor_actor_uses_snapshot', 'obor_model_snapshot_in_use', 'obor_collect_model_snapshots', *additional))])


def program(data, engine):
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    core = (engine / 'openbor.c').read_text()
    enums = re.findall(r'(?ms)^enum[ \t]+\w+[ \t]*(?://[^\n]*)?\s*\{[^}]*^};', source)
    names = [re.search(r'static const char\s*\*\s*' + name + r'\[\]\s*=\s*\{[^}]+\};', source, re.S)
             for name in ('eplist', 'eplist_aiflag', 'eplist_edgerange')]
    default = re.search(r'(?ms)^const s_projectile projectile_default_config\s*=\s*\{.*?^};', core)
    if any(match is None for match in names) or default is None or not enums:
        raise ValueError('Complete native legacy names/enums/default required')
    shadow_index = re.search(r'(?ms)^enum\s*\{\s*OBOR_LEGACY_EP_NOSHADOW = _ep_the_end \+ 1\s*\};', source)[0]
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    historical_fields = ('_ep_nopain', '_ep_nodrop', 'OBOR_LEGACY_EP_NOSHADOW', '_ep_falldie', '_ep_nodieblink',
                         '_ep_blockback', '_ep_running', '_ep_type', '_ep_hostile', '_ep_candamage', '_ep_projectilehit',
                         '_ep_dead')
    deadlines = ('_ep_combotime', '_ep_freezetime', '_ep_invinctime', '_ep_knockdowncount', '_ep_maptime',
                 '_ep_nextanim', '_ep_nextmove', '_ep_nextthink', '_ep_pain_time', '_ep_releasetime',
                 '_ep_sealtime', '_ep_stalltime', '_ep_tosstime')
    palette_fields = ('_ep_alpha', '_ep_hmapl', '_ep_hmapu', '_ep_komap')
    air_fields = ('_ep_jumpmovex', '_ep_jumpmovez')
    getter_fields = ('_ep_a', '_ep_y', '_ep_health', '_ep_numweapons', '_ep_nextanim',
                     '_ep_maps', *palette_fields, *air_fields, *historical_fields)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){' + ''.join(
        'case ' + key + ':' + cases[key]['body'] for key in getter_fields) +
        'default:' + cases['default']['body'] + '}\nreturn S_OK;\n}\n')
    setter, mutations = switch_cases(source, 'openbor_changeentityproperty', 'propind', outermost=True)
    entity_types = re.search(r'static const int entitytypes\[\]\s*=\s*\{[^}]+\};', setter)[0]
    mutation = '\n'.join('case ' + name + ':' + mutations[name]['body']
                         for name in (*historical_fields, *deadlines, *palette_fields, *air_fields))
    target = 'propind = obor_profile_entity_native_index(varlist[1]->lVal);'
    if setter.count(target) != 1 or 'mapstrings_entityproperty(varlist, paramCount);' not in setter:
        raise ValueError('Complete native legacy entity setter required')
    shadow_draw = re.search(r'if \((obor_profile_build < 7475u \? e->modeldata\.legacy_noshadow != 1\s*'
                            r': !\(e->shadow_config_flags & SHADOW_CONFIG_DISABLED\))\)',
                            function(core, 'display_ents'))[1]
    death_accessors = ('death_config_get_falldie_from_value', 'death_config_get_nodieblink_from_value',
                       'death_config_get_value_from_falldie', 'death_config_get_value_from_nodieblink')
    parts = dict(ENUMS='\n'.join([*enums, shadow_index]), NAMES='\n'.join(match[0] for match in names),
        DEFAULT=default[0], GETTER=getter, ENTITY_MUTATIONS=mutation, ENTITY_TYPES=entity_types,
        ENTITY_DEADLINE=function(source, 'obor_script_entity_deadline'),
        AIR_CONTROL='\n'.join(function(core, f'air_control_interpret_{direction}_legacy_jumpmove_{axis}')
                              for axis in ('x', 'z') for direction in ('from', 'to')),
        SHADOW_DRAW=shadow_draw,
        DEATH_ACCESSORS='\n'.join(function(core, name) for name in death_accessors),
        VARIANTS='\n'.join(function(variant, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
            'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        MAPPER='\n'.join(function(source, name) for name in ('obor_profile_entity_native_index', 'mapstrings_entityproperty')),
        PROJECTILE=function(source, 'openbor_projectile'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(n) for n in row) + '}' for row in data['projectile_cases']))
    code = Path(__file__).with_name('modern_legacy_script_routing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved legacy routing input')
    return code


class ModernLegacyScriptRoutingContracts(unittest.TestCase):
    def test_original_script_execution_diagnostic(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openborscript.c').read_text()
        code = r'''
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>
#undef printf

uint32_t obor_profile_build;
Script *pcurrentscript;
int no_nested_script, no_cmd_compatible;
static Interpreter interpreter;
static HRESULT outcome;
static char diagnostic[192];

void Interpreter_Reset(Interpreter *value) { assert(value == &interpreter); }
HRESULT Interpreter_EvaluateImmediate(Interpreter *value)
{
    assert(value == &interpreter);
    return outcome;
}

void borShutdown(int status, char *format, ...)
{
    assert(status == 1);
    va_list arguments;
    va_start(arguments, format);
    int written = vsnprintf(diagnostic, sizeof(diagnostic), format, arguments);
    va_end(arguments);
    assert(written >= 0 && (size_t)written < sizeof(diagnostic));
}

@EXECUTE@

int main(void)
{
    static const uint32_t builds[] = {7369, 7391, 7420, 7503, 7504, 7533};
    static char context[] = "sample";
    static Script caller, script;
    memcpy(interpreter.theSymbolTable.name, "fixture", sizeof("fixture"));
    script.pinterpreter = &interpreter;
    script.comment = context;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        pcurrentscript = &caller;
        diagnostic[0] = '\0';
        outcome = S_OK;
        assert(Script_Execute(&script) == 1 && pcurrentscript == &caller && diagnostic[0] == '\0');
        outcome = E_FAIL;
        assert(Script_Execute(&script) == 0 && pcurrentscript == &caller);
        const char *expected = builds[i] < 7504u ? "There's an exception while executing script 'fixture' sample"
            : "There's an exception while executing script 'fixture' sample. Please review log to locate the exception alert(s). \n\n";
        assert(strcmp(diagnostic, expected) == 0);
    }
    return 0;
}
'''
        code = code.replace('@EXECUTE@', function(source, 'Script_Execute'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_shadow_color_and_alpha(self):
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
#undef printf

uint32_t obor_profile_build;
int shadowcolor;
e_blend_mode shadowalpha;

@INTEGER@
@SHADOW@

int main(void)
{
    static const uint32_t builds[] = {7369, 7391, 7420, 7470, 7471, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const LONG alphas[] = {-7, 0, 2, 9};
        for (size_t j = 0; j < sizeof(alphas) / sizeof(*alphas); ++j)
        {
            ScriptVariant color = {.vt = VT_INTEGER, .lVal = 12};
            ScriptVariant alpha = {.vt = VT_INTEGER, .lVal = alphas[j]};
            ScriptVariant *args[] = {&color, &alpha};
            ScriptVariant result = {.vt = VT_EMPTY}, *out = &result;
            assert(openbor_changeshadowcolor(args, &out, 2) == S_OK && out == NULL);
            assert(shadowcolor == 12 && shadowalpha == alphas[j]);
            color.lVal = -1;
            assert(openbor_changeshadowcolor(args, &out, 1) == S_OK);
            assert(shadowcolor == -1 && shadowalpha == alphas[j]);
        }
    }
    return 0;
}
'''
        code = (code.replace('@INTEGER@', function(variant, 'ScriptVariant_IntegerValue'))
                    .replace('@SHADOW@', function(source, 'openbor_changeshadowcolor')))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_legacy_defense_fields(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openborscript.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        _, readers = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
        _, writers = switch_cases(source, 'openbor_changeentityproperty', 'propind', outermost=True)
        fields = re.search(r'enum _ep_defense_enum\s*\{[^}]+\};', source)[0]
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#undef printf
#include <assert.h>

uint32_t obor_profile_build;
int max_attack_types = MAX_ATKS;

void StrCache_Collect(int index) { (void)index; abort(); }
CHAR *StrCache_Get(int index) { (void)index; abort(); }
CHAR *StrCache_GetIfPresent(int index) { (void)index; abort(); }

@VARIANTS@
@FIELDS@

static HRESULT read_defense(entity *ent, ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    LONG ltemp, ltemp2;
    switch (0)
    {
        case 0:
@READ@
    }
    return S_OK;
}

static void write_defense(entity *ent, ScriptVariant **varlist, int paramCount)
{
    LONG ltemp, ltemp2;
    DOUBLE dbltemp;
    switch (0)
    {
        case 0:
@WRITE@
    }
}

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7434, 7435, 7441, 7442, 7533};
    const struct { int selector; DOUBLE expected; } cases[] = {
        { _ep_defense_factor, 0.625 }, { _ep_defense_pain, -3 },
        { _ep_defense_knockdown, 3.25 }, { _ep_defense_blockpower, 8 },
        { _ep_defense_blockthreshold, 4 }, { _ep_defense_blockratio, 0.25 },
        { _ep_defense_blocktype, 2 },
    };
    static s_defense defenses[MAX_ATKS];
    static entity actor;
    actor.defense = defenses;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        defenses[ATK_NORMAL2] = (s_defense){.damage_max = 17, .block_damage_adjust = 5};
        ScriptVariant values[] = {
            {.vt = VT_EMPTY}, {.vt = VT_EMPTY}, {.vt = VT_INTEGER, .lVal = ATK_NORMAL2},
            {.vt = VT_DECIMAL, .dblVal = 0.625}, {.vt = VT_DECIMAL, .dblVal = -3.5},
            {.vt = VT_DECIMAL, .dblVal = 3.25}, {.vt = VT_DECIMAL, .dblVal = 8.75},
            {.vt = VT_DECIMAL, .dblVal = 4.25}, {.vt = VT_DECIMAL, .dblVal = 0.25},
            {.vt = VT_INTEGER, .lVal = 2},
        };
        ScriptVariant *args[sizeof(values) / sizeof(*values)];
        for (size_t j = 0; j < sizeof(values) / sizeof(*values); ++j)
        {
            args[j] = &values[j];
        }
        write_defense(&actor, args, sizeof(args) / sizeof(*args));
        assert(defenses[ATK_NORMAL2].damage_max == 17 && defenses[ATK_NORMAL2].block_damage_adjust == 5);
        ScriptVariant result = {.vt = VT_EMPTY};
        ScriptVariant *out = &result;
        assert(read_defense(&actor, args, &out, 3) == S_OK && result.vt == VT_DECIMAL && result.dblVal == 0.625);
        values[3].vt = VT_INTEGER;
        for (size_t j = 0; j < sizeof(cases) / sizeof(*cases); ++j)
        {
            values[3].lVal = cases[j].selector;
            assert(read_defense(&actor, args, &out, 4) == S_OK);
            assert(result.vt == VT_DECIMAL && result.dblVal == cases[j].expected);
        }
    }
    return 0;
}
'''
        methods = ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue',
                   'ScriptVariant_DecimalValue')
        code = (code.replace('@VARIANTS@', '\n'.join(function(variants, name) for name in methods))
                .replace('@FIELDS@', fields)
                .replace('@READ@', readers['_ep_defense']['body'])
                .replace('@WRITE@', writers['_ep_defense']['body']))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_drawmethod_property_entry_points(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        drawing = (engine / 'source/openborscript/drawmethod.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        code = r'''
#include <stdint.h>
#include "scriptcommon.h"
#undef printf
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
const s_drawmethod plainmethod = {0};

void StrCache_Collect(int index) { (void)index; abort(); }
CHAR *StrCache_Get(int index) { (void)index; abort(); }
CHAR *StrCache_GetIfPresent(int index) { (void)index; abort(); }

static HRESULT obor_profile_get_drawmethod_property(const ScriptVariant *const *args, ScriptVariant **out, int count)
{
    (void)args;
    (void)out;
    (void)count;
    abort();
}

static HRESULT obor_profile_set_drawmethod_property(ScriptVariant **args, ScriptVariant **out, int count)
{
    (void)args;
    (void)out;
    (void)count;
    abort();
}

@VARIANTS@
@PROPERTIES@

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7533, 7566};
    const struct { int property; LONG value; } cases[] = {
        { DRAWMETHOD_PROPERTY_ALPHA, 3 },
        { DRAWMETHOD_PROPERTY_CENTER_X, -12 },
        { DRAWMETHOD_PROPERTY_ENABLE, 1 },
        { DRAWMETHOD_PROPERTY_FLIP_X, 1 },
        { DRAWMETHOD_PROPERTY_ROTATE, 90 },
        { DRAWMETHOD_PROPERTY_SCALE_X, 427 },
    };

    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        s_drawmethod method = {0};
        ScriptVariant handle = {.vt = VT_PTR, .ptrVal = &method};
        ScriptVariant property = {.vt = VT_INTEGER};
        ScriptVariant value = {.vt = VT_INTEGER};
        ScriptVariant *args[] = {&handle, &property, &value};
        for (size_t j = 0; j < sizeof(cases) / sizeof(*cases); ++j)
        {
            property.lVal = cases[j].property;
            value.lVal = cases[j].value;
            ScriptVariant result = {0};
            ScriptVariant *out = &result;
            assert(openbor_set_drawmethod_property(args, &out, 3) == S_OK && out == &result);
            assert(result.vt == VT_EMPTY);
            assert(openbor_get_drawmethod_property(args, &out, 2) == S_OK && out == &result);
            assert(result.vt == VT_INTEGER && result.lVal == cases[j].value);
        }
        assert(method.alpha == 3 && method.centerx == -12 && method.flag == 1);
        assert(method.flipx == 1 && method.rotate == 90 && method.scalex == 427);
    }
    return 0;
}
'''
        conversions = ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')
        accessors = ('openbor_get_drawmethod_property', 'openbor_set_drawmethod_property')
        code = code.replace('@VARIANTS@', '\n'.join(function(variants, name) for name in conversions))
        code = code.replace('@PROPERTIES@', '\n'.join(function(drawing, name) for name in accessors))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine,
                                      extra_cflags=('-Wno-error=ignored-qualifiers',
                                                    '-Wno-error=implicit-fallthrough')), '')

    def test_original_animation_schedule_and_infinite_delay(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        load = function(core, 'load_cached_model')
        command = re.search(r'(?ms)^            case CMD_MODEL_DELAY:.*?(?=^            case CMD_MODEL_)', load)[0]
        attack = function(core, 'do_attack')
        attacker = braced_statement(attack, 'if(attacking_entity->pausetime < _time')
        end = attack.index(attacker) + len(attacker)
        defender = attack[end:attack.index(' // So anything that auto moves will pause', end)]
        throw_wait = function(core, 'common_throw_wait')
        release = re.search(r'(?m)^\s*self->releasetime\s*(?:\+=|=)[^;]+;', throw_wait)[0]
        player_think = function(core, 'player_think')
        release_attack = braced_statement(player_think, 'if((acting_player->releasekeys & FLAG_ATTACK))')
        charge = braced_statement(release_attack, 'if(acting_entity->stalltime && notinair &&').partition('{')[0]
        animate = function(core, 'update_animation')
        advance = re.search(r'(?ms)^    (if\(\(self->nextanim == _time.*?)(?=^    \{)', animate)[1]
        hold = re.compile(r'if \(obor_animation_can_reschedule\(other->nextanim\)\)\s*'
                          r'(?:\{\s*other->nextanim = [^;]+;\s*\})\s*other->nextthink = [^;]+;')
        weapon, projectile = hold.findall(function(core, 'common_pickupitem'))
        identified, = hold.findall(function(core, 'didfind_item'))
        parts = {
            'HELPERS': '\n'.join(function(core, name) for name in
                                  ('isNumeric', 'getValidInt', 'ParseArgs', 'obor_animation_can_reschedule',
                                   'obor_entity_deadline_value', 'obor_extend_entity_deadline',
                                   'obor_advance_frozen_deadline', 'obor_extend_frozen_entity_deadlines',
                                   'diff', 'inair')),
            'MODEL_COMMAND': command,
            'FRAME': braced_statement(function(core, 'update_frame'),
                                      'if (obor_animation_can_reschedule(self->nextanim))'),
            'MODEL': braced_statement(function(core, 'ent_set_model'),
                                      'if (obor_animation_can_reschedule(ent->nextanim))'),
            'ATTACKER': attacker,
            'DEFENDER': defender,
            'RELEASE': release,
            'CHARGE_READY': charge,
            'ADVANCE': advance,
            'WEAPON': weapon,
            'PROJECTILE': projectile,
            'IDENTIFIED': identified,
        }
        template = Path(__file__).with_name('legacy_animation_schedule_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        self.assertEqual(native_output(code, data, engine_source=engine,
                                       extra_cflags=('-Wno-implicit-fallthrough',)), 'PASS\n')

    def test_original_shadow_settings_and_drawing(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        script = (engine / 'openborscript.c').read_text(encoding='latin1')
        model = function(core, 'load_cached_model')
        command = re.compile(r'(?ms)^            case CMD_MODEL_(?:SHADOW|GFXSHADOW|AIRONLY|FSHADOW):.*?(?=^            case CMD_MODEL_)')
        model_commands = command.findall(model)
        self.assertEqual(len(model_commands), 4)
        properties = ('gfxshadow', 'shadowbase')
        methods = ('isNumeric', 'getValidInt', 'ParseArgs', 'shadow_get_config_from_legacy_aironly',
                   'shadow_get_config_from_legacy_gfxshadow', 'shadow_get_config_from_legacy_shadowbase',
                   'obor_display_shadow_flags')
        parts = {
            'METHODS': '\n'.join(function(core, name) for name in methods),
            'MODEL_COMMANDS': '\n'.join(model_commands),
            'DRAW': braced_statement(function(core, 'display_ents'),
                                      'if (obor_profile_build < 7475u ? e->modeldata.legacy_noshadow != 1'),
        }
        for access, name in (('READ', 'openbor_getentityproperty'), ('WRITE', 'openbor_changeentityproperty')):
            body = function(script, name)
            parts[access] = '\n'.join(braced_statement(body, 'case _ep_' + prop + ':') for prop in properties)
        template = Path(__file__).with_name('legacy_shadow_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        self.assertEqual(native_output(code, data, engine_source=engine,
                                       extra_cflags=('-Wno-implicit-fallthrough',)), 'PASS\n')

    def test_enhanced_delay_uses_original_mode_and_caps(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        scripts = (engine / 'openborscript.c').read_text()
        defaults = braced_statement(function(core, 'init_model'),
            'if (obor_profile_build >= 7495u)\n    {\n        newchar->edelay')
        model_loader = function(core, 'load_cached_model')
        first = model_loader.index('case CMD_MODEL_EDELAY:') + len('case CMD_MODEL_EDELAY:')
        command = model_loader[first:model_loader.index('case CMD_MODEL_ENHANCED_DELAY_CAP_MAX:', first)]
        _, readers = switch_cases(scripts, 'openbor_getentityproperty', 'propind', outermost=True)
        _, writers = switch_cases(scripts, 'openbor_changeentityproperty', 'propind', outermost=True)
        selectors = re.search(r'(?ms)^enum gep_edelay_enum\s*\{[^}]+\};', scripts)
        self.assertIsNotNone(selectors)
        parts = dict(DEFAULTS=defaults, MODEL=command, READ=readers['_ep_edelay']['body'],
                     WRITE=writers['_ep_edelay']['body'], SELECTORS=selectors[0],
                     CALCULATION='\n'.join(function(core, name) for name in (
                         'obor_legacy_delay_integer', 'calculate_edelay')))
        code = Path(__file__).with_name('modern_legacy_delay_contract.c.in').read_text()
        for key, fragment in parts.items():
            code = code.replace('@' + key + '@', fragment)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_typed_entity_property_selector_boundaries(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        script = engine / 'source/openborscript'
        constants = (script / 'constants.c').read_text()
        entity = (script / 'entity.c').read_text()
        index = (script / 'index.c').read_text()
        members = (script / 'common_property.c').read_text()
        source = function(constants, 'mapstrings_transconst')
        properties = r'(?:ENTITY|MODEL|ICON|STATUS_DIAL|SPAWN_HUD|COLORSET)_PROPERTY_'
        exposed = re.findall(r'^        ICMPCONST_(?:SINCE|RANGE|ALIAS_RANGE)\((?:' + properties +
                             r'|DEATH_STATE_|EXPLODE_|QUAKE_CONFIG_).*\)[ \t]*$', source, re.M)
        exposed += re.findall(r'^        ICMPCONST_PROFILE_NAME\((?:ATTACK|COLLISION_COORDINATES|LEVEL|SET)'
                              r'_PROP_.*\)$', source, re.M)
        _, level_cases = switch_cases((script / 'level.c').read_text(), 'openbor_get_level_property',
                                      'property', outermost=True)
        parts = {
            'CONSTANT_HELPER': function(constants, 'obor_profile_property_constant'),
            'CONSTANT_MACROS': '\n'.join(continued_macro(constants, name)
                                        for name in ('ICMPCONST_SINCE', 'ICMPCONST_RANGE', 'ICMPCONST_ALIAS_RANGE',
                                                     'ICMPCONST_PROFILE_NAME')),
            'CONSTANT_NAMES': '\n'.join(exposed),
            'FUNCTION_MAPPER': braced_statement(index, 'else if (obor_profile_build < 7445u &&'),
            'RETIRED_LEVEL_PROPERTY': level_cases['LEVEL_PROPERTY_PALETTE_BLENDING_COLLECTION']['body'],
            'ROUTINES': '\n'.join([
                combat_snapshot_support(core, (
                    'obor_is_combat_collection', 'obor_entity_set_combat_collection', 'obor_capture_combat_collections')),
                function((engine / 'source/utils.c').read_text(), 'searchList'),
                '#define property_access_dump_members native_property_dump\n' +
                function(members, 'property_access_dump_members') + '\n#undef property_access_dump_members',
                function(members, 'property_access_get_member'),
                function(members, 'property_access_set_member'),
                *(function(entity, name) for name in (
                    'obor_profile_entity_property_end', 'mapstrings_entity_property',
                    'obor_entity_property_native_id', 'entity_get_property_map', 'obor_legacy_entity_scalar',
                    'obor_report_legacy_entity_property_usage', 'openbor_get_entity_property',
                    'openbor_set_entity_property', 'openbor_get_attack_id_value', 'openbor_set_attack_id_value')),
            ]),
        }
        code = Path(__file__).with_name('modern_typed_entity_routing_contract.c.in').read_text()
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_faction_properties_and_admission(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        script = engine / 'source/openborscript'
        constants = (script / 'constants.c').read_text()
        mapper = function(constants, 'mapstrings_transconst')
        exposed = re.findall(r'^        ICMPCONST_SINCE\((?:FACTION_\w+|(?:MODEL|ENTITY)_PROPERTY_FACTION), \d+\)$',
                             mapper, re.M)
        self.assertEqual(len(exposed), 46)
        routines = '\n'.join(function((script / file).read_text(), name)
                             for file, name in (
                                 ('faction.c', 'openbor_get_faction_property'),
                                 ('faction.c', 'openbor_set_faction_property'),
                                 ('entity.c', 'obor_profile_entity_property_end'),
                                 ('entity.c', 'obor_entity_property_native_id'),
                                 ('entity.c', 'entity_get_property_map'),
                                 ('model.c', 'obor_profile_model_property_end'),
                                 ('model.c', 'model_get_property_map'),
                             ))
        parts = {
            'CONSTANT_HELPER': function(constants, 'obor_profile_property_constant'),
            'CONSTANT_MACRO': continued_macro(constants, 'ICMPCONST_SINCE'),
            'CONSTANT_NAMES': '\n'.join(exposed),
            'ROUTINES': routines,
            'REGISTRATION': braced_statement((script / 'index.c').read_text(), 'if (obor_profile_build >= 7445u)'),
        }
        code = Path(__file__).with_name('modern_legacy_faction_contract.c.in').read_text()
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_aimove_script_values_and_movement(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openborscript.c').read_text()
        _, reads = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
        _, writes = switch_cases(source, 'openbor_changeentityproperty', 'propind', outermost=True)
        constants = (engine / 'source/openborscript/constants.c').read_text()
        mapper = function(constants, 'mapstrings_transconst')
        start = mapper.index('ICMPCONST_SINCE(AIMOVE_SPECIAL_DEFAULT')
        end = mapper.index('/* Air control options. */', start)
        move = function((engine / 'openbor.c').read_text(), 'common_move')
        start_move = move.index('if(acting_entity->modeldata.aimove ==')
        no_move = braced_statement(move, 'if(aimove & AIMOVE1_NOMOVE)')
        end_move = move.index('else', move.index(no_move.splitlines()[0], start_move) + len(no_move))
        default_move = braced_statement(move, 'if (!aimove && target)')
        code = r'''
#include <stdint.h>
#include <strings.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>
#undef stricmp
#define stricmp strcasecmp

uint32_t obor_profile_build;

void ScriptVariant_ChangeType(ScriptVariant *var, VARTYPE type) { var->vt = type; }
HRESULT ScriptVariant_IntegerValue(ScriptVariant *value, LONG *result)
{
    *result = value->lVal;
    return S_OK;
}

@HELPER@
@MACROS@

static int lookup(const char *constname, LONG *result)
{
    ScriptVariant v = {0};
    if (0) {}
    @CONSTANTS@
    else { return 0; }
    *result = v.lVal;
    return 1;
}

static uint32_t get_aimove(entity *ent)
{
    ScriptVariant value = {0};
    ScriptVariant *output = &value;
    ScriptVariant **pretvar = &output;
    do { @READ@ } while (0);
    assert(value.vt == VT_INTEGER);
    return (uint32_t)value.lVal;
}

static void set_aimove(entity *ent, uint32_t bits)
{
    LONG ltemp;
    ScriptVariant value = {.vt = VT_INTEGER, .lVal = (LONG)bits};
    ScriptVariant *varlist[] = {NULL, NULL, &value};
    do { @WRITE@ } while (0);
}

int biker_move(void) { return 1; }
int arrow_move(entity *actor) { return 2; }
int star_move(void) { return 3; }
int bomb_move(entity *actor) { return 4; }

static int movement(entity *acting_entity)
{
    int aimove;
    @MOVEMENT@
    return 5;
}

static int wander_calls;
int common_try_wander(entity *target, int dox, int doz)
{
    assert(target && dox == 1 && doz == 1);
    return ++wander_calls;
}

static int use_default_movement(entity *target)
{
    entity *ent = NULL;
    int aimove = target->modeldata.aimove & MASK_AIMOVE1;
    wander_calls = 0;
    @DEFAULT_MOVE@
    assert((ent != NULL) == (wander_calls == 1));
    return wander_calls;
}

int main(void)
{
    static entity actor;
    const unsigned builds[] = {7369, 7381, 7382, 7391, 7420, 7431, 7432, 7533};
    const char *names[] = {"AIMOVE1_CHASE", "AIMOVE1_CHASEZ", "AIMOVE1_CHASEX",
        "AIMOVE1_AVOID", "AIMOVE1_AVOIDZ", "AIMOVE1_AVOIDX", "AIMOVE1_WANDER",
        "AIMOVE1_BIKER", "AIMOVE1_ARROW", "AIMOVE1_STAR", "AIMOVE1_BOMB", "AIMOVE1_NOMOVE"};
    const int moves[] = {5, 5, 5, 5, 5, 5, 5, 1, 2, 3, 4, 0};
    const uint32_t upper[] = {0u, 0x10000u, 0x20000u, 0x80000000u, 0xffff0000u};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7382u;
        LONG value;
        assert(lookup("AIMOVE1_NORMAL", &value) && value == (legacy ? 0 : 1));
        assert(lookup("AIMOVE2_NORMAL", &value) && value == 0);
        assert(lookup("AIMOVE2_IGNOREHOLES", &value) && value == 0x10000);
        assert(lookup("AIMOVE2_NOTARGETIDLE", &value) && value == 0x20000);
        assert(!lookup("AIMOVE1_NONE", &value));
        assert(lookup("AIMOVE_SPECIAL_DEFAULT", &value) == (builds[i] >= 7432u));
        for (size_t j = 0; j < sizeof(names) / sizeof(*names); ++j)
        {
            assert(lookup(names[j], &value));
            assert(value == (1 << (j + !legacy)));
            set_aimove(&actor, value | 0x20000u);
            assert(get_aimove(&actor) == (value | 0x20000u));
            assert(movement(&actor) == moves[j]);
        }
        for (size_t j = 0; j < sizeof(upper) / sizeof(*upper); ++j)
        {
            for (uint32_t primary = 0; primary < 0x10000u; ++primary)
            {
                uint32_t requested = upper[j] | primary;
                set_aimove(&actor, requested);
                assert(get_aimove(&actor) == requested);
            }
        }
        const uint32_t none = (uint32_t)obor_unspecified_aimove();
        actor.modeldata.aimove = obor_unspecified_aimove();
        assert(get_aimove(&actor) == (legacy ? UINT32_MAX : 0));
        set_aimove(&actor, 0);
        assert(movement(&actor) == 5);
        assert(use_default_movement(&actor) == 1);
        set_aimove(&actor, 0x20000u);
        assert(use_default_movement(&actor) == 1);
        set_aimove(&actor, 0x8000u);
        assert(movement(&actor) == 5);
        assert(use_default_movement(&actor) == 0);
        set_aimove(&actor, UINT32_MAX);
        assert(movement(&actor) == 0);
        assert(none == (legacy ? UINT32_MAX : 0));
    }
    return 0;
}
'''
        parts = {'HELPER': function(constants, 'obor_profile_property_constant'),
                 'MACROS': '\n'.join(continued_macro(constants, name)
                                     for name in ('ICMPCONST', 'ICMPCONST_SINCE')),
                 'CONSTANTS': mapper[start:end], 'READ': reads['_ep_aimove']['body'],
                 'WRITE': writes['_ep_aimove']['body'], 'MOVEMENT': move[start_move:end_move],
                 'DEFAULT_MOVE': default_move}
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_entity_type_constants(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'source/openborscript/constants.c').read_text()
        mapper = function(source, 'mapstrings_transconst')
        start = mapper.index('/* Model/Entity types. */')
        end = mapper.index('// Level sets', start)
        macros = ('ICMPCONST', 'ICMPCONST_SINCE')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef stricmp
#define stricmp strcasecmp

uint32_t obor_profile_build;
@HELPER@
@MACROS@

static int lookup(const char *constname, uint32_t *value)
{
    ScriptVariant v = {0};
    if (0) {}
    @TYPE_NAMES@
    else { return 0; }
    *value = v.lVal;
    return 1;
}

int main(void)
{
    const unsigned revisions[] = {7369, 7384, 7385, 7391, 7420, 7444, 7445, 7446, 7447, 7533};
    const char *names[] = {"TYPE_NONE", "TYPE_PLAYER", "TYPE_ENEMY", "TYPE_ITEM", "TYPE_OBSTACLE",
        "TYPE_STEAMER", "TYPE_SHOT", "TYPE_TRAP", "TYPE_TEXTBOX", "TYPE_ENDLEVEL",
        "TYPE_NPC", "TYPE_PANEL", "TYPE_RESERVED", "TYPE_MAX", "TYPE_UNKNOWN",
        "TYPE_NO_COPY", "TYPE_PROJECTILE", "TYPE_ANY"};
    const uint32_t values[3][18] = {
        {0,1,2,4,8,32,64,128,256,512,1024,4096,UINT32_C(0x40000000),8192,0,0,0,0},
        {1,2,4,8,16,64,128,256,512,1024,2048,4096,UINT32_C(0x80000000),8192,0,0,0,8191},
        {1,4,8,16,32,128,256,512,1024,2048,4096,8192,UINT32_C(0x80000000),0,16384,2,64,16381}
    };
    for (size_t row = 0; row < sizeof(revisions) / sizeof(*revisions); ++row)
    {
        obor_profile_build = revisions[row];
        const int generation = revisions[row] < 7385 ? 0 : revisions[row] < 7447 ? 1 : 2;
        for (size_t column = 0; column < sizeof(names) / sizeof(*names); ++column)
        {
            uint32_t value = UINT32_MAX;
            const int found = lookup(names[column], &value);
            const int expected = column < 13 || (column == 13 && revisions[row] < 7445)
                || (column >= 14 && column <= 16 && generation == 2)
                || (column == 17 && revisions[row] >= 7445);
            if (found != expected || (found && value != values[generation][column]))
            {
                fprintf(stderr, "%u: %s gave %u, expected %u\n", revisions[row], names[column],
                        value, values[generation][column]);
                abort();
            }
        }
    }
    return 0;
}
'''
        parts = {'HELPER': function(source, 'obor_profile_property_constant'),
                 'MACROS': '\n'.join(continued_macro(source, name) for name in macros),
                 'TYPE_NAMES': mapper[start:end]}
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_script_constant_admission_and_values(self):
        data = load_contract_fixture(FIXTURE.with_name('modern-script-constant-admission.json'))
        self.check_original_script_constant_values(data)

    def test_original_projectile_prime_constant_values(self):
        flags = {
            'BASE_FLOOR': 1, 'BASE_Y': 2, 'LAUNCH_MOVING': 4, 'LAUNCH_STATIONARY': 8,
            'SOURCE_GLOBAL_KNIFE': 16, 'SOURCE_GLOBAL_SHOT': 32, 'SOURCE_GLOBAL_STAR': 64,
            'SOURCE_MODEL_BOMB': 128, 'SOURCE_MODEL_KNIFE': 256, 'SOURCE_MODEL_PSHOTNO': 512,
            'SOURCE_MODEL_STAR': 1024, 'SOURCE_PROJ_FLASH': 4096, 'SOURCE_PROJ_KNIFE': 8192,
            'SOURCE_PROJ_STAR': 16384, 'SOURCE_WEAPON_PROJECTILE': 32768,
        }
        builds = (7369, 7391, 7420, 7421, 7533)
        self.check_original_script_constant_values({
            'engine': '7533',
            'names': ['PROJECTILE_PRIME_' + name for name in flags],
            'contracts': [list(flags.values()), [value if value < 4 else 2 * value for value in flags.values()]],
            'sources': [{'revision': build, 'contract': int(build >= 7421)} for build in builds],
            'expected_revisions': builds,
        })

    def check_original_script_constant_values(self, data):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'source/openborscript/constants.c').read_text()
        mapper = function(source, 'mapstrings_transconst')
        names = data['names']
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        registration = re.compile(r'\s*ICMPCONST(?:_\w+)?\((\w+)')
        entries = '\n'.join(line for line in mapper.splitlines()
                            if (call := registration.match(line)) and call[1] in names)
        self.assertTrue(entries)
        values = []
        for contract in data['contracts']:
            self.assertEqual(len(contract), len(names))
            values.append('{' + ','.join(f'{{{int(value is not None)}, {value or 0}}}' for value in contract) + '}')
        profiles = ','.join(f'{{{row["revision"]}, {row["contract"]}}}' for row in data['sources'])
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef printf
#undef stricmp
#define stricmp strcasecmp

uint32_t obor_profile_build;
@HELPER@
@MACROS@

static int lookup_constant(const char *constname, LONG *value)
{
    ScriptVariant v = {.vt = VT_INTEGER};
    if (0) { }
    @ENTRIES@
    else return 0;
    *value = v.lVal;
    return 1;
}

int main(void)
{
    static const char *const names[] = {@NAMES@};
    static const struct { int present; LONG value; } contracts[][sizeof(names) / sizeof(*names)] = {@VALUES@};
    static const struct { uint32_t revision; size_t index; } profiles[] = {@PROFILES@};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i].revision;
        for (size_t j = 0; j < sizeof(names) / sizeof(*names); ++j)
        {
            const size_t index = profiles[i].index;
            LONG value = 0;
            const int present = lookup_constant(names[j], &value);
            if (present != contracts[index][j].present || (present && value != contracts[index][j].value))
            {
                fprintf(stderr, "%u: %s returned %d/%ld, expected %d/%ld\n", obor_profile_build, names[j],
                        present, (long)value, contracts[index][j].present, (long)contracts[index][j].value);
                return 1;
            }
        }
    }
    return 0;
}
'''
        macros = ('ICMPCONST', 'ICMPCONST_SINCE', 'ICMPCONST_RANGE', 'ICMPCONST_ALIAS_RANGE',
                  'ICMPCONST_PROFILE_NAME')
        parts = {'HELPER': function(source, 'obor_profile_property_constant'),
                 'MACROS': '\n'.join(continued_macro(source, name) for name in macros),
                 'ENTRIES': entries, 'NAMES': ','.join(json.dumps(name) for name in names),
                 'VALUES': ',\n'.join(values), 'PROFILES': profiles}
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, data, engine_source=engine), '')

    def test_movement_property_getters_return_original_bit_values(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openborscript.c').read_text()
        _, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
        suffixes = ('basemap', 'gravity', 'hole', 'maxz', 'minz', 'obstacle', 'platform', 'screen', 'wall')
        properties = (*(f'_ep_subject_to_{suffix}' for suffix in suffixes), '_ep_no_adjust_base', '_ep_nohithead')
        branches = ''.join('case %d:' % index + cases[property_name]['body']
                           for index, property_name in enumerate(properties))
        template = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;

void ScriptVariant_ChangeType(ScriptVariant *value, VARTYPE type)
{
    value->vt = type;
}

@MOVEMENT@

static LONG read_property(entity *ent, unsigned int property)
{
    ScriptVariant result = {0};
    ScriptVariant *output = &result;
    ScriptVariant **pretvar = &output;
    switch (property)
    {
@BRANCHES@
    default:
        abort();
    }
    if (result.vt != VT_INTEGER) abort();
    return result.lVal;
}

static void check(entity *ent, unsigned int property, LONG expected)
{
    LONG value = read_property(ent, property);
    if (value != expected)
    {
        fprintf(stderr, "Movement property %u for profile %u gave %ld instead of %ld\n",
                property, obor_profile_build, (long)value, (long)expected);
        abort();
    }
}

int main(void)
{
    static const struct { uint32_t profile; unsigned int first_bit; } profiles[] = {
        {7369, 4}, {7391, 4}, {7420, 4}, {7426, 4}, {7427, 16},
        {7446, 16}, {7447, 256}, {7497, 256}, {7498, 1024}, {7530, 1024}, {7533, 1024},
    };
    static const e_move_config_flags physical[] = {
        MOVE_CONFIG_SUBJECT_TO_BASEMAP, MOVE_CONFIG_SUBJECT_TO_GRAVITY, MOVE_CONFIG_SUBJECT_TO_HOLE,
        MOVE_CONFIG_SUBJECT_TO_MAX_Z, MOVE_CONFIG_SUBJECT_TO_MIN_Z, MOVE_CONFIG_SUBJECT_TO_OBSTACLE,
        MOVE_CONFIG_SUBJECT_TO_PLATFORM, MOVE_CONFIG_SUBJECT_TO_SCREEN, MOVE_CONFIG_SUBJECT_TO_WALL,
    };
    entity actor = {0};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i].profile;
        for (unsigned int j = 0; j < sizeof(physical) / sizeof(*physical); ++j)
        {
            actor.modeldata.move_config_flags = MOVE_CONFIG_NO_MOVE;
            check(&actor, j, 0);
            actor.modeldata.move_config_flags |= physical[j];
            check(&actor, j, (LONG)(profiles[i].first_bit << j));
        }
        const unsigned no_adjust_base = sizeof(physical) / sizeof(*physical);
        const unsigned no_hit_head = no_adjust_base + 1;
        actor.modeldata.move_config_flags = MOVE_CONFIG_NO_MOVE;
        check(&actor, no_adjust_base, 0);
        check(&actor, no_hit_head, 0);
        actor.modeldata.move_config_flags |= MOVE_CONFIG_NO_ADJUST_BASE | MOVE_CONFIG_NO_HIT_HEAD;
        check(&actor, no_adjust_base, 1);
        check(&actor, no_hit_head, profiles[i].profile < 7447u ? 2 : 16);
    }
    return 0;
}
'''
        code = (template.replace('@MOVEMENT@', function(source, 'obor_profile_movement_property'))
                .replace('@BRANCHES@', branches))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_legacy_offense_factor_properties_use_original_slots(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        script = (engine / 'openborscript.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        _, reads = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
        _, writes = switch_cases(script, 'openbor_changeentityproperty', 'propind', outermost=True)
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
int max_attack_types = MAX_ATKS + 4;
@CONVERSIONS@

void ScriptVariant_ChangeType(ScriptVariant *value, VARTYPE type)
{
    value->vt = type;
}

static void expect(int condition, const char *description)
{
    if (!condition)
    {
        fprintf(stderr, "Profile %u: %s\n", obor_profile_build, description);
        abort();
    }
}

static DOUBLE read_factor(entity *ent, int paramCount, ScriptVariant selector)
{
    LONG ltemp;
    ScriptVariant result = {0}, *output = &result, **pretvar = &output, *arg;
    ScriptVariant *varlist[] = {NULL, NULL, &selector};
    switch (0)
    {
    case 0:
        @READ@
    }
    expect(result.vt == VT_DECIMAL, "offense getter result type");
    return result.dblVal;
}

static void write_factor(entity *ent, int paramCount, ScriptVariant selector, ScriptVariant value)
{
    LONG ltemp;
    DOUBLE dbltemp;
    ScriptVariant *varlist[] = {NULL, NULL, &selector, &value};
    switch (0)
    {
    case 0:
        @WRITE@
    }
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7391, 7420, 7434, 7435, 7533};
    for (size_t p = 0; p < sizeof(profiles) / sizeof(*profiles); ++p)
    {
        obor_profile_build = profiles[p];
        s_offense slots[MAX_ATKS + 4] = {0};
        static entity actor;
        actor.offense = slots;
        for (int i = 0; i < max_attack_types; ++i)
        {
            slots[i].factor = 0.25f * (i + 1);
            expect(read_factor(&actor, 3, (ScriptVariant){.vt=VT_INTEGER,.lVal=i}) == slots[i].factor,
                   "indexed factor read");
        }
        ScriptVariant selector = {.vt=VT_INTEGER,.lVal=MAX_ATKS - 1};
        ScriptVariant value = {.vt=VT_DECIMAL,.dblVal=-2.75};
        expect(read_factor(&actor, 2, selector) == slots[0].factor &&
               read_factor(&actor, 3, (ScriptVariant){.vt=VT_EMPTY}) == slots[0].factor,
               "default factor when no usable index is given");
        write_factor(&actor, 4, selector, value);
        expect(read_factor(&actor, 3, selector) == -2.75, "fractional factor write");
        selector.lVal = MAX_ATKS;
        const DOUBLE extended = slots[MAX_ATKS].factor;
        write_factor(&actor, 4, selector, value);
        expect(read_factor(&actor, 3, selector) == extended, "extended slots remain read-only");
        selector.lVal = max_attack_types;
        expect(read_factor(&actor, 3, selector) == 0.0, "unavailable factor");
        actor.offense = NULL;
        selector.lVal = 0;
        write_factor(&actor, 4, selector, value);
        expect(read_factor(&actor, 3, selector) == 0.0, "empty offense collection");
    }
    return 0;
}
'''
        code = code.replace('@CONVERSIONS@', '\n'.join(function(variants, name) for name in
                            ('ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')))
        code = code.replace('@READ@', reads['_ep_offense']['body']).replace('@WRITE@', writes['_ep_offense']['body'])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_entity_removal_script_trigger_at_7425_boundary(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
static Script onkill;
static entity actor;
s_player player[MAX_PLAYERS];
static ScriptVariant local_self, local_trigger;
static unsigned callbacks, self_writes, trigger_writes;
static LONG expected_trigger;
static int active;

static void check(int value, const char *description)
{
    if(!value)
    {
        fprintf(stderr, "%s for profile %u\n", description, obor_profile_build);
        abort();
    }
}

void ScriptVariant_Init(ScriptVariant *value) { *value = (ScriptVariant){.vt = VT_EMPTY}; }
void ScriptVariant_Clear(ScriptVariant *value) { ScriptVariant_Init(value); }
void ScriptVariant_ChangeType(ScriptVariant *value, VARTYPE type) { value->vt = type; }
int Script_IsInitialized(Script *script) { return active && script == &onkill; }

static void set_local(Script *script, const char *name, const ScriptVariant *value)
{
    if(strcmp(name, "self") == 0)
    {
        ++self_writes;
        local_self = *value;
    }
    else if(strcmp(name, "trigger") == 0)
    {
        ++trigger_writes;
        local_trigger = *value;
    }
    else abort();
}

#undef Script_Set_Local_Variant
#define Script_Set_Local_Variant set_local
int Script_Execute(Script *script)
{
    check(script == &onkill && local_self.vt == VT_PTR && local_self.ptrVal == &actor,
          "Wrong self during removal callback");
    check(local_trigger.vt == VT_INTEGER && local_trigger.lVal == expected_trigger,
          "Wrong trigger during removal callback");
    ++callbacks;
    return 1;
}

@REMOVAL_CALLBACK@

void kill_entity(entity *victim, e_kill_entity_trigger trigger)
{
    execute_onkill_script(victim, trigger);
}

static void remove_player_on_game_over(int i)
{
    @GAME_OVER_REMOVAL@
}

static void remove_actor_at_level_end(entity *e)
{
    @LEVEL_END_REMOVAL@
}

@SCRIPT_REMOVAL@

static void check_script_removal(void)
{
    ScriptVariant handle = {.vt = VT_PTR, .ptrVal = &actor};
    ScriptVariant reason = {.vt = VT_INTEGER};
    ScriptVariant result = {.vt = VT_EMPTY};
    ScriptVariant *args[] = {&handle, &reason};
    ScriptVariant *returned = &result;
    const int expose_trigger = obor_profile_build >= 7425u;
    const int original_numbers = obor_profile_build < 7433u;
    const int reasons[] = {6, 7, original_numbers ? 44 : 45, 45, 47};

    active = 1;
    callbacks = 0;
    local_trigger = (ScriptVariant){.vt = VT_INTEGER, .lVal = 123};
    expected_trigger = expose_trigger ? (original_numbers ? 22 : 23) : 123;
    check(openbor_killentity(args, &returned, 1) == S_OK && result.vt == VT_INTEGER &&
          result.lVal == 1 && callbacks == 1, "Wrong default script removal");
    for(size_t i = 0; i < sizeof(reasons) / sizeof(*reasons); ++i)
    {
        reason.lVal = reasons[i];
        expected_trigger = expose_trigger ? reason.lVal : 123;
        check(openbor_killentity(args, &returned, 2) == S_OK && result.lVal == 1 &&
              callbacks == i + 2, "Wrong explicit script removal");
    }
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7391, 7420, 7424, 7425, 7426, 7432, 7433, 7530, 7533, 7555};
    s_scripts scripts = {.onkill_script = &onkill};
    actor.scripts = &scripts;
    player[0].ent = &actor;
    for(size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int expose_trigger = obor_profile_build >= 7425;
        active = 1;
        callbacks = self_writes = trigger_writes = 0;
        local_trigger = (ScriptVariant){.vt = VT_INTEGER, .lVal = 123};
        expected_trigger = expose_trigger ? (obor_profile_build < 7433u ? 7 : 8) : 123;
        execute_onkill_script(&actor, KILL_ENTITY_TRIGGER_BIND_ANIMATION_MATCH);
        check(callbacks == 1 && self_writes == 2 && local_self.vt == VT_EMPTY,
              "Unexpected self after removal callback");
        check(trigger_writes == (expose_trigger ? 2u : 0u), "Unexpected trigger writes");
        check(expose_trigger ? local_trigger.vt == VT_EMPTY
                            : local_trigger.vt == VT_INTEGER && local_trigger.lVal == 123,
              "Unexpected trigger after removal callback");
        active = 0;
        execute_onkill_script(&actor, KILL_ENTITY_TRIGGER_BIND_ANIMATION_MATCH);
        check(callbacks == 1 && self_writes == 2 && trigger_writes == (expose_trigger ? 2u : 0u),
              "Uninitialized removal callback changed");
        active = 1;
        callbacks = self_writes = trigger_writes = 0;
        local_trigger = (ScriptVariant){.vt = VT_INTEGER, .lVal = 123};
        expected_trigger = expose_trigger ? (obor_profile_build < 7433u ? 11 : 12) : 123;
        remove_player_on_game_over(0);
        check(callbacks == 1 && self_writes == 2 && local_self.vt == VT_EMPTY,
              "Game over removal callback changed");
        check(trigger_writes == (expose_trigger ? 2u : 0u), "Unexpected game over trigger writes");
        check(expose_trigger ? local_trigger.vt == VT_EMPTY
                            : local_trigger.vt == VT_INTEGER && local_trigger.lVal == 123,
              "Unexpected trigger after game over callback");
        callbacks = self_writes = trigger_writes = 0;
        local_trigger = (ScriptVariant){.vt = VT_INTEGER, .lVal = 123};
        expected_trigger = expose_trigger ? 1 : 123;
        remove_actor_at_level_end(&actor);
        check(callbacks == 1 && self_writes == 2 && local_self.vt == VT_EMPTY,
              "Level end removal callback changed");
        check(trigger_writes == (expose_trigger ? 2u : 0u), "Unexpected level end trigger writes");
        check(expose_trigger ? local_trigger.vt == VT_EMPTY
                            : local_trigger.vt == VT_INTEGER && local_trigger.lVal == 123,
              "Unexpected trigger after level end callback");
        check_script_removal();
    }
    return 0;
}
'''
        code = code.replace('@REMOVAL_CALLBACK@', function(source, 'execute_onkill_script'))
        code = code.replace('@SCRIPT_REMOVAL@', function(script, 'openbor_killentity'))
        game_over = braced_statement(function(source, 'playlevel'), 'if (level->force_gameover)')
        removal = re.search(r'kill_entity\(player\[i\]\.ent, [A-Z_]+\);', game_over)
        self.assertIsNotNone(removal, 'Expected player removal during game over')
        code = code.replace('@GAME_OVER_REMOVAL@', removal[0])
        removal = re.search(r'execute_onkill_script\(e, [A-Z_]+\);', function(source, 'kill_all'))
        self.assertIsNotNone(removal, 'Expected removal callback during level cleanup')
        code = code.replace('@LEVEL_END_REMOVAL@', removal[0])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def check_script_spawn_entry(self, physical):
        data = load_contract_fixture(SPAWN_SCRIPT_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        names = ('item', '2pitem', '3pitem', '4pitem', 'itemhealth', 'itemalias', 'itemmap')
        setter, cases = switch_cases(source, 'openbor_setspawnentry', 'prop', outermost=True)
        prefix = re.split(r'\bswitch\s*\(prop\)', setter, maxsplit=1)[0]
        branches = ''.join('case _sse_' + name + ':' + cases['_sse_' + name]['body'] for name in names)
        error = setter[setter.index('\nsetspawnentry_error:'):]
        methods = ('mapstrings_setspawnentry', 'openbor_clearspawnentry', 'openbor_spawn', 'openbor_projectile')
        macro_source = (engine / 'source/openborscript/scriptcommon.h').read_text() if physical == '6391' else source
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', macro_source)[0]
        name_helpers = ''
        if physical == '4432':
            core = (engine / 'openbor.c').read_text(encoding='latin-1')
            name_helpers = '\n'.join(function(core, name) for name in
                                     ('obor_profile_name_limit', 'obor_profile_copy_name'))
        methods = '\n'.join(function(source, name) for name in methods)
        if 'obor_profile_uses_5134_script_ids(' in setter + methods:
            profile_ids = (engine / 'source/openborscript/profile_ids.h').read_text()
            name_helpers += function(profile_ids, 'obor_profile_uses_5134_script_ids') + '\n'
        values = {
            'VARIANTS': '\n'.join(function(variant, name) for name in ('ScriptVariant_Clear',
                                      'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
            'SEARCH': function(utility, 'searchList'), 'MAP_MACRO': macro,
            'ENUM': re.search(r'enum setspawnentry_enum\s*\{[^}]*\};', source)[0],
            'METHODS': name_helpers + methods,
            'SETTER': prefix + 'switch(prop){' + branches + 'default: abort();}\nreturn S_OK;\n' + error,
            'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['zero_prime'], row['nonzero_prime'])
                             for row in rows),
        }
        template = Path(__file__).with_name('script_spawn_entry_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_script_spawn_entry(self):
        self.check_script_spawn_entry('4432')

    def test_6391_script_spawn_entry(self):
        self.check_script_spawn_entry('6391')

    def test_runtime_names_and_projectile_prime_recipient(self):
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', flags=[1,16,2,8,4], profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data, engine), data, engine_source=engine)), expected)


if __name__ == '__main__':
    unittest.main()
