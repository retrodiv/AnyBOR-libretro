"""Keep Script byte layouts while supporting its native inline owners.

Frozen declarations supply portable layout controls. Native initialization
queries and shared-reference release run on real record storage; interpreter
execution, arbitrary handles and complete VM lifetime need separate controls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/script-record-native-baseline.json'


def record_layout_print(records):
    """Render layout observations, without making host sizes public expectations."""
    result = ['printf("{");']
    for i, row in enumerate(records):
        name, label = row['name'], row['label']
        assert re.fullmatch(r'[A-Za-z_]\w*', name)
        prefix = (',' if i else '') + json.dumps(label) + ':{"size":%zu,"align":%zu,"members":{'
        result.append('printf(%s,sizeof(%s),_Alignof(%s));' % (json.dumps(prefix), name, name))
        for j, field in enumerate(row['members']):
            assert re.fullmatch(r'[A-Za-z_]\w*', field)
            prefix = (',' if j else '') + json.dumps(field) + ':{"offset":%zu,"size":%zu}'
            result.append('printf(%s,offsetof(%s,%s),sizeof(((%s*)0)->%s));' %
                          (json.dumps(prefix), name, field, name, field))
        result.append('printf("}}");')
    result.append('printf("}");')
    return '\n'.join(result)


def program(engine, profiles, *, wrong_query=False):
    data = load_contract_fixture(FIXTURE)['engines'][engine.name]
    core = (engine / 'openborscript.c').read_text(encoding='latin1')
    getter = function(core, 'Script_IsInitialized')
    if wrong_query:
        line = 'return pscript->initialized;'
        if getter.count(line) != 1:
            raise ValueError('One unchanged integer initialization result required')
        getter = getter.replace(line, 'return 0;', 1)
    replacements = {'Script': 'fixture_before_Script', 'pcurrentscript': 'fixture_before_current',
                    'Script_IsInitialized': 'fixture_before_is_initialized'}
    replacements.update({p['name']: 'fixture_before_' + p['name'] for p in data['parents']})
    declarations = ['#pragma pack(push)\n#pragma pack()\n' +
                    rename_identifiers(data['script_declaration'], replacements) + '\n#pragma pack(pop)']
    checks = ['_Static_assert(sizeof(void*)==8 && sizeof(int)==4,"Supported 64-bit scalar ABI");',
              '_Static_assert(sizeof(Script)==sizeof(fixture_before_Script),"Script size");',
              '_Static_assert(_Alignof(Script)==%d,"Script owner alignment");' % data['target_alignment']]
    old_records = [dict(name='fixture_before_Script', label='Script', members=data['script_members'])]
    new_records = [dict(name='Script', label='Script', members=data['script_members'])]
    for field in data['script_members']:
        checks += ['_Static_assert(offsetof(Script,%s)==offsetof(fixture_before_Script,%s),"Script field offset");' % (field, field),
                   '_Static_assert(sizeof(((Script*)0)->%s)==sizeof(((fixture_before_Script*)0)->%s),"Script field size");' % (field, field)]
    owners, offsets = [], []
    for i, parent in enumerate(data['parents']):
        name, before = parent['name'], replacements[parent['name']]
        packing = '#pragma pack()' if parent['packing'] == 8 else '#pragma pack(%d)' % parent['packing']
        declarations.append('#pragma pack(push)\n' + packing + '\n' +
                            rename_identifiers(parent['declaration'], replacements) + '\n#pragma pack(pop)')
        # Script bytes remain frozen. These inline owners gain exactly one
        # separate text-table ownership pointer ahead of their Script members.
        text_owner = name == 's_level' and engine.name in ('6391','7142','7533','8023')
        delta = 8 if text_owner else 0
        if text_owner:
            checks += [
                '_Static_assert(sizeof(((s_level*)0)->obor_text_tables)==8,"One text ownership pointer");',
                '_Static_assert(offsetof(s_level,textobjs)==offsetof(%s,textobjs),"Visible text table offset");' % before,
                '_Static_assert(offsetof(s_level,obor_text_tables)==offsetof(%s,textobjs)+sizeof(((%s*)0)->textobjs),"Text ownership pointer position");' % (before,before)]
        checks += ['_Static_assert(sizeof(%s)==sizeof(%s)+%d,"Owner size");' % (name, before, delta),
                   '_Static_assert(_Alignof(%s)==_Alignof(%s),"Owner alignment");' % (name, before),
                   '_Static_assert(_Alignof(Script)<=_Alignof(%s),"Packed Script owner");' % name]
        for field in parent['script_members']:
            if text_owner:
                checks += ['_Static_assert(offsetof(%s,%s)>=offsetof(%s,textobjs)+sizeof(((%s*)0)->textobjs),"Inline Script follows text ownership slot");' % (before,field,before,before)]
            checks += ['_Static_assert(offsetof(%s,%s)==offsetof(%s,%s)+%d,"Owner field offset");' % (name, field, before, field, delta),
                       '_Static_assert(offsetof(%s,%s)%%_Alignof(Script)==0,"Inline Script alignment");' % (name, field)]
        offsets.append('static const size_t offsets_%d[]={%s};' %
                       (i, ','.join('offsetof(%s,%s)' % (name, f) for f in parent['script_members'])))
        owners.append('{sizeof(%s),_Alignof(%s),%d,offsets_%d}' % (name, name, len(parent['script_members']), i))
        old_records.append(dict(name=before, label=name, members=parent['script_members']))
        new_records.append(dict(name=name, label=name, members=parent['script_members']))
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        BEFORE_DECLARATIONS='\n'.join(declarations), ABI_CHECKS='\n'.join(checks),
        ORIGINAL_GETTER=rename_identifiers(data['is_initialized'], replacements), GETTER=getter,
        FIELD_OFFSETS='\n'.join(offsets), OWNERS=','.join(owners),
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles),
        MAGIC_INIT='script->magic=script_magic;' if 'magic' in data['script_members'] else '',
        BEFORE_LAYOUT=record_layout_print(old_records), AFTER_LAYOUT=record_layout_print(new_records))
    text = (HERE / 'script_record_alignment.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved Script layout input')
    return text


class ScriptRecordAlignmentTests(unittest.TestCase):
    def test_sizes_offsets_inline_queries_and_reference_slots_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['profiles']), {p['build'] for p in pin['profiles']})
        output = os.environ.get('OBOR_NATIVE_LAYOUT_OUTPUT')
        if output:
            Path(output).mkdir(exist_ok=False)
        for entry in pin['engines']:
            engine = ROOT / 'src/engines' / entry['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreater(value['cases'], 30 * len(profiles))
                self.assertEqual(value['reference_allocations'], value['reference_frees'])
                if output:
                    (Path(output) / (engine.name + '.json')).write_text(json.dumps(value, indent=2)+'\n')

    def test_wrong_initialization_result_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        entry = pin['engines'][0]
        engine = ROOT / 'src/engines' / entry['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, '#define QUERY_ONLY 1\n' + program(engine, [profile], wrong_query=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('observed == expected', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
