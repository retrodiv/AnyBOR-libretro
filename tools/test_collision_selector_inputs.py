"""Check native collision masks and bounded type-table selectors.

Native cases, records, conversions and collision mapping are used. Outer
property numbering and string storage are bounded providers; complete script
dispatch and gameplay are separate controls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_early_entity_namespaces import selected_dispatch
from test_early_system_callbacks import block
from test_historical_player import function, switch_cases
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, reject_last=False):
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    prefix = '_cep_' if engine.name == '3400' else '_ep_'
    names = ('candamage', 'hostile', 'projectilehit')
    labels = [prefix + name for name in names]
    setter = selected_dispatch(source, 'openbor_changeentityproperty', labels)
    guard = re.compile(r'/\* AnyBOR: validate collision selector extent\. \*/.*?'
                       r'/\* AnyBOR: native collision value follows\. \*/', re.S)
    if len(guard.findall(setter)) != 3:
        raise ValueError('Three native collision selector bounds required')
    baseline = guard.sub('', setter).replace(
        'if(varlist[i] && varlist[i]->vt == VT_INTEGER)',
        'if(varlist[i]->vt == VT_INTEGER)').replace(
        'openbor_changeentityproperty(', 'baseline_changeentityproperty(', 1)
    if reject_last:
        def smaller(match):
            text, count = re.subn(r'(>=\s*sizeof\(entitytypes\)\s*/\s*sizeof\(\*entitytypes\))',
                                 r'\1-1', match[0])
            if count != 1:
                raise ValueError('One table extent per native guard required')
            return text
        setter = guard.sub(smaller, setter)
    enums = [m[0] for m in re.finditer(r'enum\s+\w+\s*\{[^{}]*\}\s*;', source)
             if re.search(r'_(?:cep|ep)_hcd_ground\b', m[0])]
    if len(enums) != 1:
        raise ValueError('One native collision subproperty enum required')
    macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
    if macro is None and not re.search(r'^#define\s+MAPSTRINGS\(',
            (engine / 'source/openborscript/scriptcommon.h').read_text(encoding='latin1'), re.M):
        raise ValueError('Native string mapping macro required')
    mapping = []
    for name in ('mapstrings_changeentityproperty', 'mapstrings_entityproperty'):
        result_type = re.search(r'\b(void|int)\s+'+name+r'\(', source)
        if result_type is None:
            continue
        method = function(source, name)
        table = re.search(r'static\s+const\s+char\s*\*\s*proplist_hostile_candamage\[\]\s*=\s*\{[^{}]*\}\s*;', method)
        if table is None:
            raise ValueError('Native collision string table required')
        start = re.search(r'// entity type\(s\).*?\n\s*if\(', method, re.S)
        if start:
            selected = block(method, method.index('if(', start.start()))
        else:
            start = re.search(r'\bcase\s+_ep_hostile\s*:', method)
            if start is None:
                raise ValueError('Native collision mapping branch required')
            selected = 'switch(varlist[1]->lVal) {'+block(method, start.start())+'default:break;}'
        if selected.count('if(!varlist[i]) continue;') != 1:
            raise ValueError('One bounded native collision mapping loop required')
        mapping.append(result_type[1]+' '+name+'(ScriptVariant **varlist,int paramCount) {\n'
                       'char *propname;int prop,i,t,native_property=varlist[1]->lVal,obor_property=varlist[1]->lVal;'
                       'const char *eps=varlist[1]->lVal==10000?"candamage":'
                       'varlist[1]->lVal==10001?"hostile":"projectilehit";\n'+table[0]+'\n'+selected+'\n'+
                       ('return 1;' if result_type[1] == 'int' else '')+'\n}')
    fields = []
    _, cases = switch_cases(source, 'openbor_changeentityproperty', 'propind')
    for label in labels:
        clear = re.search(r'\bent->([\w.]+)\s*=\s*(?:0|TYPE_UNDEL?CA?RED|TYPE_UNDECLARED)\s*;', cases[label]['body'])
        if clear is None:
            raise ValueError('One native collision mask destination required')
        fields.append(clear[1])
    pieces = dict(
        CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        ENUM=enums[0], ROOT_IDS='\n'.join('#define '+label+' '+str(10000+i) for i, label in enumerate(labels)),
        END=prefix+'the_end', MACRO=macro[0] if macro else '', MAPPING='\n'.join(mapping),
        SEARCH=function((engine / 'source/utils.c').read_text(encoding='latin1'), 'searchList'),
        CONVERSIONS='\n'.join(function(variants, name) for name in
                             ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')),
        RESERVED=function(source, 'obor_entity_type_reserved') if 'obor_entity_type_reserved()' in setter else '',
        SETTER=setter, BASELINE=baseline,
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in
            (engine / 'source/scriptlib/ScriptVariant.h').read_text() else 'void',
        READ_FIELDS=','.join('ent.'+field for field in fields),
        INIT_FIELDS='\n'.join('ent.'+field+'=123;' for field in fields),
        TAGGED=str(int('ltemp & 0x7fffffff' in setter)),
        MASK_FAST='obor_profile_build>=3596' if engine.name == '3741' else
                  '1' if engine.name == '3842' else '0',
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'collision_selector_inputs.c.in').read_text()
    for key, value in pieces.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native collision dependency')
    return text


class CollisionSelectorInputTests(unittest.TestCase):
    def _check_profiles(self, family):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        selected = 0
        for row in pin['engines']:
            if row['build'] not in family:
                continue
            selected += 1
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 500*len(profiles))
        self.assertEqual(selected, len(family))

    def test_native_masks_mapping_results_and_bounded_errors_by_profile(self):
        self._check_profiles({'3400', '3842', '4086', '4432'})

    def test_legacy_marker_masks_and_error_boundaries_by_profile(self):
        self._check_profiles({'3741'})

    def test_shared_header_collision_mappers_by_profile(self):
        self._check_profiles({'6391', '7142', '7533', '8023'})

    def test_rejecting_a_valid_last_type_fails_a_logical_control(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3400'
        profile = next(p for p in pin['profiles'] if p['build'] == '3400')
        result = run_native(engine, program(engine, [profile], reject_last=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('a.status==b.status', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
