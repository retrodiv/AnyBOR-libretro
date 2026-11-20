"""Check animation names, constants and the native dynamic slot allocator.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'profile-animation-namespace-contracts.json'


def constant_branch(method, symbol):
    macro = 'ICMPCONST(' + symbol + ')'
    if macro in method:
        return macro
    branch = re.search(r'(?m)^[ \t]*else if\([^{}]*?stricmp\("' + symbol +
                       r'", constname\)[^{}]*\{[^{}]+\}', method)
    if branch is None:
        raise ValueError('Missing native constant branch ' + symbol)
    return branch[0]


def program(data, engine):
    native = (engine / 'openbor.c').read_text(encoding='latin1')
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    names = function(native, 'translate_ani_id')
    start = names.index('else if(stricmp(value, "run")')
    end = names.index('else if(starts_with_num(value, "up")', start)
    loader = function(native, 'load_model_constants')
    first = loader.index('// calculate max animations')
    last = loader.index('if(buf)', first)
    allocation = loader[first:last]
    constant = function(script, 'mapstrings_transconst')
    defaults, pointers, resets, record, cleanup = [], [], [], [], []
    limits = {}
    for pointer, values, limit, count in data['layout']:
        array = re.search(r'(?ms)^(?:static )?int\s+' + values +
                          r'\[[^\]]+\]\s*=\s*\{[^}]+\};', native)
        if array is None:
            raise ValueError('Missing native animation array ' + values)
        defaults.append(array[0])
        pointers.append('static int *' + pointer + ';')
        limits[limit] = count
        record.append('    if(extra) printf(",%d", ' + pointer + '[' + count + ']);')
        cleanup.append('    free(' + pointer + ');')
    resets = ['    ' + field + ' = ' + count + ' + extra;' for field, count in limits.items()]
    counters = '\n'.join('static int ' + field + ';' for field in limits)
    helper = 'obor_profile_animation_base'
    parts = {
        'HELPER': function(native, helper) if helper in native else '',
        'NAMES': names[start + len('else '):end],
        'CONSTANTS': '\n'.join(constant_branch(constant, name) for name in data['constant_names']),
        'COUNTERS': counters,
        'POINTERS': '\n'.join(pointers),
        'DEFAULTS': '\n'.join(defaults),
        'RESET_COUNTS': '\n'.join(resets),
        'FIRST_DYNAMIC': re.search(r'\bint maxanim\s*=[^;]+;', loader)[0],
        'RESET_BASE': re.search(r'\bmax_animations\s*=[^;]+;', loader)[0],
        'ALLOCATE': allocation,
        'CAPACITY': re.search(r'(?m)^(?:    const int fixed_animations[^\n]+\n)?'
                              r'    newchar->animation_capacity = [^;]+;', native)[0],
        'OBSERVE': '\n'.join(record),
        'CLEANUP': '\n'.join(cleanup),
        'PROFILE_ROWS': ','.join(str(row['revision']) for row in data['sources']),
        'MODEL_NAMES': ','.join(json.dumps(name) for name in data['model_names']),
        'CONSTANT_NAMES': ','.join(json.dumps(name) for name in data['constant_names']),
    }
    template = Path(__file__).with_name('animation_namespace_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)


class HistoricalAnimationNamespaceTests(unittest.TestCase):
    def test_6391_dynamic_and_block_reaction_animations(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-reaction-animation-slots.json'))
        fixed = load_contract_fixture(FIXTURE.with_name('profile-6391-fixed-reaction-defaults.json'))
        rows = data['sources']
        self.assertEqual([row['revision'] for row in rows],
                         sorted(contract_revisions(data, data['expected_revisions'])))
        fixed_profiles = [row['revision'] for row in fixed['sources']]
        self.assertEqual(fixed_profiles, sorted(contract_revisions(fixed, fixed['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        loader = function(source, 'load_model_constants')
        first = loader.index('    // calculate max animations')
        allocation = loader[first:loader.index('    if(buf)', first)]
        release = loader[loader.index('    // free old values'):loader.index('    // Read file')]
        tables = sorted({table for row in rows for table in row['order']})
        resets = '\n'.join(f'    {count} = {base} + extra;' for count, base in data['counts'].items())
        counts = '\n'.join(f'static int {count};' for count in data['counts'])
        base_defs = '\n'.join(re.search(r'(?ms)^int\s+' + name +
                                        r'\[[^\]]+\]\s*=\s*\{[^}]+\};', source)[0]
                              for name, _ in data['layout'].values())
        pointers = '\n'.join(f'static int *{table};' for table in tables)
        descriptors = '\n'.join(f'static const AnimationSeries order_{row["revision"]}[] = {{' +
                                ', '.join('{&' + table + ', ' + ', '.join(data['layout'][table]) + '}'
                                          for table in row['order']) + '};'
                                for row in rows)
        table_sets = '\n    '.join('check_allocation(%du, %d, order_%d, %d);' %
                                   (row['revision'], row['first_native'], row['revision'], len(row['order']))
                                   for row in reversed(rows))
        chosen = '\n'.join('    {%du, %d, %d, %d, %d, %d, %d, %d},' %
                           (row['revision'], *inputs, *want)
                           for row in rows for inputs, want in zip(data['block_cases'], row['block_results'], strict=True))
        defaults = []
        for row in fixed['sources']:
            expected = []
            for name, values in row['vectors'].items():
                self.assertIn(name, tables)
                self.assertTrue(all(re.fullmatch(r'ANI_[A-Z0-9_]+', value) for value in values))
                literals = ', '.join(values) or '0'
                expected.append(f'    {{&{name}, {len(values)}, {{{literals}}}}}')
            defaults.append(f'static const FixedSeries fixed_{row["revision"]}[] = {{\n'
                            + ',\n'.join(expected) + '\n};')
        fixed_calls = '\n    '.join(
            f'CHECK_FIXED({revision});' for revision in (6391, 6510, 5134, 6330, 6119, 6510, 6391)
            if revision in fixed_profiles
        )
        parts = {'DECLARATIONS': '\n'.join((counts, base_defs, pointers, descriptors)),
                 'DEFAULT_FUNCTION': function(source, 'obor_profile_attack_defaults'),
                 'FIXED_DEFAULTS': '\n'.join(defaults), 'FIXED_CHECKS': fixed_calls,
                 'RESET': resets, 'RELEASE': release, 'ALLOCATION': allocation, 'TABLE_CHECKS': table_sets,
                 'BLOCK': function(source, 'set_blockpain') + function(source, 'reset_backpain'),
                 'BLOCK_CASES': chosen}
        template = Path(__file__).with_name('reaction_animation_slots_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        self.assertEqual(native_output(code, data, engine_source=engine), 'PASS reaction animations\n')

    def test_native_names_and_dynamic_slots(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, observed in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(observed, [row['revision'], data['contracts'][row['contract']]])


if __name__ == '__main__':
    unittest.main()
