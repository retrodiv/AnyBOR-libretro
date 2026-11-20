"""Execute native module-debug and pause-offset command admission.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-menu-command-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own command sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                set(row['features']) != {'nodebug', 'pauseoffset'} or
                any(type(v) is not bool for v in row['features'].values()) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Original command identities and availability required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    models, order = (function(core, n) for n in ('load_models', 'load_levelorder'))
    _, model_arms = switch_cases(models, 'load_models', 'cmd', outermost=True)
    _, order_arms = switch_cases(order, 'load_levelorder', 'cmd', outermost=True)
    methods = '\n'.join(function(commands, n) + '\n#undef LIST_ADD\n' for n in
                        ('prepareList', 'freeCommandList', 'getCommandlistCommand',
                         'getModelCommand', 'getLevelOrderCommand',
                         'createModelstxtCommandList', 'createLevelOrderCommandList'))
    methods += '\n' + '\n'.join(function(utility, n) for n in ('lc', 'getNewLineStart'))
    parser = ('#pragma GCC diagnostic push\n'
              '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
              function(core, 'ParseArgs') + '\n#pragma GCC diagnostic pop\n')
    parser += '\n'.join(function(core, n) for n in ('isNumeric', 'getValidInt', 'add_set'))
    cases = []
    for row in data['cases']:
        if (row['kind'] not in ('models', 'levels') or len(row['offsets']) != 7 or
                not isinstance(row['text'], str) or len(row['text']) > 2048):
            raise ValueError('Bounded command sequences and scalar seeds required')
        cases.append('{%d,%s,%d,%d,{%s}}' %
                     (row['kind'] == 'levels', json.dumps(row['text']), row['nodebug'],
                      row['nocheats'], ','.join(map(str, row['offsets']))))
    values = dict(METHODS=methods, PARSER=parser,
        LINE_DIAGNOSTICS=re.search(r'const int line_diagnostics = [^;]+;\s*int warned_unknown = 0;', order)[0],
        GLOBALS='\n'.join(re.search(pattern, core, re.M)[0] for pattern in
            (r'^int\s+nodebugoptions\s*=\s*[^;]+;', r'^int\s+pauseoffset\[7\]\s*=\s*[^;]+;')),
        MODEL_ARMS=''.join('case ' + n + ':' + model_arms[n]['body'] for n in
                          ('CMD_MODELSTXT_NODEBUG', 'CMD_MODELSTXT_NOCHEATS')),
        MODEL_DEFAULT=model_arms['default']['body'],
        ORDER_ARMS=''.join('case ' + n + ':' + order_arms[n]['body'] for n in
                          ('CMD_LEVELORDER_SET', 'CMD_LEVELORDER_PAUSEOFFSET')),
        ORDER_DEFAULT=order_arms['default']['body'],
        DEFAULT_ERROR=re.search(r'static const char \*defaulterr = [^\n]+;', order)[0],
        CHKDEF=re.search(r'^#define CHKDEF[^\n]+', order, re.M)[0],
        NO_SET=re.search(r'if\(!set\)\s*\{\s*errormessage = "No levels were loaded!";\s*\}', order)[0],
        CLEANUP=order[order.index('lCleanup:'):],
        CONTEXTS=','.join('{%du,%d,%d}' %
            (r['revision'], r['features']['nodebug'], r['features']['pauseoffset']) for r in data['sources']),
        CASES=','.join(cases))
    text = Path(__file__).with_name('menu_commands_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native command dependency')
    return text


class MenuCommandContracts(unittest.TestCase):
    def test_native_registry_conversion_messages_and_partial_updates(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        wanted = []
        for row in data['sources']:
            for index, case in enumerate(data['cases']):
                feature = 'nodebug' if case['kind'] == 'models' else 'pauseoffset'
                expected = case['after' if row['features'][feature] else 'before']
                wanted.append(dict(revision=row['revision'], case=index, **expected))
        self.assertEqual(len(actual), len(wanted))
        for got, correct in zip(actual, wanted):
            self.assertEqual(got, correct, 'revision=%s case=%s' %
                             (correct['revision'], correct['case']))


if __name__ == '__main__':
    unittest.main()
