"""Keep variable-table values while bounding allocation and relocation.

Valid native references use bounded allocation providers. Modern controls also
use native variant/cache reference operations and native List/Clear methods.
Callback teardown and arbitrary foreign handles are separate scopes.
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
FIXTURE = HERE/'fixtures/script-variable-native-baseline.json'


def program(engine, profiles, *, negative=None):
    data = load_contract_fixture(FIXTURE)['engines'][engine.name]
    code = (engine/'openborscript.c').read_text(encoding='latin1')
    profile_values = ','.join(str(p.get('revision',int(p['build'].split('-')[0])))+'u' for p in profiles)
    if 'Script_Global_Init' in data:
        base = arrays.program(engine,profiles)
        support = named_allocation_support(engine)
        if support:
            if not base.endswith(support):
                raise ValueError('One trailing named allocation provider required')
            base = base[:-len(support)]
        if base.count('int main(void)')!=1:
            raise ValueError('One unused array entry point required')
        base = base.replace('int main(void)','int unused_array_entry(void)',1)
        after = function(code,'Script_Global_Init')
        if negative:
            if negative!='extra_global_slot' or after.count('(size_t)max_indexed_vars + 1')!=1:
                raise ValueError('One native global size expression required')
            after = after.replace('(size_t)max_indexed_vars + 1','(size_t)max_indexed_vars + 2',1)
        types = (engine/'source/gamelib/types.h').read_text(encoding='latin1')
        readonly = bool(re.search(r'extern\s+const\s+s_drawmethod\s+plainmethod\s*;',types))
        values = dict(PLAIN_DECL='const s_drawmethod plainmethod={.flag=1};' if readonly else 's_drawmethod plainmethod;',
            PLAIN_RESET='' if readonly else ('memset(&plainmethod,0,sizeof(plainmethod));plainmethod.flag=-1;' if engine.name=='3741' else 'memset(&plainmethod,0,sizeof(plainmethod));plainmethod.flag=1;'),
            FLAG_EXPECTED='1' if engine.name=='3400' else 'plainmethod.flag',ALLOCATION_POLICY=support,
            BEFORE_GLOBAL=rename_identifiers(data['Script_Global_Init'],{'Script_Global_Init':'before_global'}),
            AFTER_GLOBAL=after,PROFILES=profile_values)
        text = (HERE/'script_global_storage.c.in').read_text()
    else:
        base = ''
        variant_path, = (engine/'source').rglob('ScriptVariant.c')
        variant = variant_path.read_text(encoding='latin1')
        header = variant_path.with_suffix('.h').read_text(encoding='latin1')
        match = re.search(r'typedef struct\s*\{[^}]*\}\s*Varstr;',variant)
        if not match:
            raise ValueError('One native cache record definition required')
        functions = '\n'.join(function(code,n) for n in (
            'clear_named_var_list','Varlist_Init','Varlist_Cleanup','Varlist_Clear','Varlist_GetByIndex','Varlist_GetByName'))
        for name in ('Varlist_Cleanup','Varlist_Clear'):
            if function(code,name)!=data[name]:
                raise ValueError('Native variable cleanup changed unexpectedly')
        if negative:
            if negative!='skip_cleanup_last':
                raise ValueError('Unknown bounded variable control')
            original = function(code,'Varlist_Cleanup')
            if original.count('i <= varlist->vars->lVal')!=1:
                raise ValueError('One native cleanup bound required')
            functions = functions.replace(original,original.replace('i <= varlist->vars->lVal','i < varlist->vars->lVal',1),1)
        cache = '\n'.join(rename_identifiers(function(variant,n),{n:alias}) for n,alias in (
            ('StrCache_Grab','native_cache_grab'),('StrCache_Collect','native_cache_collect')))
        values = dict(CONFIG='#include "config.h"' if (engine/'config.h').is_file() else '',
            SCRIPT_HEADER='openborscript.h' if (engine/'openborscript.h').is_file() else 'scriptcommon.h',
            CACHE_TYPE=match[0],NATIVE_CACHE=cache,
            POP_ARGS='int length' if 'StrCache_Pop(int length)' in header else 'void',
            POP_UNUSED='(void)length;' if 'StrCache_Pop(int length)' in header else '',
            VARIANT_METHODS='\n'.join(function(variant,n) for n in ('ScriptVariant_Init','ScriptVariant_ChangeType','ScriptVariant_Clear','ScriptVariant_Copy')),
            VARLIST_METHODS=functions,
            BEFORE_INDEX=rename_identifiers(data['Varlist_SetByIndex'],{'Varlist_SetByIndex':'before_index'}),
            AFTER_INDEX=function(code,'Varlist_SetByIndex'),
            BEFORE_NAME=rename_identifiers(data['Varlist_SetByName'],{'Varlist_SetByName':'before_name'}),
            AFTER_NAME=function(code,'Varlist_SetByName'),PROFILES=profile_values)
        text = (HERE/'script_variable_growth.c.in').read_text()
    for key,value in values.items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved variable-table input')
    return base+'\n'+text


class ScriptVariableStorageTests(unittest.TestCase):
    def test_native_tables_values_relocation_and_refusals_by_profile(self):
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
                self.assertGreaterEqual(value['cases'],20*len(profiles))

    def control(self,key,diagnostic,kind):
        pin = json.loads((ROOT/'src/pin.json').read_text())
        engine = ROOT/'src/engines'/key
        profile = next(p for p in pin['profiles'] if p['engine']==key)
        result = run_native(engine,program(engine,[profile],negative=kind))
        self.assertNotEqual(result.returncode,0)
        self.assertIn(diagnostic,result.stderr)
        self.assertNotIn('runtime error:',result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer',result.stderr)

    def test_native_global_extent_changes_are_detected(self):
        data = load_contract_fixture(FIXTURE)['engines']
        key = next(k for k,v in data.items() if 'Script_Global_Init' in v)
        self.control(key,'!memcmp(&before,&after,sizeof(before))','extra_global_slot')

    def test_last_initialized_slot_is_cleaned(self):
        data = load_contract_fixture(FIXTURE)['engines']
        key = next(k for k,v in data.items() if 'Varlist_SetByIndex' in v)
        self.control(key,'table.vars[i].vt==VT_EMPTY && !table.vars[i].ptrVal','skip_cleanup_last')


if __name__=='__main__':
    unittest.main()
