"""Execute native shadow command admission, event effects and draw publication.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-shadow-opacity-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(set(revisions)) != len(revisions) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own shadow sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values()) or
                set(row['features'].values()) not in ({False}, {True})):
            raise ValueError('Consistent own shadow availability required')
    for case in data['cases']:
        if (case['kind'] not in range(4) or len(case['parameters']) != 6 or
                len(case['before']['values']) != len(case['after']['values']) or
                not 1 <= len(case['before']['values']) <= 18):
            raise ValueError('Explicit before/after observations required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    _, arms = switch_cases(core, 'load_level', 'cmd', outermost=True)
    scroller = function(core, 'update_scroller')
    begin = scroller.index('else if(level->spawnpoints[current_spawn].light.y)')
    end = scroller.index('++current_spawn;', begin) + len('++current_spawn;')
    events = scroller[begin:end]
    # The preceding event classes are outside this contract's suffix.
    events = events.removeprefix('else ')
    draw = function(core, 'display_ents')
    begin = draw.index('shadowmethod = plainmethod;')
    end = draw.index(';', draw.index('spriteq_add_sprite(', begin)) + 1
    draw = draw[begin:end]
    methods = '\n'.join(function(utility, name) for name in ('lc', 'getNewLineStart'))
    for name in ('getCommandlistCommand', 'getLevelCommand', 'prepareList',
                 'createLevelCommandList', 'freeCommandList'):
        methods += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
    parser = ('#pragma GCC diagnostic push\n'
              '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
              function(core, 'ParseArgs') + '\n#pragma GCC diagnostic pop\n')
    parser += '\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt', 'parsecolor'))
    plain = re.search(r'(?ms)^const s_drawmethod plainmethod =\s*\{.*?^\};', core)
    if not plain:
        raise ValueError('Native plain drawing initializer required')
    cases = []
    expectations = []
    for case in data['cases']:
        cases.append('{%d,%s,{%s}}' % (case['kind'],
            'NULL' if case['text'] is None else json.dumps(case['text']),
            ','.join(str(x) for x in case['parameters'])))
        epochs = []
        for epoch in ('before', 'after'):
            expected = case[epoch]
            epochs.append('{%s,%d,{%s},{%s}}' % (
                json.dumps(expected['diagnostic']), len(expected['values']),
                ','.join(str(v if v is not None else 0) + 'LL' for v in expected['values']),
                ','.join(str(int(v is not None)) for v in expected['values'])))
        expectations.append('{%s}' % ','.join(epochs))
    values = dict(PLAIN=plain[0], METHODS=methods, PARSER=parser,
        LIFEBAR=function(core, 'lifebar_colors'), EVENTS=events, DRAW=draw,
        LEVEL_ARMS=''.join('case ' + name + ':' + arms[name]['body'] for name in
            ('CMD_LEVEL_SHADOWCOLOR', 'CMD_LEVEL_SHADOWALPHA',
             'CMD_LEVEL_SHADOWOPACITY', 'CMD_LEVEL_LIGHT')),
        LEVEL_DEFAULT=arms['default']['body'],
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], int(r['features']['global_present']))
                          for r in data['sources']),
        CASES=','.join(cases), EXPECTATIONS=','.join(expectations))
    text = Path(__file__).with_name('shadow_opacity_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native shadow dependency')
    return text


class ShadowOpacityContracts(unittest.TestCase):
    def test_native_commands_events_and_draw_parameters(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
