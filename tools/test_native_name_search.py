"""Check source-defined native name-search ordering by profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-native-name-search-contracts.json'


class NativeNameSearchTests(unittest.TestCase):
    def test_native_ordering_and_duplicate_preference(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(data, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_NAME_SEARCH_ENGINE',
                                     ROOT / 'src/engines' / data['engine']))
        search = function((engine / 'source/utils.c').read_text(), 'searchList')
        contexts = []
        for row in rows:
            self.assertEqual(row['engine'], data['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertIs(type(row['binary_search']), bool)
            contexts.append('{%du,%d}' % (row['revision'], row['binary_search']))
        tables, cases = [], []
        for index, case in enumerate(data['cases']):
            tables.append('static const char *table_%d[]={%s};' %
                          (index, ','.join(json.dumps(value) for value in case['table'])))
            cases.append('{table_%d,%d,%s,%d,%d}' %
                         (index, len(case['table']), json.dumps(case['query']),
                          case['legacy'], case['binary']))
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <strings.h>
#define stricmp strcasecmp
uint32_t obor_profile_build;
@SEARCH@
@TABLES@
static const struct {unsigned revision;int binary;} contexts[]={@CONTEXTS@};
static const struct {const char **table;int size;const char *query;int legacy,binary;} cases[]={@CASES@};
int main(void) {
 for(size_t i=0;i<sizeof(contexts)/sizeof(*contexts);i++) {
  obor_profile_build=contexts[i].revision;
  for(size_t j=0;j<sizeof(cases)/sizeof(*cases);j++)
   assert(searchList(cases[j].table,cases[j].query,cases[j].size)==
          (contexts[i].binary?cases[j].binary:cases[j].legacy));
  /* Stability controls have no claim about the original unsafe inputs. */
  assert(searchList(NULL,"alpha",1)==-1);
  assert(searchList(table_0,NULL,4)==-1);
  assert(searchList(table_0,"alpha",0)==-1);
  assert(searchList(table_0,"alpha",-1)==-1);
 }
 puts("name_search=1");return 0;
}
'''
        for key, value in dict(SEARCH=search, TABLES='\n'.join(tables),
                               CONTEXTS=','.join(contexts), CASES=','.join(cases)).items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, data).strip(), 'name_search=1')


if __name__ == '__main__':
    unittest.main()
