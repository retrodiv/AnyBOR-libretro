"""Check native pause-menu draws against each original source's layout policy.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import json
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-pause-menu-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own pause sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or type(row['custom_layout']) is not bool or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c']) or
                not re.fullmatch('[0-9a-f]{64}', row['method_sha256'])):
            raise ValueError('Original pause source identity and draw policy required')
    return data


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    header = (ROOT / 'src/engines' / data['engine'] / 'openbor.h').read_text()
    end = header.index('} e_key_def;') + len('} e_key_def;')
    start = header.rfind('typedef enum', 0, end)
    keys = dict(start='FLAG_START', up='FLAG_MOVEUP', down='FLAG_MOVEDOWN',
                escape='FLAG_ESC', options='FLAG_SCREENSHOT', idle='0')
    cases = []
    for row in data['cases']:
        if (not 1 <= len(row['keys']) <= 8 or len(row['offsets']) != 7 or
                not 0 <= row['actor'] < 4 or row['maxplayers'] not in (2, 4)):
            raise ValueError('Bounded pause frame recipes required')
        values = ['|'.join(keys[k] for k in key) for key in row['keys']]
        cases.append('{%d,%d,%d,%d,%d,{%s},{%s}}' %
                     (row['actor'], row['starters'], row['entities'], row['maxplayers'],
                      len(values), ','.join(values), ','.join(map(str, row['offsets']))))
    values = dict(FLAGS=header[start:end], FUNCTION=function(core, 'pausemenu'),
                  CONTEXTS=','.join(str(r['revision']) + 'u' for r in data['sources']),
                  CASES=','.join(cases))
    text = Path(__file__).with_name('pause_menu_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native pause dependency')
    return text


def expected(row, scene):
    """Source-owned draw policies; selected item follows the native key order."""
    result, selected = [], 0
    offsets = scene['offsets'] if row['custom_layout'] else [0, 1, 0, 0, 3, 0, 0]
    for key in scene['keys']:
        result.extend([[offsets[4], -2, 0, offsets[5], offsets[6], 'Pause'],
                       [offsets[1 if selected == 0 else 0], -1, 0, offsets[2], offsets[3], 'Continue'],
                       [offsets[1 if selected == 1 else 0], 0, 0, offsets[2], offsets[3], 'End Game']])
        if 'up' in key or 'down' in key:
            selected ^= 1
        if 'start' in key or 'escape' in key:
            break
    else:
        raise ValueError('Pause recipe must terminate')
    return result


class PauseMenuContracts(unittest.TestCase):
    def test_native_frames_fonts_offsets_and_selected_items(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        wanted = [dict(revision=r['revision'], case=i, draws=expected(r, c))
                  for r in data['sources'] for i, c in enumerate(data['cases'])]
        self.assertEqual(len(actual), len(wanted))
        for got, correct in zip(actual, wanted):
            self.assertEqual(got, correct, 'revision=%s case=%s' %
                             (correct['revision'], correct['case']))


if __name__ == '__main__':
    unittest.main()
