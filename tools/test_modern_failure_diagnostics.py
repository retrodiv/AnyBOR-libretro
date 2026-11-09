"""Check source-specific allocation diagnostics through typed host observers.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-failure-diagnostics.json'


def program(data, platform):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/utils.c').read_text()
    config = {'linux': '#define LINUX 1\n#undef __GLIBC__\n#undef __GLIBC_PREREQ\n#define __GLIBC__ 2\n#define __GLIBC_PREREQ(major,minor) 1',
              'linux_narrow': '#define LINUX 1\n#undef __GLIBC__',
              'windows': '#define WIN 1', 'darwin': '#define DARWIN 1'}
    if platform not in config:
        raise ValueError('Declared diagnostic platform required')
    parts = dict(PLATFORM=config[platform],
        HELPER=function(source, 'obor_profile_allocation_arena_bytes'),
        FUNCTION=function(source, 'checkAlloc'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_failure_diagnostics_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved diagnostic dependency')
    return code


class ModernFailureDiagnostics(unittest.TestCase):
    def run_contract(self, platform):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']][platform]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data, platform), data)), expected)

    def test_native_linux_observer_selection(self):
        self.run_contract('linux')

    def test_portable_narrow_observer_fallback(self):
        self.run_contract('linux_narrow')

    def test_windows_branch(self):
        self.run_contract('windows')

    def test_darwin_branch(self):
        self.run_contract('darwin')


if __name__ == '__main__':
    unittest.main()
