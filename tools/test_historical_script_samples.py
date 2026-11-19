"""Execute native sample controls, query conventions and channel effects.

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
from test_historical_update_flow import event_digest

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-sample-contracts.json'
NAMES = ('pausesamples', 'isactivesample', 'sampleid', 'pausesample')
CALLBACKS = tuple('openbor_' + n for n in NAMES)
KINDS = ('integer', 'decimal', 'string', 'empty', 'pointer', 'null', 'null-pointer')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions) or data['channel_count'] != 64):
        raise ValueError('Own sample sources, storage extent and boundary controls required')
    for row in data['sources']:
        if (set(row['available']) != set(NAMES) or
                any(type(v) is not bool for v in row['available'].values()) or
                type(row['limit_available']) is not bool or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Source-bound sample callback and native helper presence required')
    for case in data['cases']:
        if (case['function'] not in NAMES or case['count'] not in (-1, 0, 1, 2, 3) or
                case['configured'] not in (0, 2, 3, 64) or case['pattern'] not in (0, 1) or
                type(case['null_list']) is not bool):
            raise ValueError('Bounded sample control recipe required')
        for arg in (case['first'], case['second']):
            if (arg['kind'] not in KINDS or type(arg['integer']) is not int or
                    not -2147483648 <= arg['integer'] <= 2147483647 or
                    not re.fullmatch(r'-?(?:0x[0-9a-f]+(?:\.[0-9a-f]*)?p[+-]\d+|INFINITY)|NAN', arg['decimal'])):
                raise ValueError('Bounded typed sample arguments required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
    declaration = re.search(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*'
                            r'typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;', variants)
    dependencies = (engine / 'source/scriptlib/depends.h').read_text()
    primitives = ['typedef int32_t s32;']
    for name in ('HRESULT', 'LONG', 'DOUBLE', 'VOID', 'BOOL'):
        found = re.search(r'^typedef\s+\w+\s+' + name + r'\s*;', dependencies, re.M)
        if found is None: raise ValueError('Native sample scalar declaration required')
        primitives.append(found[0])
    for name in ('S_OK', 'E_FAIL', 'FAILED'):
        found = re.search(r'^#define\s+' + name + r'\b[^\n]*', dependencies, re.M)
        if found is None: raise ValueError('Native sample result definition required')
        primitives.append(found[0])
    if declaration is None: raise ValueError('Native variant declaration required')
    registry = '\n'.join(function(script, n) for n in
                         ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', registry)))
    if not 8 <= len(symbols) <= 512 or not set(CALLBACKS) <= set(symbols):
        raise ValueError('Complete bounded native sample registry required')
    renamed = {n: 'other_' + n for n in symbols if n not in CALLBACKS}
    sound = (engine / 'source/gamelib/soundmix.c').read_text()
    channel_type = re.search(r'typedef struct\s*\{[^{}]*\}\s*channelstruct;', sound)
    extent = re.search(r'^#define\s+MAX_CHANNELS\s+\d+[^\n]*', sound, re.M)
    if channel_type is None or extent is None: raise ValueError('Native channel type and extent required')
    observations = dict(sound_pause_sample='observe_all', sound_pause_single_sample='observe_single',
                        sound_is_active='observe_active', sound_id='observe_id')
    rows = []
    for case in data['cases']:
        args = ['{%d,%d,%s}' % (KINDS.index(a['kind']), a['integer'], a['decimal'])
                for a in (case['first'], case['second'])]
        rows.append('{%d,%d,%d,%d,%d,{%s}}' % (NAMES.index(case['function']), case['count'],
            case['null_list'], case['configured'], case['pattern'], ','.join(args)))
    variant_source = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    values = dict(PRIMITIVES='\n'.join(primitives), VARIANT_TYPES=declaration[0],
        CHANNEL_TYPE=channel_type[0], CHANNEL_EXTENT=extent[0],
        SOUND_METHODS='\n'.join(function(sound, n) for n in
            ('sound_pause_sample', 'sound_pause_single_sample', 'sound_is_active', 'sound_id', 'maxchannels')),
        VARIANTS='\n'.join(function(variant_source, n) for n in
            ('ScriptVariant_IntegerValue', 'ScriptVariant_IsTrue', 'ScriptVariant_ChangeType')),
        CALLBACKS=rename_identifiers('\n'.join(function(script, n) for n in CALLBACKS), observations),
        STUBS='\n'.join('static void %s(void){stub_calls+=%du;}' % (renamed[n], i + 1)
                         for i, n in enumerate(symbols) if n in renamed),
        REGISTRY=rename_identifiers(registry, renamed), NAMES=','.join(map(json.dumps, NAMES)),
        POINTERS=','.join('(void *)' + n for n in CALLBACKS),
        CONTEXTS=','.join('{%du,%d,{%s}}' % (r['revision'], r['limit_available'],
            ','.join(str(int(r['available'][n])) for n in NAMES)) for r in data['sources']),
        CASES=','.join(rows))
    text = Path(__file__).with_name('script_samples_contract.c.in').read_text()
    for key, value in values.items(): text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native sample dependency')
    return text


def expected(case, marker):
    paused = [(i + case['pattern']) % 2 for i in range(64)]
    result = dict(status=0, out_null=False, marker_type=6 if marker == 0 else 1,
        marker_value=17 if marker == 0 else -77, collected=0, cache_reads=0,
        backend='', channel=-999, toggle=-999, helper_result=-2147483648,
        events=[], arguments_unchanged=True, other_fields_unchanged=True)
    name = case['function']
    count = 2 if name == 'pausesample' else 1
    first, second = case['first'], case['second']
    present = (case['count'] >= count and not case['null_list'] and first['kind'] != 'null' and
               (name != 'pausesample' or second['kind'] != 'null'))
    if name in ('pausesamples', 'pausesample'):
        if present:
            truth = int(first['truth'])
            if first['kind'] == 'string':
                result['cache_reads'] = 1
                result['events'].append('string')
            if name == 'pausesamples':
                result.update(backend='all', toggle=truth)
                result['events'].append('all')
                for i in range(case['configured']): paused[i] = truth
            elif second['converted'] is not None:
                channel = second['converted']
                result.update(backend='single', channel=channel, toggle=truth)
                result['events'].append('single')
                if 0 <= channel < 64: paused[channel] = truth
    else:
        result.update(status=-1, out_null=True)
        if present and first['converted'] is not None:
            channel = first['converted']
            active = 0 <= channel < 64 and (channel + case['pattern']) % 3 != 0
            value = int(active) if name == 'isactivesample' else 1000 + 13 * channel if active else -1
            result.update(marker_type=1, marker_value=value, backend='active' if name == 'isactivesample' else 'id',
                          channel=channel, helper_result=value)
            if marker == 0:
                result['collected'] = 1
                result['events'].append('collect')
            result['events'].append(result['backend'])
    result['channel_digest'] = event_digest([['paused', *paused]])
    return result


class ScriptSampleContracts(unittest.TestCase):
    def test_native_names_truth_conversion_channels_and_return_conventions(self):
        data = fixture_data()
        actual = iter(io.StringIO(native_output(program(data), data)))
        for row in data['sources']:
            line = next(actual, None)
            self.assertIsNotNone(line)
            self.assertEqual(json.loads(line), dict(revision=row['revision'],
                registered=[int(row['available'][n]) for n in NAMES],
                reverse=[n if row['available'][n] else '<unknown function>' for n in NAMES],
                native_limit=64 if row['limit_available'] else 0, control_names=True, resets=1))
            for index, case in enumerate(data['cases']):
                if not row['available'][case['function']]: continue
                for marker in (0, 1):
                    line = next(actual, None)
                    self.assertIsNotNone(line)
                    self.assertEqual(json.loads(line), dict(revision=row['revision'], case=index,
                        marker=marker, **expected(case, marker)), 'revision=%d case=%s marker=%d' %
                        (row['revision'], case['name'], marker))
        self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
