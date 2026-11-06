"""Check native screen/sprite repeats and historical drawmethod properties.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-draw-repeat-contracts.json'


def fill(name, parts):
    text = Path(__file__).with_name(name).read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native draw repeat dependency')
    return text


def contexts(data, script=False):
    if script:
        fields = []
        names = {}
        for i, (key, value) in enumerate(data['contracts'].items()):
            names[key] = 'fields_'+str(i)
            fields.append('static const char *const '+names[key]+'[]={'+
                          ','.join(json.dumps(x) for x in value)+'};')
        rows = ['{%du,%d,%s,%d}' % (r['revision'], r['available'], names[r['contract']],
                 len(data['contracts'][r['contract']])) for r in data['sources']]
        return '\n'.join(fields), ','.join(rows)
    return ','.join('{%du,%d,%d,%d}' % (r['revision'], r['repeat_mode'],
                       r['screen_transform'], r['offset_fastcopy']) for r in data['sources'])


def render_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    screen = (engine / 'source/gamelib/screen.c').read_text()
    sprite = (engine / 'source/gamelib/sprite.c').read_text()
    pixels = (engine / 'source/gamelib/pixelformat.c').read_text()
    core = (engine / 'openbor.c').read_text()
    start = core.index('const s_drawmethod plainmethod = {')
    return fill('draw_repeat_render_contract.c.in', dict(
        CONTEXTS=contexts(data), PLAIN=core[start:core.index('\n};', start)+3],
        FUNCTIONS='\n'.join([function(pixels, 'obor_profile_blend_count'),
            function(pixels, 'drawmethod_global_init'), function(screen, 'obor_screen_blend_table'),
            function(screen, '_putscreen'), function(screen, 'putscreen'),
            function(sprite, '_putsprite'), function(sprite, 'putsprite')])))


def script_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    core = (engine / 'openbor.c').read_text()
    start = core.index('const s_drawmethod plainmethod = {')
    fields, rows = contexts(data, script=True)
    return fill('draw_repeat_script_contract.c.in', dict(
        FIELDS=fields, CONTEXTS=rows, PLAIN=core[start:core.index('\n};', start)+3],
        ENUM=re.search(r'(?m)^enum drawmethod_enum\s*\{[\s\S]*?^};', source)[0],
        MACRO=re.search(r'(?m)^#define MAPSTRINGS\([^\n]*(?:\n[^\n]*)*?\n}', source)[0],
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        VARIANTS='\n'.join(function(variant, x) for x in ('ScriptVariant_Clear',
            'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        FUNCTIONS='\n'.join(function(source, x) for x in
                           ('mapstrings_drawmethodproperty', 'openbor_changedrawmethod'))))


def route_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    methods = '\n'.join(function(source, name) for name in
                        ('obor_script_function_available', 'Script_GetStringMapFunction'))
    names = sorted(set(re.findall(r'\(void\*\)\s*([A-Za-z_]\w*)', methods)))
    if not {'openbor_changedrawmethod', 'mapstrings_drawmethodproperty'} <= set(names):
        raise ValueError('Complete native function and mapper route required')
    return ('#include <stdint.h>\n#include <stdlib.h>\nuint32_t obor_profile_build;\n'+
        '\n'.join('static void '+x+'(void){}' for x in names)+'\n'+methods+
        '\nint main(void){\n'+
        '\n'.join('obor_profile_build=%du;if(obor_script_function_available((void*)openbor_changedrawmethod)!=%d || '
            'Script_GetStringMapFunction((void*)openbor_changedrawmethod)!=%s)abort();' %
            (r['revision'], r['available'], '(void*)mapstrings_drawmethodproperty' if r['available']
             else 'NULL') for r in data['sources'])+'return 0;}\n')


class DrawRepeatContracts(unittest.TestCase):
    def fixture(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        return data

    def test_native_copy_coordinates_transform_and_offset_boundaries(self):
        data = self.fixture()
        rows = [json.loads(x) for x in native_output(render_program(data), data).splitlines()]
        self.assertEqual(rows, [dict(revision=r['revision'], cases=1458) for r in data['sources']])

    def test_native_property_names_numbers_targets_and_values(self):
        data = self.fixture()
        rows = [json.loads(x) for x in native_output(script_program(data), data).splitlines()]
        self.assertEqual(rows, [dict(revision=r['revision'], cases=(
            6*len(data['contracts'][r['contract']])+13+
            (16 if 'xrepeat' in data['contracts'][r['contract']] else 0)) if r['available'] else 0)
            for r in data['sources']])

    def test_native_compiler_mapper_and_function_availability(self):
        data = self.fixture()
        native_output(route_program(data), data)


if __name__ == '__main__':
    unittest.main()
