"""Execute native completion-display configuration and stage advancement.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-completion-visibility-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own completion sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values()) or
                set(row['features'].values()) not in ({False}, {True})):
            raise ValueError('Consistent own command and consumer availability required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    loader = function(core, 'load_levelorder')
    _, arms = switch_cases(loader, 'load_levelorder', 'cmd', outermost=True)
    game = function(core, 'playgame')
    begin = game.index('if(le->gonext == 1)')
    end = game.index('current_level = set->numlevels;', begin)
    end = game.index('}', end) + 1
    methods = '\n'.join(function(utility, n) for n in ('lc', 'getNewLineStart'))
    for name in ('getCommandlistCommand', 'getLevelOrderCommand', 'prepareList',
                 'createLevelOrderCommandList', 'freeCommandList'):
        methods += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
    parser = ('#pragma GCC diagnostic push\n'
              '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
              function(core, 'ParseArgs') + '\n#pragma GCC diagnostic pop\n')
    parser += '\n'.join(function(core, n) for n in ('isNumeric', 'getValidInt', 'add_set'))
    cases, expectations = [], []
    for case in data['cases']:
        if case['kind'] not in (0, 1) or len(case['parameters']) != 3:
            raise ValueError('Bounded parser or stage cases required')
        cases.append('{%d,%s,{%s}}' % (case['kind'], json.dumps(case['text']),
            ','.join(str(v) for v in case['parameters'])))
        epochs = []
        for epoch in ('before', 'after'):
            row = case[epoch]
            if not 1 <= len(row['values']) <= 16:
                raise ValueError('Explicit native observations required')
            epochs.append('{%s,%d,{%s},{%s}}' % (json.dumps(row['diagnostic']),
                len(row['values']), ','.join(str(v if v is not None else 0) for v in row['values']),
                ','.join(str(int(v is not None)) for v in row['values'])))
        expectations.append('{%s}' % ','.join(epochs))
    values = dict(METHODS=methods, PARSER=parser,
        DEFAULT_ERROR=re.search(r'static const char \*defaulterr = [^\n]+;', loader)[0],
        CHKDEF=re.search(r'^#define CHKDEF[^\n]+', loader, re.M)[0],
        ARMS=''.join('case ' + name + ':' + arms[name]['body'] for name in
                    ('CMD_LEVELORDER_SET', 'CMD_LEVELORDER_NOSHOWCOMPLETE')),
        DEFAULT=arms['default']['body'],
        NO_SET=re.search(r'if\(!set\)\s*\{\s*errormessage = "No levels were loaded!";\s*\}', loader)[0],
        CLEANUP=loader[loader.index('lCleanup:'):], COMPLETION=game[begin:end],
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], int(r['features']['command']))
                          for r in data['sources']),
        CASES=','.join(cases), EXPECTATIONS=','.join(expectations))
    text = Path(__file__).with_name('completion_visibility_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native completion dependency')
    return text


class CompletionVisibilityContracts(unittest.TestCase):
    def test_native_configuration_errors_defaults_and_stage_progress(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
