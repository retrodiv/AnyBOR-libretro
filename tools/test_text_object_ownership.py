"""Exercise replacement ownership in every retained native text setter.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from test_historical_player import function
from native_sanitizers import sanitizer_environment

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class TextObjectOwnershipTests(unittest.TestCase):
    def test_repeated_replacement_keeps_one_owned_allocation(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        with tempfile.TemporaryDirectory(prefix='text-object-ownership-') as folder:
            work = Path(folder)
            for engine in pin['engines']:
                build = engine['build']
                with self.subTest(engine=build):
                    source = (ROOT / 'src/engines' / build / 'openborscript.c').read_text()
                    setter = function(source, 'openbor_changetextobjproperty')
                    match = re.search(r'case\s+_(?:c)?top_text\s*:', setter)
                    self.assertIsNotNone(match)
                    end = re.search(r'\n\s*case\s+', setter[match.end():])
                    self.assertIsNotNone(end)
                    # Execute the native text branch, including its conversion
                    # and allocation path, rather than a copied implementation.
                    branch = setter[match.end():match.end() + end.start()]
                    helper = (function(source, 'openbor_textobj_set_text')
                              if 'openbor_textobj_set_text(' in branch else '')
                    profiles = [int(p.get('revision', p['build'])) for p in pin['profiles']
                                if p['engine'] == build]
                    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int HRESULT,LONG;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
#define MAX_STR_VAR_LEN 255
#define SCRIPT_VARIANT_CONVERSION_BUFFER_LENGTH 255
enum {VT_STR=1,VT_INTEGER=2};
typedef struct {int vt; const char *strVal;} ScriptVariant;
typedef struct {const char *string;size_t length;} ScriptVariantStringView;
typedef struct {char *text;} s_textobj;
static struct {s_textobj textobjs[1];} storage,*level=&storage;
static uint32_t obor_profile_build;
static size_t live_allocations;
static void *counted_malloc(size_t n) {void *p=malloc(n);assert(p);++live_allocations;return p;}
static void counted_free(void *p) {if(p){assert(live_allocations);--live_allocations;free(p);}}
#define malloc counted_malloc
#define free counted_free
#define StrCache_Get(x) (x)
static void ScriptVariant_ToString(const ScriptVariant *v,char *b) {strcpy(b,v->strVal);}
static HRESULT ScriptVariant_GetStringView(const ScriptVariant *v,char *b,size_t n,ScriptVariantStringView *out) {
    (void)b;(void)n;if(v->vt!=VT_STR)return E_FAIL;
    out->string=v->strVal;out->length=strlen(v->strVal);return S_OK;
}
HELPER
static HRESULT replace(ScriptVariant **varlist) {
    int ind=0,legacy_result=obor_profile_build<3821;char buf[MAX_STR_VAR_LEN];
    struct {int lVal;} result,*result_ptr=&result,**pretvar=&result_ptr;
    (void)ind;(void)buf;(void)pretvar;(void)legacy_result;
    switch(0) {case 0: BRANCH }
    return S_OK;
changetextobjproperty_error:
    return E_FAIL;
}
int main(void) {
    static const uint32_t profiles[]={PROFILES};
    for(size_t profile=0;profile<sizeof(profiles)/sizeof(*profiles);++profile) {
        obor_profile_build=profiles[profile];
        ScriptVariant value={VT_STR,"first"},*args[]={NULL,NULL,&value};
        for(unsigned i=0;i<1000;++i) {
            value.strVal=(i%2)?"second replacement":"first";
            assert(replace(args)==S_OK);
            assert(live_allocations==1);
            assert(!strcmp(storage.textobjs[0].text,value.strVal));
        }
        free(storage.textobjs[0].text);storage.textobjs[0].text=NULL;
        assert(live_allocations==0);
    }
}
'''.replace('HELPER', helper).replace('BRANCH', branch).replace(
                        'PROFILES', ','.join(map(str, profiles)))
                    src = work / (build + '.c')
                    exe = work / build
                    src.write_text(program)
                    cc = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
                    compile_run = subprocess.run(cc + ['-std=gnu99', '-O1', '-g',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        str(src), '-o', str(exe)], capture_output=True, text=True, timeout=30)
                    self.assertEqual(compile_run.returncode, 0,
                                     compile_run.stdout + compile_run.stderr)
                    run = subprocess.run([str(exe)], capture_output=True, text=True,
                        timeout=10, env=sanitizer_environment())
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
