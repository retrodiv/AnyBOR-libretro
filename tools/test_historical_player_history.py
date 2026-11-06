"""Check native input history and the history-reset block in player spawning.

Controller sampling and the timer are declared providers. The remaining spawn
body, matching algorithms and full gameplay have separate contracts.
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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-player-history-contracts.json'


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    if '#ifndef DISABLE_MOVIE\n#define DISABLE_MOVIE\n#endif' not in core:
        raise ValueError('Native input requires the source movie exclusion')
    spawn = function(core, 'spawnplayer')
    guarded = re.findall(r'if\(obor_profile_build >= \d+\)\s*\{\s*'
                         r'memset\(player\[index\]\.combokey', spawn)
    if guarded:
        if len(guarded) != 1:
            raise ValueError('One native spawn history reset required')
        start = spawn.index(guarded[0])
        brace = spawn.index('{', start)
        block = function('void selected()\n' + spawn[brace:], 'selected')
        reset = spawn[start:brace] + block[block.index('{'):]
    else:
        blocks = re.findall(r'memset\(player\[index\]\.combokey[^;]*;\s*'
                            r'memset\(player\[index\]\.inputtime[^;]*;\s*'
                            r'player\[index\]\.combostep = 0;', spawn)
        if len(blocks) != 1:
            raise ValueError('One native spawn history reset required')
        reset = blocks[0]
    parts = dict(INPUT=function(core, 'inputrefresh'), RESET=reset,
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join('{%s}' % ','.join(str(row[key]) for key in data['parameters'])
                                   for row in data['cases']))
    text = Path(__file__).with_name('player_history_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native player history dependency')
    return text


class PlayerHistoryContracts(unittest.TestCase):
    def test_native_history_append_reset_timestamps_and_wrap(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
