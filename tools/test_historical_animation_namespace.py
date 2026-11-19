"""Check animation names, constants and the native dynamic slot allocator.

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
