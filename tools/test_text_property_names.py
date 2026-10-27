"""Check text-property name tables at each actual engine entry point.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function
from native_sanitizers import sanitizer_environment
from historical_stringmap_dispatch import render_dispatch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',ROOT))
class TextPropertyNameTests(unittest.TestCase):
    def test_every_engine_names_numeric_ids_unknowns_and_repeated_lowering(self):
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('text-property-contracts.json').read_text())
        self.assertEqual(fixture['schema'],1)
        for engine_spec in pin['engines']:
            engine=engine_spec['build']
            with self.subTest(engine=engine),tempfile.TemporaryDirectory(prefix='text-property-names-') as temporary:
                source=SOURCE/f'src/engines/{engine}/openborscript.c'
                if 'OBOR_TOLERANCE_DRAFT'in os.environ:source=Path(os.environ['OBOR_TOLERANCE_DRAFT'])/'text-maps'/engine/'openborscript.c'
                text=source.read_text()
                declared=fixture['engines'].get(engine)
                methods=list(declared['rules'][0]['methods'])if declared else['mapstrings_textobjproperty']
                enums='\n'.join(re.findall(r'enum (?:g|c)top_enum\s*\{.*?\};',text,re.S));assert enums,engine
                body='';checks=[]
                for method in methods:
                    body+=function(text,method)
                if re.search(r'\bsearchList\s*\(', body):
                    body=function(source.with_name('source').joinpath('utils.c').read_text(),'searchList')+'\n'+body
                if not declared:
                    properties=[n for n in re.findall(r'\b_top_([a-z_]+)\b',enums)if n!='the_end']
                    declared=dict(extra_contexts=[],rules=[dict(first=0,last=2147483647,
                        methods={methods[0]:{name:'_top_'+name for name in properties}},
                        get=methods[0],change=methods[0])])
                contexts=sorted({int(p.get('revision',p['build']))for p in pin['profiles']if p['engine']==engine}|
                                set(declared['extra_contexts']))
                checks += ['const uint32_t contexts[]={'+','.join(str(n)+'u'for n in contexts)+'};',
                           'unsigned checked=0;',
                           'for(unsigned context=0;context<sizeof(contexts)/sizeof(*contexts);++context){',
                           'obor_profile_build=contexts[context];unsigned matched=0;']
                for rule in declared['rules']:
                    checks.append('if(obor_profile_build>='+str(rule['first'])+'u&&obor_profile_build<='+str(rule['last'])+'u){++matched;')
                    for method,names in rule['methods'].items():
                        for name,number in names.items():
                            self.assertRegex(name,r'^[A-Za-z0-9_]+$')
                            checks.append(f'check({method},"{name.upper()}",{number});')
                        for unknown in ['unknown','zz','timeextra','fontextra','aextra','']+rule.get('unknowns',[]):
                            self.assertRegex(unknown,r'^[A-Za-z0-9_]*$')
                            checks.append(f'check({method},"{unknown}",-1);')
                    checks.append('assert(Script_GetStringMapFunction((void*)openbor_gettextobjproperty)==(void*)'+rule['get']+');')
                    checks.append('assert(Script_GetStringMapFunction((void*)openbor_changetextobjproperty)==(void*)'+rule['change']+');')
                    checks.append('}')
                checks.append('assert(matched==1);++checked;}')
                dispatch_source=text
                if not re.search(r'(?m)^void\s*\*\s*Script_GetStringMapFunction\s*\(',text):
                    dispatch_source=source.with_name('source').joinpath('openborscript/index.c').read_text()
                dispatch=render_dispatch(function(dispatch_source,'Script_GetStringMapFunction'),
                    retained_references=['openbor_gettextobjproperty','openbor_changetextobjproperty',*methods])
                program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
enum {VT_INTEGER,VT_STR};
typedef struct {int vt;long lVal;const char *strVal;} ScriptVariant;
#define StrCache_Get(x) (x)
#define StrCache_GetIfPresent(x) (x)
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){v->vt=type;}
uint32_t obor_profile_build;
static void openbor_gettextobjproperty(void){abort();}
static void openbor_changetextobjproperty(void){abort();}
'''+enums+'\n'+body+'\n'+dispatch+r'''
/* Return types differ by era; use a macro so the exact function signature stays intact. */
#define check(METHOD,NAME,EXPECTED) do { \
 ScriptVariant a={.vt=VT_INTEGER},b={.vt=VT_STR,.strVal=NAME},*v[]={&a,&b}; \
 METHOD(v,2);if(EXPECTED>=0){assert(b.vt==VT_INTEGER&&b.lVal==EXPECTED); \
 METHOD(v,2);assert(b.vt==VT_INTEGER&&b.lVal==EXPECTED);} \
 else assert(b.vt==VT_STR&&!strcmp(b.strVal,NAME)); \
 METHOD(v,1); }while(0)
int main(void){
'''+ '\n'.join(checks)+'\nprintf("text_names=1 native_ids=1 unknown_refused=1 cached_ids=1 native_mapper_entry=1 contexts=%u\\n",checked);return 0;}\n'
                work=Path(temporary);src=work/'test.c';src.write_text(program);binary=work/'test'
                cmd=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))+['-std=gnu99','-O1','-g','-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)]
                p=subprocess.run(cmd,text=True,capture_output=True,timeout=30);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                p=subprocess.run([str(binary)],text=True,capture_output=True,timeout=10,env=sanitizer_environment());self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertRegex(p.stdout,r'(?m)^text_names=1 native_ids=1 unknown_refused=1 cached_ids=1 native_mapper_entry=1 contexts='+str(len(contexts))+r'$')
                print(engine,p.stdout.strip(),flush=True)
if __name__=='__main__':unittest.main()
