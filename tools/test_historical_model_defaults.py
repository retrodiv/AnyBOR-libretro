"""Execute native model defaults, inheritance and command admission.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-model-defaults-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(set(revisions)) != len(revisions) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own model sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', value)
                        for value in row['source_sha256'].values()) or
                row['none_mode'] not in range(4) or row['boomerang_spelling'] not in range(3)):
            raise ValueError('Complete original model observations required')
    if len(set(data['fields'])) != len(data['fields']):
        raise ValueError('Unique model observations required')
    return data


def expected(data, context, case, initial=None):
    """Independent field effects transcribed from the original handlers."""
    seed = 37 if case['kind'] == 'inherit' else case.get('seed', 0)
    values = dict.fromkeys(data['fields'], seed) if initial is None else initial.copy()
    if initial is None and case.get('ai_sentinel'):
        values.update(aimove=4294967295, aiattack=4294967295)
    diagnostic = ''
    if case['kind'] == 'sequence':
        for text in case['commands']:
            step = dict(kind='command', text=text)
            if text.startswith('subject_to_basemap '):
                step['boolean'] = int(int(text.split()[1]) != 0)
            values, message = expected(data, context, step, values)
            diagnostic += message
            if message.startswith('Model '):
                break
    elif case['kind'] == 'constructor':
        values = dict.fromkeys(data['fields'], 0)
        values.update(aimove=4294967295, aiattack=4294967295, chainlength=1)
        values.update({name: -1 for name in data['constraints']})
        values.update({'atchain[%d]' % i: 1 for i in range(12)})
        values.update({'defense[%d].factor' % i: 1 for i in range(3)})
    elif case['kind'] == 'inherit':
        old = case['old']
        value = case['seed']
        values.update({name: old if value < 0 else value for name in data['constraints']})
        if case.get('ai_sentinel'):
            values.update(aimove=44, aiattack=55)
    else:
        command, _, argument = case['text'].partition(' ')
        command, argument = command.lower(), argument.lower()
        if command == 'subject_to_basemap':
            if context['basemap_admitted']:
                values['subject_to_basemap'] = case['boolean']
                if case.get('numeric_warning'):
                    diagnostic = data['numeric_warning'].format(value=argument)
            else:
                diagnostic = data['unknown_warning'].format(command=command)
        elif command in ('type', 'subtype'):
            table = data['types' if command == 'type' else 'subtypes']
            admitted = argument in table
            if argument in ('boomrang', 'boomerang'):
                admitted = context['boomerang_spelling'] == (1 if argument == 'boomrang' else 2)
            if not admitted:
                diagnostic = "Model 'unit-model' has invalid %s: '%s'" % (command, argument)
            else:
                rule = table[argument]
                values.update(rule['set'])
                if 'aimove_or' in rule:
                    values['aimove'] = (0 if values['aimove'] == 4294967295 else
                                        values['aimove']) | rule['aimove_or']
                if 'offscreen_default' in rule and not values['offscreenkill']:
                    values['offscreenkill'] = rule['offscreen_default']
                if command == 'type' and argument == 'none' and context['none_mode']:
                    names = data['none_seven']
                    if context['none_mode'] in (1, 2):
                        names = names + ['subject_to_gravity', 'no_adjust_base']
                    values.update({name: int(context['none_mode'] == 1 and name != 'no_adjust_base')
                                   for name in names})
        else:
            diagnostic = data['unknown_warning'].format(command=command)
    # There is no such member in the older originals. Shared physical storage
    # and historical script-number exposure are separate from this observation.
    if not context['basemap_present']:
        values['subject_to_basemap'] = None
    return values, diagnostic


def model_command_functions(commands, utility):
    result = [function(utility, 'lc')]
    for name in ('getCommandlistCommand', 'getModelCommand', 'prepareList',
                 'createModelCommandList', 'freeCommandList'):
        result.append(function(commands, name) + '\n#undef LIST_ADD')
    return '\n'.join(result)


def model_number_functions(source):
    return ('#pragma GCC diagnostic push\n'
            '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
            function(source, 'ParseArgs') + '#pragma GCC diagnostic pop\n' +
            '\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat')))


def program(data, extra_commands=()):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    loader, arms = switch_cases(function(source, 'load_cached_model'),
                                'load_cached_model', 'cmd', outermost=True)
    prefix = loader[:loader.index('switch(cmd)')]
    marker = 'if(ParseArgs(&arglist, buf + pos, argbuf))'
    if prefix.count(marker) != 1:
        raise ValueError('One native model parser admission prefix required')
    prefix = prefix[prefix.index(marker):]
    cases = ['{%s,%s,%d,%d,%d}' % (json.dumps(case['kind']), json.dumps(
             '|'.join(case['commands']) if case['kind'] == 'sequence' else case.get('text', '')),
             case.get('seed', 0), int(case.get('ai_sentinel', False)), case.get('old', 0))
             for case in data['cases']]
    model_functions = ('lcmHandleCommandType', 'lcmHandleCommandSubtype', 'init_model', 'ent_copy_uninit')
    if 'obor_profile_animation_base()' in function(source, 'init_model'):
        model_functions = ('obor_profile_animation_base', *model_functions)
    values = dict(
        CONSTANTS=re.search(r'(?m)^static const char \*E_OUT_OF_MEMORY = [^\n]+;', source)[0],
        NUMBERS=model_number_functions(source), COMMANDS=model_command_functions(commands, utility), PREFIX=prefix,
        ARMS=''.join('case ' + name + ':' + arms[name]['body'] for name in
                     ('CMD_MODEL_TYPE', 'CMD_MODEL_SUBTYPE', 'CMD_MODEL_SUBJECT_TO_BASEMAP', *extra_commands)),
        DEFAULT=arms['default']['body'],
        FUNCTIONS='\n'.join(function(source, name) for name in model_functions),
        CONTEXTS=','.join(str(row['revision']) for row in data['sources']),
        CASES=','.join(cases),
        SEED='\n'.join('model.%s = seed;' % name for name in data['fields']),
        INHERIT_SEED='\n'.join('actor.modeldata.%s=seed;' % name for name in data['constraints']),
        CONSTRAINTS='\n'.join('parent.%s=old;' % name for name in data['constraints']),
        SNAPSHOT=','.join('(double)observed->' + name for name in data['fields']))
    text = Path(__file__).with_name('model_defaults_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native model default dependency')
    return text


class ModelDefaultsContracts(unittest.TestCase):
    def test_4432_model_command_names_and_ai_controls(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') / 'profile-model-ai-control-contracts.json')
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(data['engine'], '4432')
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        source = (engine / 'openbor.c').read_text()
        commands = (engine / 'source/gamelib/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        _, arms = switch_cases(function(source, 'load_cached_model'), 'load_cached_model', 'cmd', outermost=True)
        cases = ('CMD_MODEL_SUBJECT_TO_BASEMAP', 'CMD_MODEL_ONAF',
                 'CMD_MODEL_BOOMERANG', 'CMD_MODEL_BOMB', 'CMD_MODEL_PLAYBOMB')
        rows = []
        for row in data['sources']:
            self.assertIn(row['boomerang_command'], ('', 'boomrangacc', 'boomrang', 'boomerang'))
            self.assertIn(row['aimove'], ('', 'boomrang', 'boomerang'))
            self.assertTrue(all(type(row[key]) is bool for key in ('basemap', 'per_model_factor')))
            rows.append('check_context(%du, %d, %d, %s, %s);' % (
                row['revision'], row['basemap'], row['per_model_factor'],
                json.dumps(row['boomerang_command']), json.dumps(row['aimove'])))
        parts = dict(
            COMMANDS=model_command_functions(commands, utility),
            NUMBERS='\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat')),
            ARMS=''.join('case ' + name + ':' + arms[name]['body'] for name in cases),
            CONSUMERS='\n'.join(function(source, name) for name in ('lcmHandleCommandAimove', 'check_attack_chance')),
            CHECKS='\n'.join(rows))
        template = Path(__file__).with_name('model_ai_control_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)
        result = native_output(code, data, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(json.loads(result), {'contexts': len(revisions), 'checks': 19 * len(revisions)})
        print(result.strip(), flush=True)

    def test_native_defaults_admission_and_inheritance(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']) * len(data['cases']))
        for result, (context, case) in zip(actual, ((r, c) for r in data['sources'] for c in data['cases'])):
            with self.subTest(revision=context['revision'], case=case):
                values, diagnostic = expected(data, context, case)
                self.assertEqual(result['revision'], context['revision'])
                self.assertEqual(result['diagnostic'], diagnostic)
                self.assertEqual(len(result['values']), len(data['fields']))
                for field, value in zip(data['fields'], result['values']):
                    if values[field] is not None:
                        self.assertEqual(value, values[field], field)


if __name__ == '__main__':
    unittest.main()
