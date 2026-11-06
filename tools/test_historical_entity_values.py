"""Check selected actual entity getter/setter bodies with native engine records.

Caller/mapper contracts are covered separately. Geometry, AI and full scripts
are not executed here. Only valid animation/frame and type-table selectors run.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from native_sanitizers import sanitizer_environment
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-value-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    # A bound native helper is part of this probe's actual source dependencies.
    function(script, 'obor_entity_type_reserved')
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    declarations = {}
    for key, pattern in (
        ('GET_DECLARATIONS', r'(?ms)^enum entityproperty_enum\s*\{.*?(?=^void mapstrings_getentityproperty\()'),
        ('SET_DECLARATIONS', r'(?ms)^enum cep_energycost_enum\s*\{.*?(?=^void mapstrings_changeentityproperty\()'),
        ('CONSTANT_MACRO', r'(?ms)^#define ICMPCONST\(.*?(?=^void mapstrings_transconst\()')):
        match = re.search(pattern, script)
        if match is None:
            raise ValueError('Missing native property dependency: ' + key)
        declarations[key] = match[0]
    for operation, name in (('GET_CASES', 'openbor_getentityproperty'),
                            ('SET_CASES', 'openbor_changeentityproperty')):
        method, cases = switch_cases(script, name, 'propind')
        selected = []
        for prop in data['properties']:
            label = '_ep_' + prop
            if label in cases:
                row = cases[label]
                selected.append(method[row['label_start']:row['end']])
        declarations[operation] = '\n'.join(selected)
    entry = function(script, 'openbor_transconst')
    arrays = set(re.findall(r'\b(anim\w+)\s*\[', entry))
    declarations.update(CONVERTERS='\n'.join(function(variants, name) for name in (
        'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
        'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        # Other constant checks cannot match the selected marker name and have
        # separate contracts; keep the native argument check and marker branch.
        CONSTANT_MAPPER=re.sub(r'(?m)^\s*ICMPCONST\([A-Za-z_]\w*\);?\s*$', '',
                               function(script, 'mapstrings_transconst')),
        CONSTANT_ENTRY=entry,
        ANIMATION_ARRAYS='\n'.join('int *' + name + ';' for name in sorted(arrays)))
    cases = []
    for row in data['cases']:
        cases.append('{%d,%d,%d,%d,{%s},{%s},{%s}}' % (
            row['operation'], data['properties'].index(row['property']), row['count'], row['bound_null'],
            ','.join(str(v) for v in row['kinds']),
            ','.join(str(v) + 'LL' for v in row['integers']),
            ','.join(float(v).hex() for v in row['decimals'])))
    declarations['CASES'] = ',\n'.join(cases)
    declarations['PROFILES'] = ',\n'.join('{%du,{{%s},{%s}},%uu,%d,{%s}}' % (
        row['revision'], ','.join(str(v) for v in row['selectors'][0]),
        ','.join(str(v) for v in row['selectors'][1]), row['marker'], row['representation'],
        ','.join(str(int(v)) for v in row['enabled'])) for row in data['sources'])
    declarations['OWN_REPRESENTATIONS'] = 'static void own_representation(unsigned kind,LONG value,int *out) {switch(kind){' + ''.join(
        'case %d:{struct {%s} original={0};original.candamage=value;original.hostile=value;original.projectilehit=value;out[0]=original.candamage;out[1]=original.hostile;out[2]=original.projectilehit;break;}' % (
            i, ''.join(fields)) for i, fields in enumerate(data['representations'])) + 'default:abort();}}'
    for fields in data['representations']:
        if len(fields) != 3 or any(not re.fullmatch(r'(?:short|int)\s+(?:hostile|candamage|projectilehit)\s*(?::\s*16)?\s*;', field) for field in fields):
            raise ValueError('Bound signed16 original declaration variants required')
    text = Path(__file__).with_name('entity_value_contract.c.in').read_text()
    for key, value in declarations.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native property probe substitution')
    return text


class EntityValueContracts(unittest.TestCase):
    def test_actual_property_values_and_writes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertLessEqual(len(data['properties']), 10)
        for row in data['sources']:
            self.assertEqual(len(row['selectors']), 2)
            for indices in row['selectors']:
                self.assertEqual(len(indices), len(data['properties']))
            self.assertIn(row['contract'], data['contracts'])
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        engine = ROOT / 'src/engines' / data['engine']
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in
            sorted((engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-entity-values-') as temporary:
            source = Path(temporary) / 'probe.c'
            executable = Path(temporary) / 'probe'
            source.write_text(program(data))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-O2', '-fsigned-char',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function',
                '-Wno-unused-const-variable', '-Wno-error=deprecated-declarations',
                '-DOBOR_ENGINE_BUILD=' + data['engine'], '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in includes), str(source), '-o', str(executable)],
                check=True, timeout=60)
            raw = subprocess.check_output([str(executable)], text=True, timeout=30,
                                          env=sanitizer_environment())
        actual = [json.loads(line) for line in raw.splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
