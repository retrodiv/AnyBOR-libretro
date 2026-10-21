"""Require complete, distinct and owned script variable names in every engine.

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

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))


def variable_key_fixture(members):
    result = dict(members)
    result['data/script.txt'] = b'alwaysupdate 1\n'
    result['data/scripts/updated.c'] = b'''void main() {
    void tick;
    void first;
    void second;
    if(getglobalvar("vk_checked") == 1) {
        if(getglobalvar("abcdefghijklmnopqrstuvwx") != 17 ||
           getglobalvar("abcdefghijklmnopqrstuvwx_tail") != 29 ||
           getglobalvar("abcdefghijklmnopqrstuvw") != 43 ||
           getlocalvar("abcdefghijklmnopqrstuvwx") != 71 ||
           getlocalvar("abcdefghijklmnopqrstuvwx_tail") != 73)
            log("VARIABLE_KEY_BAD_RESULT\\n");
        tick = getglobalvar("vk_tick") + 1;
        setglobalvar("vk_tick", tick);
        if(tick % 32 == 0) log("VARIABLE_KEY_VERIFIED\\n");
        return;
    }
    setglobalvar("vk_checked", 1);
    setglobalvar("vk_tick", 0);
    setglobalvar("abcdefghijklmnopqrstuvw", 43);
    first = setglobalvar("abcdefghijklmnopqrstuvwx", 17);
    second = setglobalvar("abcdefghijklmnopqrstuvwx_tail", 29);
    setlocalvar("abcdefghijklmnopqrstuvwx", 71);
    setlocalvar("abcdefghijklmnopqrstuvwx_tail", 73);
    if(first == 1 && second == 1 &&
       getglobalvar("abcdefghijklmnopqrstuvwx") == 17 &&
       getglobalvar("abcdefghijklmnopqrstuvwx_tail") == 29 &&
       getglobalvar("abcdefghijklmnopqrstuvw") == 43)
        log("VARIABLE_KEY_FULL_NAMES\\n");
    else log("VARIABLE_KEY_BAD_RESULT\\n");
    log("VARIABLE_KEY_CONTINUED\\n");
}
'''
    return result


def check_variable_key_continuation(log, engine, restarts=0):
    markers = re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                         r'(VARIABLE_KEY_[A-Z_]+)[ \t]*\r?$', log)
    verified = markers.count('VARIABLE_KEY_VERIFIED')
    markers = [marker for marker in markers if marker != 'VARIABLE_KEY_VERIFIED']
    if markers != ['VARIABLE_KEY_FULL_NAMES', 'VARIABLE_KEY_CONTINUED'] * (1 + restarts) or \
            verified < 2 or \
            "There's an exception while executing script" in log:
        raise RuntimeError('Complete script variable names differ in engine ' + str(engine) + ': ' + log)


def function(source, name):
    start = re.search(r'(?m)^(?:static )?[\w* ]+\b' + name + r'\([^;]*?\)\s*\{', source)
    if start is None:
        raise AssertionError('Missing native function ' + name)
    end, depth = start.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start.start():end] + '\n'


class ScriptVariableKeyTests(unittest.TestCase):
    def test_runtime_check_requires_actual_full_name_continuation(self):
        check_variable_key_continuation('[game] VARIABLE_KEY_FULL_NAMES\n'
                                       '[game] VARIABLE_KEY_CONTINUED\n'
                                       '[game] VARIABLE_KEY_VERIFIED\n'
                                       '[game] VARIABLE_KEY_VERIFIED\n', '3400')
        for log in ('log("VARIABLE_KEY_FULL_NAMES\\n");',
                    '[game] VARIABLE_KEY_BAD_RESULT\n[game] VARIABLE_KEY_CONTINUED\n',
                    '[game] VARIABLE_KEY_FULL_NAMES\n'):
            with self.subTest(log=log), self.assertRaises(RuntimeError):
                check_variable_key_continuation(log, '3842')

    def check_old_table(self, source, header, *, has_gc, explicit_owner):
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct Script { int initialized; } Script;
typedef struct { int vt,value; } ScriptVariant;
enum { VT_EMPTY,VT_INTEGER };
NODE
static s_variantnode nodes[8],*slots[8];
static s_variantnode **global_var_list=slots;
static int max_global_var_index=-1,max_global_vars=8,copies,active,fail_next;
Script *pcurrentscript;
static void ScriptVariant_Copy(ScriptVariant *to,ScriptVariant *from) { *to=*from;++copies; }
static void *test_malloc(size_t bytes) {
    if(fail_next) { fail_next=0;return NULL; }
    void *p=malloc(bytes);assert(p);++active;return p;
}
static void test_free(void *p) { if(p) { assert(active>0);--active;free(p); } }
#define malloc test_malloc
#define free test_free
GC
METHODS
LOCAL_WRAPPER
int main(void) {
    for(int i=0;i<8;++i) slots[i]=nodes+i;
    char name[]="abcdefghijklmnopqrstuvwx";
    const char *full="abcdefghijklmnopqrstuvwx",*longer="abcdefghijklmnopqrstuvwx_tail";
    const char *prefix="abcdefghijklmnopqrstuvw";
    char large[1025];memset(large,'z',sizeof(large));large[sizeof(large)-1]=0;
    ScriptVariant value={VT_INTEGER,17};
    assert(_set_var(name,&value,NULL)==1 && max_global_var_index==0);
    name[0]='Z';
    assert(Script_Get_Global_Variant((char *)full)->value==17);
    assert(Script_Get_Global_Variant(name)==NULL);
    value.value=29;assert(_set_var((char *)longer,&value,NULL)==1);
    value.value=43;assert(_set_var((char *)prefix,&value,NULL)==1);
    value.value=47;assert(_set_var(large,&value,NULL)==1);
    assert(Script_Get_Global_Variant((char *)full)->value==17);
    assert(Script_Get_Global_Variant((char *)longer)->value==29);
    assert(Script_Get_Global_Variant((char *)prefix)->value==43);
    assert(Script_Get_Global_Variant(large)->value==47);
    assert(active==4 && max_global_var_index==3);
    s_variantnode before[8];memcpy(before,nodes,sizeof(nodes));
    int prior_copies=copies;
    assert(!_set_var(NULL,&value,NULL) && !_set_var("",&value,NULL));
    fail_next=1;
    assert(!_set_var("another_complete_name_over_twenty_four_bytes",&value,NULL));
    assert(max_global_var_index==3 && copies==prior_copies && active==4);
    assert(!memcmp(nodes,before,sizeof(nodes)));
    Script owner={1},other={1};pcurrentscript=&owner;
    value.value=59;assert(_set_var((char *)full,&value,&owner)==1);
    value.value=61;assert(_set_var((char *)full,&value,&other)==1);
    assert(read_local(&owner,(char *)full)->value==59);
    assert(read_local(&other,(char *)full)->value==61);
    assert(Script_Get_Global_Variant((char *)full)->value==17);
    value.vt=VT_EMPTY;
    assert(_set_var((char *)longer,&value,NULL)==1);
    assert(!Script_Get_Global_Variant((char *)longer));
    /* The source can alias a retired slot's old name. Copy before releasing it. */
    char *retired=global_var_list[max_global_var_index+1]->key;
    assert(!strcmp(retired,longer));
    value.vt=VT_INTEGER;value.value=67;
    assert(_set_var(retired,&value,NULL)==1);
    assert(Script_Get_Global_Variant((char *)longer)->value==67);
    assert(max_global_var_index==5 && active==6);
    value.value=71;assert(_set_var("seventh",&value,NULL)==1);
    value.value=73;assert(_set_var("eighth",&value,NULL)==1);
    prior_copies=copies;memcpy(before,nodes,sizeof(nodes));
    assert(!_set_var("ninth",&value,NULL));
    assert(max_global_var_index==7 && copies==prior_copies && active==8);
    assert(!memcmp(nodes,before,sizeof(nodes)));
    obor_script_variable_names_clear();
    assert(active==0);
    for(int i=0;i<8;++i) assert(nodes[i].key==NULL);
    obor_script_variable_names_clear();assert(active==0);
    global_var_list=NULL;obor_script_variable_names_clear();
    puts("complete script variable names: OK");
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='anybor-script-key-') as temporary:
            end = header.index('}s_variantnode;') + len('}s_variantnode;')
            node = header[header.rfind('typedef struct', 0, end):end]
            self.assertRegex(node, r'char\s*\*\s*key\s*;')
            self.assertIn('obor_script_variable_names_clear();', function(source, 'Script_Global_Clear'))
            gc = function(source, '_gc_var') if has_gc else ''
            methods = '\n'.join(function(source, name) for name in (
                'obor_script_variable_names_clear', 'Script_Get_Global_Variant',
                'Script_Get_Local_Variant', '_set_var'))
            local = ('static ScriptVariant *read_local(Script *owner,char *name) { '
                     'return Script_Get_Local_Variant(owner,name); }') if explicit_owner else (
                     'static ScriptVariant *read_local(Script *owner,char *name) { '
                     'pcurrentscript=owner;return Script_Get_Local_Variant(name); }')
            native = Path(temporary) / 'keys.c'
            body = program
            for key, value in (('NODE', node), ('GC', gc), ('METHODS', methods), ('LOCAL_WRAPPER', local)):
                body = body.replace(key, value)
            native.write_text(body)
            host = Path(temporary) / 'keys'
            subprocess.run(shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc'))) + [
                '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations', '-g',
                '-fsanitize=address,undefined', str(native), '-o', str(host)],
                check=True, timeout=60)
            result = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('complete script variable names: OK', result.stdout)

    def test_old_tables_own_full_names_without_truncation_or_aliases(self):
        for build in ('3400', '3741', '3842'):
            with self.subTest(build=build):
                engine = SOURCE / 'src/engines' / build
                self.check_old_table((engine / 'openborscript.c').read_text(),
                                     (engine / 'openborscript.h').read_text(),
                                     has_gc=build == '3842', explicit_owner=build != '3400')


if __name__ == '__main__':
    unittest.main()
