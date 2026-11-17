"""Check native spawn-property namespaces, raw parent values and callback order.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-spawn-property-contracts.json'


def program(data, engine):
    source = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    enum = re.search(r'enum setspawnentry_enum\s*\{[\s\S]*?\};', source)
    if enum is None:
        raise ValueError('Complete native spawn enum required')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    providers = Path(__file__).with_name('classic_player_properties_contract.c.in').read_text().split('@VARIANTS@')[0]
    contexts = ','.join('{%du,%d,%d,%d,{%s}}' % (r['revision'], r['new_properties'],
        r['parent_accepts_pointer'], len(r['names']), ','.join(json.dumps(n) for n in r['names']))
        for r in data['sources'])
    parts = dict(PROVIDERS=providers,
        VARIANTS='\n'.join(function(variant, n) for n in ('ScriptVariant_Init', 'ScriptVariant_Clear',
            'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utility, 'searchList'), MAP_MACRO=''.join(lines[first:last+1]),
        METHODS=enum[0]+'\n'+'\n'.join(function(source, n) for n in
            ('mapstrings_setspawnentry', 'openbor_setspawnentry', 'openbor_spawn')),
        SMARTSPAWN=function(core, 'smartspawn'), CONTEXTS=contexts)
    result = Path(__file__).with_name('forward_spawn_properties_contract.c.in').read_text()
    for key, value in parts.items():
        result = result.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved native spawn dependency')
    return result


class ForwardSpawnPropertyTests(unittest.TestCase):
    def test_native_namespace_setter_spawn_and_callback_visibility(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_SPAWN_PROPERTIES_ENGINE', ROOT / 'src/engines' / data['engine']))
        rows = [json.loads(line) for line in native_output(program(data, engine), data,
                engine_source=engine).splitlines()]
        self.assertEqual(rows, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
