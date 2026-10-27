"""Check early script ownership against each build's source contract.

Actual init/copy/clear and container bodies run with reduced interpreter,
local-variable and variant callbacks. These checks do not prove complete
interpreter execution, model loading or gameplay.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from historical_script_lifecycle import render, render_owned
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-script-lifecycle-contracts.json'


def source_parts():
    root = SOURCE / 'src/engines/3741'
    game = (root / 'openbor.c').read_text()
    code = (root / 'openborscript.c').read_text()
    parts = {name: function(game, name) for name in ('alloc_all_scripts',
        'clear_all_scripts', 'copy_all_scripts', 'free_all_scripts')}
    parts.update({name: function(code, name) for name in
        ('alloc_script', 'Script_Init', 'Script_Copy', 'Script_Clear')})
    declaration = re.search(r'typedef\s+struct\s+Script\s*\{[^{}]*\}\s*Script\s*;',
                            (root / 'openborscript.h').read_text())
    container = re.search(r'typedef\s+struct[^{;]*\{[^{}]*\}\s*s_scripts\s*;',
                          (root / 'openbor.h').read_text())
    if declaration is None or container is None:
        raise ValueError('Exact script and container source declarations required')
    parts.update(script=declaration[0], container=container[0])
    support = '\n'.join(function(code, name) for name in (
        'obor_script_destroy_interpreter', 'obor_script_replace_interpreter',
        'obor_script_destroy_comment', 'obor_script_replace_comment',
        'obor_script_share_references'))
    header = SOURCE / 'src/port/libretro/obor_script_storage.h'
    if not header.is_file():
        raise ValueError('The tested source must contain its actual shared storage header')
    options = dict(pointer_container=True, allocation_magic=True, cleanup_safe=True,
                   labels=['source_contract'], includes=('#include '+json.dumps(str(header))+
                       '\nstatic uint32_t obor_profile_build;\nstatic int fixture_expected_magic;'),
                   support=support)
    return parts, options


def program(owned):
    parts, options = source_parts()
    text = (render_owned if owned else render)(parts, **options)
    marker_magic='owner->magic==(1?script_magic:0)'
    if text.count(marker_magic)!=1:
        raise ValueError('One allocation-magic assertion required')
    text=text.replace(marker_magic,'owner->magic==(fixture_expected_magic?script_magic:0)')
    rows = json.loads(CONTRACT_PATH.read_text())['sources']
    # Profile selection belongs to the test main, outside every extracted body.
    # Shared storage is unconditional across this physical engine's profiles.
    marker = 'int main(void) {'
    if text.count(marker) != 1:
        raise ValueError('Exactly one authored fixture main required')
    checks = ('direct_checks();container_checks();owned_order_checks();'
              'owned_reinitialization_checks();owned_replacement_checks();' if owned else
              'direct_checks();container_checks();')
    revisions = ','.join(str(row['revision']) for row in rows)
    magic=','.join(str(int(row['source_allocation_magic'])) for row in rows)
    return text[:text.index(marker)] + '''
int main(int argc,char **argv) {
 const int revisions[]={@REVISIONS@};
 const int magic[]={@MAGIC@};
 assert(argc==2);int revision=atoi(argv[1]),matches=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==revision) {++matches;obor_profile_build=(uint32_t)revision;fixture_expected_magic=magic[i];@CHECKS@}
 assert(matches==1);return 0;
}
'''.replace('@REVISIONS@', revisions).replace('@MAGIC@',magic).replace('@CHECKS@', checks)


class LoadingScriptCleanupTests(unittest.TestCase):
    def test_global_cleanup_callback_order_matches_each_source_profile(self):
        fixture=json.loads((Path(__file__).parent /
            'fixtures/profile-loading-script-clear-contracts.json').read_text())
        rows=fixture['sources'];revisions={row['revision'] for row in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for row in rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertIs(type(row['loading_clear_callback']),bool)
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
        parts,options=source_parts();code=render(parts,**options)
        game=(SOURCE/'src/engines/3741/openbor.c').read_text()
        clear=function(game,'clear_scripts')
        fields=list(dict.fromkeys((m[1],bool(m[2])) for m in
            re.finditer(r'Script_Clear\(&([a-z_]+)(\[i\])?\s*,\s*2\)',clear)))
        self.assertEqual(len(fields),12)
        declarations='\n'.join('static Script '+name+('[4]' if array else '')+';'
                               for name,array in fields)
        pointers=[('&'+name+'[%d]'%i if array else '&'+name)
                  for name,array in fields for i in (range(4) if array else [0])]
        self.assertEqual(len(pointers),27)
        loading_index=pointers.index('&loading_script')
        declaration='static Script *expected_script;'
        self.assertEqual(code.count(declaration),1)
        code=code.replace(declaration,declaration+
            '\nstatic int fixture_global_phase;\nstatic void fixture_note_clear(Script *);')
        reset='assert(p && pcurrentscript==expected_script);++resets;'
        self.assertEqual(code.count(reset),1)
        code=code.replace(reset,'if(fixture_global_phase){fixture_note_clear(pcurrentscript);}\n '+reset)
        entry='int main(void) {'
        self.assertEqual(code.count(entry),1)
        code=code[:code.index(entry)]+r'''
@DECLARATIONS@
static unsigned fixture_clear_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Loading clear revision=%u case=%u line=%d\n",obor_profile_build,fixture_clear_case,__LINE__);abort();}}while(0)
static Script *const globals[]={@POINTERS@};
static int seen[27],active[27],enabled[27],expect_loading,global_clears;
static Interpreter *original_interpreters[27];static ScriptVariant *original_vars[27];
static void fixture_note_clear(Script *script) {
 int index=-1;for(int i=0;i<27;++i)if(globals[i]==script)index=i;
 assert(index>=0 && active[index] && enabled[index]);++seen[index];
 expected_script=script;expected_method=2;
}
static void Script_Global_Clear(void) {
 ++global_clears;
 for(int i=0;i<27;++i) {
  Script *script=globals[i];
  if(i==@LOADING@ && !expect_loading) {
   assert(script->initialized==active[i]);
   assert(script->pinterpreter==original_interpreters[i] && script->vars==original_vars[i]);
  } else assert(!script->initialized && !script->pinterpreter && !script->vars);
 }
}
@CLEAR@
static void check(int has_loading_callback,int vars,int activity,int callbacks) {
 ++fixture_clear_case;
 max_script_vars=vars;reset_counts();memset(seen,0,sizeof(seen));global_clears=0;
 expect_loading=has_loading_callback;static int entry;unsigned initialized=0;
 for(int i=0;i<27;++i) {
  Script *script=globals[i];Script_Init(script,NULL,NULL,1);
  active[i]=activity==1 || (activity==2 && i%2==0);
  enabled[i]=callbacks==1 || (callbacks==2 && i==@LOADING@) || (callbacks==3 && i!=@LOADING@);
  if(active[i]) {initialize(script,"global");++initialized;if(enabled[i])script->pinterpreter->pClearEntry=&entry;}
  original_interpreters[i]=script->pinterpreter;original_vars[i]=script->vars;
 }
 Script saved={0};pcurrentscript=&saved;fixture_global_phase=1;clear_scripts();fixture_global_phase=0;
 assert(global_clears==1 && pcurrentscript==&saved);
 for(int i=0;i<27;++i)assert(seen[i]==(active[i] && enabled[i] && (i!=@LOADING@ || expect_loading)));
 assert(interpreter_clears==initialized-(unsigned)(!expect_loading && active[@LOADING@]));
 /* The older operation retains loading until engine teardown. This fixture
  * owns its host allocations and releases them after comparing that lifetime;
  * the production port releases the complete engine arena without callbacks. */
 if(!expect_loading){
  if(loading_script.initialized)loading_script.pinterpreter->pClearEntry=NULL;
  Script_Clear(&loading_script,2);
 }
 assert(interpreter_clears==initialized);
 for(int i=0;i<27;++i)assert(!globals[i]->vars && !globals[i]->pinterpreter);
 pcurrentscript=NULL;
}
int main(void) {
 const struct {uint32_t revision;int clear_loading;} profiles[]={@PROFILES@};
 for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);++i) {
  obor_profile_build=profiles[i].revision;
  for(int vars=0;vars<=3;vars+=3)for(int active=0;active<3;++active)
  for(int callbacks=0;callbacks<4;++callbacks)check(profiles[i].clear_loading,vars,active,callbacks);
 }
 return 0;
}
'''.replace('@DECLARATIONS@',declarations).replace('@POINTERS@',','.join(pointers)).replace(
            '@LOADING@',str(loading_index)).replace('@CLEAR@',clear).replace('@PROFILES@',
            ','.join('{%d,%d}'%(row['revision'],row['loading_clear_callback']) for row in rows))
        with tempfile.TemporaryDirectory(prefix='anybor-loading-script-clear-') as temporary:
            work=Path(temporary);source=work/'probe.c';exe=work/'probe';source.write_text(code)
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc'))+[
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-function','-g','-fsanitize=address,undefined',
                str(source),'-o',str(exe)],check=True,timeout=60)
            subprocess.run([str(exe)],check=True,timeout=20,env=sanitizer_environment())


class ScriptOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix='anybor-script-ownership-')
        cls.addClassCleanup(temporary.cleanup)
        cls.work = Path(temporary.name)
        cls.rows = json.loads(CONTRACT_PATH.read_text())['sources']
        cls.executables = {}
        for mode, owned in (('valid', False), ('owned', True)):
            source = cls.work / (mode+'.c')
            executable = cls.work / mode
            source.write_text(program(owned))
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-g',
                '-fsanitize=address,undefined,float-cast-overflow',
                str(source), '-o', str(executable)], check=True, timeout=60)
            cls.executables[mode] = executable

    def test_registry_covers_registered_profiles_and_own_sources(self):
        revisions = [row['revision'] for row in self.rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in self.rows:
            with self.subTest(profile=row['revision']):
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertEqual(len(row['script_fields']), 21)
                self.assertEqual(len(set(row['script_fields'])), 21)
                self.assertIn(row['source_container'], ('pointer', 'embedded'))
                self.assertIs(type(row['source_allocation_magic']), bool)
                self.assertIs(type(row['source_cleanup_safe']), bool)
                for digest in row['source_sha256'].values():
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def run_mode(self, mode):
        for row in self.rows:
            with self.subTest(profile=row['revision']):
                subprocess.run([str(self.executables[mode]), str(row['revision'])],
                    check=True, timeout=20, env=sanitizer_environment())

    def test_valid_script_values_variables_and_callbacks_per_source(self):
        self.run_mode('valid')

    def test_both_disposal_orders_and_independent_replacement_per_source(self):
        self.run_mode('owned')


if __name__ == '__main__':
    unittest.main()
