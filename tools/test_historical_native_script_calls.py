"""Execute source-owned seed, video, truncation and rounding script calls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import io
import json
import math
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-native-script-calls-contracts.json'
NAMES = ('srand', 'playwebm', 'trunc', 'round')
CALLBACKS = ('system_srand', 'openbor_playwebm', 'math_trunc', 'math_round')
KINDS = ('integer', 'decimal', 'string', 'empty', 'pointer', 'null')
VIDEO_ERROR = 'Function need a string parameter, other parameters are optional: playwebm(path, int noskip)\n'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own native script-call sources and boundary controls required')
    for row in data['sources']:
        if (set(row['available']) != set(NAMES) or
                any(type(v) is not bool for v in row['available'].values()) or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Explicit source-owned callback availability required')
    for case in data['cases']:
        if (case['function'] not in NAMES or case['count'] not in (-1, 0, 1, 2, 3) or
                type(case['null_list']) is not bool or case['backend_result'] not in (-1, 0, 1, 37)):
            raise ValueError('Bounded native call recipe required')
        for arg in (case['first'], case['second']):
            if (arg['kind'] not in KINDS or type(arg['integer']) is not int or
                    not -2147483648 <= arg['integer'] <= 2147483647 or
                    not re.fullmatch(r'-?(?:0x[0-9a-f]+(?:\.[0-9a-f]*)?p[+-]\d+|INFINITY)|NAN', arg['decimal'])):
                raise ValueError('Explicit bounded native variant required')
    return data


def program(data, webm):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
    declaration = re.search(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*'
                            r'typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;', variants)
    dependencies = (engine / 'source/scriptlib/depends.h').read_text()
    primitives = ['typedef int32_t s32;', 'typedef uint64_t u64;']
    for name in ('HRESULT', 'LONG', 'DOUBLE', 'VOID'):
        found = re.search(r'^typedef\s+\w+\s+' + name + r'\s*;', dependencies, re.M)
        if found is None: raise ValueError('Native script scalar declaration required')
        primitives.append(found[0])
    for name in ('S_OK', 'E_FAIL', 'FAILED', 'SUCCEEDED'):
        found = re.search(r'^#define\s+' + name + r'\b[^\n]*', dependencies, re.M)
        if found is None: raise ValueError('Native script result definition required')
        primitives.append(found[0])
    if declaration is None: raise ValueError('Native variant declarations required')
    registry = '\n'.join(function(script, n) for n in
                         ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', registry)))
    if not 8 <= len(symbols) <= 512 or not set(CALLBACKS) <= set(symbols):
        raise ValueError('Bounded native registry and selected symbols required')
    renamed = {n: 'other_' + n for n in symbols if n not in CALLBACKS}
    rand = (engine / 'source/randlib/rand32.c').read_text()
    initial = re.search(r'^u64\s+seed\s*=\s*[^;]+;', rand, re.M)
    if initial is None: raise ValueError('Native seed initializer required')
    cases = []
    for case in data['cases']:
        args = []
        for arg in (case['first'], case['second']):
            args.append('{%d,%d,%s}' % (KINDS.index(arg['kind']), arg['integer'], arg['decimal']))
        cases.append('{%d,%d,%d,%d,{%s}}' % (NAMES.index(case['function']), case['count'],
            case['null_list'], case['backend_result'], ','.join(args)))
    variant_source = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    values = dict(WEBM='#define WEBM 1' if webm else '#undef WEBM',
        PRIMITIVES='\n'.join(primitives), VARIANT_TYPES=declaration[0], SEED='static ' + initial[0],
        SEED_METHODS='\n'.join(function(rand, n) for n in ('srand32', 'getseed')),
        VARIANTS='\n'.join(function(variant_source, n) for n in
            ('ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue', 'ScriptVariant_ChangeType', 'ScriptVariant_Clear')),
        CALLBACKS=rename_identifiers('\n'.join(function(script, n) for n in CALLBACKS), {'printf': 'probe_printf'}),
        STUBS='\n'.join('static void %s(void){stub_calls+=%du;}' % (renamed[n], i + 1)
                         for i, n in enumerate(symbols) if n in renamed),
        REGISTRY=rename_identifiers(registry, renamed), NAMES=','.join(map(json.dumps, NAMES)),
        POINTERS=','.join('(void *)' + n for n in CALLBACKS),
        CONTEXTS=','.join('{%du,{%s}}' % (r['revision'], ','.join(str(int(r['available'][n])) for n in NAMES))
                          for r in data['sources']), CASES=','.join(cases))
    text = Path(__file__).with_name('native_script_calls_contract.c.in').read_text()
    for key, value in values.items(): text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native script-call dependency')
    return text


def expected(case, marker, webm):
    result = dict(status=-1, out_null=True, marker_type=6 if marker == 0 else 1,
        marker_value='17' if marker == 0 else '-77', collected=0, path_gets=0,
        backend_calls=0, backend_path='', backend_skip=0,
        seed='0102030405060708', diagnostic='', events=[], arguments_unchanged=True)
    first, second = case['first'], case['second']
    present = case['count'] >= 1 and not case['null_list'] and first['kind'] != 'null'
    value = first['converted']
    name = case['function']
    success = False
    if name == 'srand':
        success = present and case['count'] == 1 and value is not None
        if success: result['seed'] = '%016x' % (value & 0xffffffffffffffff)
    elif name == 'playwebm':
        success = present and first['kind'] == 'string'
        if case['count'] > 1: success &= second['converted'] is not None
        if not success:
            result['diagnostic'] = VIDEO_ERROR
            result['events'] = ['diagnostic']
        else:
            path = ('clip.webm', '')[first['integer']]
            if webm and marker == 0:
                result['collected'] = 1
                result['events'].append('collect')
            result['path_gets'] = 1
            result['events'].append('path')
            if webm:
                result.update(out_null=False, marker_type=1, marker_value=str(case['backend_result']),
                    backend_calls=1, backend_path=path,
                    backend_skip=second['converted'] if case['count'] > 1 else 0)
                result['events'].append('play')
            else:
                result['diagnostic'] = 'Skipping video %s; WebM playback not supported on this platform\n' % path
                result['events'].append('diagnostic')
    else:
        success = present and first['kind'] in ('integer', 'decimal')
        if name == 'trunc': success &= value is not None
        if success:
            result.update(out_null=False, marker_type=1 if name == 'trunc' else 2,
                          marker_value=str(value) if name == 'trunc' else first['rounded'])
            if marker == 0:
                result['collected'] = 1
                result['events'] = ['collect']
    if success: result['status'] = 0
    return result


class NativeScriptCallContracts(unittest.TestCase):
    def test_selected_native_calls_values_errors_and_feature_conditions(self):
        data = fixture_data()
        for webm in (False, True):
            actual = iter(io.StringIO(native_output(program(data, webm), data, libraries=('m',))))
            for row in data['sources']:
                line = next(actual, None)
                self.assertIsNotNone(line)
                self.assertEqual(json.loads(line), dict(revision=row['revision'],
                    registered=[int(row['available'][n]) for n in NAMES],
                    reverse=[n if row['available'][n] else '<unknown function>' for n in NAMES],
                    control_names=True, resets=1))
                for index, case in enumerate(data['cases']):
                    if not row['available'][case['function']]: continue
                    for marker in (0, 1):
                        line = next(actual, None)
                        self.assertIsNotNone(line)
                        got = json.loads(line)
                        wanted = dict(revision=row['revision'], case=index, marker=marker,
                                      **expected(case, marker, webm))
                        if wanted['marker_type'] == 2:
                            seen = float.fromhex(got['marker_value'])
                            value = float.fromhex(wanted['marker_value'])
                            got['marker_value'] = 'nan' if math.isnan(seen) else seen.hex()
                            wanted['marker_value'] = 'nan' if math.isnan(value) else value.hex()
                        self.assertEqual(got, wanted, 'WEBM=%d revision=%d case=%s marker=%d' %
                                         (webm, row['revision'], case['name'], marker))
            self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
