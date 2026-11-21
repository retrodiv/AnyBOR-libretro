"""Check native control menu selection, rumble and binding transactions.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-control-menu-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'keyboard_setup'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_control_menu_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved control menu input')
    return code


class ModernControlMenuContracts(unittest.TestCase):
    def test_native_menu_commit_cancel_default_and_rumble(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


class ClassicControlMenuContracts(unittest.TestCase):
    def check_control_menu(self, engine_id):
        data = load_contract_fixture(FIXTURE.with_name('classic-control-menu-contracts.json'))
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        fields = ('revision', 'has_default', 'has_default_keyboard', 'label_input_length',
                  'label_display_length', 'stretch_default')
        values = dict(MENU=function(source, 'keyboard_setup'),
                      TRANSLATE=function(source, 'translate_SDID'),
                      DEFAULTS=function(source, 'clearbuttons') if engine_id == '6391' else '',
                      CLEAR_SETTINGS=function(source, 'clearsettings'),
                      ROWS=',\n'.join('{' + ','.join(str(row[k]) for k in fields) + '}' for row in rows))
        template = Path(__file__).with_name('classic_control_menu_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': engine_id}, engine_source=engine,
                               extra_cflags=('-DLINUX=1', '-fgnu89-inline'))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_control_menu(self):
        self.check_control_menu('4432')

    def test_6391_control_menu(self):
        self.check_control_menu('6391')


if __name__ == '__main__':
    unittest.main()
