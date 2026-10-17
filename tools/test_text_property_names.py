"""Check text-property name tables at each actual engine entry point.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',ROOT))
ENGINES=('3400','3842','4086','4432','6391','7142','7533','8023')
class TextPropertyNameTests(unittest.TestCase):
    def test_every_engine_names_numeric_ids_unknowns_and_repeated_lowering(self):
        for engine in ENGINES:
            with self.subTest(engine=engine),tempfile.TemporaryDirectory(prefix='text-property-names-') as name:
                source=SOURCE/f'src/engines/{engine}/openborscript.c'
                if 'OBOR_TOLERANCE_DRAFT'in os.environ:source=Path(os.environ['OBOR_TOLERANCE_DRAFT'])/'text-maps'/engine/'openborscript.c'
                text=source.read_text();methods=['mapstrings_gettextobjproperty','mapstrings_changetextobjproperty']if engine=='3400'else['mapstrings_textobjproperty']
                enums='\n'.join(re.findall(r'enum (?:g|c)top_enum\s*\{.*?\};',text,re.S));assert enums,engine
                body='';checks=[]
                for method in methods:
                    body+=function(text,method)
                    prefix='_ctop_'if 'changetext'in method else '_top_'if engine!='3400'else'_gtop_'
                    # Extract enum member spelling rather than assume modern ordering.
                    enum=next(e for e in re.findall(r'enum.*?\{.*?\};',enums,re.S)if prefix+'font'in e)
                    properties=[n for n in re.findall(r'\b'+prefix+r'([a-z]+)\b',enum)if n not in ('the','end')]
                    for prop in properties:
                        if prop=='the':continue
                        checks.append(f'check({method},"{prop.upper()}",{prefix}{prop});')
                    for unknown in ['unknown','zz','timeextra','fontextra','aextra','']:
                        checks.append(f'check({method},"{unknown}",-1);')
                program=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
enum {VT_INTEGER,VT_STR};
typedef struct {int vt;long lVal;const char *strVal;} ScriptVariant;
#define StrCache_Get(x) (x)
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){v->vt=type;}
'''+enums+'\n'+body+r'''
/* Return types differ by era; use a macro so the exact function signature stays intact. */
#define check(METHOD,NAME,EXPECTED) do { \
 ScriptVariant a={.vt=VT_INTEGER},b={.vt=VT_STR,.strVal=NAME},*v[]={&a,&b}; \
 METHOD(v,2);if(EXPECTED>=0){assert(b.vt==VT_INTEGER&&b.lVal==EXPECTED); \
 METHOD(v,2);assert(b.vt==VT_INTEGER&&b.lVal==EXPECTED);} \
 else assert(b.vt==VT_STR&&!strcmp(b.strVal,NAME)); \
 METHOD(v,1); }while(0)
int main(void){
'''+ '\n'.join(checks)+'\nputs("text_names=1 native_ids=1 unknown_refused=1 cached_ids=1");return 0;}\n'
                work=Path(name);src=work/'test.c';src.write_text(program);binary=work/'test'
                cmd=shlex.split(os.environ.get('CC','cc'))+['-std=gnu99','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(binary)]
                p=subprocess.run(cmd,text=True,capture_output=True,timeout=30);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                p=subprocess.run([str(binary)],text=True,capture_output=True,timeout=10,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'));self.assertEqual(p.returncode,0,p.stdout+p.stderr);print(engine,p.stdout.strip(),flush=True)
if __name__=='__main__':unittest.main()
