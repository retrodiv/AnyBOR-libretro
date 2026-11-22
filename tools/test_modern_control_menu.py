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

    def test_native_menu_commit_cancel_default_and_rumble(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


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
