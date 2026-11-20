"""Run the platform, array and animation callbacks at their registered addresses.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-registry-tail-contracts.json'
GROUPS = (
    ('platform', ('checkplatformbelow', 'checkplatformabove', 'checkplatformbetween')),
    ('array', ('next', 'previous', 'isfirst', 'islast')),
    ('animation', ('executeanimation',)),
)
NAMES = tuple(name for _, names in GROUPS for name in names)


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    header = (engine / 'openborscript.h').read_text()
    core = (engine / 'openbor.c').read_text()
    library = engine / 'source/scriptlib'
    variants = (library / 'ScriptVariant.c').read_text()
    listing = (library / 'List.c').read_text()
    registry = '\n'.join(function(script, name) for name in
                         ('obor_has_computed_damage', 'Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    selected = {'openbor_' + name for name in NAMES}
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', registry)))
    if not selected <= set(symbols) or len(symbols) > 512:
        raise ValueError('Native script registry and its selected callbacks required')
    renamed = {name: 'other_' + name for name in symbols if name not in selected}
    renamed.update(List_Reset='registry_reset', List_InsertAfter='registry_insert')

    def declaration(pattern, source):
        value = re.search(pattern, source, re.M)
        if not value:
            raise ValueError('Missing native registry declaration ' + pattern)
        return value[0]

    def methods(source, names):
        return '\n'.join(function(source, name) for name in names)

    def integers(rows, fields):
        return ',\n'.join('{' + ','.join(str(row[key]) for key in fields) + '}' for row in rows)

    values = {
        'TYPES': declaration(r'typedef struct\s*\{[^{}]*\}\s*Varlist;', header) + '\n' +
                 declaration(r'^#define varlist_magic[^\n]*', header),
        'VARIANTS': methods(variants, ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue',
                                     'ScriptVariant_DecimalValue')),
        'CURSORS': methods(listing, ('List_GotoNext', 'List_GotoPrevious', 'List_Retrieve',
                                     'List_GetFirst', 'List_GetLast')),
        'PLATFORMS': methods(core, ('obor_terrain_between', 'testplatform', 'check_platform_below',
                                    'check_platform_above', 'check_platform_between')),
        'ACTION': function(core, 'common_animation_normal'),
        'CALLBACKS': methods(script, sorted(selected)),
        'STUBS': '\n'.join('static void %s(void) { stub_calls += %du; }' % (renamed[name], i + 1)
                           for i, name in enumerate(symbols) if name not in selected),
        'REGISTRY': rename_identifiers(registry, renamed),
        'NAMES': ','.join('{"%s", openbor_%s}' % (name, name) for name in NAMES),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'PLATFORM_CASES': integers(data['platform_cases'],
                                  ('scene', 'argc', 'bad', 'x', 'z', 'a', 'b')),
        'ARRAY_CASES': integers(data['array_cases'], ('size', 'cursor', 'kind', 'argc')),
        'ANIMATION_CASES': integers(data['animation_cases'],
                                   ('kind', 'argc', 'anim_type', 'reset_type', 'anim', 'reset', 'tick')),
    }
    template = Path(__file__).with_name('script_registry_tail_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class ScriptRegistryTailContracts(unittest.TestCase):
    def test_native_routing_and_callback_effects(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        results = iter(native_output(program(data), data).splitlines())
        for row in data['sources']:
            for name in NAMES:
                target = row['forward'][name]
                reverse = row['reverse'][name]
                expected = [row['revision'], name, int(target is not None), target or '',
                            reverse or '<unknown function>']
                self.assertEqual(json.loads(next(results)), expected)
                if target is None:
                    continue
                group = next(group for group, names in GROUPS if name in names)
                for i, case in enumerate(data[group + '_cases']):
                    if group == 'platform':
                        mode = 'inclusive' if row['platform_inclusive'] else 'exclusive'
                        value = case['expected'][mode][target]
                    elif group == 'array':
                        value = case['expected'][target]
                    else:
                        value = case['expected']
                    self.assertEqual(json.loads(next(results)), [row['revision'], name, i, *value],
                                     (row['revision'], name, case['name']))
        self.assertIsNone(next(results, None))


if __name__ == '__main__':
    unittest.main()
