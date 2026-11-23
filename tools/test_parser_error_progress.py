"""Terminal script errors return control; finite historical recovery is retained.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class ParserErrorProgressTests(unittest.TestCase):
    def test_terminal_errors_and_finite_recovery_in_every_family(self):
        for engine in json.loads((ROOT / 'src/pin.json').read_text())['engines']:
            build = engine['build']
            source = (ROOT / 'src/engines' / build / 'source/scriptlib/Parser.c').read_text()
            name = 'Parser_Error' if build in ('3400', '3741') else 'Parser_Error2'
            body = function(source, name)
            program = r'''
#include <assert.h>
#include <stdio.h>
#include <setjmp.h>
#include <string.h>
#define LIBRETRO 1
#define TRUE 1
#define TOKEN_EOF 0
#define FAILED(x) ((x)<0)
typedef unsigned PRODUCTION;
static const PRODUCTION error=99;
typedef struct {unsigned long row,col;} Position;
typedef struct {int theType;char theSource[32];Position theTextPosition;} Token;
typedef struct {int preprocessor;} Lexer;
typedef struct {Lexer theLexer;Token theNextToken;char currentPath[64];int errorFound,theParserSet;} Parser;
static int calls,mode,errors;
static unsigned obor_profile_build;
static unsigned obor_parser_production_number(unsigned p) {return p;}
static jmp_buf escape;
static const char *_production_error_message(Parser *p,PRODUCTION o) {(void)p;(void)o;return "syntax";}
static int pp_error(void *p,const char *s,...) {(void)p;(void)s;errors++;return -1;}
static int Lexer_GetNextToken(Lexer *l,Token *t) {
 (void)l;assert(++calls<=3);
 t->theType=mode==1?TOKEN_EOF:(calls==1?1:2);
 if(mode==2)return -1;
 return 0;
}
static int ParserSet_Follow(void *p,PRODUCTION o,int t) {(void)p;(void)o;return t==2;}
static void obor_content_error(const char *path,unsigned long row,unsigned long col,const char *reason) {
 assert(!strcmp(path,"data/scripts/authored.c"));(void)row;(void)col;assert(reason&&*reason);longjmp(escape,1);
}
@FUNCTION@
static void invoke(Parser *p) {@CALL@;}
static void check(void) {
 static Parser p;memset(&p,0,sizeof(p));calls=mode=errors=0;strcpy(p.currentPath,"data/scripts/authored.c");
 mode=1;if(!setjmp(escape)) {invoke(&p);assert(!"EOF must stop the session");}
 assert(p.errorFound&&calls==1&&errors==1);
 calls=errors=0;mode=2;invoke(&p);assert(p.errorFound&&calls==1&&p.theNextToken.theType==TOKEN_EOF);
 calls=errors=0;mode=0;invoke(&p);assert(calls==@RECOVERY@&&errors==1&&p.errorFound);
}
int main(void) {unsigned profiles[]={@PROFILES@};for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);i++){obor_profile_build=profiles[i];check();} puts("terminal_and_recovery=1");return 0;}
'''
            call = name + '(p,1' + (',"production"' if name.endswith('2') else '') + ')'
            program = program.replace('@FUNCTION@', body).replace('@CALL@', call)
            profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
            revisions = {int(p.get('revision', p['build'].split('-')[0])) for p in profiles
                         if p['engine'] == build}
            if build == '3842':
                revisions.update((3809, 3810))
            program = program.replace('@PROFILES@', ','.join(map(str, sorted(revisions))))
            recovery = {'3400': '1', '3741': '1', '3842': '(obor_profile_build < 3810u ? 1 : 2)'}
            program = program.replace('@RECOVERY@', recovery.get(build, '2'))
            with self.subTest(engine=build), tempfile.TemporaryDirectory(prefix='parser-error-') as directory:
                unit, exe = Path(directory) / 'probe.c', Path(directory) / 'probe'
                unit.write_text(program)
                result = subprocess.run(['cc', '-std=gnu99', '-O1', '-Wall', '-Wextra',
                                         str(unit), '-o', str(exe)], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('terminal_and_recovery=1', result.stdout)


    def test_preprocessing_failure_and_nesting_are_terminal(self):
        for engine in json.loads((ROOT / 'src/pin.json').read_text())['engines']:
            build = engine['build']
            tree = ROOT / 'src/engines' / build
            lexer = function((tree / 'source/scriptlib/Lexer.c').read_text(), 'Lexer_GetNextToken')
            alloc = function((tree / 'source/preprocessorlib/pp_parser.c').read_text(), 'pp_parser_alloc')
            code = r'''#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <setjmp.h>
#define LIBRETRO 1
#define TOKEN_EOF 0
#define PP_TOKEN_EOF 0
#define PP_TOKEN_WHITESPACE 1
#define PP_TOKEN_NEWLINE 2
#define S_OK 0
#define E_FAIL -1
typedef int HRESULT, pp_parser_type;
typedef struct {unsigned long row,col;} TEXTPOS;
typedef struct {int theType;} Token,pp_token;
typedef struct {TEXTPOS theTokenPosition;char *pcurChar;} RawLexer;
typedef struct {struct pp_parser *discarded_parsers;} Context;
typedef struct pp_parser {const char *filename;RawLexer lexer;Context *ctx;int type;struct pp_parser *parent,*child,*discarded_next;} pp_parser;
typedef struct {pp_parser preprocessor;TEXTPOS theTokenPosition;char *pcurChar;} Lexer;
static jmp_buf escape;
static int mode,calls;
static pp_token raw;
static pp_token *pp_parser_emit_token(pp_parser *p) {(void)p;++calls;raw.theType=calls==1?PP_TOKEN_WHITESPACE:9;return mode?&raw:NULL;}
static int Token_InitFromPreprocessor(Token *t,pp_token *p) {t->theType=p->theType;return S_OK;}
static void pp_parser_init(pp_parser *p,Context *ctx,const char *name,char *source,TEXTPOS pos) {(void)source;(void)pos;p->ctx=ctx;p->filename=name;}
static void *obor_profile_malloc_named(const char *name,size_t n) {(void)name;return calloc(1,n);}
static void obor_content_error(const char *path,unsigned long row,unsigned long col,const char *reason) {(void)row;(void)col;assert(path&&reason);longjmp(escape,1);}
@LEXER@
@ALLOC@
int main(void) {
 Lexer l={0};Token t={0};l.preprocessor.filename="data/scripts/authored.c";
 if(!setjmp(escape)) {Lexer_GetNextToken(&l,&t);assert(!"failed preprocessing must stop");}
 assert(calls==1);
 mode=1;calls=0;assert(Lexer_GetNextToken(&l,&t)==S_OK&&calls==2&&t.theType==9);
 pp_parser chain[128]={0};for(unsigned i=1;i<128;++i)chain[i].parent=&chain[i-1];
 pp_parser *p=pp_parser_alloc(&chain[126],"file",NULL,0);assert(p&&p->parent==&chain[126]);free(p);
 if(!setjmp(escape)) {pp_parser_alloc(&chain[127],"file",NULL,0);assert(!"nesting must stop");}
 puts("preprocessor_terminal=1");return 0;
}
'''
            code = code.replace('@LEXER@', lexer).replace('@ALLOC@', alloc)
            with self.subTest(engine=build), tempfile.TemporaryDirectory(prefix='preprocessor-error-') as directory:
                unit, exe = Path(directory) / 'probe.c', Path(directory) / 'probe'
                unit.write_text(code)
                result = subprocess.run(['cc', '-std=gnu99', '-O1', str(unit), '-o', str(exe)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('preprocessor_terminal=1', result.stdout)



    def test_active_import_cycle_limit_and_first_reason(self):
        source = Path(os.environ.get('OBOR_CONTENT_ERROR_PORT', ROOT / 'src/port/libretro/libretroport.c')).read_text()
        # This shared implementation is used by every prefixed engine.
        names = ('obor_content_error', 'obor_content_import_begin', 'obor_content_import_end')
        code = r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
static char engine_content_message[512];
static const char *engine_content_imports[128];
static unsigned engine_content_import_depth,obor_profile_build=3482;
static jmp_buf escape;
static void borExit(int code) {assert(code==1);longjmp(escape,1);}
@FUNCTIONS@
int main(void) {
 obor_content_import_begin("one");obor_content_import_begin("two");obor_content_import_end();
 if(!setjmp(escape)) {obor_content_import_begin("one");assert(!"cycle must stop");}
 assert(strstr(engine_content_message,"Cyclic script import: one"));
 char first[512];strcpy(first,engine_content_message);
 if(!setjmp(escape)) obor_content_error("later",2,3,"Secondary failure");
 assert(!strcmp(first,engine_content_message));
 engine_content_message[0]=0;engine_content_import_depth=0;
 char paths[129][16];
 for(unsigned i=0;i<128;i++) {snprintf(paths[i],16,"path%u",i);obor_content_import_begin(paths[i]);}
 if(!setjmp(escape)) {obor_content_import_begin("overflow");assert(!"limit must stop");}
 assert(strstr(engine_content_message,"nesting limit"));
 for(unsigned i=0;i<128;i++)obor_content_import_end();
 assert(engine_content_import_depth==0);obor_content_import_begin("one");obor_content_import_end();
 puts("imports_bounded=1");return 0;
}
'''.replace('@FUNCTIONS@', '\n'.join(function(source, name) for name in names))
        with tempfile.TemporaryDirectory(prefix='import-error-') as directory:
            unit, exe = Path(directory) / 'probe.c', Path(directory) / 'probe'
            unit.write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-O1', str(unit), '-o', str(exe)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('imports_bounded=1', result.stdout)


if __name__ == '__main__':
    unittest.main()
