"""Check native level-entry construction and ownership at profile boundaries.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-level-entry-contracts.json'


def level_set_helpers(source):
    """Retain the scalar-cache dependency when testing the real unload function."""
    if 'obor_legacy_set_values(' not in function(source, 'unload_levelorder'):
        return ''
    record = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_obor_level_set_defaults\s*;', source)
    if record is None:
        raise AssertionError('Missing native set-default storage')
    names = ['obor_legacy_set_options', 'obor_legacy_set_values']
    if 'obor_legacy_levelsets(' in source:
        names += ['obor_legacy_levelsets', 'obor_level_set_player_count']
    names += ['obor_legacy_set_players', 'obor_legacy_player_control']
    return record[0] + '\n' + '\n'.join(function(source, name) for name in names)


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    start = header.index('typedef enum', header.rfind('}s_spawn_entry;'))
    end = header.index('}s_set_entry;', start) + len('}s_set_entry;')
    constants = []
    for name in ('MAX_LEVELS', 'MAX_PLAYERS', 'MAX_DIFFICULTIES', 'MAX_NAME_LEN'):
        match = re.search(r'^#define\s+' + name + r'\s+[^\n]+', header, re.M)
        if match is None:
            raise AssertionError('Missing level constant ' + name)
        constants.append(match[0])
    names = (engine / 'source/scriptlib/List.h').read_text()
    name_macro = re.search(r'^#define\s+NAME\(s\)[^\n]+', names, re.M)
    if name_macro is None:
        raise AssertionError('Missing native string ownership macro')
    packing = re.search(r'^#pragma pack\(push,\s*\d+\)', header, re.M)
    if packing is None:
        raise AssertionError('Missing native record packing')
    text = Path(__file__).with_name('level_entry_contract.c.in').read_text()
    fields = dict(RECORDS=header[start:end], PACK=packing[0],
        CONSTANTS='\n'.join(constants), NAME=name_macro[0],
        METHODS=level_set_helpers(source) + '\n'.join(function(source, name) for name in
                          ('add_level', 'add_scene', 'add_select', 'unload_levelorder')),
        CONTEXTS=','.join('{%d,%d,%d,%d}' % (r['revision'], r['fixed_limit'], r['min_z'], r['max_z'])
                          for r in data['sources']))
    for name, value in fields.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise AssertionError('Unresolved level-entry input')
    return text


class HistoricalLevelEntryContracts(unittest.TestCase):
    def test_constructors_capacity_branches_coordinates_and_owned_release(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], cases=30) for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
