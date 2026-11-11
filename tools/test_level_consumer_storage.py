"""Keep native selector values and bound fixed-width saved-name display.

Native cases/statements and records use bounded parser, allocator and text
observers. Complete level loading, menu timing and raster remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import switch_cases
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/level-consumer-native-baseline.json'


def program(engine, profiles, *, short_display=False, omit_release=False):
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    statements = re.findall(r'_menutext\([^;\n]*?savelevel\[saveslot\]\.dName\);', source)
    if len(statements) != len(data['display_statements']):
        raise ValueError('All native saved-name display statements required')
    if short_display:
        statements = [s.replace('(int)sizeof(savelevel[saveslot].dName)',
                                '(int)sizeof(savelevel[saveslot].dName)-1') for s in statements]
    def display_switch(rows):
        return '\n'.join('case %d: %s break;' % (i, s) for i, s in enumerate(rows))
    selector = ''
    if data['selector_kind'] != 'entries':
        _, cases = switch_cases(source, 'load_levelorder', 'cmd', outermost=True)
        case = cases['CMD_LEVELORDER_SKIPSELECT']['body']
        if omit_release:
            if case.count('free(set->skipselect[i]);') != 1:
                raise ValueError('One native replaced selector release required')
            case = case.replace('free(set->skipselect[i]);', '(void)0;', 1)
        table = data['selector_kind'] == 'table'
        values = dict(DECLARATION=data['table_declaration'] if table else
            'static s_set_entry set_value;static s_set_entry *set=&set_value;',
            SLOT='(skipselect?(*skipselect)[current_set][i]:NULL)' if table else 'set->skipselect[i]',
            BASE='(skipselect!=NULL)' if table else '0',
            RESET='skipselect=NULL;' if table else 'memset(&set_value,0,sizeof(set_value));',
            NOSELECT='0' if table else 'set->noselect',
            BEFORE=data['selector_case'], AFTER=case,
            REUSE='1' if table else 'obor_profile_build<%du' % data['reuse_before'] if data['reuse_before'] else '0',
            TABLE=str(int(table)))
        values['GET_ARG_RESET'] = '#undef GET_ARG\n' if re.search(r'^#define\s+GET_ARG\b', header, re.M) else ''
        selector = (HERE / 'level_selector_storage.c.in').read_text()
        for key, value in values.items():
            selector = selector.replace('@' + key + '@', value)
    else:
        selector = 'static void selector_checks(void) {}'
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        BEFORE_DISPLAY=display_switch(data['display_statements']),
        AFTER_DISPLAY=display_switch(statements), DISPLAY_COUNT=str(len(statements)),
        SELECTOR=selector,
        SAVE_STORAGE='#define records savelevel' if re.search(r'^s_savelevel\s+savelevel\[', header, re.M) else
            'static s_savelevel records[2];\ns_savelevel *savelevel=records;',
        PROFILES=','.join(str(oracle['profiles'][p['build']]['revision'])+'u' for p in profiles))
    text = (HERE / 'level_consumer_storage.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved level consumer input')
    return text


class LevelConsumerStorageTests(unittest.TestCase):
    def test_native_saved_fields_and_selector_replacement_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        self.assertEqual(set(load_contract_fixture(FIXTURE)['profiles']), {p['build'] for p in pin['profiles']})
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['cases'], 8 * len(profiles))

    def test_full_width_display_is_not_shortened(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / pin['engines'][0]['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, program(engine, [profile], short_display=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('strlen(rendered)==length', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)

    def test_missing_replaced_owner_release_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        key = next(k for k, v in oracle['engines'].items() if v['selector_kind'] == 'set')
        engine = ROOT / 'src/engines' / key
        profile = max((p for p in pin['profiles'] if p['engine'] == key),
                      key=lambda p: int(p.get('revision', p['build'].split('-')[0])))
        result = run_native(engine, program(engine, [profile], omit_release=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('live_count()==owned_count()', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
