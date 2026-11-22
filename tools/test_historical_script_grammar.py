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
from test_early_jump_walkoff import braced_statement
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
    def test_7533_original_interpreter_diagnostic(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        interpreter = (engine / 'source/scriptlib/Interpreter.c').read_text()
        dispatch = function(interpreter, 'Interpreter_Call')
        message = re.search(r'(?m)^            printf\([^;]+returned an exception[^;]+;', dispatch)
        self.assertIsNotNone(message)
        code = r'''
#include "Interpreter.h"
#include <stdint.h>
#include <stdio.h>
#undef printf

unsigned int obor_profile_build;

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7503, 7504, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
@MESSAGE@
    }
    return 0;
}
'''
        message_source = message[0].replace('List_GetName(pinterpreter->ptheFunctionList)', '"score"')
        observed = native_output(code.replace('@MESSAGE@', message_source), data, engine_source=engine)
        old = "Script function 'score' returned an exception, check the manual for details.\n"
        new = "Script function 'score' returned an exception. See any preceding error messages above for details.\n"
        self.assertEqual(observed, old * 4 + new * 2)

    def test_7533_original_bitwise_not_instruction_order(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'source/scriptlib/Parser.c').read_text()
        prefix = braced_statement(function(source, 'Parser_Unary_expr'),
                                  'else if (Parser_Check(pparser, TOKEN_BITWISE_NOT ))')
        postfix = braced_statement(function(source, 'Parser_Postfix_expr2'),
                                   'else if (obor_parser_uses_legacy_bitwise_not() && Parser_Check(pparser, TOKEN_BITWISE_NOT ))')
        code = r'''
#include "Parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#undef sprintf

unsigned int obor_profile_build;
static Token word;
static Instruction operand;
static OpCode emitted[3];
static unsigned count, matches, operands;

BOOL Parser_Check(Parser *parser, MY_TOKEN_TYPE type)
{
    return parser->theNextToken.theType == type;
}

void Parser_Match(Parser *parser) { (void)parser; ++matches; }
void Parser_Unary_expr(Parser *parser) { (void)parser; ++operands; }
void *List_Retrieve(const List *list) { (void)list; return &operand; }

void Parser_AddInstructionViaToken(Parser *parser, OpCode operation, Token *token, Label label)
{
    (void)parser;
    if (count == sizeof(emitted) / sizeof(*emitted) || label ||
        token != ((operation == SAVE || operation == LOAD) ? &word : NULL))
    {
        abort();
    }
    emitted[count++] = operation;
}

@LEGACY@

static void prefix_not(Parser *pparser)
{
    Instruction *pInstruction;
    char buf[MAX_TOKEN_LENGTH + 1];
@PREFIX@
}

static void postfix_not(Parser *pparser)
{
@POSTFIX@
}

int main(void)
{
    static const unsigned builds[] = {0, 7369, 7371, 7372, 7373, 7391, 7420, 7533};
    static Parser parser;
    operand.theToken = &word;
    parser.theNextToken.theType = TOKEN_BITWISE_NOT;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] && builds[i] < 7372u;
        operand.OpCode = LOAD;
        strcpy(word.theSource, "points");
        count = matches = operands = 0;
        prefix_not(&parser);
        if (matches != 1 || operands != 1 || count != (legacy ? 3u : 1u) ||
            emitted[0] != (legacy ? NEG : BIT_NOT) ||
            (legacy && (emitted[1] != SAVE || emitted[2] != LOAD)))
        {
            abort();
        }

        count = matches = operands = 0;
        postfix_not(&parser);
        if (matches != (unsigned)legacy || operands != (unsigned)legacy ||
            count != (legacy ? 3u : 0u) ||
            (legacy && (emitted[0] != NEG || emitted[1] != SAVE || emitted[2] != LOAD)))
        {
            abort();
        }

        operand.OpCode = CONSTINT;
        strcpy(word.theSource, "3");
        count = 0;
        prefix_not(&parser);
        if (count != (legacy ? 3u : 0u) || strcmp(word.theSource, legacy ? "3" : "-4"))
        {
            abort();
        }
    }
    return 0;
}
'''
        helpers = ('obor_parser_uses_legacy_bitwise_not', 'obor_parser_legacy_bitwise_not')
        staged = (code.replace('@LEGACY@', '\n'.join(function(source, name) for name in helpers))
                  .replace('@PREFIX@', prefix.removeprefix('else '))
                  .replace('@POSTFIX@', postfix.removeprefix('else ')))
        self.assertEqual(native_output(staged, data, engine_source=engine), '')

    def test_6391_preprocessor_diagnostic_output(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-preprocessor-diagnostics.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = source_engine(data)
        source = (engine / 'source/preprocessorlib/pp_parser.c').read_text()
        routing = re.search(r'(?ms)^#if defined\(LIBRETRO\) && !PP_TEST\n'
                            r'#define PP_MESSAGE_OUTPUT.*?^#endif\n', source)[0]
        values = {
            'ROUTING': routing,
            'MESSAGE': function(source, 'pp_message'),
            'PROFILES': ','.join('{%du,%d}' % (row['revision'], row['engine_log']) for row in rows),
        }
        template = Path(__file__).with_name('preprocessor_diagnostics_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

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
