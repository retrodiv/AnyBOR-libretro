"""Exercise historical level spawn coordinates and ordered cached scripts.

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

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
ENGINE = Path(os.environ.get('OBOR_LEVEL_ENGINE', SOURCE / 'src/engines/3842'))


def level_fixture(members, profile):
    result = dict(members)
    result['data/models.txt'] += b'load Sentry data/chars/sentry.txt\n'
    result['data/chars/sentry.txt'] = (members['data/chars/block.txt']
        .replace(b'name TestBlock', b'name Sentry').replace(b'type player', b'type enemy')
        .replace(b'health 100', b'health 100000').replace(b'speed 2', b'speed 0'))
    result['data/levels.txt'] = (b'set Diagnostics\nskipselect TestBlock\n'
                                  b'file data/levels/room.txt\n')
    script = b'''void main() {
    void count = getlocalvar("call_count");
    if(count == NULL()) count = 0;
    count = count + 1;
    setlocalvar("call_count", count);
    log("HISTORICAL_SPAWN_A_" + count + "\\n");
}
'''
    result['data/scripts/a.c'] = script
    result['data/scripts/b.c'] = script.replace(b'SPAWN_A_', b'SPAWN_B_')
    result['data/scripts/combined.c'] = script.replace(
        b'log("HISTORICAL_SPAWN_A_" + count + "\\n");',
        b'log("HISTORICAL_SPAWN_A_" + count + "\\n");\n'
        b'    log("HISTORICAL_SPAWN_B_" + count + "\\n");')
    first = (b'spawnscript data/scripts/a.c\nspawnscript data/scripts/b.c\n'
             if int(profile) < 3805 else b'spawnscript data/scripts/combined.c\n')
    result['data/levels/room.txt'] = members['data/levels/room.txt'].replace(
        b'order a\n', b'order aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n') + (
        b'nopause 1\nspawn Sentry\ncoords 150 200 0\n' + first + b'at 0\n'
        b'spawn Sentry\ncoords 200 200 0\nspawnscript data/scripts/a.c\nat 0\n')
    return result


def check_level_continuation(log, profile):
    expected = [('A', '1'), ('B', '1'), ('A', '2' if int(profile) < 3805 else '1')]
    calls = re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                       r'HISTORICAL_SPAWN_([AB])_([0-9]+)[ \t]*\r?$', log)
    if calls != expected or "There's an exception while executing script" in log:
        raise RuntimeError('Level spawn script order or shared locals differ: ' + log)


class HistoricalLevelTests(unittest.TestCase):
    def test_compiled_script_check_distinguishes_shared_and_per_entry_locals(self):
        old = '\n'.join('[game] HISTORICAL_SPAWN_' + suffix for suffix in ('A_1', 'B_1', 'A_2'))
        modern = old.replace('A_2', 'A_1')
        check_level_continuation(old, '3780')
        check_level_continuation(modern, '3805')
        for log, profile in ((modern, '3780'), (old, '3805'),
                             ('log("HISTORICAL_SPAWN_A_1");', '3780')):
            with self.subTest(profile=profile), self.assertRaises(RuntimeError):
                check_level_continuation(log, profile)

    def test_order_shared_locals_cleanup_failures_and_coordinate_boundary(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        start = header.index('typedef struct obor_level_spawn_resource {')
        declarations = header[start:header.index('typedef struct\n{\n\tint at;', start)]
        methods = '\n'.join(function(source, name) for name in (
            'obor_clear_historical_spawn_scripts', 'obor_load_historical_spawn_script',
            'obor_execute_spawn_script', 'execute_spawn_script'))
        start = source.index('case CMD_LEVEL_SPAWN1: case CMD_LEVEL_SPAWN2:')
        spawn = source[start:source.index('case CMD_LEVEL_FRONTPANEL:', start)]
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef void VOID;
enum { VT_EMPTY, VT_PTR };
typedef struct { int vt; void *ptrVal; } ScriptVariant;
typedef struct { int id; } entity;
typedef struct { int initialized,id,local; void *self; } Script;
static uint32_t obor_profile_build;
static int active,attempts,fail_at=-1,initialized,compiled,cleared,compile_failure;
static int executions,ids[16],locals[16];
static int clear_ids[16];
static void *subjects[16];
static void *test_malloc(size_t size) {
    if(attempts++==fail_at) return NULL;
    void *p=malloc(size); assert(p); ++active; return p;
}
static void *test_calloc(size_t n,size_t size) {
    void *p=test_malloc(n*size); if(p) memset(p,0,n*size); return p;
}
static void test_free(void *p) { if(p) { assert(active>0);--active;free(p); } }
static void Script_Init(Script *s,char *name,char *comment,int first) {
    assert(name && comment && first==1); memset(s,0,sizeof(*s));
    s->initialized=1;++initialized;
}
static int load_script(Script *s,char *path) {
    if(!strcasecmp(path,"missing")) return 0;
    s->id=(!strcasecmp(path,"a.c"))?1:2; return 1;
}
static int Script_Compile(Script *s) { assert(s->initialized);++compiled;return !compile_failure; }
static void Script_Clear(Script *s,int mode) {
    assert(mode==2 && s->initialized && cleared<16);
    clear_ids[cleared++]=s->id;s->initialized=0;
}
static int Script_IsInitialized(Script *s) { return s->initialized; }
static void ScriptVariant_Init(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
static void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) { v->vt=type; }
static void Script_Set_Local_Variant(Script *s,char *name,ScriptVariant *v) {
    assert(!strcmp(name,"self")); s->self=v->vt==VT_PTR?v->ptrVal:NULL;
}
static void Script_Execute(Script *s) {
    assert(executions<16);ids[executions]=s->id;locals[executions]=++s->local;
    subjects[executions++]=s->self;
}
DECLARATIONS
typedef struct {
    Script spawnscript;
    obor_level_spawn_call *historical_scripts,*historical_scripts_tail;
} s_spawn_entry;
typedef struct {
    obor_level_spawn_resource *historical_script_cache;
    obor_level_spawn_call *historical_script_calls;
    int spawn[4][3];
} s_level;
#define stricmp strcasecmp
#define malloc test_malloc
#define calloc test_calloc
#define free test_free
METHODS
enum { CMD_LEVEL_SPAWN1=10,CMD_LEVEL_SPAWN2,CMD_LEVEL_SPAWN3,CMD_LEVEL_SPAWN4 };
#define GET_INT_ARG(n) args[n]
static void set_spawn(s_level *level,int cmd,int *args) {
    int i=0;
    switch(cmd) { SPAWN_CASE }
}
static void reset_counts(void) {
    assert(active==0);attempts=initialized=compiled=cleared=executions=compile_failure=0;
    fail_at=-1;memset(ids,0,sizeof(ids));memset(locals,0,sizeof(locals));
}
int main(void) {
    const int builds[]={3780,3783,3789,3793,3797,3799,3800,3805,3814,3818,
                        3822,3824,3829,3831,3837,3839,3842};
    for(unsigned b=0;b<sizeof(builds)/sizeof(*builds);++b) {
        obor_profile_build=builds[b];
        const int z[]={-2147483647,-1,0,1,231,232,233,300,2147483647};
        for(unsigned j=0;j<sizeof(z)/sizeof(*z);++j) for(int player=0;player<4;++player) {
            s_level lv={0};int args[]={0,83,z[j],-1};
            set_spawn(&lv,CMD_LEVEL_SPAWN1+player,args);
            int expected=builds[b]<3800 && (z[j]<0 || z[j]>232)?232:z[j];
            assert(lv.spawn[player][0]==83 && lv.spawn[player][1]==expected);
            assert(lv.spawn[player][2]==300);
            for(int other=0;other<4;++other) if(other!=player)
                assert(lv.spawn[other][0]==0 && lv.spawn[other][1]==0 && lv.spawn[other][2]==0);
        }
    }
    obor_profile_build=3780;reset_counts();
    s_level lv={0};s_spawn_entry first={0},second={0};entity subject={17};
    assert(obor_load_historical_spawn_script(&lv,&first,"a.c"));
    assert(obor_load_historical_spawn_script(&lv,&first,"b.c"));
    assert(obor_load_historical_spawn_script(&lv,&second,"A.C"));
    assert(initialized==2 && compiled==2);
    assert(first.historical_scripts->resource==second.historical_scripts->resource);
    execute_spawn_script(&first,&subject);execute_spawn_script(&second,&subject);
    assert(executions==3 && ids[0]==1 && ids[1]==2 && ids[2]==1);
    assert(locals[0]==1 && locals[1]==1 && locals[2]==2);
    for(int i=0;i<3;++i) assert(subjects[i]==&subject);
    assert(!first.historical_scripts->resource->script.self);
    assert(!first.historical_scripts_tail->resource->script.self);
    execute_spawn_script(&second,NULL);
    assert(executions==4 && ids[3]==1 && locals[3]==3 && subjects[3]==NULL);
    obor_profile_build=3805;first.spawnscript.initialized=1;first.spawnscript.id=99;
    execute_spawn_script(&first,&subject);
    assert(executions==5 && ids[4]==99 && subjects[4]==&subject);
    assert(!first.spawnscript.self);
    /* Discarded unqueued entries still have a level owner. */
    memset(&first,0,sizeof(first));memset(&second,0,sizeof(second));
    obor_clear_historical_spawn_scripts(&lv);
    assert(active==0 && cleared==2 && !lv.historical_script_cache && !lv.historical_script_calls);
    assert(clear_ids[0]==1 && clear_ids[1]==2);
    obor_clear_historical_spawn_scripts(&lv);assert(cleared==2);
    for(int failure=0;failure<3;++failure) {
        reset_counts();fail_at=failure;
        assert(!obor_load_historical_spawn_script(&lv,&first,"a.c"));
        assert(!first.historical_scripts && !first.historical_scripts_tail);
        obor_clear_historical_spawn_scripts(&lv);assert(active==0);
    }
    for(int failure=0;failure<2;++failure) {
        reset_counts();compile_failure=failure;
        assert(!obor_load_historical_spawn_script(&lv,&first,failure?"a.c":"missing"));
        assert(!first.historical_scripts && !lv.historical_script_cache);
        obor_clear_historical_spawn_scripts(&lv);assert(active==0 && cleared==1);
    }
    puts("historical level native contracts: OK");
    return 0;
}
'''
        for key, value in (('DECLARATIONS', declarations), ('METHODS', methods),
                           ('SPAWN_CASE', spawn)):
            program = program.replace(key, value)
        with tempfile.TemporaryDirectory(prefix='anybor-historical-level-') as temporary:
            root = Path(temporary)
            native = root / 'level.c'
            native.write_text(program)
            host = root / 'level'
            subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
                '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations', '-g',
                '-fsanitize=address,undefined', str(native), '-o', str(host)],
                check=True, timeout=60)
            result = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('historical level native contracts: OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
