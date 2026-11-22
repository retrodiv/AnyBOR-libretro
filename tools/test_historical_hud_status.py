"""Check the native HUD tail and Start-to-selection routes by source revision.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-hud-status-contracts.json'
HUD_VARIANTS = FIXTURE.with_name('profile-6391-hud-variants.json')


def program(data, source=None):
    if source is None:
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
    predraw = function(source, 'predrawstatus')
    start = predraw.index('    }// end of for\n') + len('    }// end of for\n')
    values = {
        'UPDATE': ('\n'.join(function(source, name) for name in
                             ('obor_profile_name_limit', 'obor_profile_copy_name'))
                   if 'obor_profile_copy_name(' in source else '') + function(source, 'updatestatus'),
        'STATUS_TAIL': predraw[start:predraw.rindex('}')],
        'VISUAL_DEBUG': function(source, 'obor_collision_attack_frame') + '\n' +
                        function(source, 'draw_visual_debug'),
        'PERFORMANCE': function(source, 'obor_draw_status_performance')
                       if 'static void obor_draw_status_performance(' in source else '',
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    template = Path(__file__).with_name('hud_status_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class HistoricalHudStatusTests(unittest.TestCase):
    def test_native_overlay_order_and_entry(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        observed = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(observed), len(rows))
        for actual, row in zip(observed, rows):
            expected = data['contracts'][row['contract']]
            with self.subTest(revision=row['revision']):
                self.assertEqual(actual['revision'], row['revision'])
                self.assertEqual(actual['overlay'], expected['overlay'])
                self.assertEqual(actual['join'], expected['join'])

    def test_6391_original_join_credit_prompt(self):
        self.check_join_credit_prompt(FIXTURE.with_name('profile-6391-join-credit-prompt.json'))

    def test_6391_join_credit_boundaries(self):
        self.check_join_credit_prompt(HUD_VARIANTS)

    def check_join_credit_prompt(self, fixture):
        data = load_contract_fixture(fixture)
        rows = data['sources']
        self.assertEqual({row['revision'] for row in rows}, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        predraw = function(source, 'predrawstatus')
        branch = re.search(r'(?ms)^        else (if\(player\[i\]\.credits \|\| credits \|\| '
                           r'\(!player\[i\]\.hasplayed && noshare\)\).*?)(?=^    \}// end of for)', predraw)[1]
        checks = []
        for row in rows:
            for case, expected in zip(data['cases'], data['messages'][row['family']], strict=True):
                values = ','.join(str(value) for value in case)
                checks.append(f'check({row["revision"]}u,{values},{json.dumps(expected)});')
        template = Path(__file__).with_name('join_credit_prompt_contract.c.in').read_text()
        code = template.replace('@CREDIT_BRANCH@', branch).replace('@CHECKS@', '\n    '.join(checks))
        count = len(rows) * len(data['cases'])
        self.assertEqual(native_output(code, data, engine_source=engine), f'PASS {count}\n')

    def test_6391_original_performance_overlay(self):
        self.check_performance_overlay(FIXTURE.with_name('profile-6391-performance-overlay.json'))

    def test_6391_performance_layer_and_unit_boundaries(self):
        self.check_performance_overlay(HUD_VARIANTS)

    def check_performance_overlay(self, fixture):
        from test_early_jump_walkoff import braced_statement
        data = load_contract_fixture(fixture)
        rows = data['sources']
        self.assertEqual({row['revision'] for row in rows}, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        utilities = (engine / 'source/utils.c').read_text(encoding='latin1')
        predraw = function(source, 'predrawstatus')
        branch = braced_statement(predraw, 'if(savedata.debuginfo)')
        contexts = ',\n'.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['box_layer'], row['text_layer'],
                                data['free_bytes'] // row['byte_divisor'], data['used_bytes'] // row['byte_divisor'])
                                for row in rows)
        template = Path(__file__).with_name('performance_overlay_contract.c.in').read_text()
        code = (template.replace('@SUBJECT@', branch).replace('@FORMAT@', function(utilities, 'commaprint'))
                .replace('@CONTEXTS@', contexts).replace('@FREE_BYTES@', str(data['free_bytes']))
                .replace('@USED_BYTES@', str(data['used_bytes'])))
        self.assertEqual(native_output(code, data, engine_source=engine), f'PASS {len(rows)}\n')

    def test_6391_original_entity_collision_overlay(self):
        from test_early_jump_walkoff import braced_statement
        data = load_contract_fixture(HUD_VARIANTS)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        gate = braced_statement(function(source, 'predrawstatus'), 'if(savedata.debug_position')
        cases = '\n    '.join('check(%du, %du);' % (row['revision'], row['entity_collision_draw'])
                             for row in rows)
        template = Path(__file__).with_name('entity_collision_overlay_contract.c.in').read_text()
        code = (template.replace('@DRAW@', function(source, 'draw_visual_debug'))
                .replace('@ENTRY@', gate).replace('@CASES@', cases))
        self.assertEqual(native_output(code, data, engine_source=engine),
                         ''.join(f'PASS {revision}\n' for revision in revisions))

    def test_7533_original_graph_options_and_popup_alignment(self):
        from test_early_jump_walkoff import braced_statement

        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        script = (engine / 'openborscript.c').read_text(encoding='latin1')
        change_property = function(script, 'openbor_changeentityproperty')
        caller = function(source, 'display_ents')
        level_order = function(source, 'load_levelorder')
        start = level_order.index('    lbarstatus.size.x  = mpbarstatus.size.x = 100;')
        stop = level_order.index('    // Show Complete Default Values', start)
        methods = ('isNumeric', 'getValidInt', 'ParseArgs', 'bar_status_read_legacy_mode', '_readbarstatus',
                   'bar_status_allocate_object', 'bar', 'drawenemystatus')
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        load = '\n'.join('case CMD_MODEL_' + name + ':' + cases['CMD_MODEL_' + name]['body']
                         for name in ('LIFEPOSITION', 'NAMEPOSITION', 'LIFEBARSTATUS'))
        initializers = '\n'.join(re.search(
            r'(?ms)^s_barstatus ' + names + r'\s*=\s*\{.*?^\};', source)[0]
            for names in ('loadingbarstatus', 'lbarstatus, olbarstatus', 'mpbarstatus'))
        change = '\n'.join(braced_statement(change_property, 'case _ep_' + name + ':')
                           for name in ('lifeposition', 'nameposition'))
        template = Path(__file__).with_name('legacy_hud_bar_contract.c.in').read_text()
        code = (template.replace('@METHODS@', '\n\n'.join(function(source, name) for name in methods))
                .replace('@MODEL_COMMANDS@', load).replace('@SCRIPT_PROPERTIES@', change)
                .replace('@INITIALIZERS@', initializers)
                .replace('@DISPLAY@', braced_statement(caller, 'if(e->modeldata.hud_popup &&'))
                .replace('@LEVEL_DEFAULTS@', level_order[start:stop]))
        self.assertEqual(native_output(code, data, engine_source=engine,
                                       extra_cflags=('-Wno-implicit-fallthrough',)), 'PASS 11\n')

    def test_7533_original_go_cue_visibility_and_sound(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        update = function(source, 'updatestatus')
        draw = function(source, 'predrawstatus')
        eligibility = re.search(r'if\s*\((global_config\.showgo)\)', draw)[1]
        _, properties = switch_cases(script, 'getsyspropertybyindex', 'index', outermost=True)
        code = r'''
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build, go_time;
s_savedata savedata;
s_global_config global_config;
s_global_sample global_sample_list;
e_screen_status screen_status;
static int gosound, cues;

int sound_play_sample(int sample, unsigned int priority, int left, int right, unsigned int speed)
{
    assert(sample == 3 && priority == 0 && left == 27 && right == 27 && speed == 100);
    return ++cues;
}

void ScriptVariant_ChangeType(ScriptVariant *var, VARTYPE type)
{
    var->vt = type;
}

static void update_cue(uint32_t _time)
{
    int dt;
    @UPDATE@
}

@ADMISSION@

static int visible_in_script(void)
{
    if (obor_profile_build < obor_system_property_first_build(SYSTEM_PROPERTY_SHOWGO)) return -1;
    ScriptVariant result = {.vt = VT_EMPTY}, *var = &result;
    switch (SYSTEM_PROPERTY_SHOWGO)
    {
    case SYSTEM_PROPERTY_SHOWGO:
        @GETTER@
    }
    assert(result.vt == VT_INTEGER);
    return result.lVal;
}

static void check_cue(uint32_t now, int visible, int sound, int total)
{
    update_cue(now);
    assert(visible_in_script() == (obor_profile_build < 7409u ? -1 : visible));
    assert((@DRAW@ != 0) == visible);
    assert(screen_status == (IN_SCREEN_GAME_OVER | (visible ? IN_SCREEN_SHOW_GO_ARROW : 0)));
    assert(gosound == sound && cues == total);
}

int main(void)
{
    static const unsigned profiles[] = {7369, 7391, 7406, 7409, 7412, 7413, 7420, 7533};
    savedata.effectvol = 27;
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        go_time = 3u * GAME_SPEED;
        screen_status = IN_SCREEN_GAME_OVER;
        global_sample_list.go = 3;
        gosound = cues = 0;
        check_cue(GAME_SPEED, 1, 1, 1);
        check_cue(GAME_SPEED + 1, 0, 0, 1);
        check_cue(GAME_SPEED + GAME_SPEED / 2 + 1, 1, 1, 2);
        check_cue(2 * GAME_SPEED, 1, 1, 2);
        check_cue(go_time, 0, 1, 2);
        global_sample_list.go = -1;
        gosound = 0;
        check_cue(2 * GAME_SPEED, 1, 1, 2);
    }
    return 0;
}
'''
        code = (code.replace('@UPDATE@', update[update.index('if(go_time > _time)'):update.rfind('}')])
                .replace('@ADMISSION@', function(script, 'obor_system_property_first_build'))
                .replace('@GETTER@', properties['SYSTEM_PROPERTY_SHOWGO']['body'])
                .replace('@DRAW@', eligibility))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')


if __name__ == '__main__':
    unittest.main()
