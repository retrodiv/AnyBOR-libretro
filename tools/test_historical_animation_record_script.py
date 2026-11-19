"""Verify native script access to declared and omitted animation records.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-animation-record-script-contracts.json'


def record_entry(source, name, keep):
    entry, cases = switch_cases(source, name, 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label != 'default' and label not in keep:
            entry = entry[:row['label_start']] + entry[row['end']:]
    return re.sub(r'(?s)    static const void\s*\*\s*(?:actions|think)\[\]\s*=\s*\{[^}]*\};',
                  '', entry)


def program(data, engine):
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    native = (engine / 'openbor.c').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    enums = []
    for name in ('entityproperty_enum', 'gep_energycost_enum'):
        enum = re.search(r'(?ms)^enum ' + name + r'\s*\{.*?^};', script)
        if enum is None:
            raise ValueError('Missing native property enum ' + name)
        enums.append(enum[0])
    loader = function(native, 'load_cached_model')
    directives = []
    for first, following in (('ENERGYCOST', 'CHARGETIME'), ('DROPFRAME', 'CANCEL')):
        start = loader.index('case CMD_MODEL_' + first + ':')
        stop = loader.index('case CMD_MODEL_' + following + ':', start)
        directives.append(loader[start:stop])
    helper = 'obor_script_animation_energycost'
    parts = {
        'ENUMS': '\n'.join(enums),
        'GETTER': record_entry(script, 'openbor_getentityproperty',
                               {'_ep_energycost', '_ep_dropframe'}),
        'SETTER': record_entry(script, 'openbor_changeentityproperty', {'_ep_energycost'}),
        'COST_HELPER': function(script, helper) if helper in script else '',
        'VARIANT': '\n'.join(function(variant, name) for name in ('ScriptVariant_Clear',
                             'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        'DIRECTIVES': '\n'.join(directives),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
    }
    template = Path(__file__).with_name('animation_record_script_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)


class HistoricalAnimationRecordScriptTests(unittest.TestCase):
    def test_native_reads_writes_and_directives(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(set(revisions)), len(revisions))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        output = native_output(program(data, engine), data)
        actual = [json.loads(line) for line in output.splitlines()]
        expected = [[row['revision'], data['contracts'][row['contract']]] for row in rows]
        self.assertEqual(len(actual), len(expected))
        for observed, want in zip(actual, expected):
            with self.subTest(revision=want[0]):
                self.assertEqual(observed, want)


if __name__ == '__main__':
    unittest.main()
