"""Preserve native deletion values and retain a refused optional shrink.

Native variant/cache/List methods and real records are reused from the variable
storage control. Invalid original shrink refusal is never executed. Native API
registration, callbacks and collection alias ownership remain separate scopes.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest
from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native
import test_script_variable_storage as variables

HERE = Path(__file__).resolve().parent
ROOT = variables.ROOT
FIXTURE = HERE/'fixtures/script-variable-delete-native-baseline.json'


def program(engine,profiles,*,lose_owner=False):
    data = load_contract_fixture(FIXTURE)['engines'][engine.name]
    if data['body'] is None:
        raise ValueError('No source-defined deletion method in this family')
    base = variables.program(engine,profiles)
    if base.count('int main(void)')!=1:
        raise ValueError('One unused variable-storage entry point required')
    base = base.replace('int main(void)','int unused_growth_entry(void)',1)
    after = function((engine/'openborscript.c').read_text(encoding='latin1'),'Varlist_DeleteByIndex')
    if lose_owner:
        if not data['needs_guard'] or after.count('if(resized_vars)')!=1:
            raise ValueError('One corrected optional shrink guard required')
        after = after.replace('if(resized_vars)','if(1)',1)
    values = dict(BEFORE_DELETE=rename_identifiers(data['body'],{'Varlist_DeleteByIndex':'before_delete'}),
        AFTER_DELETE=after,CHECK_ABSENT=str(int(data['needs_guard'])),
        PROFILES=','.join(str(p.get('revision',int(p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE/'script_variable_delete.c.in').read_text()
    for key,value in values.items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved native variable deletion input')
    return base+'\n'+text


class ScriptVariableDeleteStorageTests(unittest.TestCase):
    def test_native_delete_values_cache_order_and_shrink_refusal_by_profile(self):
        pin = json.loads((ROOT/'src/pin.json').read_text())
        data = load_contract_fixture(FIXTURE)['engines']
        for key,row in data.items():
            engine = ROOT/'src/engines'/key
            profiles = [p for p in pin['profiles'] if p['engine']==key]
            with self.subTest(engine=key):
                if row['body'] is None:
                    self.assertNotRegex((engine/'openborscript.c').read_text(encoding='latin1'),r'\bVarlist_DeleteByIndex\s*\(')
                    continue
                result = run_native(engine,program(engine,profiles))
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),dict(status='PASS',profiles=len(profiles),cases=(13 if row['needs_guard'] else 11)*len(profiles)))

    def test_losing_the_owner_is_detected_before_following_it(self):
        pin = json.loads((ROOT/'src/pin.json').read_text())
        key = next(k for k,v in load_contract_fixture(FIXTURE)['engines'].items() if v['needs_guard'])
        engine = ROOT/'src/engines'/key
        profile = next(p for p in pin['profiles'] if p['engine']==key)
        result = run_native(engine,program(engine,[profile],lose_owner=True))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('table.vars==original && table.vars->lVal==2',result.stderr)
        self.assertNotIn('runtime error:',result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer',result.stderr)


if __name__=='__main__':
    unittest.main()
