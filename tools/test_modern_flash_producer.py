"""Check the script attack's flash class and historical rejection result.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import rename_identifiers
from test_modern_flash import program as api_program


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-flash-producer-contracts.json'


def program(data, api_data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    script = (engine / 'openborscript.c').read_text()
    declarations = re.findall(r'(?m)^static s_attack attack\b[^;]*;', script)
    if len(declarations) != 1:
        raise ValueError('Expected the complete script attack initializer')
    code = rename_identifiers(api_program(api_data), {'main': 'fixture_unused_api_main'})
    code += '\n' + rename_identifiers(declarations[0], {'attack': 'fixture_script_attack'})
    profiles = ','.join('{' + str(row['revision']) + 'u,' +
                        str(int(row['available'])) + ',' + str(int(row['source_tagged'])) + '}'
                        for row in data['sources'])
    code += r'''
int main(void)
{
    static const struct { unsigned revision; int available, source_tagged; } profiles[] = {@PROFILES@};
    unsigned p, c;
    puts("{\"status\":\"PASS\",\"profiles\":[");
    for(p=0;p<sizeof(profiles)/sizeof(*profiles);++p)
    {
        obor_profile_build=profiles[p].revision;
        printf("%s{\"revision\":%u,\"tagged\":%d,\"calls\":[",p?",":"",profiles[p].revision,
               profiles[p].source_tagged ? fixture_script_attack.flash.object_type==OBJECT_TYPE_FLASH : -1);
        if(profiles[p].available)
            for(c=0;c<2;++c)
            {
                s_flash_properties earlier=fixture_script_attack.flash;
                ScriptVariant handle={0},property={0},value={0},result={0},*out;
                ScriptVariant *args[]={&handle,&property,&value};
                HRESULT status;
                earlier.object_type=OBJECT_TYPE_NONE;
                handle.vt=VT_PTR; handle.ptrVal=c?&earlier:&fixture_script_attack.flash;
                property.vt=VT_INTEGER;property.lVal=0;
                value.vt=VT_INTEGER;value.lVal=9;
                result.vt=VT_INTEGER;result.lVal=77;out=&result;log_text[0]='\0';
                status=openbor_get_flash_property(args,&out,2);
                printf("%s{\"get\":",c?",":"");print_variant(status,out,&result);
                printf(",\"get_log\":");quote(log_text);
                result.vt=VT_INTEGER;result.lVal=77;out=&result;log_text[0]='\0';
                status=openbor_set_flash_property(args,&out,3);
                printf(",\"set\":");print_variant(status,out,&result);
                printf(",\"set_log\":");quote(log_text);putchar('}');
            }
        printf("]}");
    }
    puts("]}");return 0;
}
'''.replace('@PROFILES@', profiles)
    return code


class ModernFlashProducerContracts(unittest.TestCase):
    def test_script_default_and_earlier_class_rejection(self):
        data = load_contract_fixture(FIXTURE)
        api = load_contract_fixture(FIXTURE.with_name(data['api_fixture']))
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data, api), data)), expected)


if __name__ == '__main__':
    unittest.main()
