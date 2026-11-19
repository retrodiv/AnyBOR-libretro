"""Execute native main-menu script binding, conversion and request propagation.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import io
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-main-menu-script-contracts.json'
KINDS = ('integer', 'decimal', 'empty', 'string', 'pointer', 'null')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions) or data['counts'] != [-1, 0, 1, 3]):
        raise ValueError('Own main-menu script sources and count cases required')
    for row in data['sources']:
        if (type(row['available']) is not bool or not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Source-bound name and native callback availability required')
    for case in data['cases']:
        if (case['kind'] not in KINDS or type(case['accepted']) is not bool or
                type(case['value']) is not int or not -2147483648 <= case['value'] <= 2147483647 or
                not re.fullmatch(r'-?(?:\d+(?:\.\d*)?|INFINITY)|NAN', case['decimal'])):
            raise ValueError('Explicit bounded variant and conversion cases required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
    declarations = re.search(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*'
                             r'typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;', variant)
    if declarations is None: raise ValueError('Native variant declarations required')
    dependencies = (engine / 'source/scriptlib/depends.h').read_text()
    primitives = ['typedef int32_t s32;']
    for name in ('HRESULT', 'LONG', 'DOUBLE', 'VOID'):
        found = re.search(r'^typedef\s+\w+\s+' + name + r'\s*;', dependencies, re.M)
        if found is None: raise ValueError('Native script scalar declaration required')
        primitives.append(found[0])
    for name in ('S_OK', 'E_FAIL', 'FAILED'):
        found = re.search(r'^#define\s+' + name + r'\b[^\n]*', dependencies, re.M)
        if found is None: raise ValueError('Native script result constant required')
        primitives.append(found[0])
    registry = '\n'.join(function(script, name) for name in
                         ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', registry)))
    selected = 'openbor_gotomainmenu'
    if not 8 <= len(symbols) <= 512 or selected not in symbols:
        raise ValueError('Bounded native registry and main-menu symbol required')
    renamed = {name: 'other_' + name for name in symbols if name != selected}
    stubs = '\n'.join('static void %s(void){stub_calls+=%du;}' % (renamed[n], i + 1)
                      for i, n in enumerate(symbols) if n in renamed)
    samples = ','.join('{%d,%d,%s}' % (KINDS.index(c['kind']), c['integer'], c['decimal'])
                       for c in data['cases'])
    values = dict(PRIMITIVES='\n'.join(primitives), VARIANT_TYPES=declarations[0],
        GETTER=function((engine / 'source/scriptlib/ScriptVariant.c').read_text(), 'ScriptVariant_IntegerValue'),
        SETTER=function(core, 'goto_mainmenu'), CALLBACK=function(script, selected), STUBS=stubs,
        REGISTRY=rename_identifiers(registry, renamed),
        COUNTS=','.join(map(str, data['counts'])), SAMPLES=samples,
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['available']) for r in data['sources']))
    text = Path(__file__).with_name('main_menu_script_contract.c.in').read_text()
    for key, value in values.items(): text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native main-menu script dependency')
    return text


def expected(case, count):
    accepted = count <= 0 or case['accepted']
    value = 0 if count <= 0 else case['value']
    flag = (1 | ((value & 0xffffffff) << 1)) & 0xffffffff
    if flag >= 0x80000000: flag -= 0x100000000
    return dict(status=0 if accepted else -1, flag=flag if accepted else 77,
                result_null=True, arguments_unchanged=True, marker_unchanged=True)


class MainMenuScriptContracts(unittest.TestCase):
    def test_native_registry_reverse_name_and_selected_callback(self):
        data = fixture_data()
        actual = iter(io.StringIO(native_output(program(data), data)))
        for row in data['sources']:
            line = next(actual, None)
            self.assertIsNotNone(line)
            self.assertEqual(json.loads(line), dict(revision=row['revision'],
                registered=int(row['available']), reverse='gotomainmenu' if row['available'] else
                '<unknown function>', control_names=True, resets=1, unknown='<unknown function>'))
            if not row['available']: continue
            for index, case in enumerate(data['cases']):
                for count in data['counts']:
                    line = next(actual, None)
                    self.assertIsNotNone(line)
                    self.assertEqual(json.loads(line), dict(revision=row['revision'], case=index,
                        count=count, **expected(case, count)), 'revision=%d case=%s count=%d' %
                        (row['revision'], case['name'], count))
        self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
