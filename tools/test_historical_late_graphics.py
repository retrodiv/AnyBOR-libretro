"""Check source-defined later graphics property contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import native_output
from test_historical_gfx_properties import program, route_program, expected
from test_historical_common_think import ROOT
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'profile-late-gfx-property-contracts.json'
PNG_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-late-png-palette-contracts.json'


class LaterGraphicsContracts(unittest.TestCase):
    def test_grayscale_png_palette_acceptance_and_bounded_rgb_prefix(self):
        data=load_contract_fixture(PNG_FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data,data['expected_revisions']))
        source=(ROOT/'src/engines'/data['engine']/'source/gamelib/loadimg.c').read_text()
        code=Path(__file__).with_name('late_png_palette_contract.c.in').read_text()
        code=code.replace('@READER@',function(source,'readpng')).replace('@CONTEXTS@',
            ','.join('{%du,%d}'%(row['revision'],row['gray_without_plte']) for row in data['sources']))
        self.assertEqual(json.loads(native_output(code,data)),
                         {'status':'PASS','contexts':len(data['sources']),'cases':len(data['sources'])*12})

    def test_graphics_queries_and_sprite_byte_signedness(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        code = program(data)
        include = '#include "openbor.h"'
        self.assertEqual(code.count(include), 1)
        code = code.replace(include, include + '\n'
            'HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}\n'
            'HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}\n')
        actual = [json.loads(line) for line in native_output(code, data).splitlines()]
        wanted = []
        for row in data['sources']:
            fields = data['contracts'][row['contract']]
            for index, case in enumerate(data['cases']):
                result = expected(case, fields, data)
                if row['pixel_signed'] and result['pixels'] and result['value'] >= 128:
                    result['value'] -= 256
                wanted.append(dict(revision=row['revision'], case=index, **result))
        self.assertEqual(actual, wanted)

    def test_native_graphics_preconversion_route(self):
        data = load_contract_fixture(FIXTURE)
        native_output(route_program(data), data)


if __name__ == '__main__':
    unittest.main()
