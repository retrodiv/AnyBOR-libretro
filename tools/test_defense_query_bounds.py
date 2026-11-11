"""Check native defense queries with source-owned argument/storage epochs.

The selected getter, defense mapper blocks, search and conversions use native
records. Outer numeric entity dispatch, cache and table storage are bounded
providers. Full entity/model construction is a separate control.
The configured-count storage follows the getter; its visible declarations
come from the source instead of being supplied by the storage provider.
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
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, remove_bound=False):
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    enums = [m[0] for m in re.finditer(r'enum\s+\w+\s*\{[^{}]+\}\s*;', source)
             if re.search(r'\b_(?:gep|ep)_defense_factor\b', m[0])]
    if len(enums) != 1:
        raise ValueError('One native defense subproperty enum required')
    outer = '_gep_defense' if engine.name == '3400' else '_ep_defense'
    prefix = '_gep_defense_' if engine.name in ('3400', '3741') else '_ep_defense_'
    getter = selected_dispatch(source, 'openbor_getentityproperty', [outer])
    getter_prefix = source[:source.index(function(source, 'openbor_getentityproperty'))]
    count_declarations = '\n'.join(re.findall(
        r'(?m)^extern[ \t]+int[ \t]+max_attack_types[ \t]*;', getter_prefix))
    if remove_bound:
        guard = 'if(ltemp < 0 || (obor_profile_build < 3715 ? ltemp > max_attack_types : ltemp >= max_attack_types) || !factors) break;'
        if getter.count(guard) != 1:
            raise ValueError('Native runtime defense bound required')
        getter = getter.replace(guard, 'if(!factors) break;', 1)
    mapping = []
    for name in ('mapstrings_getentityproperty', 'mapstrings_entityproperty'):
        match = re.search(r'\b(void|int)\s+'+name+r'\(', source)
        if match is None:
            continue
        method = function(source, name)
        table = re.search(r'static\s+const\s+char\s*\*\s*proplist_defense\[\]\s*=\s*\{[^{}]*\}\s*;', method)
        if table is None:
            raise ValueError('Native defense name table required')
        start = re.search(r'if\(\(varlist\[1\]->vt == VT_INTEGER\) && \([^\n]*== _(?:gep|ep)_defense\)\)', method)
        if start:
            selected = block(method, start.start())
        else:
            start = re.search(r'\bcase\s+_ep_defense\s*:', method)
            if start is None:
                raise ValueError('Native defense mapping branch required')
            selected = 'switch('+outer+') {'+block(method, start.start())+'default:break;}'
        mapping.append(match[1]+' '+name+'(ScriptVariant **varlist,int paramCount) {\n'
                       'char *propname;int prop,native_property='+outer+',obor_property='+outer+';'
                       'const char *eps="defense";\n'+table[0]+'\n'+selected+'\n'+
                       ('return 1;' if match[1] == 'int' else '')+'\n}')
    macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
    values = dict(
        CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        PROFILE_HEADER='#include "source/openborscript/profile_ids.h"' if engine.name in ('6391', '7142') else '',
        ENUM=enums[0], OUTER=outer, END='_gep_the_end' if engine.name == '3400' else '_ep_the_end',
        GETTER=getter, MAPPING='\n'.join(mapping),
        ATTACK_COUNT_DECLARATIONS=count_declarations,
        MAPPING_MACRO=macro[0] if macro else '',
        SEARCH=function((engine / 'source/utils.c').read_text(encoding='latin1'), 'searchList'),
        CONVERSIONS='\n'.join(function(variant, n) for n in
            ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue')),
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in
            (engine / 'source/scriptlib/ScriptVariant.h').read_text() else 'void',
        FLAT='1' if engine.name == '3400' else '0',
        MODEL='1' if engine.name == '3400' else 'obor_profile_build<3715' if engine.name == '3741' else '0',
        EXTRA='1' if engine.name in ('3400', '7533', '8023') else 'obor_profile_build<3715' if engine.name == '3741' else '0',
        OLD='obor_profile_build<3441' if engine.name == '3400' else '0',
        CLASSIC='1' if engine.name == '3400' else '0',
        TRANSLATED='1' if engine.name in ('6391', '7142') else '0',
        INDEX_ERROR='1' if engine.name == '7142' else '0',
        LITERAL_MAPPER='mapstrings_getentityproperty(args,nargs);' if engine.name in ('3400', '3741') else
            'if(obor_profile_build<3828)mapstrings_getentityproperty(args,nargs);else mapstrings_entityproperty(args,nargs);' if engine.name == '3842' else
            'mapstrings_entityproperty(args,nargs);',
        ORDINALS=','.join(prefix+suffix for suffix in
            ('blockpower', 'blockratio', 'blockthreshold', 'blocktype', 'factor', 'knockdown', 'pain')),
        SET_BLOCK='obor_defense_set_blocktype(&model_values[i],2,obor_profile_build);'
                  'obor_defense_set_blocktype(&entity_values[i],1,obor_profile_build);' if engine.name == '4086' else
                  'model_values[i].blocktype=2;entity_values[i].blocktype=1;',
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'defense_query_bounds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native defense contract dependency')
    return text


class DefenseQueryBoundsTests(unittest.TestCase):
    def test_native_argument_mapping_storage_and_error_policy_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 100*len(profiles))

    def test_missing_dynamic_extent_is_detected_in_spare_backing(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3741'
        profile = next(p for p in pin['profiles'] if p['build'] == '3741')
        text = '#define ENDPOINT_ONLY 1\n'+program(engine, [profile], remove_bound=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('result.vt==VT_EMPTY', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
