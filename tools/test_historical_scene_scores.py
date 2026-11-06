"""Check scene input cleanup, score names and safe model-cache retirement.

Native scene/score bodies execute with controlled IO and presentation services.
The model check covers the final retirement statements; ownership is separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import sys
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-scene-score-contracts.json'


def cache_retirement_tail(source):
    body = function(source, 'free_model')
    tail = re.search(r'(?m)^[ \t]*(?:model_cache\[model->index\]\.model = NULL;\s*)?'
                     r'deleteModel\(model->name\);\s*'
                     r'(?:printf\("(?:\\.|[^"\\])*"\);\s*)*'
                     r'return models_loaded--;\s*}\s*$', body)
    if tail is None:
        raise ValueError('Complete native model retirement tail required')
    return tail[0]


def program(data, focus):
    if focus not in ('scene', 'scores'):
        raise ValueError('Explicit native scene/score focus required')
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    rows = []
    for row in data['sources']:
        rows.append('{%du,%d,%d,%d}' % (row['revision'], row['scene_clears_inputs'],
                                      row['canonical_score_name'], row['score_saved']))
    parts = dict(SCENE=function(source, 'playscene'), HALL=function(source, 'hallfame'),
        CACHE=cache_retirement_tail(source), PROFILES=',\n'.join(rows),
        PARSERS='\n'.join(function(source, n) for n in ('isNumeric', 'getValidInt')),
        FOCUS=str(int(focus == 'scores')))
    text = Path(__file__).with_name('scene_score_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native scene/score dependency')
    return text


class SceneScoreContracts(unittest.TestCase):
    def check(self, focus, cases):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(set(revisions)), len(revisions))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data, focus), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=cases) for r in revisions])
        print(json.dumps(dict(focus=focus, contexts=len(actual), cases=cases * len(actual))),
              file=sys.stderr)

    def test_scene_inputs_and_safe_cache_retirement(self):
        self.check('scene', 7)

    def test_canonical_or_player_score_names(self):
        self.check('scores', 4)


if __name__ == '__main__':
    unittest.main()
