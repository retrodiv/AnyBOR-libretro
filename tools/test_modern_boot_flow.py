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
        self.assertEqual(json.loads(native_output(program(data, kind), data)), expected)

    def test_font_order_and_model_font_override(self):
        self.run_contract('startup')

    def test_native_settings_defaults(self):
        self.run_contract('defaults')

    def test_android_native_settings_defaults(self):
        self.run_contract('android')

    def test_animated_image_cleanup_and_palette_retention(self):
        self.run_contract('gif')


if __name__ == '__main__':
    unittest.main()
