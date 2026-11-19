"""Check native counter, repeated contact and follow-up decisions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-attack-rule-contracts.json'
GROUPS = ('counter', 'contact', 'follow')


def program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    commands = (engine / 'source/gamelib/commands.c').read_text(encoding='latin1')
    attack = function(source, 'do_attack')
    setter = function(source, 'ent_set_anim')
    counter_start = attack.index('            else if(self->animation->counterrange')
    flash = attack.index('                    if(!attack->no_flash)', counter_start)
    normal = re.search(r'(?m)^ {12}else if\([^{};]*self->takedamage\(e, attack\)\)', attack)
    follow = attack.index('            if((e->animation->followup.animation)')
    follow_end = attack.index('            self->hit_by_attack_id = current_attack_id;', follow)
    repeat = attack.index('            if(target->hit_by_attack_id == current_attack_id')
    registry = re.search(r'(?m)^(?:    if\([^\n]+\)\n    \{\n)?'
                         r'[ \t]*LIST_ADD\(CMD_MODEL_IGNOREATTACKID, "ignoreattackid"\);'
                         r'(?:\n    \})?', commands)
    command = source.index('case CMD_MODEL_IGNOREATTACKID:')
    helpers = ('counter_matches_hit', 'attack_follow_animation')
    parts = {
        'HELPERS': '\n'.join(function(source, name) for name in helpers if name in source),
        'ANIMATION_GATE': setter[setter.index('{') + 1:setter.index('    ani = ')],
        'COUNTER_BODY': attack[counter_start:flash],
        'NORMAL_ROUTE': normal[0],
        'FOLLOW_BODY': attack[follow:follow_end],
        'REPEAT_GATE': attack[repeat:attack.index('{', repeat)],
        'REGISTRY': registry[0],
        'COMMAND': source[command:source.index('case CMD_MODEL_', command + 5)],
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    for name in GROUPS:
        parts[name.upper()] = ',\n'.join(
            '{' + ','.join(map(str, row['input'])) + '}' for row in data['cases'][name])
    template = Path(__file__).with_name('attack_rule_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)


class HistoricalAttackRuleTests(unittest.TestCase):
    def test_native_counter_contact_and_follow(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, (revision, observed) in zip(rows, actual, strict=True):
            self.assertEqual(revision, row['revision'])
            expected = data['contracts'][row['contract']]
            for name, cases in zip(GROUPS, observed, strict=True):
                for scenario, got, want in zip(data['cases'][name], cases, expected[name], strict=True):
                    with self.subTest(revision=revision, scenario=scenario['name']):
                        self.assertEqual(got, want)


if __name__ == '__main__':
    unittest.main()
