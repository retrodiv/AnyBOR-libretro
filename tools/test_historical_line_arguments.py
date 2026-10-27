"""Check source-defined line parser contracts in each historical profile.

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

from native_sanitizers import sanitizer_environment
from historical_findarg import render_findarg
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-line-argument-contracts.json'

ARGUMENT_PROGRAM = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stddef.h>
static uint32_t obor_profile_build;
CONSTANTS
RECORD
PARSER
static void check(const char *input,size_t expected) {
    ArgList list={0};char output[MAX_ARG_LEN+1];
    memset(output,0x5a,sizeof(output));
    assert(ParseArgs(&list,(char*)input,output)==expected && list.count==expected);
    for(size_t i=0;i<list.count;++i) {
        assert(list.args[i]>=output && list.args[i]<output+sizeof(output));
        assert(list.arglen[i]==strlen(list.args[i]));
    }
}
int main(void) {
    const size_t lengths[]={0,1,17,18,19,31,32,63,64,65,70};
    /* Covers every requested and existing profile, plus both immediate sides
       of the boundary; it does not register or select a new profile. */
    const struct {uint32_t revision;size_t argument_limit,line_capacity;} contracts[]={CONTRACTS};
    for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
        uint32_t profile=contracts[i].revision;
        obor_profile_build=profile;
        size_t limit=contracts[i].argument_limit;
        for(size_t k=0;k<sizeof(lengths)/sizeof(*lengths);++k) {
            char input[512]={0};size_t n=lengths[k];
            for(size_t i=0;i<n;++i) {input[2*i]='x';input[2*i+1]=' ';}
            input[2*n]='\n';
            check(input,n<limit?n:limit);
        }
        check("\"first second\" third\n",3);
        check("first\\ second\tthird#ignored fourth\n",3);
        check("  \t #comment\n",0);
        check("first\r\nsecond",1);
        check("first second",2);
        char input[514];memset(input,'x',sizeof(input));
        input[509]='\n';input[510]=0;check(input,1);
        input[509]='x';input[510]='\n';input[511]=0;check(input,contracts[i].line_capacity==512?1:0);
        input[510]='x';input[511]='\n';input[512]=0;check(input,0);
    }
}
'''

FINDER_PROGRAM = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <ctype.h>
typedef long LONG;
static uint32_t obor_profile_build;
static int stricmp(const char *a,const char *b) {
    while(*a && tolower((unsigned char)*a)==tolower((unsigned char)*b)) {++a;++b;}
    return tolower((unsigned char)*a)-tolower((unsigned char)*b);
}
MAXIMUM
FINDARG
static long script_constant(const char *constname) {
    struct {long lVal;} v={-1};
    if(0) {}
    CONSTANT
    return v.lVal;
}
int main(void) {
    const struct {uint32_t revision;size_t argument_limit,line_capacity;} contracts[]={CONTRACTS};
    for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
        uint32_t profile=contracts[i].revision;
        obor_profile_build=profile;
        const size_t expected=contracts[i].line_capacity;
        assert(script_constant("MAX_ARG_LEN")== (long)expected);
        assert(script_constant("max_arg_len")== (long)expected);
        char input[514];memset(input,'x',sizeof(input));input[513]=0;
        char *value=findarg(input,0);
        assert(strlen(value)==expected-1);
        for(size_t i=0;i<expected-1;++i) assert(value[i]=='x');
        assert(!strcmp(findarg("first second\n",1),"second"));
        assert(!strcmp(findarg("\"first second\" third\n",1),"second\""));
    }
}
'''

def native(program):
    with tempfile.TemporaryDirectory(prefix='anybor-line-parser-') as directory:
        source = Path(directory) / 'probe.c'
        executable = source.with_suffix('')
        source.write_text(program)
        subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
            '-std=c11', '-Wall', '-Wextra', '-Werror',
            '-Wno-error=deprecated-declarations', '-Wno-error=implicit-fallthrough',
            '-g', '-fsanitize=address,undefined,pointer-overflow', str(source), '-o', str(executable)],
            check=True, timeout=60)
        subprocess.run([str(executable)], check=True, timeout=20,
                       env=sanitizer_environment())


def contracts(rows):
    return ','.join('{%du,%du,%du}' % (row['revision'], row['argument_limit'],
                                      row['line_capacity']) for row in rows)


class LineArgumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(CONTRACT_PATH.read_text())['sources']
        cls.groups = {}
        for row in cls.rows:
            cls.groups.setdefault(row['engine'], []).append(row)

    def test_profiles_have_own_sources_and_boundary_controls(self):
        by_revision = {row['revision']:row for row in self.rows}
        self.assertEqual(len(by_revision), len(self.rows))
        self.assertTrue({3669,3670,3818,3822} <= set(by_revision))
        self.assertEqual(by_revision[3669]['argument_limit'],18)
        self.assertEqual(by_revision[3670]['argument_limit'],64)
        self.assertEqual(by_revision[3818]['line_capacity'],512)
        self.assertEqual(by_revision[3822]['line_capacity'],511)
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] in self.groups:
                row = by_revision[int(profile.get('revision',profile['build']))]
                self.assertEqual(row['engine'],profile['engine'])
        for row in self.rows:
            with self.subTest(revision=row['revision']):
                self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
                self.assertIn(row['argument_limit'],(18,64))
                self.assertIn(row['line_capacity'],(511,512))
                self.assertTrue({'line-arguments','findarg','argument-list',
                                 'line-capacity','line-constant-mapping'} <=
                                set(row['source_sha256']))
                for value in row['source_sha256'].values():
                    self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_argument_counts_tokens_and_long_lines(self):
        for engine, rows in self.groups.items():
            with self.subTest(engine=engine):
                root = SOURCE / 'src/engines' / engine
                code = (root / 'openbor.c').read_text()
                header = (root / 'openbor.h').read_text()
                record = re.search(r'typedef\s+struct\s+ArgList\s*\{[\s\S]*?\}\s*ArgList\s*;',header)
                self.assertIsNotNone(record)
                constants = '\n'.join(re.findall(
                    r'^#define[ \t]+MAX_ARG_(?:LEN|COUNT)[^\r\n]*',header,re.M))
                native(ARGUMENT_PROGRAM.replace('CONSTANTS',constants)
                    .replace('RECORD',record[0]).replace('PARSER',function(code,'ParseArgs'))
                    .replace('CONTRACTS',contracts(rows)))

    def test_findarg_capacity_and_native_script_constant(self):
        for engine, rows in self.groups.items():
            with self.subTest(engine=engine):
                root = SOURCE / 'src/engines' / engine
                code = (root / 'openbor.c').read_text()
                header = (root / 'openbor.h').read_text()
                script = (root / 'openborscript.c').read_text()
                constant = re.search(r'else if\(stricmp\(constname, "MAX_ARG_LEN"\)==0\)\s*\{[^{}]*\}',script)
                if constant is None:
                    constant = re.search(r'^[ \t]*ICMPCONST\(MAX_ARG_LEN\)[^\r\n]*',script,re.M)
                self.assertIsNotNone(constant)
                maximum = re.search(r'^#define[ \t]+MAX_ARG_LEN[^\r\n]*',header,re.M)
                self.assertIsNotNone(maximum)
                macro = '#define ICMPCONST(x) else if(stricmp(constname,#x)==0){v.lVal=x;}\n'
                native(FINDER_PROGRAM.replace('MAXIMUM',maximum[0]+'\n'+macro)
                    .replace('FINDARG',function(code,'findarg')).replace('CONSTANT',constant[0])
                    .replace('CONTRACTS',contracts(rows)))

    def test_findarg_comments_signed_indices_and_retained_bytes_per_profile(self):
        fixture=json.loads((CONTRACT_PATH.parent/'findarg-contracts.json').read_text())
        groups={}
        for row in fixture['sources']:
            groups.setdefault((row['engine'],row['comment_prefix']),[]).append(row['revision'])
        for (engine,prefix),revisions in groups.items():
            with self.subTest(engine=engine,comment_prefix=prefix):
                root=SOURCE/'src/engines'/engine
                header=(root/'openbor.h').read_text()
                capacity=int(re.search(r'^#define\s+MAX_ARG_LEN\s+(\d+)',header,re.M)[1])
                native(render_findarg(revisions=sorted(revisions),
                    parser=function((root/'openbor.c').read_text(),'findarg'),capacity=capacity,
                    cases=fixture['cases']['prefix'if prefix else'whole_suffix']))

    def test_findarg_own_sources_cover_registered_profiles_and_both_boundary_sides(self):
        fixture=json.loads((CONTRACT_PATH.parent/'findarg-contracts.json').read_text())
        rows={r['revision']:r for r in fixture['sources']}
        self.assertEqual(len(rows),len(fixture['sources']))
        self.assertTrue(rows[3830]['comment_prefix']);self.assertFalse(rows[3831]['comment_prefix'])
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine']in {'3400','3741','3842'}:
                self.assertEqual(rows[int(profile.get('revision',profile['build']))]['engine'],profile['engine'])
        for row in rows.values():
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['parser_sha256'],r'^[0-9a-f]{64}$')
            self.assertIn(row['capacity'],[511,512]);self.assertIs(type(row['comment_prefix']),bool)


if __name__ == '__main__':
    unittest.main()
