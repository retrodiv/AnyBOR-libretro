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


def variable_key_requires_level(profile):
    return (profile['engine'] == '3400' and
            int(profile.get('revision', profile['build'])) < 3358)


def variable_key_legacy_escape(profile):
    return (profile['engine'] == '3400' and
            int(profile.get('revision', profile['build'])) < 3368)


def variable_key_fixture(members, profile=None):
    result = dict(members)
    # Earlier builds run the global update callback in gameplay, and do not
    # execute the global updated callback. Keep their original callback rules.
    early = profile is not None and variable_key_requires_level(profile)
    if early:
        # Keep the level open while variables are observed and saved. This is
        # the same stationary geometric target used by the input fixture.
        result['data/models.txt'] += b'load VariableWitness data/chars/variable-witness.txt\n'
        result['data/chars/variable-witness.txt'] = (
            members['data/chars/block.txt'].replace(b'name TestBlock', b'name VariableWitness')
            .replace(b'type player', b'type enemy').replace(b'health 100', b'health 100000')
            .replace(b'speed 2', b'speed 0'))
        result['data/levels.txt'] = result['data/levels.txt'].replace(
            b'file data/levels/room.txt', b'skipselect TestBlock\nfile data/levels/room.txt')
        result['data/levels/room.txt'] = result['data/levels/room.txt'].replace(
            b'order a\n', b'order aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n') + (
            b'nopause 1\ngroup 1 1\nspawn VariableWitness\ncoords 600 200\nat 0\n')
    else:
        result['data/script.txt'] = b'alwaysupdate 1\n'
    callback = 'update' if early else 'updated'
    result['data/scripts/' + callback + '.c'] = b'''void main() {
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


def check_variable_key_continuation(log, engine, restarts=0, *, legacy_escape=False,
                                    gameplay_callback=False):
    if gameplay_callback:
        # A gameplay-only callback cannot run before startup completes. The
        # frontend log tail may read the previous session's file while a reset
        # is still loading; those lines are not evidence from this session.
        ready = False
        current = []
        for line in log.splitlines():
            if line.startswith('[OpenBOR] pak needs ') or line.startswith('[OpenBOR] reset:'):
                ready = False
            if line == '[OpenBOR] resource initialization complete':
                ready = True
            if ready:
                current.append(line)
        log = '\n'.join(current)
    # The original lexer before3368 emits LF followed by the literal n for
    # \n, which can prefix the next actual log line. Retain that behavior.
    prefix = 'n?' if legacy_escape else ''
    markers = re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                         + prefix + r'(VARIABLE_KEY_[A-Z_]+)[ \t]*\r?$', log)
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
    def test_runtime_fixture_uses_available_callback_on_both_sides(self):
        from make_fixture import files
        members = files()
        for engine, revision, early in (('3400', 3020, True), ('3400', 3357, True),
                                        ('3400', 3358, False), ('3400', 3400, False),
                                        ('3741', 3741, False)):
            with self.subTest(engine=engine, revision=revision):
                profile = dict(engine=engine, build=str(revision))
                self.assertEqual(variable_key_requires_level(profile), early)
                fixture = variable_key_fixture(members, profile)
                callback = 'update' if early else 'updated'
                self.assertIn('data/scripts/' + callback + '.c', fixture)
                self.assertEqual('data/script.txt' in fixture, not early)
                self.assertTrue(fixture['data/models.txt'].startswith(members['data/models.txt']))
                self.assertEqual('data/chars/variable-witness.txt' in fixture, early)
                if early:
                    self.assertIn(b'spawn VariableWitness', fixture['data/levels/room.txt'])
                self.assertIn(b'VARIABLE_KEY_FULL_NAMES',
                              fixture['data/scripts/' + callback + '.c'])

    def test_runtime_markers_preserve_own_lexer_escape_boundary(self):
        log = ('[game] VARIABLE_KEY_FULL_NAMES\n[game] nVARIABLE_KEY_CONTINUED\n'
               '[game] nVARIABLE_KEY_VERIFIED\n[game] nVARIABLE_KEY_VERIFIED\n')
        check_variable_key_continuation(log, '3357', legacy_escape=True)
        with self.assertRaises(RuntimeError):
            check_variable_key_continuation(log, '3368')
        for revision, legacy in ((3020, True), (3367, True), (3368, False), (3400, False)):
            self.assertEqual(variable_key_legacy_escape(dict(engine='3400', build=str(revision))), legacy)
        for bad in (log.replace('CONTINUED', 'BAD_RESULT'),
                    log.replace('nVARIABLE_KEY_CONTINUED', 'nnVARIABLE_KEY_CONTINUED'),
                    'log("VARIABLE_KEY_FULL_NAMES\\n");'):
            with self.assertRaises(RuntimeError):
                check_variable_key_continuation(bad, '3357', legacy_escape=True)

    def test_gameplay_markers_require_current_session_startup(self):
        markers = ('[game] VARIABLE_KEY_FULL_NAMES\n[game] VARIABLE_KEY_CONTINUED\n'
                   '[game] VARIABLE_KEY_VERIFIED\n[game] VARIABLE_KEY_VERIFIED\n')
        ready = '[OpenBOR] resource initialization complete\n'
        reset = '[OpenBOR] reset: booting engine 3400\n'
        log = ready + markers + reset + markers + ready + markers
        check_variable_key_continuation(log, '3020', restarts=1, gameplay_callback=True)
        for bad in (ready + markers + reset + markers,
                    log.replace(ready + markers, ready + markers.replace('CONTINUED', 'BAD_RESULT'))):
            with self.assertRaises(RuntimeError):
                check_variable_key_continuation(bad, '3020', restarts=1, gameplay_callback=True)

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

    def check_old_table(self, source, header, *, has_gc, explicit_owner, revision, counted_empty=False):
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct Script { int initialized; } Script;
typedef struct { int vt,value; } ScriptVariant;
enum { VT_EMPTY,VT_INTEGER };
enum { obor_profile_build=PROFILE_REVISION };
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
COUNTED_EMPTY
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
            empty_control = r"""
    {
        ScriptVariant seed={VT_INTEGER,101};
        Script empty_owner={1};
        max_global_var_index=0;
        assert(!Script_Get_Global_Variant("absent"));
        assert(_set_var("global_seed",&seed,NULL)==1 && max_global_var_index==1);
        assert(Script_Get_Global_Variant("global_seed")->value==101);
        nodes[0].owner=&empty_owner;
        assert(!read_local(&empty_owner,"absent"));
        assert(_set_var("local_seed",&seed,&empty_owner)==1 && max_global_var_index==2);
        assert(read_local(&empty_owner,"local_seed")->value==101);
        assert(!Script_Get_Global_Variant("local_seed"));
        assert(active==2);
        obor_script_variable_names_clear();assert(active==0);
        memset(nodes,0,sizeof(nodes));max_global_var_index=-1;copies=0;pcurrentscript=NULL;
    }
""" if counted_empty else ''
            body = program.replace('COUNTED_EMPTY', empty_control)
            for key, value in (('NODE', node), ('GC', gc), ('METHODS', methods),
                               ('LOCAL_WRAPPER', local), ('PROFILE_REVISION', str(revision))):
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

    def test_counted_empty_slot_behaves_like_original_empty_name(self):
        engine = Path(os.environ.get('OBOR_VARIABLE_KEYS_ENGINE', SOURCE / 'src/engines/3400'))
        self.check_old_table((engine / 'openborscript.c').read_text(),
                             (engine / 'openborscript.h').read_text(),
                             has_gc=False, explicit_owner=False, revision=3400, counted_empty=True)

    def test_old_tables_own_full_names_without_truncation_or_aliases(self):
        for build in ('3400', '3741', '3842'):
            with self.subTest(build=build):
                engine = SOURCE / 'src/engines' / build
                self.check_old_table((engine / 'openborscript.c').read_text(),
                                     (engine / 'openborscript.h').read_text(),
                                     has_gc=build == '3842', explicit_owner=build != '3400',
                                     revision=int(build))


if __name__ == '__main__':
    unittest.main()
