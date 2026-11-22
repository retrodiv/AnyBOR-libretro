"""Check historical global configuration values, names and constants.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-global-config-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/openborscript/global_config.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    constants = (engine / 'source/openborscript/constants.c').read_text()
    mapper = function(constants, 'mapstrings_transconst')
    chain = [line for line in mapper.splitlines() if re.fullmatch(
        r'\s*ICMPCONST_(?:SINCE|RANGE)\(GLOBAL_CONFIG_PROPERTY_\w+,\s*\d+(?:,\s*\d+)?\)\s*', line)]
    if len(chain) != 9:
        raise ValueError('Expected all nine global configuration constant registrations')
    core = (engine / 'openbor.c').read_text()
    initializer = core[core.index('s_global_config global_config ='):]
    initializer = initializer[:initializer.index('};') + 2]
    index = function((engine / 'source/openborscript/index.c').read_text(),
                     'Script_GetStringMapFunction')
    branches = re.findall(
        r'else if\s*\(functionRef == \(\(void\*\)openbor_(?:get|set)_global_config_property\)\)\s*\{[^}]+\}', index)
    if len(branches) != 2:
        raise ValueError('Expected two global configuration preconversion branches')
    parts = dict(
        INITIALIZER=initializer,
        HELPERS='\n'.join(function(source, name) for name in
                           ('obor_profile_global_config_property_end',
                            'obor_profile_global_config_get_property_map',
                            'obor_profile_get_global_config_property',
                            'obor_profile_set_global_config_property',
                            'obor_profile_legacy_global_config_property')),
        ENTRIES='\n'.join(function(source, name) for name in
                           ('mapstrings_global_config_property',
                            'openbor_get_global_config_property',
                            'openbor_set_global_config_property')),
        VARIANTS='\n'.join(function(variants, name) for name in
                            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        COMMON='\n'.join(function(common, name) for name in
                          ('property_access_get_member', 'property_access_set_member')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        PRECONVERSION='\n'.join(branches),
        CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
        MACROS='\n'.join(continued_macro(constants, name) for name in
                          ('ICMPCONST_SINCE', 'ICMPCONST_RANGE')),
        CONSTANT_CHAIN='\n'.join(chain),
        CONSTANT_QUERIES=','.join(json.dumps(n) for n in data['constant_queries']),
        STRINGS=','.join(json.dumps(n) for n in data['strings']),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_global_config_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved global configuration contract input')
    return code


class ModernGlobalConfigContracts(unittest.TestCase):
    def test_original_script_level_and_text_deadlines(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        level_source = (engine / 'source/openborscript/level.c').read_text()
        level_set = function(level_source, 'openbor_set_level_property')
        model_load = function(core, 'load_cached_model')
        entity_copy = function(core, 'ent_copy_uninit')
        change_entity = function(script, 'openbor_changeentityproperty')
        parts = {
            'SET_TEXT': re.search(r'level->textobjs\[ind\]\.time = [^;]+;',
                                  function(script, 'openbor_settextobj'))[0],
            'CHANGE_TEXT': re.search(r'level->textobjs\[ind\]\.time = [^;]+;',
                                     function(script, 'openbor_changetextobjproperty'))[0],
            'SET_LEVEL': '\n'.join(re.search(r'handle->' + field + r' = [^;]+;', level_set)[0]
                                   for field in ('advancetime', 'quaketime')),
            'SET_STAYDOWN': '\n'.join(re.search(r'ent->staydown\.' + field + r' = [^;]+;', change_entity)[0]
                                      for field in ('rise', 'riseattack', 'riseattack_stall')),
            'SET_RISETIME': '\n'.join(re.search(r'newchar->risetime\.' + field + r' = [^;]+;', model_load)[0]
                                      for field in ('rise', 'riseattack')),
            'RISE_DEFAULT': braced_statement(model_load, 'if(newchar->risetime.rise == '),
            'INHERIT_RISE': braced_statement(entity_copy, 'if(ent->modeldata.risetime.rise == '),
            'DRAW': function(core, 'draw_textobjs'),
            'CLOCKS': '\n'.join([function(core, 'obor_entity_deadline_value'),
                                 function(script, 'obor_script_entity_deadline')]),
        }
        code = r'''
#include <limits.h>
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
u32 _time;
static s_level stage;
static s_textobj text;
s_level *level = &stage;

@CLOCKS@

_Static_assert(sizeof(e_blend_mode) == sizeof(int) && (e_blend_mode)-1 < 0,
               "Blend modes preserve the signed integer representation");

int obor_textobjs_count(const s_level *value) { assert(value == level); return 1; }
void font_printf(int x, int y, int font, int layer, char *format, ...) { assert(0); }

static void set_text_deadline(LONG T)
{
    const int ind = 0;
    @SET_TEXT@
}

static void change_text_deadline(LONG ltemp)
{
    const int ind = 0;
    @CHANGE_TEXT@
}

static void set_level_deadlines(s_level *handle, LONG temp_int)
{
    @SET_LEVEL@
}

static void set_staydown(entity *ent, LONG ltemp)
{
    @SET_STAYDOWN@
}

static void set_risetime(s_model *newchar, int value)
{
    #undef GET_INT_ARG
    #define GET_INT_ARG(index) value
    @SET_RISETIME@
    #undef GET_INT_ARG
}

static void apply_default_risetime(s_model *newchar)
{
    @RISE_DEFAULT@
}

static void inherit_risetime(entity *ent, s_model *oldmodel)
{
    @INHERIT_RISE@
}

@DRAW@

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7503, 7504, 7509, 7510, 7533};
    static const LONG times[] = {0, 100, -1};
    static entity actor;
    static s_model model = {.type = TYPE_ENEMY};
    stage.textobjs = &text;
    for (size_t p = 0; p < sizeof(builds) / sizeof(*builds); ++p)
    {
        obor_profile_build = builds[p];
        for (size_t i = 0; i < sizeof(times) / sizeof(*times); ++i)
        {
            const LONG value = times[i];
            const unsigned long expected = builds[p] < 7510u ? (uint32_t)value : (unsigned long)value;
            const unsigned long expected_rise = builds[p] < 7504u ? (uint32_t)value : (unsigned long)value;
            set_text_deadline(value);
            assert(text.time == expected);
            change_text_deadline(1);
            change_text_deadline(value);
            assert(text.time == expected);
            set_level_deadlines(&stage, value);
            assert(stage.advancetime == expected && stage.quaketime == expected);
            set_staydown(&actor, value);
            assert(actor.staydown.rise == expected_rise && actor.staydown.riseattack == expected_rise &&
                   actor.staydown.riseattack_stall == expected_rise);
            set_risetime(&model, value);
            assert(model.risetime.rise == expected_rise && model.risetime.riseattack == expected_rise);
            set_risetime(&actor.modeldata, value);
            apply_default_risetime(&model);
            assert(model.risetime.rise == (value == -1 ? 0 : expected_rise));
            model.risetime.rise = 42;
            inherit_risetime(&actor, &model);
            assert(actor.modeldata.risetime.rise == (value == -1 ? 42 : expected_rise));
        }
        text.position.x = 37;
        _time = UINT32_MAX - 1;
        draw_textobjs();
        assert(text.position.x == 37);
        _time = UINT32_MAX;
        draw_textobjs();
        const int was_due = builds[p] < 7510u || ULONG_MAX == UINT32_MAX;
        assert(text.position.x == (was_due ? 0 : 37));

        text.position.x = 37;
        set_text_deadline(0);
        draw_textobjs();
        assert(text.position.x == 37);
        set_text_deadline(100);
        _time = 99;
        draw_textobjs();
        assert(text.position.x == 37);
        _time = 100;
        draw_textobjs();
        assert(text.position.x == 0 && text.time == 0);
    }
    return 0;
}
'''
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_level_and_models_txt_command_availability(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        commands = (engine / 'source/openborscript/commands.c').read_text()
        utils = (engine / 'source/utils.c').read_text()
        for loader in ('load_models', 'load_model_constants'):
            self.assertIn('getModelstxtCommand(modelstxtcmdlist, command)', function(source, loader))
        level = function(source, 'load_level')
        self.assertIn('cmd = getLevelCommand(levelcmdlist, command);', level)
        self.assertIn('cmd2 = getLevelCommand(levelcmdlist, command);', level)
        code = r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include "commands.h"
#include "source/scriptlib/List.c"

uint32_t obor_profile_build;

void *checkAlloc(void *ptr, size_t size, const char *func, const char *file, int line)
{
    (void)func;
    (void)file;
    (void)line;
    assert(ptr || size == 0);
    return ptr;
}

@METHODS@

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7438, 7439, 7444, 7445, 7533};
    const struct { const char *name; int command; unsigned introduced; int in_level; } cases[] = {
        { "LoAd", CMD_MODELSTXT_LOAD, 0, 0 },
        { "MpBlOcK", CMD_MODELSTXT_MPBLOCK, 0, 0 },
        { "global_config_flash_layer_adjust", CMD_MODELSTXT_GLOBAL_CONFIG_FLASH_LAYER_ADJUST, 7439, 0 },
        { "global_config_flash_layer_source", CMD_MODELSTXT_GLOBAL_CONFIG_FLASH_LAYER_SOURCE, 7439, 0 },
        { "global_config_flash_z_source", CMD_MODELSTXT_GLOBAL_CONFIG_FLASH_Z_SOURCE, 7439, 0 },
        { "SpAwN", CMD_LEVEL_SPAWN, 0, 1 },
        { "AT", CMD_LEVEL_AT, 0, 1 },
        { "faction_group_damage_direct", CMD_LEVEL_FACTION_GROUP_DAMAGE_DIRECT, 7445, 1 },
        { "faction_group_damage_indirect", CMD_LEVEL_FACTION_GROUP_DAMAGE_INDIRECT, 7445, 1 },
        { "faction_group_hostile", CMD_LEVEL_FACTION_GROUP_HOSTILE, 7445, 1 },
        { "faction_group_member", CMD_LEVEL_FACTION_GROUP_MEMBER, 7445, 1 },
        { "faction_type_damage_direct", CMD_LEVEL_FACTION_TYPE_DAMAGE_DIRECT, 7445, 1 },
        { "faction_type_damage_indirect", CMD_LEVEL_FACTION_TYPE_DAMAGE_INDIRECT, 7445, 1 },
        { "faction_type_hostile", CMD_LEVEL_FACTION_TYPE_HOSTILE, 7445, 1 },
    };
    obor_profile_build = 7533;
    List *models = createModelstxtCommandList();
    List *level = createLevelCommandList();
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        for (size_t j = 0; j < sizeof(cases) / sizeof(*cases); ++j)
        {
            char name[64];
            strcpy(name, cases[j].name);
            const int observed = cases[j].in_level ? getLevelCommand(level, name) : getModelstxtCommand(models, name);
            const int expected = builds[i] >= cases[j].introduced ? cases[j].command : 0;
            assert(observed == expected);
        }
        char unknown[] = "UnKnOwN";
        assert(!getLevelCommand(level, unknown) && !strcmp(unknown, "unknown"));
        assert(!getModelstxtCommand(models, unknown));
    }
    freeCommandList(models);
    freeCommandList(level);
    return 0;
}
'''
        methods = ('freeCommandList', 'getCommandlistCommand', 'getModelstxtCommand', 'getLevelCommand',
                   'prepareList', 'createModelstxtCommandList', 'createLevelCommandList')
        methods = [function(utils, 'lc'), *(function(commands, name) + '\n#undef LIST_ADD' for name in methods)]
        code = code.replace('@METHODS@', '\n'.join(methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_global_config_property_indices(self):
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        self.assertEqual(data['strings'][:4], ['ajspecial', 'block_ratio', 'block_type', 'cheats'])
        code = program(data).split('\nint main(void)', 1)[0] + r'''
static void expect(int value, const char *description)
{
    if (!value)
    {
        fprintf(stderr, "%s for profile %u\n", description, obor_profile_build);
        abort();
    }
}

int main(void)
{
    static const unsigned revisions[] = {7369, 7391, 7420, 7438, 7530, 7533};
    for (size_t i = 0; i < sizeof(revisions) / sizeof(*revisions); ++i)
    {
        obor_profile_build = revisions[i];
        const int early = obor_profile_build < 7439;
        const LONG native_cheats = early ? 1 : 3;
        seed_object();
        ScriptVariant handle = {.vt = VT_PTR, .ptrVal = &object};
        ScriptVariant property = {.vt = VT_STR, .strVal = 3};
        ScriptVariant value = {.vt = VT_INTEGER, .lVal = 0x4301};
        ScriptVariant result = {.vt = VT_INTEGER, .lVal = 77}, *out = &result;
        ScriptVariant *args[] = {&handle, &property, &value};
        expect(mapstrings_global_config_property(args, 3) && property.vt == VT_INTEGER &&
               property.lVal == native_cheats, "Native cheat property number");
        expect(openbor_set_global_config_property(args, &out, 3) == S_OK &&
               object.cheats == 0x4301 && object.block_ratio == 12,
               "Cheat property preserves the native mask and other settings");
        expect(openbor_get_global_config_property(args, &out, 2) == S_OK &&
               result.vt == VT_INTEGER && result.lVal == 0x4301, "Read the exact native cheat mask");

        property = (ScriptVariant){.vt = VT_INTEGER, .lVal = 1};
        expect(openbor_get_global_config_property(args, &out, 2) == S_OK &&
               result.lVal == (early ? 0x4301 : 12), "Original property at index one");
        property = (ScriptVariant){.vt = VT_STR, .strVal = 1};
        log_text[0] = '\0';
        if (early)
        {
            expect(openbor_get_global_config_property(args, &out, 2) == E_FAIL && !out &&
                   strstr(log_text, "Property name 'block_ratio' is not supported"),
                   "Unavailable name before expanded global configuration");
            property = (ScriptVariant){.vt = VT_INTEGER, .lVal = 2};
            out = &result;
            expect(openbor_set_global_config_property(args, &out, 3) == E_FAIL &&
                   out == &result && object.block_type == 13, "Unavailable index before expanded configuration");
        }
        else
        {
            expect(openbor_get_global_config_property(args, &out, 2) == S_OK &&
                   result.lVal == 12, "Expanded global configuration name");
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code, data, engine_source=engine), '')

    def test_system_menu_return_keeps_original_config_dispatch(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include "openbor.h"
#include "translation.h"
#undef _menutext
#undef _menutextm
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static e_screen_status screen_status;
static unsigned long long bothnewkeys;
static int nodebugoptions = 1, versusdamage = 2, current_set;
static s_level *level;
static s_set_entry menu_set = {.maxplayers = 2};
static s_set_entry *levelsets = &menu_set;
s_savedata savedata;
s_global_config global_config;
static s_global_sample global_sample_list = {.beep = -1, .beep_2 = -1};
static int frames, config_calls, save_calls, scenario;

char *ob_gettrans(char *message) { return message; }
static void text(int selected, int x, int y, const char *format, ...) {}
static void config_menu(void) { ++config_calls; }
static void save(void) { ++save_calls; }

static void next_frame(int ingame, int wait)
{
    assert(screen_status & IN_SCREEN_SYSTEM_OPTIONS_MENU);
    static const unsigned config[] = {FLAG_MOVEDOWN, FLAG_MOVEDOWN, FLAG_ATTACK,
                                      FLAG_MOVEDOWN, FLAG_ATTACK};
    static const unsigned settings[] = {FLAG_ATTACK, FLAG_MOVEDOWN, FLAG_ATTACK, FLAG_ESC};
    assert(frames < (scenario ? 4 : 5));
    bothnewkeys = (scenario ? settings : config)[frames++];
}

#define _menutext text
#define _menutextm text
#define getSystemRam(...) 0
#define getUsedRam(...) 0
#define commaprint(...) "0"
#define sound_play_sample(...) ((void)0)
#define menu_options_cheats() abort()
#define menu_options_debug() abort()
#define menu_options_config config_menu
#define savesettings save
#define update next_frame
@SYSTEM_MENU@

int main(void)
{
    static const uint32_t builds[] = {7369, 7391, 7406, 7409, 7420, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        frames = config_calls = save_calls = scenario = 0;
        menu_options_system();
        assert(config_calls == (builds[i] < 7409 ? 1 : 0));
        assert(frames == (builds[i] < 7409 ? 5 : 3));
        assert(save_calls == 1 && !bothnewkeys && !screen_status);

        frames = config_calls = save_calls = 0;
        scenario = 1;
        savedata.uselog = savedata.mode = 0;
        menu_options_system();
        assert(frames == 4 && savedata.uselog == 1 && savedata.mode == 1);
        assert(config_calls == 0 && save_calls == 1 && !bothnewkeys && !screen_status);
    }
    return 0;
}
'''
        code = code.replace('@SYSTEM_MENU@', function(source, 'menu_options_system'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_cheat_flags_constants_and_menu(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        constants = (engine / 'source/openborscript/constants.c').read_text()
        mapper = function(constants, 'mapstrings_transconst')
        chain = [line for line in mapper.splitlines() if re.match(
            r'\s*ICMPCONST(?:_SINCE|_PROFILE_VALUE|_CHEAT_MASK)?\(CHEAT_OPTIONS_', line)]
        self.assertEqual(len(chain), 17)
        parts = {
            'CONSTANT_HELPER': function(constants, 'obor_profile_property_constant'),
            'CONSTANT_MACROS': '\n'.join(continued_macro(constants, name) for name in
                                       ('ICMPCONST', 'ICMPCONST_SINCE', 'ICMPCONST_PROFILE_VALUE',
                                        'ICMPCONST_CHEAT_MASK')),
            'CONSTANT_CHAIN': '\n'.join(chain),
            'CHEAT_FUNCTIONS': '\n'.join(function(source, name) for name in
                                        ('find_cheat_options_from_string',
                                         'lcmHandleCommandGlobalConfigCheats', 'menu_options_cheats')),
        }
        code = Path(__file__).with_name('modern_cheat_options_contract.c.in').read_text()
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_values_names_constants_tags_and_preconversion(self):
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data, engine_source=engine)), expected)


if __name__ == '__main__':
    unittest.main()
