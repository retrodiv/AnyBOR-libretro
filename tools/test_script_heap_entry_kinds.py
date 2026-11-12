"""Keep native heap disposal contracts while validating entry ownership.

Native List/free methods and real records use bounded script/FIX_GIF observers and
native empty Varlist cleanup. Constructors, nested script callbacks, list-cursor
mutation and actor lifetime retain separate controls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/script-heap-kind-native-baseline.json'


def program(engine, profiles, *, bypass_owner=False):
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    helper = function(source, '_freeheapnode') if data['helper'] else ''
    if bypass_owner:
        predicate = 'owner && strcmp(owner, "openbor_allocscript") == 0 &&'
        if helper.count(predicate) != 1:
            raise ValueError('One native script-owner discriminator required')
        helper = helper.replace(predicate, '', 1)
        helper = helper.replace('owner = List_GetName(&scriptheap);',
                                'owner = List_GetName(&scriptheap);(void)owner;', 1)
        # The semantic negative uses a defined scalar read, so it cannot pass
        # merely because a wrong-layout typed read stops under a sanitizer.
        helper = helper.replace('((Script *)ptr)->magic', 'byte_tag(ptr)', 1)
    shutdown = ''
    if helper:
        body = function(source, 'Script_Global_Clear')
        start = body.index('size = List_GetSize(&scriptheap);')
        end = 'List_Clear(&scriptheap);'
        stop = body.index(end, start) + len(end)
        shutdown = ('static void clear_fixture_heap(void)\n{\n    int i, size;\n    ' +
                    body[start:stop] + '\n}\n')
    before = data['helper'] or ''
    checks = []
    types = set(re.findall(r'\(\((\w+)\s*\*\)ptr\)->magic', before))
    if types:
        # The old dispatcher probes distinct record layouts. Copy their proven
        # common scalar prefix for this reference instead of executing those
        # cross-layout lvalue accesses. Native predicates/order stay intact.
        for name in sorted(types):
            checks += ['_Static_assert(offsetof(%s,magic)==0,"Native tag offset");' % name,
                       '_Static_assert(sizeof(((%s*)0)->magic)==sizeof(int),"Native tag size");' % name]
        before = re.sub(r'\(\(\w+\s*\*\)ptr\)->magic', 'before_tag', before)
        at = before.index('{') + 1
        before = before[:at] + '\n int before_tag;memcpy(&before_tag,ptr,sizeof(before_tag));' + before[at:]
    before = rename_identifiers(before, {'_freeheapnode': 'before_heap_node'})
    before_free = rename_identifiers(data['system_free'], {
        'system_free': 'before_system_free', '_freeheapnode': 'before_heap_node'})
    native_varlist = ''
    if data['kind'] == 'typed':
        variants, = (engine / 'source').rglob('ScriptVariant.c')
        code = variants.read_text(encoding='latin1')
        native_varlist = '\n'.join(function(code, n) for n in (
            'ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType'))
        native_varlist += '\n' + '\n'.join(function(source, n) for n in (
            'clear_named_var_list', 'Varlist_Init'))
        native_varlist += '\n' + rename_identifiers(function(source, 'Varlist_Clear'),
                                                   {'Varlist_Clear': 'native_varlist_clear'})
        header = variants.with_suffix('.h').read_text(encoding='latin1')
        native_varlist = ('int StrCache_Pop(%s){%s abort();}\n' % (
            'int length' if 'StrCache_Pop(int length)' in header else 'void',
            '(void)length;' if 'StrCache_Pop(int length)' in header else '') +
            'void StrCache_Collect(int index){(void)index;abort();}\n' + native_varlist + '''
void Varlist_Clear(Varlist *value)
{assert(kind_of(value)==FIX_ARRAY);event(20+FIX_ARRAY);native_varlist_clear(value);}
''')
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        GIF_HEADER='#include "anigif.h"' if data['kind'] == 'typed' else '',
        PREFIX_CHECKS='\n'.join(checks), HELPER=helper, BEFORE_HELPER=before,
        FREE=function(source, 'system_free'), BEFORE_FREE=before_free,
        NATIVE_VARLIST=native_varlist, SHUTDOWN=shutdown, HAS_SCRIPT=str(int(data['kind'] != 'raw')),
        OWNED_VARLIST=str(int('obor_varlist_release(ptr, 1);' in helper)),
        TYPED=str(int(data['kind'] == 'typed')),
        SCRIPT_ALLOWED='obor_profile_build>=%du' % data['script_before'] if data['script_before'] else '1',
        SCRIPT_TAG='script_magic' if data['kind'] != 'raw' else '0',
        PROFILES=','.join(str(oracle['profiles'][p['build']]['revision'])+'u' for p in profiles))
    text = (HERE / 'script_heap_entry_kinds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved heap entry-kind input')
    return bind_named_allocation_support(text, engine)


class ScriptHeapEntryKindTests(unittest.TestCase):
    def test_native_disposal_return_protocol_and_entry_kinds_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['profiles']), {p['build'] for p in pin['profiles']})
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                native = oracle['engines'][engine.name]
                expected_cases = 9 * len(profiles)
                if native['kind'] != 'raw':
                    expected_cases += 5 * sum(
                        oracle['profiles'][p['build']]['revision'] >= native['script_before']
                        for p in profiles)
                if native['kind'] == 'typed':
                    expected_cases += 4 * len(profiles)
                if 'anybor_varlist_ownership.inc' in (engine/'openborscript.c').read_text(encoding='latin1'):
                    expected_cases += 3 * len(profiles)
                self.assertEqual(value['cases'], expected_cases)

    def test_payload_tag_cannot_replace_owner_metadata(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        key = next(k for k, v in oracle['engines'].items() if v['kind'] == 'script' and not v['script_before'])
        engine = ROOT / 'src/engines' / key
        profile = next(p for p in pin['profiles'] if p['engine'] == key)
        result = run_native(engine, '#define OWNER_CONTROL_ONLY 1\n' + program(engine, [profile], bypass_owner=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('kind_of(value)==FIX_SCRIPT', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
