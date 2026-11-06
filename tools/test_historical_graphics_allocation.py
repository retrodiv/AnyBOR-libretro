"""Check native graphical allocations and sprite encoding for each profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function
from test_sprite_encoding import encoding_program

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-graphics-allocation-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    sprite = (engine / 'source/gamelib/sprite.c').read_text()
    code = encoding_program(sprite, emit=False)
    code = code.replace('int main(void) {', 'static int encoding_checks(void) {', 1)
    prefix = r'''
uint32_t obor_profile_build;
#undef assert
#define assert(c) do { if(!(c)) { fprintf(stderr,"GRAPHICS_ALLOCATION profile=%u line=%d\n",obor_profile_build,__LINE__); abort(); } } while(0)
'''
    code = code.replace('int screenformat;', prefix + '\nint screenformat;', 1)
    methods = '\n'.join(function((engine / name).read_text(), callback) for name, callback in
        [('source/gamelib/screen.c', 'allocscreen'),
         ('source/gamelib/bitmap.c', 'allocbitmap')])
    tail = Path(__file__).with_name('graphics_allocation_contract.c.in').read_text()
    return code + tail.replace('@ALLOCATORS@', methods).replace('@CONTEXTS@', ','.join(
        '{%du,%d}' % (r['revision'], r['signature']) for r in data['sources']))


class GraphicsAllocationContracts(unittest.TestCase):
    def test_native_allocators_encoder_size_pixels_palette_and_signatures(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [r['revision'] for r in data['sources']]
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(set(revisions)))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], signature=r['signature'])
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
