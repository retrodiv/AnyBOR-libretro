"""Preserve Script initialization bytes while checking required storage.

Native Script constructors and variable-list initialization run with real
records and bounded allocation observers. Named interpreter/comment services
must remain uncalled in this allocation-phase control. Teardown is separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest
from contract_fixtures import load_contract_fixture
from native_allocation_policy import named_allocation_support
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native
import test_script_array_storage as arrays

HERE = Path(__file__).resolve().parent
ROOT = arrays.ROOT
FIXTURE = HERE / 'fixtures/script-constructor-native-baseline.json'


def program(engine, profiles, *, wrong_magic=False):
    oracle = load_contract_fixture(FIXTURE)['engines'][engine.name]
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    modern = 'Varlist_Init' in oracle['alloc_script']
    base = arrays.program(engine, profiles)
    support = named_allocation_support(engine)
    if support:
        if not base.endswith(support):
            raise ValueError('One trailing native allocation-policy provider required')
        base = base[:-len(support)]
    if base.count('int main(void)')!=1:
        raise ValueError('One unused array entry point required')
    base = base.replace('int main(void)', 'int array_control_not_run(void)', 1)
    providers = {name:'fixture_constructor_stop' for name in ('shutdown','borShutdown')
                 if re.search(r'\b'+name+r'\b',oracle['Script_Init'])}
    if len(providers)!=1:
        raise ValueError('One own native constructor stop alias required')
    after = function(source, 'alloc_script')
    if wrong_magic:
        if after.count('pscript->magic = script_magic;')!=1:
            raise ValueError('One native Script magic initialization required')
        after = after.replace('pscript->magic = script_magic;', 'pscript->magic = 0;', 1)
    def init_call(name, target, first):
        return '%s(%s,mode==3?"":NULL,%s%s);' % (
            name, target, '' if engine.name=='3400' else 'NULL,', first)
    values = dict(ALLOCATION_POLICY=support, MODERN=str(int(modern)),
        BEFORE_ALLOC=rename_identifiers(oracle['alloc_script'], {'alloc_script':'before_alloc_script','Varlist_Init':'before_init'}),
        AFTER_ALLOC=after,
        BEFORE_SCRIPT_INIT=rename_identifiers(oracle['Script_Init'], dict(providers,Script_Init='before_script_init',Varlist_Init='before_init')),
        AFTER_SCRIPT_INIT=rename_identifiers(function(source,'Script_Init'),providers),
        CALL_BEFORE_INIT=init_call('before_script_init','value','1'),
        CALL_AFTER_INIT=init_call('Script_Init','value','1'),
        CALL_BEFORE_REUSE=init_call('before_script_init','value','0'),
        CALL_AFTER_REUSE=init_call('Script_Init','value','0'),
        CALL_FAILURE_INIT=init_call('Script_Init','&value','1'),
        CALL_MISSING_INIT=init_call('Script_Init','NULL','first').replace('mode==3?"":NULL','NULL'),
        PROFILES=','.join(str(p.get('revision',int(p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'script_constructor_storage.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved Script constructor input')
    return base+'\n'+text


class ScriptConstructorStorageTests(unittest.TestCase):
    def test_native_constructor_bytes_and_refused_storage_by_profile(self):
        pin = json.loads((ROOT/'src/pin.json').read_text())
        self.assertEqual(set(load_contract_fixture(FIXTURE)['engines']),{e['build'] for e in pin['engines']})
        for row in pin['engines']:
            engine = ROOT/'src/engines'/row['build']
            profiles = [p for p in pin['profiles'] if p['engine']==engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine,program(engine,profiles))
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'],'PASS')
                self.assertEqual(value['profiles'],len(profiles))
                self.assertGreaterEqual(value['cases'],23*len(profiles))

    def test_valid_record_identity_changes_are_detected(self):
        pin = json.loads((ROOT/'src/pin.json').read_text())
        key = next(k for k,v in load_contract_fixture(FIXTURE)['engines'].items() if 'Varlist_Init' in v['alloc_script'])
        engine = ROOT/'src/engines'/key
        profile = next(p for p in pin['profiles'] if p['engine']==key)
        result = run_native(engine,program(engine,[profile],wrong_magic=True))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('!memcmp(&before,&after,sizeof(before))',result.stderr)
        self.assertNotIn('runtime error:',result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer',result.stderr)


if __name__=='__main__':
    unittest.main()
