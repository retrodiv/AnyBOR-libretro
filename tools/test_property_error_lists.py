"""Keep unknown-property diagnostics within each native mapping table.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import unittest
from test_historical_behavior import native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class PropertyErrorListTests(unittest.TestCase):
    def test_unknown_names_without_a_null_terminator_in_every_affected_engine(self):
        headers = sorted((ROOT / 'src/engines').glob('*/source/openborscript/scriptcommon.h'))
        self.assertTrue(headers)
        for header in headers:
            engine = header.parents[2].name
            if 'OBOR_PROPERTY_HEADER_DIR' in os.environ:
                header = Path(os.environ['OBOR_PROPERTY_HEADER_DIR']) / engine / 'scriptcommon.h'
            text = header.read_text()
            if '#define MAPSTRINGS(' not in text:
                continue
            with self.subTest(engine=engine):
                start = text.index('#define MAPSTRINGS(')
                end = text.index('\n}', start) + len('\n}')
                macro = text[start:end]
                native(r'''
#include <assert.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
enum { VT_STR,VT_INTEGER };
typedef struct {int vt,lVal;const char *strVal;} ScriptVariant;
static int printed;
static int print_record(const char *format,...) { ++printed;(void)format;return 0; }
#define printf print_record
#define StrCache_Get(x) (x)
static void ScriptVariant_ChangeType(ScriptVariant *v,int kind) {v->vt=kind;}
static int searchList(const char *list[],const char *value,int length) {
 for(int i=0;i<length;++i)if(!strcmp(list[i],value))return i;
 return -1;
}
MACRO
static int map(ScriptVariant *v,int count) {
 const char *table[3]={"alpha","beta","gamma"}; /* No terminal sentinel. */
 char *propname=NULL;int prop;
 MAPSTRINGS(v,table,count,"Unknown: %s");
 return 1;
}
int main(void) {
 for(int count=0;count<=3;++count) {
  const char *names[]={"alpha","beta","gamma","unknown","","ALPHA"};
  for(unsigned n=0;n<sizeof(names)/sizeof(*names);++n) {
   ScriptVariant v={VT_STR,0,names[n]};printed=0;
   int found=(int)n<count;
   assert(map(&v,count)==found);
   if(found) {
    assert(v.vt==VT_INTEGER && v.lVal==(int)n && !printed);
    assert(map(&v,count) && v.lVal==(int)n && !printed);
   } else {
    assert(v.vt==VT_STR && !strcmp(v.strVal,names[n]));
    assert(printed==count+3);
   }
  }
 }
}
'''.replace('MACRO', macro))


if __name__ == '__main__':
    unittest.main()
