"""Match import directives, identifiers and module ownership to own sources.

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

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-script-imports.json'


class EarlyScriptImportTests(unittest.TestCase):
    def test_directives_identifiers_and_module_owners(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        checks, errors = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for group in ['source_sha256', 'function_sha256']:
                self.assertTrue(row[group])
                for digest in row[group].values():
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertIn(row['keyword'], ('PP_TOKEN_IDENTIFIER', 'PP_TOKEN_IMPORT'))
            checks.append('check_keyword(%d,%s);' % (row['revision'], row['keyword']))
            self.assertEqual(set(row['cases']), set(fixture['cases']))
            for name, expected in row['cases'].items():
                self.assertEqual(set(expected), {'tokens', 'imports', 'objects', 'functions', 'error'})
                for key in ['tokens', 'imports']:
                    self.assertIsInstance(expected[key], list)
                    self.assertTrue(all(isinstance(value, str) and 0 < len(value) < 128
                                        for value in expected[key]))
                self.assertTrue(all(type(expected[key]) is int and 0 <= expected[key] <= 1
                                    for key in ['objects', 'functions']))
                arrays = []
                for key in ['tokens', 'imports']:
                    arrays.append('(const char *const[]){' +
                                  ','.join(json.dumps(value) for value in expected[key]) +
                                  ('' if expected[key] else 'NULL') + '}')
                checks.append('check(%d,%s,%s,%s,%d,%s,%d,%d,%d,%d);' % (
                    row['revision'], json.dumps(name), json.dumps(fixture['cases'][name]),
                    arrays[0], len(expected['tokens']), arrays[1], len(expected['imports']),
                    expected['objects'], expected['functions'], bool(expected['error'])))
                if expected['error']:
                    errors.append(expected['error'])
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        interpreter = (engine / 'source/scriptlib/Interpreter.c').read_text()
        compile_body = function(interpreter, 'Interpreter_CompileInstructions')
        start = compile_body.index('size = pinterpreter->theContext.imports.size;')
        end = compile_body.index('pp_context_destroy', start)
        # Retain the complete import loop; the remaining instruction compiler
        # and imported module compiler have their own separate contracts.
        import_loop = compile_body[start:end]
        clear_imports = function(interpreter, 'Interpreter_ClearImports')
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "Lexer.h"
#include "pp_parser.h"
#include "ImportCache.h"
HRESULT Token_InitFromPreprocessor(Token *,pp_token *);
uint32_t obor_profile_build;
List theFunctionList;
char *packfile="authored";
extern List importCache;
static unsigned opened,closed,parsed,compiled,cleared;
static const char module[]="void helper() {}";
void writeToLogFile(const char *format,...) {
 va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);
}
void exitIfFalse(int value,const char *condition,const char *func,const char *file,int line) {
 (void)condition;(void)func;(void)file;(void)line;if(!value)abort();
}
/* Deterministic file and imported-module compiler providers. */
int openpackfile(const char *path,const char *pak) {
 assert(!strcmp(path,"module.c") && !strcmp(pak,"authored"));opened++;return 7;
}
int seekpackfile(int handle,int offset,int whence) {
 assert(handle==7 && offset==0 && (whence==SEEK_END || whence==SEEK_SET));
 return whence==SEEK_END?(int)strlen(module):0;
}
int readpackfile(int handle,void *buffer,int length) {
 assert(handle==7 && length==(int)strlen(module));memcpy(buffer,module,length);return length;
}
int closepackfile(int handle) {assert(handle==7);closed++;return 0;}
void Interpreter_Init(Interpreter *self,LPCSTR name,List *functions) {
 assert(!strcmp(name,"#import") && functions==&theFunctionList);
 memset(self,0,sizeof(*self));
}
HRESULT Interpreter_ParseText(Interpreter *self,LPSTR text,ULONG line,LPCSTR path) {
 (void)self;assert(!strcmp(text,module) && line==1 && !strcmp(path,"module.c"));
 parsed++;return S_OK;
}
HRESULT Interpreter_CompileInstructions(Interpreter *self,List *exports) {
 (void)self;assert(!exports);compiled++;return S_OK;
}
void Interpreter_Clear(Interpreter *self) {(void)self;cleared++;}
static HRESULT load_imports(Interpreter *pinterpreter) {
 int i,size;LPCSTR pLabel;ImportNode *pImport;
 @IMPORT_LOOP@
 return S_OK;
}
@CLEAR_IMPORTS@
static void check_keyword(unsigned revision,int expected) {
 char input[]="import";pp_lexer lexer;pp_token raw;Token token;TEXTPOS start={1,0};
 obor_profile_build=revision;pp_lexer_Init(&lexer,input,start);
 assert(pp_lexer_GetNextToken(&lexer,&raw)==S_OK && raw.theType==expected);
 assert(!strcmp(raw.theSource,"import"));
 memset(&token,0,sizeof(token));assert(Token_InitFromPreprocessor(&token,&raw)==S_OK);
 assert(token.theType==TOKEN_IDENTIFIER && !strcmp(token.theSource,"import"));
}
static void check(unsigned revision,const char *name,const char *text,
                  const char *const *tokens,size_t count,const char *const *imports,
                  size_t import_count,int objects,int functions,int expect_error) {
 Interpreter owner;pp_parser parser;TEXTPOS start={1,0};
 memset(&owner,0,sizeof(owner));char *owned=strdup(text);assert(owned);
 obor_profile_build=revision;opened=closed=parsed=compiled=cleared=0;
 List_Init(&owner.theImportList);pp_context_init(&owner.theContext);ImportCache_Init();
 pp_parser_init(&parser,&owner.theContext,name,owned,start);
 size_t emitted=0;int eof=0,failed=0;
 for(unsigned budget=0;budget<512;budget++) {
  pp_token *token=pp_parser_emit_token(&parser);
  if(!token) {failed=1;break;}
  if(token->theType==PP_TOKEN_EOF) {eof=1;break;}
  if(token->theType==PP_TOKEN_NEWLINE || token->theType==PP_TOKEN_WHITESPACE)continue;
  if(emitted>=count || strcmp(token->theSource,tokens[emitted])) {
   fprintf(stderr,"Import tokens differ: revision=%u case=%s token=%zu got=%s\n",
           revision,name,emitted,token->theSource);abort();
  }
  emitted++;
 }
 assert(emitted==count && failed==expect_error && eof==!expect_error && !parser.child);
 assert(owner.theContext.macros.size==objects && owner.theContext.func_macros.size==functions);
 assert(!owner.theContext.num_conditionals && owner.theContext.imports.size==(int)import_count);
 List_Reset(&owner.theContext.imports);
 for(size_t i=0;i<import_count;i++) {
  assert(!strcmp(List_GetName(&owner.theContext.imports),imports[i]));
  List_GotoNext(&owner.theContext.imports);
 }
 assert(load_imports(&owner)==S_OK && owner.theImportList.size==(int)import_count);
 assert(opened==(import_count?1u:0u) && closed==opened && parsed==opened && compiled==opened);
 if(import_count) {
  List_Reset(&owner.theImportList);ImportNode *node=List_Retrieve(&owner.theImportList);
  assert(node->numRefs==(int)import_count && importCache.size==1);
 }
 pp_context_destroy(&owner.theContext);
 Interpreter_ClearImports(&owner);
 assert(!owner.theImportList.size && !importCache.size && cleared==opened);
 ImportCache_Clear();pp_context_destroy(&owner.theContext);free(owned);
}
int main(void) {@CHECKS@ puts("early_script_imports=1");return 0;}
'''.replace('@CHECKS@', '\n'.join(checks)).replace('@IMPORT_LOOP@', import_loop).replace(
            '@CLEAR_IMPORTS@', clear_imports)
        pp, script = engine / 'source/preprocessorlib', engine / 'source/scriptlib'
        with tempfile.TemporaryDirectory(prefix='early-script-imports-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            # ImportCache only needs this public declaration from the engine
            # API; the real cache, records and list/preprocessor units execute.
            (work / 'openborscript.h').write_text('#include "List.h"\nextern List theFunctionList;\n')
            (work / 'packfile.h').write_text('extern char *packfile;\n'
                'int openpackfile(const char*,const char*);\nint readpackfile(int,void*,int);\n'
                'int seekpackfile(int,int,int);\nint closepackfile(int);\n')
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-fcommon', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-DPP_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                '-Wno-deprecated-declarations', '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast',
                '-I', str(work), '-I', str(pp), '-I', str(script), '-I', str(engine / 'source'),
                '-I', str(engine / 'source/gamelib'), '-I', str(ROOT / 'src/port/libretro'),
                str(unit), str(pp / 'pp_parser.c'), str(pp / 'pp_lexer.c'),
                str(script / 'Lexer.c'), str(script / 'List.c'), str(script / 'ImportCache.c'),
                *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_script_imports=1', run.stdout)
            actual = re.findall(r'(?m)^Script error: [^\n]*?, line \d+: (.*)$', run.stderr)
            self.assertEqual(actual, errors, run.stderr)
            self.assertNotIn('Script warning:', run.stderr)


if __name__ == '__main__':
    unittest.main()
