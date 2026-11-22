"""Check native boot order, settings defaults and animated-image cleanup.

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
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-boot-flow-contracts.json'


def program(data, kind):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    if kind not in ('startup', 'defaults', 'android', 'gif'):
        raise ValueError('Declared boot contract kind required')
    name, template = {'startup': ('startup', 'modern_boot_schedule_contract.c.in'),
        'defaults': ('clearsettings', 'modern_boot_defaults_contract.c.in'),
        'android': ('clearsettings', 'modern_boot_defaults_contract.c.in'),
        'gif': ('playgif', 'modern_gif_cleanup_contract.c.in')}[kind]
    parts = dict(FUNCTION=function(core, name),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name(template).read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native boot dependency')
    return ('#define ANDROID 1\n' if kind == 'android' else '') + code


class ModernBootFlowContracts(unittest.TestCase):
    def run_contract(self, kind):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']][kind]) for row in data['sources']])
        engine_source = os.environ.get('OBOR_HISTORICAL_ENGINE')
        self.assertEqual(json.loads(native_output(program(data, kind), data, engine_source=engine_source)), expected)

    def test_font_order_and_model_font_override(self):
        self.run_contract('startup')

    def test_original_lifebar_color_source_order(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#include <assert.h>

uint32_t obor_profile_build;
int color_black, color_red, color_orange, color_yellow, color_white, color_blue;
int color_green, color_pink, color_purple, color_magic, color_magic2, colorbars;
int shadowcolor, shadowalpha, shadowopacity;
static unsigned calls, available, loaded;

int buffer_pakfile(char *name, char **data, size_t *length)
{
    unsigned kind;
    if (strcmp(name, "saves/lifebar.txt") == 0)
        kind = 1;
    else
    {
        assert(strcmp(name, "data/lifebar.txt") == 0);
        kind = 2;
    }
    calls = calls * 10 + kind;
    if (!(available & kind)) return 0;
    loaded = kind;
    *data = NULL;
    *length = 0;
    return 1;
}

#undef GET_ARG
#undef GET_INT_ARG
#undef stricmp
#define GET_ARG(index) ((char *)NULL)
#define GET_INT_ARG(index) 0
#define ParseArgs(...) 0
#define getNewLineStart(...) 1
#define _makecolour(...) 0
#define stricmp strcmp

@LIFEBAR@

int main(void)
{
    static const unsigned profiles[] = {7369, 7391, 7420, 7475, 7477, 7533};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int external_first = profiles[i] >= 7477u;
        for (available = 0; available < 4; ++available)
        {
            calls = loaded = colorbars = 0;
            color_red = 70;
            lifebar_colors();
            const unsigned expected = external_first && (available & 1) ? 1 : available & 2;
            assert(loaded == expected);
            assert(calls == (external_first ? (expected == 1 ? 1u : 12u) : 2u));
            assert(colorbars == (expected != 0));
            assert(color_red == (expected == 0 ? 0 : 70));
        }
    }
    return 0;
}
'''
        code = code.replace('@LIFEBAR@', function(source, 'lifebar_colors'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_native_settings_defaults(self):
        self.run_contract('defaults')

    def test_android_native_settings_defaults(self):
        self.run_contract('android')

    def test_animated_image_cleanup_and_palette_retention(self):
        self.run_contract('gif')


if __name__ == '__main__':
    unittest.main()
