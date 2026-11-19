"""Check own grammar tables, native parser instruction order and recovery.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-grammar-contracts.json'
STATEMENTS = FIXTURE.with_name('profile-4432-statement-list-contracts.json')


def source_engine(data):
    return Path(os.environ.get('OBOR_GRAMMAR_ENGINE', ROOT / 'src/engines' / data['engine']))


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own grammar profiles and transition controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['Parser.c']) or
                row['table_contract'] not in data['table_contracts'] or
                any(row[f] not in (0, 1) for f in
                    ('bitwise_forms', 'numeric_constant_not', 'decimal_constant_not',
                     'chained_assignment'))):
            raise ValueError('Bound native grammar expectations required')
    return data


def quoted(value):
    return 'NULL' if value is None else json.dumps(value)


def program(data):
    engine = source_engine(data)
    source = (engine / 'source/scriptlib/Parser.c').read_text()
    lexer = (engine / 'source/scriptlib/Lexer.c').read_text()
    names = ('obor_parser_legacy_bitwise', 'obor_parser_prefix_token',
        'Parser_Check', 'Parser_Match', '_production_error_message', 'Parser_Error2',
        'Parser_Assignment_op', 'Parser_Constant', 'Parser_Primary_expr',
        'Parser_Postfix_expr', 'Parser_Unary_expr', 'Parser_Postfix_expr2',
        'Parser_Cond_expr', 'Parser_Cond_expr2', 'Parser_Assignment_expr',
        'Parser_Assignment_expr2')
    keys = sorted(data['table_contracts'])
    tables = []
    for key in keys:
        table = data['table_contracts'][key]
        families = []
        for family in ('first', 'follow'):
            if len(table[family]) != 67:
                raise ValueError('Complete own production table required')
            families.append('{' + ','.join('{%d,{%s}}' %
                (len(r['tokens']), ','.join(r['tokens']) or '0') for r in table[family]) + '}')
        tables.append('{' + ','.join(families) + '}')
    rows = []
    for row in data['sources']:
        choices = [row[c['feature']] if c.get('feature') else 0 for c in data['cases']]
        rows.append('{%du,%d,{%s}}' % (row['revision'], keys.index(row['table_contract']),
                                     ','.join(map(str, choices))))
    cases = []
    methods = {'assignment': 0, 'operator': 1, 'recovery': 2}
    for case in data['cases']:
        if not 1 <= len(case['tokens']) <= 16:
            raise ValueError('Bounded explicit token stream required')
        tokens = ','.join('{%s,%s}' % (t, json.dumps(s)) for t, s in case['tokens'])
        expectations = []
        for outcome in case['outcomes']:
            if len(outcome['instructions']) > 24:
                raise ValueError('Bounded native instruction stream required')
            instructions = ','.join('{%s,%s}' % (op, quoted(text))
                                     for op, text in outcome['instructions']) or '{NOOP,NULL}'
            expectations.append('{%s,%s,%s,%d,{%s}}' %
                (quoted(outcome['diagnostic']), outcome['next'], outcome.get('operator', 'ERR'),
                 len(outcome['instructions']), instructions))
        if len(expectations) != 2:
            raise ValueError('Both sides of source behavior required')
        cases.append('{%s,%d,%d,{%s},{%s}}' % (json.dumps(case['name']),
            methods[case['method']], len(case['tokens']), tokens, ','.join(expectations)))
    values = dict(TABLES=','.join(tables), CONTEXTS=','.join(rows), CASES=','.join(cases),
        CASE_COUNT=str(len(cases)), FUNCTIONS=function(lexer, 'Token_Init') + '\n' +
            '\n'.join(function(source, n) for n in names))
    code = Path(__file__).with_name('script_grammar_contract.c.in').read_text()
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native grammar dependency')
    return code


class ScriptGrammarContracts(unittest.TestCase):
    def test_complete_memberships_native_emission_and_error_recovery(self):
        data = fixture_data()
        output = native_output(program(data), data, engine_source=source_engine(data))
        lines = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(lines, [dict(revision=r['revision'], status='PASS',
            tables=2, productions=67, cases=len(data['cases'])) for r in data['sources']])

    def test_native_compound_and_switch_statement_lists(self):
        data = load_contract_fixture(STATEMENTS)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = source_engine(data)
        source = (engine / 'source/scriptlib/Parser.c').read_text()
        names = ('Parser_Check', 'Parser_Match', 'Parser_Decl_list', 'Parser_Decl_list2',
                 'Parser_Stmt_list', 'Parser_Stmt_list2', 'obor_parser_compound_body',
                 'Parser_Comp_stmt_Label', 'Parser_Comp_stmt', 'Parser_Comp_stmt2',
                 'Parser_Comp_stmt3', 'Parser_Switch_body', '_production_error_message',
                 'Parser_Error2')
        cases = []
        for row in data['cases']:
            self.assertLessEqual(len(row['tokens']), 12)
            cases.append('{%s,%d,{%s},{%s},{%s}}' % (
                row['route'], len(row['tokens']), ','.join(row['tokens']),
                ','.join(quoted(item) for item in row['trace']),
                ','.join(quoted(item) for item in row['diagnostic'])))
        families = ('first', 'follow')
        tables = ',\n'.join('{' + ','.join('{' + ','.join(table[key] + ['END_OF_TOKENS']) + '}'
                            for key in families) + '}' for table in data['tables'])
        parts = dict(FUNCTIONS='\n'.join(function(source, n) for n in names),
                     CASES=',\n'.join(cases), TABLES=tables,
                     CONTEXTS=',\n'.join('{%du,%d}' % (row['revision'], row['table'])
                                         for row in data['sources']))
        template = Path(__file__).with_name('statement_lists_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)
        output = native_output(probe, data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)


if __name__ == '__main__':
    unittest.main()
