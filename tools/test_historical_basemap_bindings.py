"""Execute native basemap bindings, including the historical height alias.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-basemap-binding-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own basemap binding sources and boundary controls required')
    for row in data['sources']:
        if (type(row['index_available']) is not bool or row['index_target'] not in (None, 'height') or
                row['direct_target'] not in (None, 'height', 'index') or
                (row['index_target'] is not None) != row['index_available'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Own native/reverse presence and actual forward target required')
    for c in data['cases']:
        if (not 0 <= c['scene'] < len(data['scenes']) or c['count'] not in (0, 1, 2, 3) or
                any(t not in (0, 1, 2, 3, 4) for t in c['types']) or
                any(not re.fullmatch(r'-?0x[0-9a-f]+(?:\.[0-9a-f]*)?p[+-]\d+', x) for x in c['values'])):
            raise ValueError('Bounded defined coordinate cases required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
    declaration = re.search(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*'
                            r'typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;', variant)
    dependencies = (engine / 'source/scriptlib/depends.h').read_text()
    primitives = ['typedef int32_t s32;']
    for name in ('HRESULT', 'LONG', 'DOUBLE', 'VOID'):
        m = re.search(r'^typedef\s+\w+\s+' + name + r'\s*;', dependencies, re.M)
        if m is None: raise ValueError('Native basemap scalar declaration required')
        primitives.append(m[0])
    for name in ('S_OK', 'E_FAIL', 'FAILED'):
        m = re.search(r'^#define\s+' + name + r'\b[^\n]*', dependencies, re.M)
        if m is None: raise ValueError('Native basemap status definition required')
        primitives.append(m[0])
    if declaration is None: raise ValueError('Native variant declarations required')
    types = []
    for name in ('s_axis_i', 's_basemap'):
        m = re.search(r'typedef struct\s*\{[^{}]*\}\s*' + name + ';', header)
        if m is None: raise ValueError('Native integral basemap metadata required')
        types.append(m[0])
    registry = '\n'.join(function(script, n) for n in ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    if 'obor_has_computed_damage()' in registry:
        registry = function(script, 'obor_has_computed_damage') + '\n' + registry
    selected = {'openbor_checkbasemap', 'openbor_checkbasemapindex'}
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', registry)))
    if not selected <= set(symbols) or not 8 <= len(symbols) <= 512:
        raise ValueError('Bounded complete registry and both native callbacks required')
    renamed = {n: 'other_' + n for n in symbols if n not in selected}
    scenes = []
    for scene in data['scenes']:
        maps = []
        for b in scene['maps']:
            if b['size'] != [2, 2] or len(b['data']) != 4: raise ValueError('Bounded authored map cells required')
            maps.append('{%d,%d,{%s}}' % (*b['position'], ','.join(float(x).hex() for x in b['data'])))
        scenes.append('{%d,%d,{%s}}' % (scene['level'], len(maps), ','.join(maps) or '{0}'))
    values = dict(PRIMITIVES='\n'.join(primitives), VARIANT_TYPES=declaration[0], TYPES='\n'.join(types),
        CORE='\n'.join(function(core, n) for n in ('check_basemap', 'check_basemap_index')),
        VARIANTS='\n'.join(function((engine / 'source/scriptlib/ScriptVariant.c').read_text(), n)
                           for n in ('ScriptVariant_DecimalValue', 'ScriptVariant_ChangeType')),
        CALLBACKS=rename_identifiers('\n'.join(function(script, n) for n in
            ('openbor_checkbasemap', 'openbor_checkbasemapindex')),
            {'check_basemap': 'observe_height', 'check_basemap_index': 'observe_index'}),
        STUBS='\n'.join('static void %s(void){stub_calls+=%du;}' % (renamed[n], i + 1)
                         for i, n in enumerate(symbols) if n in renamed),
        REGISTRY=rename_identifiers(registry, renamed), SCENES=','.join(scenes),
        CASES=','.join('{%d,%d,{%d,%d},{%s}}' % (c['scene'], c['count'], *c['types'], ','.join(c['values']))
                       for c in data['cases']),
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['index_available']) for r in data['sources']))
    text = Path(__file__).with_name('basemap_binding_contract.c.in').read_text()
    for key, value in values.items(): text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native basemap dependency')
    return text


def expected(case, entry, marker, direct_target='index'):
    result = dict(status=0, out_null=False, marker_type=2, value='0x0p+0', collected=int(marker == 0),
                  backend='', x=0, z=0, arguments_unchanged=True)
    if case['count'] < 2:
        result.update(status=-1, out_null=True, marker_type=6 if marker == 0 else 1,
                      value='17' if marker == 0 else '-77', collected=0)
    elif all(t in (0, 1) for t in case['types']):
        index = entry == 2 and direct_target == 'index'
        result.update(backend='index' if index else 'height', x=case['coordinates'][0], z=case['coordinates'][1],
                      value=float(case['index' if index else 'height']).hex())
    return result


class BasemapBindingContracts(unittest.TestCase):
    def test_native_alias_reverse_names_coordinate_calls_and_results(self):
        data = fixture_data()
        actual = iter(io.StringIO(native_output(program(data), data)))
        for row in data['sources']:
            self.assertEqual(json.loads(next(actual)), dict(revision=row['revision'],
                registered=[1, int(row['index_available'])], reverse=['checkbasemap',
                    'checkbasemapindex' if row['index_available'] else '<unknown function>'],
                index_name_uses_height=row['index_available'], control_names=True, resets=1))
            for entry in (0, 1, 2):
                if entry and not row['index_available']: continue
                for index, case in enumerate(data['cases']):
                    for marker in (0, 1):
                        got = json.loads(next(actual))
                        want = dict(revision=row['revision'], entry=entry, case=index, marker=marker,
                                    **expected(case, entry, marker, row['direct_target']))
                        if want['marker_type'] == 2:
                            got['value'] = float.fromhex(got['value']).hex()
                            want['value'] = float.fromhex(want['value']).hex()
                        self.assertEqual(got, want, 'revision=%d entry=%d case=%s' %
                                         (row['revision'], entry, case['name']))
        self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
