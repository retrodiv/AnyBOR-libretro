"""Check native control menu selection, rumble and binding transactions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-control-menu-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'keyboard_setup'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_control_menu_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved control menu input')
    return code


class ModernControlMenuContracts(unittest.TestCase):
    def test_8020_menu_action_and_navigation_order(self):
        data = {'engine': '8023'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        main_options = function(source, 'menu_options')
        prefix = ('(bothnewkeys & FLAG_MOVEUP)', '(bothnewkeys & FLAG_MOVEDOWN)',
                  'obor_menu_has_action(bothnewkeys)')
        conditions = []
        for start in prefix:
            matching = re.search(r'(?m)^\s*if\((' + re.escape(start) + r'[^{};]*?)\)\s*\n\s*\{', main_options)
            self.assertIsNotNone(matching, start)
            conditions.append(matching[1])
        for name in ('menu_options_config', 'menu_options_system'):
            self.assertIn('if(obor_menu_has_action(bothnewkeys))', function(source, name))
        for name in ('menu_options_sound', 'menu_options_debug', 'menu_options_cheats', 'menu_options_video'):
            self.assertIn('FLAG_MOVELEFT | FLAG_MOVERIGHT) || obor_menu_has_confirm(bothnewkeys)',
                          function(source, name))
        for name in ('menu_difficulty', 'choose_mode', 'openborMain'):
            self.assertIn('if(obor_menu_has_confirm(bothnewkeys))', function(source, name))
        self.assertEqual(function(source, 'selectplayer').count('obor_menu_has_confirm(player[i].newkeys)'), 2)
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
@HELPERS@

static unsigned menu_events(int bothnewkeys)
{
    unsigned result = (bothnewkeys & FLAG_ESC) ? 1u : 0u;
    if (@UP@) result |= 2u;
    if (@DOWN@) result |= 4u;
    if (@ACTION@) result |= 8u;
    return result;
}

static unsigned original_8020(int keys)
{
    unsigned result = 0;
    if (keys & FLAG_ESC) result |= 1u;
    if (keys & FLAG_MOVEUP) result |= 2u;
    if (keys & FLAG_MOVEDOWN) result |= 4u;
    if (keys & (FLAG_MOVELEFT | FLAG_MOVERIGHT | FLAG_ANYBUTTON)) result |= 8u;
    return result;
}

static unsigned original_8021(int keys)
{
    if (keys & FLAG_ESC) return 1u;
    if (keys & FLAG_MOVEUP) return 2u;
    if (keys & FLAG_MOVEDOWN) return 4u;
    if (any_button_except_esc(keys)) return 8u;
    return 0u;
}

int main(void)
{
    static const uint32_t profiles[] = {8020, 8021, 8023};
    static const int buttons[] = {FLAG_ESC, FLAG_MOVEUP, FLAG_MOVEDOWN, FLAG_MOVELEFT,
                                 FLAG_MOVERIGHT, FLAG_START, FLAG_ATTACK};
    for (size_t revision = 0; revision < sizeof(profiles) / sizeof(*profiles); ++revision)
    {
        obor_profile_build = profiles[revision];
        for (unsigned combination = 0; combination < (1u << (sizeof(buttons) / sizeof(*buttons))); ++combination)
        {
            int keys = 0;
            for (size_t button = 0; button < sizeof(buttons) / sizeof(*buttons); ++button)
            {
                if (combination & (1u << button)) keys |= buttons[button];
            }
            const bool legacy = profiles[revision] == 8020;
            const unsigned expected = legacy ? original_8020(keys) : original_8021(keys);
            assert(menu_events(keys) == expected);
            assert(obor_menu_has_confirm(keys) == !!((keys & FLAG_ANYBUTTON) && (legacy || !(keys & FLAG_ESC))));
            assert(obor_menu_has_action(keys) == !!(legacy ? keys & (FLAG_ANYBUTTON | FLAG_MOVELEFT | FLAG_MOVERIGHT)
                                                          : any_button_except_esc(keys)));
        }
    }
    return 0;
}
'''
        helpers = '\n'.join(function(source, name) for name in (
            'obor_uses_8020_controls', 'obor_menu_has_confirm', 'obor_menu_has_action'))
        inputs = dict(zip(('UP', 'DOWN', 'ACTION'), conditions))
        inputs['HELPERS'] = helpers
        for name, value in inputs.items():
            code = code.replace('@' + name + '@', value)
        self.assertEqual(native_output(code, data, engine_source=engine), '')

    def test_8020_settings_use_player_keys_in_the_main_record(self):
        data = {'engine': '8023'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        settings_cases = []
        names = ('savesettings', 'saveasdefault', 'loadsettings', 'loadfromdefault')
        for index, name in enumerate(names):
            routine = function(source, name)
            gate = re.search(r'(?m)^    (if \(obor_uses_8020_controls\(\)\)\n        return;)\n\n'
                             r'    // (?:save|load) controls', routine)
            self.assertIsNotNone(gate)
            self.assertIn('fclose(handle);', routine[:gate.start()])
            settings_cases.append(f'        case {index}:\n{gate[1]}\n    break;')
        control_source = (ROOT / 'src/port/libretro/control.c').resolve()
        code = r'''
#include @CONTROL@
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
unsigned char obor_pad[4][16];
s_savedata savedata;
s_global_config global_config;
static int separate_files;

void obor_poll_tick(void) { }

@SETTINGS@

static void use_mappings_file(unsigned operation)
{
    switch (operation)
    {
@GATES@
        default: abort();
    }
    ++separate_files;
}

int main(void)
{
    const uint32_t revisions[] = {8020, 8021, 8023};
    for (size_t i = 0; i < sizeof(revisions) / sizeof(*revisions); ++i)
    {
        obor_profile_build = revisions[i];
        const bool legacy = revisions[i] == 8020;
        separate_files = 0;
        memset(&savedata, 0, sizeof(savedata));
        memset(obor_pad, 0, sizeof(obor_pad));
        clearsettings();
        apply_controls();
        for (unsigned operation = 0; operation < 4; ++operation)
            use_mappings_file(operation);
        assert(separate_files == (legacy ? 0 : 4));
        s_playercontrols first = {.deviceID = 0};
        s_playercontrols second = {.deviceID = 1};
        s_playercontrols *players[] = {&first, &second};
        obor_pad[0][4] = obor_pad[1][4] = 1;
        control_update(players, 2);
        assert(first.keyflags == FLAG_ATTACK && first.newkeyflags == FLAG_ATTACK);
        assert(second.keyflags == (legacy ? 0u : FLAG_ATTACK));
        control_update(players, 2);
        assert(!first.newkeyflags && !second.newkeyflags);
        if (legacy)
        {
            assert(savedata.keys[0][SDID_ATTACK] == OBOR_KEY(0, 4));
            assert(savedata.keys[1][SDID_ATTACK] == CONTROL_NONE);
            savedata.keys[0][SDID_JUMP] = OBOR_KEY(1, 9);
            apply_controls();
            obor_pad[0][4] = obor_pad[1][4] = 0;
            obor_pad[1][9] = 1;
            control_update(players, 2);
            assert(first.newkeyflags == FLAG_JUMP && !second.keyflags);
            savedata.usejoy = 0;
            apply_controls();
            control_update(players, 2);
            assert(!first.keyflags && !second.keyflags);
            obor_pad[0][11] = 1;
            control_update(players, 2);
            assert(first.newkeyflags == FLAG_ESC && second.newkeyflags == FLAG_ESC);

            memset(obor_pad, 0, sizeof(obor_pad));
            obor_pad[0][4] = 1;
            control_legacy_begin_scan();
            assert(control_legacy_scan_key() == 0);
            obor_pad[1][6] = 1;
            assert(control_legacy_scan_key() == 0);
            obor_pad[0][6] = 1;
            assert(control_legacy_scan_key() == OBOR_KEY(0, 6));
            assert(!strcmp(control_legacy_key_name(OBOR_KEY(0, 6)), "P1 Attack3"));
            control_legacy_usejoy(1);
            obor_pad[1][9] = 1;
            assert(control_legacy_scan_key() == OBOR_KEY(1, 9));
        }
    }
    return 0;
}
'''
        control_functions = ('obor_uses_8020_controls', 'clearsettings', 'apply_controls')
        replacements = dict(CONTROL=json.dumps(str(control_source)), GATES='\n'.join(settings_cases),
                            SETTINGS='\n'.join(function(source, name) for name in control_functions))
        for name, value in replacements.items():
            code = code.replace('@' + name + '@', value)
        self.assertEqual(native_output(code, data, engine_source=engine), '')

    def test_8020_player_binding_editor_confirmation_and_cancellation(self):
        data = {'engine': '8023'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        editor = function(source, 'keyboard_setup')
        branch = braced_statement(editor, 'if (obor_uses_8020_controls())')
        offset = editor.index(branch)
        editor = (editor[:offset + len(branch)] + '\n    abort();\n' +
                  editor[editor.index('finish_binding:', offset):])
        options_entry = function(source, 'menu_options_input')
        self.assertIn('obor_control_options_8020();', braced_statement(options_entry,
                                                                       'if (obor_uses_8020_controls())'))
        functions = '\n'.join(function(source, name) for name in ('obor_uses_8020_controls', 'safe_set',
                                                                  'obor_edit_player_bindings_8020'))
        code = Path(__file__).with_name('modern_8020_control_editor_contract.c.in').read_text()
        code = (code.replace('@FUNCTIONS@', functions + '\n' + editor)
                    .replace('@OPTIONS@', function(source, 'obor_control_options_8020'))
                    .replace('@MENU_CALL@', 'obor_control_options_8020'))
        self.assertEqual(native_output(code, data, engine_source=engine), '')

    def test_8020_startup_victory_and_video_rows(self):
        data = {'engine': '8023'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        startup = function(source, 'startup')
        begin = startup.index('    init_input_recorder();')
        end = startup.index('    printf("Loading translation', begin)
        video = function(source, 'menu_options_video')
        shift = re.search(r'(?m)^    const int row_shift = [^;]+;', video)
        self.assertIsNotNone(shift)
        positions = re.findall(r'(-?\d+ \+ row_shift),', video)
        self.assertEqual(len(positions), 23)
        code = r'''
#include "openbor.h"
#include <string.h>
#undef assert
#include <assert.h>
#undef printf

uint32_t obor_profile_build;
s_savedata savedata;
static char events[16];
static size_t event_count;
static int victory_frames;

static void mark(char event)
{
    assert(event_count + 1 < sizeof(events));
    events[event_count++] = event;
    events[event_count] = '\0';
}
static void victory_animation(entity *ent, int animation, int reset)
{
    assert(ent->idling == IDLING_NONE && animation == ANI_VICTORY && reset == 0);
    ++victory_frames;
}

#define init_input_recorder() mark('I')
#define load_all_fonts() mark('F')
#define load_special_sprites() mark('S')
#define load_levelorder() mark('L')
#define load_model_constants() mark('C')
#define load_menu_txt() mark('U')
#define load_script_setting() mark('T')
#define load_scripts() mark('R')
#define load_models() mark('M')
#define alloc_ents() (mark('E'), 1)
#define borShutdown(...) abort()
#define printf(...) ((void)0)
#define ent_set_anim victory_animation

@FUNCTIONS@

static void load_startup_items(void)
{
@STARTUP@
@LOGO@
}

static void check_video_rows(bool legacy)
{
@SHIFT@
    const int actual[] = {@POSITIONS@};
    const int modern[] = {-7,-5,-5,-4,-4,-3,-3,-2,-2,-1,-1,0,0,0,1,1,2,2,3,3,4,4,7};
    const int historical[] = {-5,-3,-3,-2,-2,-1,-1,0,0,1,1,2,2,2,3,3,4,4,5,5,6,6,9};
    const int *expected = legacy ? historical : modern;
    for (size_t row = 0; row < sizeof(actual) / sizeof(*actual); ++row)
        assert(actual[row] == expected[row]);
}

int main(void)
{
    static const uint32_t revisions[] = {8020, 8021, 8023};
    static entity actor;
    for (size_t i = 0; i < sizeof(revisions) / sizeof(*revisions); ++i)
    {
        obor_profile_build = revisions[i];
        const bool legacy = revisions[i] == 8020;
        event_count = 0;
        savedata.logo = 11;
        load_startup_items();
        assert(!strcmp(events, legacy ? "IFSLCTRMEU" : "ISLCUFTRME"));
        assert(savedata.logo == (legacy ? 0 : 1));
        for (int pain = 0; pain <= 1; ++pain)
        {
            actor.inpain = pain ? IN_PAIN_HIT : IN_PAIN_NONE;
            actor.idling = IDLING_ACTIVE;
            victory_frames = 0;
            tryvictorypose(&actor);
            assert(victory_frames == (legacy ? pain : !pain));
        }
        check_video_rows(legacy);
    }
    return 0;
}
'''
        functions = '\n'.join(function(source, name) for name in (
            'obor_uses_8020_controls', 'obor_load_startup_fonts', 'obor_load_startup_menu', 'tryvictorypose'))
        logo = braced_statement(startup, 'if(savedata.logo++ > 10)')
        # The logo decision follows the same profile selection as the asset order.
        replacements = dict(FUNCTIONS=functions, STARTUP=startup[begin:end], LOGO=logo,
                            SHIFT=shift[0], POSITIONS=', '.join(positions))
        for key, value in replacements.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, data, engine_source=engine), '')

    def test_original_credits_and_video_on_menu_return(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        shutdown = function(source, 'borShutdown')
        start = shutdown.index('savesettings();') + len('savesettings();')
        credits = shutdown[start:shutdown.index('if(startup_done)', start)]
        main = function(source, 'openborMain')
        translation = main.rindex('ob_inittrans();')
        opening = main.index('{', main.rindex('if(started)', 0, translation)) + 1
        restored = 'screen_status &= ~IN_SCREEN_TITLE;'
        menu = main[opening:main.index(restored, translation) + len(restored)]
        code = r'''
#include "openbor.h"
#include <stdlib.h>

uint32_t obor_profile_build;
static unsigned screen_status;
static int credits_calls, video_calls, translations;
static s_videomodes videomodes;

void display_credits(void)
{
    if (!(screen_status & IN_SCREEN_ENGINE_CREDIT))
    {
        abort();
    }
    ++credits_calls;
}

int video_set_mode(s_videomodes mode)
{
    if (translations || mode.hRes != videomodes.hRes)
    {
        abort();
    }
    ++video_calls;
    return 1;
}

void ob_inittrans(void) { ++translations; }

static void shutdown_credits(int status)
{
@CREDITS@
}

static void return_to_menu(void)
{
@MENU@
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7406, 7409, 7420, 7439, 7440, 7533};
    videomodes.hRes = 320;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        for (int status = 0; status <= 2; ++status)
        {
            screen_status = 0;
            credits_calls = 0;
            shutdown_credits(status);
            if (credits_calls != (builds[i] < 7409u && status != 2) ||
                !!(screen_status & IN_SCREEN_ENGINE_CREDIT) != (builds[i] < 7409u))
            {
                abort();
            }
        }

        screen_status = IN_SCREEN_TITLE;
        video_calls = translations = 0;
        return_to_menu();
        if (video_calls != (builds[i] >= 7440u) || translations != 1 || screen_status != IN_SCREEN_MENU)
        {
            abort();
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@CREDITS@', credits).replace('@MENU@', menu),
                                       data, engine_source=engine), '')

    def test_original_separate_device_mapping_files(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        paths = ('savesettings', 'saveasdefault', 'loadsettings', 'loadfromdefault')
        cases = []
        for operation, name in enumerate(paths):
            routine = function(source, name)
            gate = re.search(r'(?m)^    (if \([^\n]+\))\n    \{\n        obor_device_settings_io\(', routine)
            self.assertIsNotNone(gate)
            cases.append(f'case {operation}: {braced_statement(routine, gate[1])} break;')
        code = r'''
#include "openbor.h"
#include <stdlib.h>

uint32_t obor_profile_build;
static int calls, written, defaults_path;

bool control_uses_device_mappings(void)
{
    return obor_profile_build < 7404u;
}

static void obor_device_settings_io(int write, int defaults)
{
    ++calls;
    written = write;
    defaults_path = defaults;
}

static void dispatch(unsigned operation)
{
    switch (operation)
    {
@DISPATCH@
    }
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7402, 7403, 7404, 7420, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        for (unsigned operation = 0; operation < 4; ++operation)
        {
            calls = 0;
            dispatch(operation);
            if (calls != (builds[i] < 7403u) ||
                (calls && (written != (operation < 2) || defaults_path != (int)(operation % 2))))
            {
                abort();
            }
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@DISPATCH@', '\n'.join(cases)), data,
                                       engine_source=engine), '')

    def test_original_hall_of_fame_exit_keys(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        hall = function((engine / 'openbor.c').read_text(), 'hallfame')
        exit_checks = re.search(r'(?m)^        done \|= \(_time[^\n]*\n'
                                r'        done \|= \(bothnewkeys[^;]*;', hall)
        self.assertIsNotNone(exit_checks)
        code = r'''
#include "openbor.h"
#include <stdlib.h>

uint32_t obor_profile_build;

static int should_exit(u32 _time, uint64_t bothnewkeys)
{
    int done = 0;
@EXIT_CHECKS@
    return done != 0;
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7427, 7428, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        if (should_exit(0, FLAG_ATTACK) != (builds[i] >= 7428u) ||
            !should_exit(0, FLAG_START) || !should_exit(0, FLAG_ESC) ||
            should_exit(0, FLAG_MOVELEFT) || should_exit(GAME_SPEED * 8, 0) ||
            !should_exit(GAME_SPEED * 8 + 1, 0))
        {
            abort();
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@EXIT_CHECKS@', exit_checks[0]), data,
                                       engine_source=engine), '')

    def test_original_video_mode_message(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        log_line = re.findall(r'(?m)^        printf\([^;]*Initialized video[^;]*;', source)
        self.assertEqual(len(log_line), 1)
        code = r'''
#include "openbor.h"
#include <stdio.h>
#undef printf

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7406, 7409, 7420, 7533};
    const struct { int hRes, vRes; } videomodes = {320, 240};
    const int videoMode = 2;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        const unsigned obor_profile_build = builds[i];
@LOG@
    }
    return 0;
}
'''
        observed = native_output(code.replace('@LOG@', log_line[0]), data, engine_source=engine)
        self.assertEqual(observed, ''.join(
            f'Initialized video{"." * n}\t320x240 (Mode: 2)\n\n' for n in (13, 13, 13, 12, 12, 12)))

    def test_original_device_assignment_and_mapping_transactions(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        methods = ('safe_set', 'obor_keyboard_setup_devices', 'keyboard_setup',
                   'obor_assign_input_device', 'obor_menu_input_devices', 'menu_options_input')
        template = Path(__file__).with_name('legacy_device_menu_contract.c.in').read_text()
        code = template.replace('@MENUS@', '\n'.join(function(source, name) for name in methods))
        defaults = ('libretro_default_buttons', 'clearbuttons', 'clearsettings', 'apply_controls')
        code = code.replace('@DEFAULTS@', '\n'.join(function(source, name) for name in defaults))
        with tempfile.TemporaryDirectory(prefix='anybor-device-menu-') as directory:
            code = code.replace('@MAP_PATH@', json.dumps(str(Path(directory) / 'mappings.controls')))
            self.assertEqual(native_output(code, data, engine_source=engine), 'PASS\n')

    def test_native_menu_commit_cancel_and_default_with_core_managed_rumble(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        without_game_rumble = next(row['contract'] for row in data['sources']
                                   if row['revision'] < 7690)
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][without_game_rumble]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


    def test_rumble_strength_and_live_stop_across_engine_families(self):
        port = (ROOT / 'src/port/libretro/control.c').read_text()
        glue = (ROOT / 'src/glue/libretro.cpp').read_text()
        first = port.index('static int rumble_ratio[4]')
        last = port.rindex('static int rumble_ratio[4]')
        code = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include "libretro.h"
#define OBOR_MAX_PLAYERS 4
static uint32_t obor_profile_build;
static long g_frame_no;
static bool g_rumble_have = true, g_rumble_on = true;
static uint64_t g_rumble_off_at[4];
static struct retro_rumble_interface g_rumble_if;
static int last_strength[2], events;

typedef struct { int deviceID; } s_playercontrols;
static s_playercontrols controls[4];
static s_playercontrols *playercontrolpointers[] = {
    &controls[0], &controls[1], &controls[2], &controls[3]
};
static bool control_uses_device_mappings(void) { return false; }
static bool control_isvaliddevice(int id) { return id >= 0 && id < 4; }

@PORT@
#define p_get_rumble obor_get_rumble
@FRAME@

static bool record(unsigned port, enum retro_rumble_effect effect, uint16_t strength)
{
    assert(port == 0);
    assert(effect == RETRO_RUMBLE_STRONG || effect == RETRO_RUMBLE_WEAK);
    last_strength[effect] = strength;
    ++events;
    return true;
}

static void hit(void)
{
#if OBOR_ENGINE_BUILD >= 5000
    control_rumble(0, 1, 34);
#else
    control_rumble(0, 34);
#endif
    rumble_frame();
}

int main(void)
{
    g_rumble_if.set_rumble_state = record;
#if OBOR_ENGINE_BUILD == 6391
    obor_profile_build = 6228;
    hit();
    assert(!events);
    obor_profile_build = 6229;
#endif
    hit();
    assert(events == 2 && last_strength[0] == UINT16_MAX && last_strength[1] == UINT16_MAX);
    g_frame_no = 1;
    g_rumble_on = false;
    hit();
    assert(events == 4 && !last_strength[0] && !last_strength[1]);
    hit();
    assert(events == 4);
    g_rumble_on = true;
    hit();
    assert(events == 6 && last_strength[0] == UINT16_MAX && last_strength[1] == UINT16_MAX);
    g_frame_no = 3;
    rumble_frame();
    assert(events == 6);
    g_frame_no = 4;
    rumble_frame();
    assert(events == 8 && !last_strength[0] && !last_strength[1]);
    return 0;
}
"""
        for build in ('4432', '6391', '7142', '7533', '8023'):
            with self.subTest(build=build):
                if build == '8023':
                    events = port[first:port.index('\n#else\n', first)]
                else:
                    events = port[last:port.rindex('#endif /* OBOR_ENGINE_BUILD')]
                source = code.replace('@PORT@', events).replace('@FRAME@', function(glue, 'rumble_frame'))
                self.assertEqual(native_output(source, {'engine': build},
                    extra_includes=(ROOT / 'src/third_party',)), '')


class ClassicControlMenuContracts(unittest.TestCase):
    def check_control_menu(self, engine_id):
        data = load_contract_fixture(FIXTURE.with_name('classic-control-menu-contracts.json'))
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        fields = ('revision', 'has_default', 'has_default_keyboard', 'label_input_length',
                  'label_display_length', 'stretch_default')
        values = dict(MENU=function(source, 'keyboard_setup'),
                      TRANSLATE=function(source, 'translate_SDID'),
                      DEFAULTS=function(source, 'clearbuttons') if engine_id == '6391' else '',
                      CLEAR_SETTINGS=function(source, 'clearsettings'),
                      ROWS=',\n'.join('{' + ','.join(str(row[k]) for k in fields) + '}' for row in rows))
        template = Path(__file__).with_name('classic_control_menu_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': engine_id}, engine_source=engine,
                               extra_cflags=('-DLINUX=1', '-fgnu89-inline'))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_control_menu(self):
        self.check_control_menu('4432')

    def test_6391_control_menu(self):
        self.check_control_menu('6391')


if __name__ == '__main__':
    unittest.main()
