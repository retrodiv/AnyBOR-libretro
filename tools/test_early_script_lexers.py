"""Match early script tokens and string bytes to their own source contracts.

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

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-script-lexers.json'


def byte_array(values):
    if not values or any(type(value) is not int or not 0 <= value <= 255 for value in values):
        raise ValueError('Explicit nonempty byte vector required')
    return '(const unsigned char[]){' + ','.join(str(value) for value in values) + '}'


class EarlyScriptLexerTests(unittest.TestCase):
    def test_unmapped_token_feedback(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-token-default.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for row in contract_profiles(fixture, profiles):
            revision = int(row.get('revision', row['build']))
            if row['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['default_error']), bool)
            checks.append('check(%d,%d);' % (row['revision'], row['default_error']))
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include "Lexer.h"
#undef printf
uint32_t obor_profile_build;
static char diagnostic[256];
static int messages;
static int capture_printf(const char *format,...) {
 va_list ap;va_start(ap,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);
 assert(n>=0 && (size_t)n<sizeof(diagnostic));++messages;return n;
}
#define printf capture_printf
@CONVERT@
#undef printf
static void check(unsigned revision,int default_error) {
 static const int input[]={PP_TOKEN_IDENTIFIER,PP_TOKEN_EOF,PP_TOKEN_ERROR,
                           PP_TOKEN_WHITESPACE,10000,10001};
 static const MY_TOKEN_TYPE mapped[]={TOKEN_IDENTIFIER,TOKEN_EOF,TOKEN_ERROR,TOKEN_ERROR};
 obor_profile_build=revision;
 for(unsigned i=0;i<sizeof(input)/sizeof(input[0]);++i) {
  pp_token raw;Token token;memset(&raw,0,sizeof(raw));memset(&token,0,sizeof(token));
  raw.theType=(PP_TOKEN_TYPE)input[i];raw.theTextPosition.row=17;raw.theTextPosition.col=3;
  raw.charOffset=29;strcpy(raw.theSource,"token_sample");token.theType=TOKEN_FLOAT;
  messages=0;diagnostic[0]=0;
  HRESULT result=Token_InitFromPreprocessor(&token,&raw);
  int error=i==2 || i==3 || (i>=4 && default_error);
  MY_TOKEN_TYPE wanted=i<4?mapped[i]:(default_error?TOKEN_ERROR:TOKEN_FLOAT);
  if(result!=(error?E_FAIL:S_OK) || token.theType!=wanted || messages!=(i>=4 && default_error)) {
   fprintf(stderr,"Token conversion mismatch revision=%u case=%u\n",revision,i);abort();
  }
  assert(token.theTextPosition.row==17 && token.theTextPosition.col==3 && token.charOffset==29);
  assert(!strcmp(token.theSource,raw.theSource));
  if(messages) {
   char expected[128];snprintf(expected,sizeof(expected),"Script error: unknown token type %d\n",input[i]);
   assert(!strcmp(diagnostic,expected));
  }
 }
}
int main(void) {@CHECKS@ puts("early_token_default=1");return 0;}
'''
        program = program.replace('@CONVERT@', function((engine / 'source/scriptlib/Lexer.c').read_text(),
                                                        'Token_InitFromPreprocessor'))
        program = program.replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-token-default-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-DPP_TEST=1', '-DSAFEALLOC_H=1',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-I', str(engine / 'source/preprocessorlib'), '-I', str(engine / 'source/scriptlib'),
                '-I', str(engine / 'source/gamelib'),
                '-I', str(engine / 'source'), '-I', str(ROOT / 'src/port/libretro'),
                str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=10, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_token_default=1', run.stdout)

    def test_own_source_tokens_and_string_bytes(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        low, high = fixture['range']
        self.assertEqual((min(revisions), max(revisions)), (low, high))
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        profiles = [row for row in profiles if row['engine'] == fixture['engine'] and
                    low <= int(row.get('revision', row['build'])) <= high]
        for row in contract_profiles(fixture, profiles):
            self.assertIn(int(row.get('revision', row['build'])), revisions)

        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for group, count in (('source_sha256', 4), ('function_sha256', 3)):
                self.assertEqual(len(row[group]), count)
                for digest in row[group].values():
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertIn(row['nbsp_token'], ('PP_TOKEN_ERROR', 'PP_TOKEN_WHITESPACE'))
            self.assertIn(row['escape_mode'], ('legacy', 'current'))
            self.assertIn(row['lookup_value'], (17, 29))
            checks.append('check_nbsp(%d,%s);' % (row['revision'], row['nbsp_token']))
            checks.append('check_lookup(%d,%d);' % (row['revision'], row['lookup_value']))
            for case in fixture['cases']:
                expected = case['expected'][row['escape_mode']]
                checks.append('check_string(%d,%s,%d,%s,%d);' % (
                    row['revision'], byte_array(case['input_bytes']), len(case['input_bytes']),
                    byte_array(expected), len(expected)))

        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Lexer.h"
#include "List.h"
/* This engine's internal conversion entry has no declaration in Lexer.h. */
HRESULT Token_InitFromPreprocessor(Token *,pp_token *);
uint32_t obor_profile_build;
void writeToLogFile(const char *format,...) {
 (void)format;assert(!"Unexpected lexer diagnostic for a source-reviewed input");
}
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line) {
 (void)condition;(void)function;(void)file;(void)line;if(!value)abort();
}
static void check_lookup(unsigned revision,int expected) {
 List list;static int existing=17,parameter=29;
 obor_profile_build=revision;List_Init(&list);
 List_InsertAfter(&list,&existing,"shared");
 List_Reset(&list);List_InsertBefore(&list,&parameter,"shared");
 assert(List_FindByName(&list,"shared"));
 if(*(int*)List_Retrieve(&list)!=expected) {
  fprintf(stderr,"Script name lookup mismatch at revision %u\n",revision);abort();
 }
 void *selected=List_Retrieve(&list);
 assert(!List_FindByName(&list,"SHARED") && List_Retrieve(&list)==selected);
 assert(!List_FindByName(&list,"absent") && List_Retrieve(&list)==selected);
 List_Clear(&list);
}
static void check_nbsp(unsigned revision,int expected_type) {
 char input[]={(char)0xa0,0};pp_lexer lexer;pp_token token;TEXTPOS start={1,0};
 obor_profile_build=revision;pp_lexer_Init(&lexer,input,start);
 assert(pp_lexer_GetNextToken(&lexer,&token)==S_OK);
 assert(token.theType==expected_type && token.charOffset==0);
 assert(token.theTextPosition.row==1 && token.theTextPosition.col==0);
 assert((unsigned char)token.theSource[0]==
        (expected_type==PP_TOKEN_WHITESPACE?' ':0xa0) && token.theSource[1]==0);
 assert(lexer.offset==1 && lexer.pcurChar==input+1);
 assert(pp_lexer_GetNextToken(&lexer,&token)==S_OK && token.theType==PP_TOKEN_EOF);
}
static void check_string(unsigned revision,const unsigned char *input,size_t input_size,
                         const unsigned char *expected,size_t expected_size) {
 char source[MAX_TOKEN_LENGTH]={0};pp_lexer lexer;pp_token raw;Token token;
 TEXTPOS start={3,7};
 assert(input_size<sizeof(source) && expected_size<=sizeof(token.theSource));
 memcpy(source,input,input_size);obor_profile_build=revision;
 pp_lexer_Init(&lexer,source,start);
 assert(pp_lexer_GetNextToken(&lexer,&raw)==S_OK && raw.theType==PP_TOKEN_STRING_LITERAL);
 memset(&token,0x5a,sizeof(token));
 assert(Token_InitFromPreprocessor(&token,&raw)==S_OK);
 if(token.theType!=TOKEN_STRING_LITERAL || memcmp(token.theSource,expected,expected_size)) {
  fprintf(stderr,"Script string mismatch at revision %u\n",revision);abort();
 }
 assert(token.charOffset==raw.charOffset && token.theTextPosition.row==3 &&
        token.theTextPosition.col==7);
}
int main(void) { CHECKS puts("early_script_lexers=1");return 0; }
'''.replace('CHECKS', '\n'.join(checks))
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        with tempfile.TemporaryDirectory(prefix='early-script-lexers-') as name:
            work = Path(name)
            source = work / 'probe.c'
            source.write_text(bind_named_allocation_support(program, engine))
            binary = work / 'probe'
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            command = shlex.split(os.environ.get('CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-fcommon', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-DPP_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                '-I', str(engine / 'source/preprocessorlib'),
                '-I', str(engine / 'source/scriptlib'), '-I', str(engine / 'source'),
                '-I', str(engine / 'source/gamelib'), '-I', str(ROOT / 'src/port/libretro'),
                str(source), str(engine / 'source/preprocessorlib/pp_lexer.c'),
                str(engine / 'source/scriptlib/Lexer.c'),
                str(engine / 'source/scriptlib/List.c'), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=10, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_script_lexers=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
