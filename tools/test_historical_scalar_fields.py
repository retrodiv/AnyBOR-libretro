"""Compare scalar values with own-source declarations and native sleep scheduling.

Record layout, whole-object IO and delegated frame effects have separate contracts.
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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-scalar-field-contracts.json'
IDENTIFIER = re.compile(r'[A-Za-z_]\w*\Z')
DECLARATION = re.compile(r'(?:unsigned\s+(?:char|short|int)|signed\s+(?:char|short)|'
                         r'short\s+int|unsigned|signed|char|short|int)\s+'
                         r'([A-Za-z_]\w*)\s*(?::\s*\d+)?\s*;\Z')


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    declarations, checks, calls = [], [], []
    for group_index, group in enumerate(data['declaration_groups']):
        fields = group['fields']
        for record in ('s_model', 'entity'):
            lines = []
            for field in fields:
                if field['record'] != record or not field['present']:
                    continue
                match = DECLARATION.fullmatch(field['declaration'])
                if match is None or match[1] != field['name']:
                    raise ValueError('An exact scalar source declaration is required')
                lines.append(field['declaration'])
            if not lines:
                raise ValueError('Two nonempty scalar source records required')
            declarations.append('struct own_%d_%s {\n%s\n};' %
                                (group_index, record, '\n'.join(lines)))
        statements = []
        for field in fields:
            if not field['present']:
                continue
            record, name = field['record'], field['name']
            key = record + '.' + name
            member = data['native_members'].get(key, name)
            if member is None:
                continue  # Source-owned write-only storage, reviewed separately.
            if not IDENTIFIER.fullmatch(member):
                raise ValueError('An explicit native scalar member required')
            left, right = 'actual_' + record + '.' + member, 'original_' + record + '.' + name
            # Compare stored bits here; the complete native consumer below
            # independently checks their historically signed interpretation.
            observed = '(uint16_t)' + right if key in data['stored_u16_fields'] else right
            statements.append('%s=input;%s=input;CHECK((long long)%s==(long long)%s,%s);'
                              '++assignments;' % (left, right, left, observed, json.dumps(key)))
        wait = data['sleep_field']
        if not IDENTIFIER.fullmatch(wait):
            raise ValueError('An explicit native sleep field required')
        checks.append('''static void check_%d(void) {
 struct own_%d_s_model original_s_model;
 struct own_%d_entity original_entity;
 unsigned assignments=0, schedules=0;
 for(unsigned v=0;v<sizeof(inputs)/sizeof(*inputs);++v) {
  int input=inputs[v];
  @STATEMENTS@
  for(unsigned c=0;c<sizeof(clocks)/sizeof(*clocks);++c)
  for(int sleeping=0;sleeping<2;++sleeping) {
   memset(&subject,0,sizeof(subject));memset(&animation,0,sizeof(animation));
   memset(animation_table,0,sizeof(animation_table));
   int index=sleeping?ANI_SLEEP:ANI_IDLE;
   animation.numframes=4;animation.sync=-1;animation_table[index]=&animation;
   subject.modeldata.animation=animation_table;subject.modeldata.animation_capacity=MAX_ANIS;
   subject.modeldata.@WAIT@=input;original_s_model.@WAIT@=input;
   subject.sleeptime=44;frame_calls=0;fixture_clock=clocks[c];
   ent_set_anim(&subject,index,1);
   uint32_t wanted=sleeping?44u:fixture_clock+(int)original_s_model.@WAIT@;
   CHECK(subject.sleeptime==wanted,"sleep scheduling");
   CHECK(subject.animation==&animation && subject.animnum==index &&
         subject.animpos==0 && frame_calls==1,"native animation selection");
   ++schedules;
  }
 }
 printf("{\\"revision\\":%%u,\\"assignments\\":%%u,\\"schedules\\":%%u}\\n",
        obor_profile_build,assignments,schedules);
}''' % (group_index, group_index, group_index))
        checks[-1] = checks[-1].replace('@STATEMENTS@', '\n'.join(statements)).replace('@WAIT@', wait)
        calls.extend('obor_profile_build=%du;check_%d();' % (row['revision'], group_index)
                     for row in data['sources'] if row['contract'] == group['key'])
    text = Path(__file__).with_name('scalar_fields_contract.c.in').read_text()
    parts = dict(DECLARATIONS='\n'.join(declarations), CHECKS='\n'.join(checks),
                 CALLS='\n'.join(calls), NATIVE=function(core, 'ent_set_anim'),
                 INPUTS=','.join(str(v) for v in data['values']),
                 CLOCKS=','.join(str(v) + 'u' for v in data['clocks']))
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved scalar contract dependency')
    return text


class ScalarFieldContracts(unittest.TestCase):
    def test_own_scalar_values_and_native_sleep_consumer_for_each_profile(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        groups = {g['key']: g for g in data['declaration_groups']}
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']))
        by_revision = {row['revision']: row for row in actual}
        self.assertEqual(len(by_revision), len(actual))
        for row in data['sources']:
            fields = groups[row['contract']]['fields']
            count = sum(f['present'] and data['native_members'].get(
                f['record'] + '.' + f['name'], f['name']) is not None for f in fields)
            with self.subTest(revision=row['revision']):
                self.assertEqual(by_revision[row['revision']], dict(
                    revision=row['revision'], assignments=count*len(data['values']),
                    schedules=2*len(data['values'])*len(data['clocks'])))


if __name__ == '__main__':
    unittest.main()
