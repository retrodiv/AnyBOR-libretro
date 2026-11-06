"""Check own debug-counter values and queued/direct message composition.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_hud_schedule import native_declarations
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frame-debug-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    update = function(core, 'update')
    overlay = update[update.index('// Debug stuff'):update.index('if(usevwait)')]
    unload = function(core, 'unload_level')
    start = unload.index('go_time = 0;') + len('go_time = 0;')
    unload = unload[start:unload.index('neon_time = 0;', start)]
    present = 'static void obor_profile_debug_init(' in core
    if present:
        main = function(core, 'openborMain')
        if not main[main.index('{')+1:].lstrip().startswith('obor_profile_debug_init();'):
            raise AssertionError('Profile debug initialization must precede entry services')
    # The preceding control has no init hook:keep its real zero initialization
    # executable so its values,not an unrelated compile failure,reject the oracle.
    init = function(core, 'obor_profile_debug_init') if present else 'static void obor_profile_debug_init(void){}'
    definitions = []
    for pattern in (r'(?m)^char\s+debug_msg\[[^\]]+\];',
                    r'(?m)^(?:u32|unsigned long)\s+debug_time\s*=[^;]+;'):
        matches = re.findall(pattern, utils)
        if len(matches) != 1:
            raise AssertionError('Exact native debug globals required')
        definitions.extend(matches)
    fields = dict(DECLARATIONS=native_declarations(core), GLOBALS='\n'.join(definitions),
        INIT=init, PRODUCER=function(utils, 'debug_printf'), OVERLAY=overlay, UNLOAD=unload,
        CONTEXTS=','.join('{%d,%d,%d,%d}' % (r['revision'], r['legacy_overlay'],
            r['initial_pending'], r['unload_clears']) for r in data['sources']))
    text = Path(__file__).with_name('frame_debug_contract.c.in').read_text()
    for name,value in fields.items():
        text = text.replace('@'+name+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise AssertionError('Unresolved native debug input')
    return text


class HistoricalFrameDebug(unittest.TestCase):
    def test_initial_message_expiry_refresh_unload_and_rendering(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [r['revision'] for r in data['sources']]
        self.assertEqual(len(revisions),len(set(revisions)))
        self.assertEqual(set(revisions),contract_revisions(data,data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data),data).splitlines()]
        self.assertEqual(actual,[dict(revision=r,cases=23,status='PASS') for r in revisions])


if __name__ == '__main__':
    unittest.main()
