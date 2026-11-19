"""Check string operations and text queries on the historical 4432 profiles.

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
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-4432-script-strings.json'
QUERY_FIXTURE = FIXTURE.with_name('profile-4432-script-text-queries.json')
CONSTANT_FIXTURE = FIXTURE.with_name('profile-4432-script-string-constants.json')
CONCAT_FIXTURE = FIXTURE.with_name('profile-4432-script-string-concatenation.json')
OPERATIONS = ('strinfirst', 'strleft', 'strright')


class HistoricalScriptStringTests(unittest.TestCase):
    def profile_sources(self, data):
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        cache = variant[variant.index('typedef struct'):variant.index('// find an existing constant')]
        return revisions, engine, script, variant, cache + '\n' + function(variant, 'ScriptVariant_Copy')

    def test_4432_normal_string_results(self):
        data = load_contract_fixture(FIXTURE)
        _, engine, script, _, cache = self.profile_sources(data)
        contexts = []
        for row in data['sources']:
            for operation, source, argument, result in row['cases']:
                self.assertIn(operation, OPERATIONS)
                self.assertIs(type(argument), str if operation == 'strinfirst' else int)
                self.assertIs(type(result), str if result != -1 else int)
                contexts.append('{%du,openbor_%s,%s,%s,%s,%d}' % (
                    row['revision'], operation, json.dumps(source),
                    json.dumps(argument) if isinstance(argument, str) else 'NULL',
                    json.dumps(result) if isinstance(result, str) else 'NULL',
                    argument if isinstance(argument, int) else 0))
        parts = {
            'CACHE': cache,
            'OPERATIONS': '\n'.join(function(script, 'openbor_' + name) for name in OPERATIONS),
            'CONTEXTS': ',\n'.join(contexts),
        }
        template = Path(__file__).with_name('script_strings_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()],
                         [row['revision'] for row in data['sources'] for _ in row['cases']])

    def test_4432_script_text_queries(self):
        data = load_contract_fixture(QUERY_FIXTURE)
        revisions, engine, script, variant, cache = self.profile_sources(data)
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        lists = (engine / 'source/scriptlib/List.c').read_text()
        _, entity_cases = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
        _, player_cases = switch_cases(script, 'openbor_getplayerproperty', 'prop', outermost=True)
        _, text_cases = switch_cases(script, 'openbor_gettextobjproperty', 'propind', outermost=True)
        sprite = entity_cases['_ep_spritea']['body']
        sprite = sprite[sprite.index('case _ep_spritea_file:') + len('case _ep_spritea_file:'):
                        sprite.index('case _ep_spritea_offsetx:')]
        parts = {
            'CACHE': cache + function(variant, 'ScriptVariant_IntegerValue'),
            'SUPPORT': function(lists, 'List_GetName') + ''.join(
                function(core, name) for name in ('findarg', 'readByte', 'get_cached_model_index')),
            'GETTERS': '\n'.join(function(script, name) for name in (
                'openbor_getmodelproperty', 'openbor_getfilestreamline', 'openbor_getfilestreamargument',
                'openbor_getsaveinfo', 'openbor_key', 'obor_script_sprite_name_readable')),
            'ENTITY_CASES': '\n'.join(
                'case %d:%s' % (index, entity_cases['_ep_' + name]['body'])
                for index, name in enumerate(('defaultname', 'model', 'name', 'path'))) + 'case 4:' + sprite,
            'PLAYER_CASE': player_cases['_pp_name']['body'],
            'TEXT_CASE': text_cases['_top_text']['body'],
            'CONTEXTS': ','.join(map(str, revisions)),
        }
        template = Path(__file__).with_name('script_text_queries_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline', '-Wno-error=implicit-fallthrough'))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_compiled_string_constants(self):
        data = load_contract_fixture(CONSTANT_FIXTURE)
        revisions, engine, script, variant, cache = self.profile_sources(data)
        instruction = (engine / 'source/scriptlib/Instruction.c').read_text()
        parts = {
            'METHODS': cache + function(variant, 'ScriptVariant_ParseStringConstant') + ''.join(
                function(instruction, name) for name in ('htoi', 'Instruction_ConvertConstant')) +
                function(script, 'openbor_strinlast'),
            'CONTEXTS': ','.join(map(str, revisions)),
        }
        template = Path(__file__).with_name('script_string_constants_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        results = [line.split('\t') for line in output.splitlines()]
        self.assertEqual([int(result[0]) for result in results], revisions)
        for row, (_, shared, suffix) in zip(data['sources'], results, strict=True):
            with self.subTest(profile=row['revision']):
                self.assertEqual((int(shared), suffix), (row['shared'], row['suffix']))

    def test_4432_string_concatenation(self):
        data = load_contract_fixture(CONCAT_FIXTURE)
        revisions, engine, _, variant, cache = self.profile_sources(data)
        parts = {
            'METHODS': cache + ''.join(function(variant, name) for name in (
                'ScriptVariant_DecimalValue', 'ScriptVariant_FormatValue',
                'ScriptVariant_JoinText', 'ScriptVariant_Add', 'ScriptVariant_AddAssign')),
            'CONTEXTS': ','.join('{%du,%d}' % (row['revision'], row['long_join'])
                                 for row in data['sources']),
        }
        template = Path(__file__).with_name('script_string_concatenation_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)


if __name__ == '__main__':
    unittest.main()
