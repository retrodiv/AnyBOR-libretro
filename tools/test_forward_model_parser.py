"""Execute native model command admission, parser arms and script-slot storage.

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
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-model-parser-contracts.json'


def program(data, engine, legacy_revisions):
    source = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    loader_source = function(source, 'load_cached_model')
    loader, cases = switch_cases(loader_source.replace('switch(cmd)', 'switch(model_command)', 1),
                                 'load_cached_model', 'model_command', outermost=True)
    prefix = loader[:loader.index('switch(model_command)')]
    marker = 'if(ParseArgs(&arglist, buf + pos, argbuf))'
    if prefix.count(marker) != 1:
        raise ValueError('One actual model parser admission prefix required')
    prefix = prefix[prefix.index(marker):]
    selected = [row['symbol'] for row in data['commands'] if row['kind'] != 'unhandled']
    selected += ['CMD_MODEL_RUNNING', 'CMD_MODEL_BBOX', 'CMD_MODEL_HITFLASH',
                 'CMD_MODEL_BLOCKFLASH', 'CMD_MODEL_HITFX', 'CMD_MODEL_BLOCKFX']
    attack_start = min(cases[name]['label_start'] for name in
                       ('CMD_MODEL_ATTACK', 'CMD_MODEL_ATTACK_BLOCK_COST'))
    attack_end = cases['CMD_MODEL_ATTACKZ']['label_start']
    # Keep the attack labels and every intervening arm in source order.
    # Reconstructing individual arms could hide a fall-through into a new case.
    arms = ''.join('case ' + name + ':' + cases[name]['body'] for name in selected
                   if not attack_start <= cases[name]['label_start'] < attack_end)
    arms += loader[attack_start:attack_end]
    rows = []
    for row in data['sources']:
        admitted = set(row['admitted'])
        label = row['script_labels'].get('CMD_MODEL_ONBLOCKPSCRIPT', {}).get('label', '')
        rows.append('{%d,{%s},%d,{%s},%s}' % (
            row['revision'], ','.join(str(int(case['symbol'] in admitted)) for case in data['commands']),
            len(row['script_members']), ','.join('offsetof(s_scripts,' + field + ')' for field in row['script_members']),
            json.dumps(label)))
    field_cases = []
    command_rows = []
    for index, row in enumerate(data['commands']):
        kind = row['kind']
        if kind in ('int', 'float', 'float-int', 'model-service', 'sound-service'):
            if not re.fullmatch(r'(?:model|attack|bbox|abox)(?:\.[a-z_]+|\[[0-5]\])+', row['field']):
                raise ValueError('Explicit bounded native model field required')
            value = 'number' if kind == 'float' else '(int64_t)number'
            field_cases.append('case %d:%s=(__typeof__(%s))(%s);break;' %
                               (index, row['field'], row['field'], value))
        command_rows.append('{%s,%s,%s}' % (json.dumps(row['name']), row['symbol'], json.dumps(kind)))
    # The native parser intentionally shares terminator/separator handling.
    definitions = ('#pragma GCC diagnostic push\n'
                   '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
                   function(source, 'ParseArgs') + '#pragma GCC diagnostic pop\n')
    definitions += '\n'.join(function(source, name) for name in ['isNumeric', 'getValidInt', 'getValidFloat'])
    command_functions = function(utility, 'lc') + '\n'
    for name in ['getCommandlistCommand', 'getModelCommand', 'prepareList', 'createModelCommandList', 'freeCommandList']:
        command_functions += function(commands, name) + '\n#undef LIST_ADD\n'
    values = dict(HEADER='#include ' + json.dumps(str(engine / 'openbor.h')) + '\n#include ' +
                        json.dumps(str(engine / 'source/gamelib/commands.h')),
        LIST='#include ' + json.dumps(str(engine / 'source/scriptlib/List.c')),
        NUMBERS=definitions, COMMANDS=command_functions, PREFIX=prefix, CASES=arms,
        DEFAULT=cases['default']['body'], CONTEXTS=','.join(rows), FIELDS='\n'.join(field_cases),
        LEGACY_REVISIONS=','.join(map(str, legacy_revisions)),
        COMMAND_ROWS=','.join(command_rows),
        VALUES=','.join('{%s,%.17g,%.17g,%.17g,%d}' %
            (json.dumps(row['text']), row['integer'], row['floating'], row['float_integer'], row['warning'])
            for row in data['numeric_values']),
        SLOT_SUPPORT=function(source, 'obor_profile_script_slot_enabled'),
        SCRIPT_CONTAINERS='\n'.join(function(source, name) for name in
            ['alloc_all_scripts', 'clear_all_scripts', 'free_all_scripts', 'copy_all_scripts']),
        SCRIPT_LOADER=function(source, 'lcmHandleCommandScripts'))
    text = Path(__file__).with_name('forward_model_parser_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native model parser contract input')
    return text


class ForwardModelParserTests(unittest.TestCase):
    def test_native_admission_record_effects_and_script_slot_lifecycle(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(data, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_MODEL_PARSER_ENGINE', ROOT / 'src/engines' / data['engine']))
        legacy_revisions = sorted({int(profile.get('revision', profile['build']))
                                   for profile in profiles if profile['engine'] == data['engine']})
        self.assertTrue(legacy_revisions)
        output = native_output(program(data, engine, legacy_revisions), data, engine_source=engine)
        actual = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
