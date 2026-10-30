"""Match macro replacement, removal and emitted tokens to own-source contracts.

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


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-script-macros.json'


class EarlyScriptMacroTests(unittest.TestCase):
    def test_list_mutation_and_name_bucket_order(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-list-mutation.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        checks = []
        for row in rows:
            self.assertIn(row['first_duplicate'], (1, 2))
            self.assertIn(row['after_head_duplicate'], (3, 4))
            self.assertIs(type(row['removal_query_original_defined']), bool)
            checks.append('check(%d,%d,%d);' % (
                row['revision'], row['first_duplicate'], row['after_head_duplicate']))
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        script = engine / 'source/scriptlib'
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "List.h"
uint32_t obor_profile_build;
static int values[16];
static void lookup(List *list,const char *name,int expected) {
 Node *saved=list->current,*found=List_GetNodeByName(list,name);
 assert(list->current==saved);
 if((found?*(int*)found->value:0)!=expected)
  fprintf(stderr,"List lookup revision=%u name=%s expected=%d got=%d\n",
          obor_profile_build,name,expected,found?*(int*)found->value:0);
 assert((found?*(int*)found->value:0)==expected);
 assert(List_FindByName(list,name)==(expected!=0));
 assert(list->current==(found?found:saved));
}
static void check(unsigned revision,int first_duplicate,int after_head_duplicate) {
 obor_profile_build=revision;for(int i=0;i<16;++i)values[i]=i;
 List list;List_Init(&list);assert(!list.size&&!list.current&&!list.first&&!list.last);
 List_InsertAfter(&list,&values[1],"shared");Node *old=list.current;
 List_InsertBefore(&list,&values[2],"shared");Node *head=list.current;
 assert(list.first==head&&head->next==old&&old->prev==head);
 lookup(&list,"shared",first_duplicate);
 List_GotoLast(&list);List_InsertAfter(&list,&values[3],"shared");
 List_GotoFirst(&list);List_InsertAfter(&list,&values[4],"shared");
 /* Twelve entries in one bucket cross its original eight-entry capacity. */
 for(int i=5;i<=12;++i) {List_GotoLast(&list);List_InsertAfter(&list,&values[i],"shared");}
 assert(list.size==12);lookup(&list,"shared",first_duplicate);lookup(&list,"absent",0);
 /* For originals without a NULL-hole guard these post-removal queries are
    candidate stability controls only, as recorded separately per profile. */
 List_SetCurrent(&list,old);List_Remove(&list);assert(list.size==11);
 lookup(&list,"shared",2);
 List_SetCurrent(&list,head);List_Remove(&list);assert(list.size==10);
 lookup(&list,"shared",after_head_duplicate);
 while(list.size>1) {List_GotoFirst(&list);List_Remove(&list);}
 assert(list.size==1&&list.first==list.last&&list.current==list.first);
 lookup(&list,"shared",12);List_Remove(&list);
 assert(!list.size&&!list.current&&!list.first&&!list.last);lookup(&list,"shared",0);
 List_Clear(&list);List_Clear(&list);assert(!list.buckets);
 /* The same list is reusable; colliding distinct names remain distinct. */
 List_InsertAfter(&list,&values[1],NULL);
 List_InsertAfter(&list,&values[2],"ab");List_InsertAfter(&list,&values[3],"ba");
 List_InsertAfter(&list,&values[4],"");
 lookup(&list,"ab",2);lookup(&list,"ba",3);lookup(&list,"",4);lookup(&list,"missing",0);
 List_Clear(&list);assert(!list.size&&!list.buckets&&!list.current);
}
int main(void) {@CHECKS@ puts("early_list_mutation=1");return 0;}
'''.replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-list-mutation-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-DUNIT_TEST=1', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-Wno-deprecated-declarations', '-I', str(script),
                str(unit), str(script / 'List.c'), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_list_mutation=1', run.stdout)

    def test_definitions_and_script_tokens(self):
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
        checks = []
        warnings = 0
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['function_sha256']), {
                'pp_parser_define', 'pp_parser_parse_directive', 'pp_parser_insert_function_macro'})
            for digest in [row['source_sha256'], *row['function_sha256'].values()]:
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(set(row['cases']), set(fixture['cases']))
            for name, expected in row['cases'].items():
                self.assertEqual(set(expected), {'objects', 'functions', 'tokens', 'warnings'})
                self.assertTrue(all(type(expected[key]) is int and 0 <= expected[key] <= 2
                                    for key in ('objects', 'functions', 'warnings')))
                self.assertTrue(expected['tokens'] and all(
                    isinstance(token, str) and token and len(token) < 64 for token in expected['tokens']))
                tokens = '(const char *const[]){' + ','.join(
                    json.dumps(token) for token in expected['tokens']) + '}'
                checks.append('check(%d,%s,%s,%d,%d,%s,%d);' % (
                    row['revision'], json.dumps(name), json.dumps(fixture['cases'][name]),
                    expected['objects'], expected['functions'], tokens, len(expected['tokens'])))
                warnings += expected['warnings']
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pp_parser.h"
uint32_t obor_profile_build;
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line) {
 (void)condition;(void)function;(void)file;(void)line;if(!value)abort();
}
static void check(unsigned revision,const char *name,const char *source,
                  int objects,int functions,const char *const *tokens,size_t count) {
 pp_context context;pp_parser parser;TEXTPOS start={1,0};
 char *owned=strdup(source);assert(owned);obor_profile_build=revision;
 pp_context_init(&context);pp_parser_init(&parser,&context,name,owned,start);
 size_t emitted=0;int eof=0;
 for(unsigned budget=0;budget<512;budget++) {
  pp_token *token=pp_parser_emit_token(&parser);assert(token);
  if(token->theType==PP_TOKEN_EOF) {eof=1;break;}
  if(token->theType==PP_TOKEN_NEWLINE || token->theType==PP_TOKEN_WHITESPACE)continue;
  if(emitted>=count || strcmp(token->theSource,tokens[emitted])) {
   fprintf(stderr,"Macro tokens differ: revision=%u case=%s token=%zu got=%s\n",
           revision,name,emitted,token->theSource);abort();
  }
  emitted++;
 }
 assert(eof && emitted==count && !parser.child);
 assert(context.macros.size==objects && context.func_macros.size==functions);
 assert(!context.num_conditionals && !context.imports.size);
 pp_context_destroy(&context);pp_context_destroy(&context);free(owned);
}
int main(void) {@CHECKS@ puts("early_script_macros=1");return 0;}
'''.replace('@CHECKS@', '\n'.join(checks))
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        pp = engine / 'source/preprocessorlib'
        script = engine / 'source/scriptlib'
        with tempfile.TemporaryDirectory(prefix='early-script-macros-') as name:
            work = Path(name)
            unit = work / 'probe.c'
            binary = work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-fcommon', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-DPP_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                '-Wno-deprecated-declarations', '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast',
                '-I', str(pp), '-I', str(script), '-I', str(engine / 'source'),
                '-I', str(engine / 'source/gamelib'), '-I', str(ROOT / 'src/port/libretro'),
                str(unit), str(pp / 'pp_parser.c'), str(pp / 'pp_lexer.c'),
                str(script / 'List.c'), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_script_macros=1', run.stdout)
            messages = re.findall(r"(?m)^Script warning: [^\n]*: 'shared' redefined$", run.stderr)
            self.assertEqual(len(messages), warnings, run.stderr)
            self.assertNotIn('Script error:', run.stderr)


if __name__ == '__main__':
    unittest.main()
