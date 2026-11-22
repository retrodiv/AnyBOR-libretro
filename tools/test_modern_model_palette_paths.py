"""Check native model palette commands and controlled cleanup diagnostics.

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
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-model-palette-paths.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    body = function((engine / 'openbor.c').read_text(), 'load_cached_model')
    start = body.index('            case CMD_MODEL_PALETTE:')
    end = body.index('            case CMD_MODEL_GLOBALMAP:', start)
    cleanup = body[body.index('lCleanup:'):body.rfind('}')]
    cleanup = cleanup.replace('lCleanup:',
        'lCleanup:\n    cleanup_owners[3]=mapflag;\n    (void)nopalette;', 1)
    parts = dict(COMMANDS=body[start:end], CLEANUP=cleanup,
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_model_palette_paths_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved model palette input')
    return code


class ModernModelPalettePaths(unittest.TestCase):
    def test_original_remap_capacity_message(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        assignment, = [line for line in re.findall(r'\bvalue2\s*=\s*[^;]+;', cases['CMD_MODEL_REMAP']['body'])
                       if 'Color maps full error' in line]
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>

uint32_t obor_profile_build;

static const char *remap_message(void)
{
    const char *value2;
    @ASSIGNMENT@
    return value2;
}

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7491, 7492, 7533};
    for (unsigned i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const char *ending = strstr(remap_message(), "console");
        assert(ending && strcmp(ending, builds[i] < 7492u ? "console!" : "console)!") == 0);
    }
    return 0;
}
'''
        code = code.replace('@ASSIGNMENT@', assignment)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_parent_color_selection(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>

@METHODS@

int main(void)
{
    static entity actor;
    static entity parent;
    static unsigned char base, actor_first, actor_second, parent_base, parent_first, parent_second;
    unsigned char *actor_maps[] = {&actor_first, &actor_second};
    unsigned char *parent_maps[] = {&parent_first, &parent_second};
    actor.modeldata.palette = &base;
    actor.modeldata.colourmap = actor_maps;
    actor.modeldata.maps_loaded = 2;
    parent.modeldata.palette = &parent_base;
    parent.modeldata.colourmap = parent_maps;
    parent.modeldata.maps_loaded = 2;

    apply_color_set_adjust(&actor, &parent, 2);
    assert(actor.map == 2 && actor.colourmap == &actor_second);
    apply_color_set_adjust(&actor, &parent, COLORSET_ADJUST_NONE);
    assert(actor.map == 2 && actor.colourmap == &actor_second);

    parent.colourmap = &parent_first;
    apply_color_set_adjust(&actor, &parent, COLORSET_ADJUST_PARENT_INDEX);
    assert(actor.map == 0 && actor.colourmap == &base);
    parent.colourmap = &parent_second;
    apply_color_set_adjust(&actor, &parent, COLORSET_ADJUST_PARENT_INDEX);
    assert(actor.map == 1 && actor.colourmap == &actor_first);
    apply_color_set_adjust(&actor, &parent, COLORSET_ADJUST_PARENT_TABLE);
    assert(actor.map == 1 && actor.colourmap == &parent_second);
    parent.colourmap = &parent_base;
    apply_color_set_adjust(&actor, &parent, COLORSET_ADJUST_PARENT_INDEX);
    assert(actor.map == 1 && actor.colourmap == &parent_second);
    return 0;
}
'''
        methods = ('ent_set_colourmap', 'apply_color_set_adjust')
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_ko_palette_directives_and_original_palette_selection(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, commands = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        ko_cases = ('CMD_MODEL_KOMAP', 'CMD_MODEL_MAP_KO_TYPE')
        methods = ('isNumeric', 'getValidInt', 'komap_type_get_value_from_argument',
                   'model_get_colourmap', 'is_map_hidden', 'nextcolourmap', 'nextcolourmapn',
                   'prevcolourmap', 'prevcolourmapn')
        code = r'''
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#include "source/openborscript/commands.h"
#undef printf
#undef stricmp
#define stricmp strcasecmp
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static s_set_entry rules = {.nosame = 2};
s_set_entry *levelsets = &rules;
s_player player[MAX_PLAYERS];
int current_set;
int colourselect = 1;

@METHODS@

static void read_ko(s_model *newchar, int combined, char *value)
{
    char *filename = "model.txt";
    char *command = combined ? "komap" : "palette.ko.type";
    ArgList arglist = {.count = 2, .args = {command, value}};
    if (combined)
    {
        arglist.count = 3;
        arglist.args[1] = "2";
        arglist.args[2] = value;
    }
    switch (combined ? CMD_MODEL_KOMAP : CMD_MODEL_MAP_KO_TYPE)
    {
        @COMMANDS@
        default:
            abort();
    }
}

static void apply_ko(entity *acting_entity)
{
    @APPLY@
}

int main(void)
{
    static entity actor;
    static unsigned char palette, frozen, ko;
    static unsigned char *maps[] = {&frozen, &ko};
    actor.modeldata.palette = &palette;
    actor.modeldata.colourmap = maps;
    actor.modeldata.maps_loaded = 2;

    static const uint32_t builds[] = {7369, 7373, 7374, 7391, 7420, 7470, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        for (int combined = 0; combined <= 1; ++combined)
        {
            actor.modeldata.colorsets.ko = combined ? COLORSET_INDEX_NONE : 2;
            read_ko(&actor.modeldata, combined, "0");
            assert(actor.modeldata.colorsets.ko == 2);
            assert(actor.modeldata.colorsets.kotype == KO_COLORSET_CONFIG_INSTANT);
            read_ko(&actor.modeldata, combined, "1");
            assert(actor.modeldata.colorsets.kotype == KO_COLORSET_CONFIG_COMPLETE);
            read_ko(&actor.modeldata, combined, "finish");
            actor.colourmap = &palette;
            actor.animating = 1;
            apply_ko(&actor);
            assert(actor.colourmap == (builds[i] < 7374 ? &ko : &palette));
            actor.animating = 0;
            apply_ko(&actor);
            assert(actor.colourmap == &ko);
            read_ko(&actor.modeldata, combined, "instant");
            assert(actor.modeldata.colorsets.kotype == KO_COLORSET_CONFIG_INSTANT);
        }
    }

    s_model roster = {.maps_loaded = 7,
        .colorsets = {.frozen = 1, .ko = 2, .hide_start = 3, .hide_end = 4}};
    strcpy(player[0].name, "hero");
    strcpy(player[1].name, "HERO");
    player[1].colourmap = 5;
    assert(nextcolourmapn(&roster, 0, 0) == 6);
    assert(prevcolourmapn(&roster, 6, 0) == 0);
    rules.nosame = 0;
    assert(nextcolourmapn(&roster, 0, 0) == 5);
    assert(prevcolourmapn(&roster, 6, 0) == 5);
    puts("PASS");
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        code = code.replace('@COMMANDS@', '\n'.join('case ' + name + ':\n' + commands[name]['body']
                                                    for name in ko_cases))
        code = code.replace('@APPLY@', braced_statement(function(source, 'common_lie'),
                            'if (acting_entity->modeldata.colorsets.ko != COLORSET_INDEX_NONE)'))
        output = native_output(code, {'engine': '7533'}, engine_source=engine)
        warnings = ''.join(f'WARNING: model.txt tries to load a non-numeric value at {command}, '
                           f'where a number is expected!\nerroneus string: {value}\n'
                           for command in ('palette.ko.type', 'komap') for value in ('finish', 'instant'))
        self.assertEqual(output, warnings * 2 + 'PASS\n')

    def test_native_model_palette_result_and_cleanup(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
