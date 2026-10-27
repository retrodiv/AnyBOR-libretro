"""Reject incomplete or oversized preprocessor strings without overreading.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from native_sanitizers import sanitizer_environment

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',ROOT))
ENGINES=('3400','3741','3842','4086','4432','6391','7142','7533','8023')

class PreprocessorStringTests(unittest.TestCase):
    def test_real_lexers_across_every_physical_engine(self):
        program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pp_lexer.h"
uint32_t obor_profile_build=OBOR_ENGINE_BUILD;
void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line) {
 (void)assertion;(void)func;(void)file;(void)line;if(!value)abort();
}
static void check(const char *source,int accepted) {
 pp_lexer lexer;pp_token token;TEXTPOS start={1,0};
 char *owned=malloc(strlen(source)+1);assert(owned);strcpy(owned,source);
 pp_lexer_Init(&lexer,owned,start);
 int result=pp_lexer_GetNextToken(&lexer,&token);
 assert((result>=0)==accepted);if(accepted)assert(token.theType==PP_TOKEN_STRING_LITERAL);
 free(owned);
}
int main(void) {
 check("\"\"",1);check("\"abc\"",1);check("\"a\\\"b\"",1);
 check("\"",0);check("\"abc",0);check("\"abc\\",0);
 check("\"abc\\\"",0);check("\"abc\n",0);
 char *s=malloc(MAX_TOKEN_LENGTH*2+4);assert(s);
 memset(s,'x',MAX_TOKEN_LENGTH*2+3);s[0]='"';s[MAX_TOKEN_LENGTH*2+2]='"';s[MAX_TOKEN_LENGTH*2+3]=0;
 /* The dynamic-string engine accepts a complete long literal by source view. */
 check(s,OBOR_ENGINE_BUILD==8023);
 s[MAX_TOKEN_LENGTH*2+2]=0;check(s,0);
 memset(s,'x',MAX_TOKEN_LENGTH);s[0]='"';s[MAX_TOKEN_LENGTH-2]='"';s[MAX_TOKEN_LENGTH-1]=0;check(s,1);
 free(s);puts("string_bounds=1 unterminated=1 trailing_escape=1 valid_escapes=1");return 0;
}
'''
        for engine in ENGINES:
            with self.subTest(engine=engine),tempfile.TemporaryDirectory(prefix='preprocessor-strings-') as name:
                work=Path(name);src=work/'test.c';src.write_text(program);binary=work/'test'
                e=SOURCE/'src/engines'/engine;pp=e/'source/preprocessorlib';script=e/'source/scriptlib'
                lexer=pp/'pp_lexer.c'
                if 'OBOR_TOLERANCE_DRAFT'in os.environ and engine!='8023':lexer=Path(os.environ['OBOR_TOLERANCE_DRAFT'])/'lexers'/engine/'pp_lexer.c'
                links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
                command=shlex.split(os.environ.get('CC','cc'))+['-std=gnu99','-O1','-g','-fcommon','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined','-fno-omit-frame-pointer','-DPP_TEST=1','-DSAFEALLOC_H=1',f'-DOBOR_ENGINE_BUILD={engine}','-Dstricmp=strcasecmp','-Dstrnicmp=strncasecmp','-I',str(pp),'-I',str(script),'-I',str(e/'source'),'-I',str(e/'source/gamelib'),'-I',str(SOURCE/'src/port/libretro'),str(src),str(lexer),*links,'-o',str(binary)]
                build=subprocess.run(command,text=True,capture_output=True,timeout=45);self.assertEqual(build.returncode,0,build.stdout+build.stderr)
                run=subprocess.run([str(binary)],text=True,capture_output=True,timeout=10,env=sanitizer_environment());self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                self.assertIn('string_bounds=1',run.stdout);print(engine,run.stdout.strip(),flush=True)

    def test_integer_suffixes_match_each_source_profile(self):
        fixture=json.loads((Path(__file__).parent /
            'fixtures/profile-preprocessor-numeric-contracts.json').read_text())
        revisions={row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions),len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        checks=[]
        for row in fixture['sources']:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
            for case in fixture['scenarios']:
                self.assertRegex(case['type'],r'^PP_TOKEN_(INT|HEX|FLOAT)CONSTANT$')
                first,rest=case['legacy' if row['legacy'] else 'modern']
                checks.append('check(%d,%s,%s,%s,%s);' % (
                    row['revision'],json.dumps(case['input']),case['type'],
                    json.dumps(first),json.dumps(rest)))
        program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pp_lexer.h"
uint32_t obor_profile_build;
void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line) {
 (void)assertion;(void)func;(void)file;(void)line;if(!value)abort();
}
static void check(unsigned revision,const char *input,int type,const char *first,const char *rest) {
 obor_profile_build=revision;pp_lexer lexer;pp_token token;TEXTPOS start={1,0};
 char *source=strdup(input);assert(source);pp_lexer_Init(&lexer,source,start);
 assert(pp_lexer_GetNextToken(&lexer,&token)>=0);
 if(token.theType!=type || strcmp(token.theSource,first)) {
  fprintf(stderr,"Numeric lexer revision=%u input=%s expected=%s got=%s\n",revision,input,first,token.theSource);abort();
 }
 assert(pp_lexer_GetNextToken(&lexer,&token)>=0);
 if(rest[0]) {
  assert(token.theType==PP_TOKEN_IDENTIFIER && !strcmp(token.theSource,rest));
  assert(pp_lexer_GetNextToken(&lexer,&token)>=0);
 }
 assert(token.theType==PP_TOKEN_EOF);free(source);
}
int main(void) { CHECKS return 0; }
'''.replace('CHECKS','\n'.join(checks))
        engine=SOURCE/'src/engines/3842';pp=engine/'source/preprocessorlib';script=engine/'source/scriptlib'
        with tempfile.TemporaryDirectory(prefix='preprocessor-numeric-') as name:
            work=Path(name);probe=work/'probe.c';probe.write_text(program);binary=work/'probe'
            links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
            command=shlex.split(os.environ.get('CC','cc'))+[
                '-std=gnu99','-O1','-g','-fcommon','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DPP_TEST=1',
                '-DSAFEALLOC_H=1','-Dstricmp=strcasecmp','-Dstrnicmp=strncasecmp',
                '-I',str(pp),'-I',str(script),'-I',str(engine/'source'),
                '-I',str(engine/'source/gamelib'),'-I',str(SOURCE/'src/port/libretro'),
                str(probe),str(pp/'pp_lexer.c'),*links,'-o',str(binary)]
            subprocess.run(command,check=True,timeout=45)
            subprocess.run([str(binary)],check=True,timeout=10,env=sanitizer_environment())

if __name__=='__main__':unittest.main()
