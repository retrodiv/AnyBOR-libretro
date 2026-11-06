"""Check historical load, spawn and toss script entry contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-model-caller-contracts.json'


class WaypointScriptAndModel(unittest.TestCase):
    def test_native_waypoint_calls_and_model_command_boundaries(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-waypoint-api-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        engine = ROOT / 'src/engines' / data['engine']
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        commands = (engine / 'source/gamelib/commands.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        _, cases = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
        gates = re.findall(r'if\(functionRef == \(void\*\)openbor_waypoints\) return [^;]+;',
                           function(script, 'obor_script_function_available'))
        self.assertEqual(len(gates), 1)
        observer = function(core, 'handle_txt_include').split('{', 1)[0] + '{abort();}'
        parts = dict(LOWERCASE=function((engine / 'source/utils.c').read_text(), 'lc'),
                     COMMANDS='\n'.join(function(commands, name) for name in
                                       ('prepareList', 'createModelCommandList', 'getCommandlistCommand',
                                        'getModelCommand', 'freeCommandList')),
                     INCLUDE_OBSERVER=observer, DECIMAL_VALUE=function(variants, 'ScriptVariant_DecimalValue'),
                     WAYPOINTS=function(script, 'openbor_waypoints'),
                     CASE=cases['CMD_MODEL_PATHFINDSTEP']['body'], DEFAULT=cases['default']['body'],
                     AVAILABILITY=gates[0]+'\n',
                     PROFILES=','.join(str(r['revision'])+'u' for r in rows),
                     MODEL_CASES=',\n'.join('{%s,%s,%s}' %
                                            (json.dumps(c['name']), repr(c['initial']), repr(c['value']))
                                            for c in data['model_cases']),
                     SCRIPT_CASES=',\n'.join('{%d,%d,%d,%d}' %
                                             (c['argc'], c['seed'], c['first_type'], c['coordinates'])
                                             for c in data['script_cases']))
        text = Path(__file__).with_name('waypoint_api_contract.c.in').read_text()
        for key, value in parts.items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        expected = [dict(revision=r['revision'], **c) for r in rows for c in data['contracts'][r['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], kind=oracle['kind'], case=oracle['case']):
                self.assertEqual(result, oracle)


class InlineModelScriptPosition(unittest.TestCase):
    def test_native_inline_script_admission_and_generated_text(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-model-script-position-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        model = function(core, 'load_cached_model')
        case = model.split('case CMD_MODEL_AT_SCRIPT:', 1)[1].split('case CMD_MODEL_AT_CMD:', 1)[0]
        first = re.search(r'static const char(?:\*\s*|\s+)pre_text', model)
        self.assertIsNotNone(first)
        constants = model[first.start():model.index('modelCommands cmd;', first.start())]
        text = Path(__file__).with_name('model_script_position_contract.c.in').read_text()
        for key, value in {'APPEND': function(core, 'buffer_append'), 'CASE': case,
                           'CONSTANTS': constants,
                           'PROFILES': ','.join(str(r['revision']) + 'u' for r in rows),
                           'CASES': ',\n'.join('{%d,%d,%s}' % (c['reset'], c['animation'],
                                                   json.dumps(c['body'])) for c in data['cases'])}.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        expected = [dict(revision=row['revision'], case=i, **value) for row in rows
                    for i, value in enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], case=oracle['case']):
                self.assertEqual(result, oracle)


class DynamicScriptHeap(unittest.TestCase):
    def test_native_arguments_return_tags_and_owned_disposal(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-script-heap-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        engine = ROOT / 'src/engines' / data['engine']
        source = (engine / 'openborscript.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        names = ('openbor_allocscript', 'openbor_loadscript',
                 'openbor_compilescript', 'openbor_executescript')
        availability = function(source, 'obor_script_function_available')
        gates = []
        for name in names:
            matches = re.findall(r'if\(functionRef == \(void\*\)' + name +
                                 r'\) return [^;]+;', availability)
            self.assertEqual(len(matches), 1)
            gates.append(matches[0])
        parts = dict(
            VARIANTS='\n'.join(function(variants, name) for name in
                              ('ScriptVariant_ChangeType', 'ScriptVariant_Init', 'ScriptVariant_Clear')),
            REFERENCES='\n'.join(function(source, name) for name in
                                ('obor_script_destroy_interpreter', 'obor_script_replace_interpreter',
                                 'obor_script_destroy_comment', 'obor_script_replace_comment')),
            LIFECYCLE='\n'.join(function(source, name) for name in ('Script_Init', 'Script_Clear')),
            DISPOSAL='\n'.join(function(source, name) for name in
                              ('_freeheapnode', 'obor_script_variable_names_clear', 'Script_Global_Clear', 'system_free')),
            ENTRY_POINTS='\n'.join(function(source, name) for name in names),
            AVAILABILITY='\n'.join(gates),
            PROFILES=','.join('{%du,%d,%d,%d}' %
                              (r['revision'], r['dynamic_available'], r['second_string_is_comment'],
                               r['typed_return']) for r in rows))
        text = Path(__file__).with_name('script_heap_contract.c.in').read_text()
        for key, value in parts.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        expected = [dict(revision=row['revision'], case=i, **value) for row in rows
                    for i, value in enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], case=oracle['case']):
                self.assertEqual(result, oracle)


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    parts = dict(FUNCTIONS='\n'.join(function(source, n) for n in
        ('openbor_loadmodel', 'openbor_spawn', 'openbor_tossentity')),
        VARIANTS='\n'.join(function(variant, n) for n in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue',
             'ScriptVariant_IsTrue')),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d,%s,%s}' % (r['revision'],
            r['unload_extra'], r['selectable'], r['spawn_boss'], r['toss_strict'],
            json.dumps(r['load_diagnostic']), json.dumps(r['toss_diagnostic']))
            for r in data['sources']))
    text = Path(__file__).with_name('model_callers_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved model caller dependency')
    return text


class ScriptModelCalls(unittest.TestCase):
    def test_native_arguments_results_and_service_order(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], model_cases=58,
                                      spawn_cases=24, toss_cases=48)
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
