"""Compare script callback entry and dispatch contracts with each own source.

Exact prepared copy/compile/helper and compiler entry-lookup bodies execute
with instrumented compilation, evaluation, variables and cleanup fixtures.
Linked interpreter/ownership and gameplay acceptance remain separate checks.
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

from historical_script_callbacks import entry_lookup, render_callbacks
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-script-callback-contracts.json'


def source_parts(engine):
    root = SOURCE / 'src/engines' / engine
    code = (root / 'openborscript.c').read_text()
    compiler = (root / 'source/scriptlib/Interpreter.c').read_text()
    return dict(copy=function(code, 'Script_Copy'),
                compile=function(code, 'Script_Compile'),
                init_helper=function(code, 'execute_init_method') if re.search(
                    r'(?m)^\s*(?:static\s+)?void\s+execute_init_method\(', code) else '',
                entries=entry_lookup(function(compiler, 'Interpreter_CompileInstructions')))


def program(parts, rows):
    first = rows[0]
    text = render_callbacks(parts, create_name=first['create_name'],
                            destroy_name=first['destroy_name'],
                            dispatch_init=first['dispatch_init'],
                            compile_resets=first['compile_resets'],
                            revision=first['revision'], labels=['prepared_source'])
    marker = 'int main(void) {'
    if text.count(marker) != 1:
        raise ValueError('Exactly one authored callback fixture main required')
    revisions = ','.join(str(row['revision']) for row in rows)
    # Selection is outside all extracted source bodies. One executable serves
    # only profiles with identical independently recorded expectations.
    return '#include <stdlib.h>\n' + text[:text.index(marker)] + '''
int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);int matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build) {++matched;lookup_checks();dispatch_checks();}
 assert(matched==1);return 0;
}
'''.replace('@REVISIONS@', revisions)


class ScriptCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(CONTRACT_PATH.read_text())['sources']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-script-callbacks-')
        cls.addClassCleanup(temporary.cleanup)
        cls.work = Path(temporary.name)
        cls.groups = {}
        for row in cls.rows:
            key = tuple(row[name] for name in ('engine', 'create_name', 'destroy_name',
                                              'dispatch_init', 'compile_resets'))
            cls.groups.setdefault(key, []).append(row)
        cls.executables = {}
        for index, (key, rows) in enumerate(cls.groups.items()):
            code = cls.work / ('contract-%d.c' % index)
            executable = code.with_suffix('')
            code.write_text(program(source_parts(key[0]), rows))
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-g',
                '-fsanitize=address,undefined,float-cast-overflow',
                str(code), '-o', str(executable)], check=True, timeout=60)
            cls.executables[key] = executable

    def test_registered_profiles_have_independent_source_contracts(self):
        revisions = [row['revision'] for row in self.rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertTrue({3761,3762,3766,3767,3807,3808} <= set(revisions))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] in ('3741', '3842'):
                revision = int(profile.get('revision', profile['build']))
                rows = [row for row in self.rows if row['revision'] == revision]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['engine'], profile['engine'])
        for row in self.rows:
            with self.subTest(revision=row['revision']):
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertIs(type(row['dispatch_init']), bool)
                self.assertIs(type(row['compile_resets']), bool)
                self.assertEqual(set(row['source_sha256']),
                                 {'copy', 'compile', 'init_helper', 'entries'})
                for name, digest in row['source_sha256'].items():
                    if name == 'init_helper' and not row['dispatch_init']:
                        self.assertIsNone(digest)
                    else:
                        self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_entry_names_copy_compile_and_current_script_per_source(self):
        for key, rows in self.groups.items():
            for row in rows:
                with self.subTest(revision=row['revision']):
                    subprocess.run([str(self.executables[key]), str(row['revision'])],
                                   check=True, timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
