"""Check historical clear entry/lifecycle through the native parser and VM.

Authored scripts use a bounded native callback registry. File/import services
refuse access. The game kill-all caller is tested on its declared entity pool;
whole game execution and external resources remain separate.
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
from native_allocation_policy import bind_named_allocation_support
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-script-clear.json'


class EarlyScriptClearTests(unittest.TestCase):
    def test_registry_and_source_controls(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_compacted_entry_callback_values_and_entity_cleanup(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        port = Path(os.environ.get('OBOR_EARLY_SCRIPT_PORT', ROOT / 'src/port/libretro'))
        script = (engine / 'openborscript.c').read_text()
        core = (engine / 'openbor.c').read_text()
        compiler_body = function((engine / 'source/scriptlib/Interpreter.c').read_text(),
                                 'Interpreter_CompileInstructions')
        failure = compiler_body.index('if(FAILED(hr)){')
        first = compiler_body.index('\t\t\tpinterpreter->mainEntryIndex = -1;', failure)
        last = compiler_body.index('\t\t\tbreak;', first)
        failure_entries = compiler_body[first:last]
        first = compiler_body.index('if(pinterpreter->mainEntryIndex >= 0)')
        last = compiler_body.index('// convert theJumpTargetIndex', first)
        resolve_entries = compiler_body[first:last]
        functions = ['obor_script_destroy_interpreter', 'obor_script_replace_interpreter',
                     'obor_script_share_references', 'alloc_script', 'Script_Init', 'Script_Copy',
                     'Script_Clear', 'Script_AppendText', '_set_var', 'Script_Get_Local_Variant',
                     'Script_Set_Local_Variant', 'Script_Local_Clear', 'system_getlocalvar']
        # Fresh script storage must not enter the core stop path in this VM test.
        bodies = 'void borExit(int reset){(void)reset;abort();}\n'
        bodies += '\n'.join(function(script, name) for name in functions)
        bodies += '\n' + '\n'.join(function(core, name) for name in
                                  ('alloc_all_scripts', 'clear_all_scripts', 'free_all_scripts', 'kill_all'))
        code = (FIXTURE.parent / 'early_script_clear.c').read_text()
        checks = '\n'.join('check(%d,%d,%d,%d);' % (r['revision'], r['clear_entry'], r['kill_clear'], r['local_retention'])
                           for r in fixture['sources'])
        code = code.replace('@BODIES@', bodies).replace('@CHECKS@', checks)
        code = code.replace('@FAILURE_ENTRIES@', failure_entries).replace('@RESOLVE_ENTRIES@', resolve_entries)
        code = bind_named_allocation_support(code, engine)
        with tempfile.TemporaryDirectory(prefix='early-script-clear-') as directory:
            work = Path(directory)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(code)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            includes = [engine, engine / 'source', port, ROOT / 'src/glue',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            flags = ['-std=gnu11', '-O1', '-g', '-fcommon', '-fsigned-char', '-fgnu89-inline',
                     '-ffunction-sections', '-fdata-sections', '-DSAFEALLOC_H=1', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD=' + fixture['engine'],
                     '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                     '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer',
                     *['-I' + str(p) for p in includes]]
            units = ['scriptlib/' + name + '.c' for name in
                     ('Interpreter', 'Instruction', 'Parser', 'ParserSet', 'Lexer', 'List',
                      'ScriptVariant', 'Stack', 'SymbolTable', 'StackedSymbolTable')]
            units += ['preprocessorlib/pp_parser.c', 'preprocessorlib/pp_lexer.c']
            objects = []
            for i, name in enumerate(units):
                obj = work / ('unit-%d.o' % i)
                compile_checked(compiler + flags + ['-Wno-deprecated-declarations',
                    '-c', str(engine / 'source' / name), '-o', str(obj)])
                objects.append(str(obj))
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            warnings = ['-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                        '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function']
            if sys.platform == 'darwin':
                warnings.append('-Wno-error=pragma-pack')
            compile_checked(compiler + flags + warnings +
                [str(source), *objects, *links, '-lm', '-o', str(binary)])
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=45,
                                    env=sanitizer_environment())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('early_script_clear=1', result.stdout)


if __name__ == '__main__':
    unittest.main()
