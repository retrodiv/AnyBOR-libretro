"""Check native layer defaults, repeat parsing and script round trips.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-layer-repeat-contracts.json'


def parser_window(source, first, last):
    start = source.index(first)
    end = source.index(last, start)
    return source[start:end]


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    level = function(core, 'load_level')
    layer = parser_window(level, 'case CMD_LEVEL_BACKGROUND:', 'case CMD_LEVEL_WATER:')
    water = level[level.index('case CMD_LEVEL_WATER:'):]
    panel = level[level.index('case CMD_LEVEL_FRONTPANEL:'):]
    parts = dict(NAN=re.search(r'(?m)^#define NaN[^\n]*', core)[0],
        ENUMS='\n'.join(re.search(r'(?m)^enum '+name+r'\s*\{[\s\S]*?^};', script)[0]
                         for name in ('getlt_enum', 'getbglp_enum')),
        MACRO=re.search(r'(?m)^#define MAPSTRINGS\([^\n]*(?:\n[^\n]*)*?\n}', script)[0],
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue',
             'ScriptVariant_DecimalValue')),
        FUNCTIONS='\n'.join(function(script, name) for name in
            ('mapstrings_layerproperty', '_getlayerproperty', '_changelayerproperty',
             '_getlayer', 'openbor_getlayerproperty', 'openbor_changelayerproperty')),
        NORMALIZER=function(core, 'load_layer'),
        LAYER=parser_window(layer, 'if(cmd==CMD_LEVEL_BACKGROUND || cmd==CMD_LEVEL_BGLAYER)',
                            'if(blendfx_is_set==0'),
        WATER=parser_window(water, 'dm = &(bgl->drawmethod);', 'load_layer(GET_ARG(1)'),
        PANEL=parser_window(panel, 'if(bgl->oldtype==bgt_panel)', 'load_layer(GET_ARG(1)'),
        CONTEXTS=','.join('{%du,%d,%d,%d,%s}' % (row['revision'], row['all_speed_default'],
                         row['legacy_layer_type'], row['water_depth'], row['front_zratio'])
                         for row in data['sources']))
    start = core.index('const s_drawmethod plainmethod = {')
    parts['PLAIN'] = core[start:core.index('\n};', start)+3]
    text = Path(__file__).with_name('layer_repeat_contract.c.in').read_text()
    for name, value in parts.items():
        text = text.replace('@'+name+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native layer repeat dependency')
    return text


def diagnostic_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    text = Path(__file__).with_name('layer_diagnostic_contract.c.in').read_text()
    values = dict(FUNCTIONS='\n'.join(function(script, n) for n in
        ('openbor_getlayerproperty', 'openbor_changelayerproperty')),
        INTEGER=function(variant, 'ScriptVariant_IntegerValue'),
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['split_errors'])
                          for r in data['sources']))
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved layer diagnostic dependency')
    return text


class LayerRepeatContracts(unittest.TestCase):
    def test_native_parser_normalizer_and_script_round_trips(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], cases=175) for r in data['sources']])

    def test_native_script_layer_error_diagnostics(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-layer-diagnostic-contracts.json')
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(diagnostic_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], diagnostic_cases=18)
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
