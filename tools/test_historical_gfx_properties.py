"""Check native graphics property names, numbers, values and compiler route.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-gfx-property-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    enum = re.search(r'(?m)^enum gfxproperty_enum\s*\{[\s\S]*?^};', script)
    macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]*(?:\n[^\n]*)*?\n}', script)
    if enum is None or macro is None:
        raise ValueError('Complete native graphics enum and mapping macro required')
    cases = []
    for row in data['cases']:
        if row['format'] not in data['formats'] or not re.fullmatch(r'[a-z_]+', row['name']):
            raise ValueError('Declared format and bounded property token required')
        cases.append('{%s,%s,%s}' % (
            ','.join(str(row[key]) for key in data['parameters']),
            row['format'], json.dumps(row['name'])))
    parts = dict(ENUM=enum[0], MACRO=macro[0],
        FUNCTIONS='\n'.join(function(script, name) for name in
                            ('mapstrings_gfxproperty', 'openbor_getgfxproperty')),
        VARIANTS='\n'.join(function(variant, name) for name in
                           ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], bool(data['contracts'][row['contract']]))
                          for row in data['sources']), CASES=',\n'.join(cases))
    text = Path(__file__).with_name('gfx_property_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native graphics dependency')
    return text


def route_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    method = function(source, 'Script_GetStringMapFunction')
    symbols = sorted(set(re.findall(r'\(void\*\)\s*([A-Za-z_]\w*)', method)))
    if not 4 <= len(symbols) <= 128 or not {'openbor_getgfxproperty', 'mapstrings_gfxproperty'} <= set(symbols):
        raise ValueError('Bounded compiler mapper route required')
    return ('#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n'
        'uint32_t obor_profile_build;\n'+
        '\n'.join('static void '+name+'(void){}' for name in symbols)+
        '\nstatic void unknown(void){}\n'+method+'\nint main(void){\n'+
        '\n'.join('obor_profile_build=%du;if(Script_GetStringMapFunction((void*)openbor_getgfxproperty)'
                  '!=%s || Script_GetStringMapFunction((void*)unknown)!=NULL)abort();' %
                  (row['revision'], '(void*)mapstrings_gfxproperty' if data['contracts'][row['contract']]
                   else 'NULL') for row in data['sources'])+'return 0;}\n')


def expected(case, fields, data):
    named = case['mode'] != 3
    name = case['name']
    mapped = named and name in fields and case['argc'] >= 2
    index = fields.index(name) if mapped else 63 if named else case['index']
    result = dict(ok=1, present=1, kind='integer', value=0, mapped=int(mapped or not named),
                  index=index, collects=int(mapped), diagnostics=0, message='', pixels=0, x=0, y=0)
    if named and not mapped and case['argc'] >= 2:
        shown = name.upper() if case['mode'] in (1, 2) else name
        result.update(diagnostics=2 if case['mode'] == 2 else 1,
                      message="Property name '%s' is not supported by gfxproperty.\n" % shown)
    def fail(message):
        result.update(ok=0, present=0, kind='none', value=0,
                      diagnostics=result['diagnostics']+1, message=message)
        return result
    if case['argc'] < 2 or case['handle'] in (1, 2):
        return fail('Function getgfxproperty must have a valid handle and a property name.\n')
    field = fields[index] if 0 <= index < len(fields) else None
    if field is None:
        return result
    if case['handle'] == 3:
        return fail('Function getgfxproperty encountered an invalid handle.\n')
    sprite = case['shape'] == 2
    width = 5 if case['shape'] == 1 else 3
    height = 2 if case['shape'] != 0 else 1
    if field == 'pixel':
        if case['argc'] < 4:
            return fail('You need to specify x, y value for getgfxproperty.\n')
        if case['coordinate_kind'] == 2:
            return fail('Invalid x or y value for getgfxproperty.\n')
        x, y = case['x'], case['y']
        if 0 <= x < width and 0 <= y < height:
            if sprite:
                result.update(pixels=1, x=x, y=y, value=200+x+3*y)
            else:
                pos=y*width+x
                result['value'] = ((100+17*pos) & 255 if case['format'] in ('PIXEL_8', 'PIXEL_x8')
                    else 0x8000+pos if case['format'] == 'PIXEL_16' else -0x80000000+pos)
    elif field == 'palette':
        result.update(kind='pointer', value=1)
    else:
        result['value'] = dict(width=width, height=height,
            srcwidth=7 if sprite else width, srcheight=9 if sprite else height,
            centerx=-2 if sprite else 0, centery=4 if sprite else 0,
            pixelformat=data['formats'][case['format']])[field]
    return result


class GraphicsPropertyContracts(unittest.TestCase):
    def test_native_names_numbers_results_and_diagnostics(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        wanted = [(row, i, case) for row in data['sources'] if data['contracts'][row['contract']]
                  for i, case in enumerate(data['cases'])]
        self.assertEqual(len(actual), len(wanted))
        for result, (row, i, case) in zip(actual, wanted):
            with self.subTest(profile=row['revision'], case=case['id']):
                self.assertEqual(result, dict(revision=row['revision'], case=i,
                    **expected(case, data['contracts'][row['contract']], data)))

    def test_native_compiler_mapping_route(self):
        data = load_contract_fixture(FIXTURE)
        native_output(route_program(data), data)


if __name__ == '__main__':
    unittest.main()
