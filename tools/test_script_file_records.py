"""Keep script save fields, traversal and capacity within each profile's contract.

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
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-script-file-records.json'


class ScriptFileRecordsTests(unittest.TestCase):
    def fixture(self):
        return load_contract_fixture(FIXTURE)

    def paths(self):
        fixture = self.fixture()
        return (Path(os.environ.get('OBOR_SCRIPT_RECORD_ENGINE',
                                    ROOT / 'src/engines' / fixture['engine'])),
                Path(os.environ.get('OBOR_SCRIPT_RECORD_PORT', ROOT / 'src/port/libretro')))

    def program(self):
        fixture = self.fixture()
        engine, unused = self.paths()
        source = (engine / 'openbor.c').read_text()
        self.assertIn('#include "obor_script_file32.inc"', source)
        for name, call in [('saveScriptFile', 'obor_script_file32_write'),
                           ('loadScriptFile', 'obor_script_file32_read')]:
            body = function(source, name)
            self.assertIn(call + '(handle, obor_script32_target_variant_size())', body)
            self.assertIn('fclose(handle)', body)
            self.assertNotIn('sizeof(s_variantnode)', body)
            self.assertNotIn('sizeof(ScriptVariant)', body)
        variant = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
        script = (engine / 'openborscript.h').read_text()
        enum = re.search(r'typedef enum VariantType\s*\{[^{}]*\}\s*VARTYPE;', variant)
        value = re.search(r'typedef struct ScriptVariant\s*\{[\s\S]*?\}\s*ScriptVariant;', variant)
        node = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_variantnode;', script)
        self.assertIsNotNone(enum)
        self.assertIsNotNone(value)
        self.assertIsNotNone(node)
        self.assertRegex(node.group(), r'char\s*\*\s*key\s*;')
        rows = fixture['contexts']
        self.assertTrue(rows)
        self.assertEqual(len(rows), len({row['revision'] for row in rows}))
        self.assertTrue(any(row['indexed_extra_slot'] for row in rows))
        self.assertTrue(any(not row['indexed_extra_slot'] for row in rows))
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertIs(type(row['revision']), int)
            self.assertGreater(row['revision'], 0)
            self.assertLessEqual(row['revision'], 0xFFFFFFFF)
            self.assertIs(type(row['indexed_extra_slot']), bool)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            entries.append('{%d,%d}' % (row['revision'], row['indexed_extra_slot']))
        definitions = ('static const struct { uint32_t revision; int extra_slot; } contexts[] = {' +
                       ','.join(entries) + '};')
        program = Path(__file__).with_name('script_file_record_io.c.in').read_text()
        for marker, text in [('@VARIANT@', enum.group() + '\n' + value.group()),
                             ('@NODE@', node.group()), ('@CONTEXTS@', definitions)]:
            self.assertEqual(program.count(marker), 1)
            program = program.replace(marker, text)
        return program

    def run_probe(self, program):
        unused, port = self.paths()
        with tempfile.TemporaryDirectory(prefix='script-file-records-') as directory:
            work = Path(directory)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(program)
            compiler = os.environ.get('HOST_CC', os.environ.get('CC', 'cc'))
            command = [*shlex.split(compiler), '-std=c99', '-Wall', '-Wextra', '-Werror',
                       '-Wno-deprecated-declarations', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
            if sys.platform.startswith('linux'):
                command.append('-no-pie')
            command += ['-I', str(port), str(source), '-o', str(binary)]
            built = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True,
                                  timeout=30, env=sanitizer_environment())

    def test_profile_registry_coverage(self):
        fixture = self.fixture()
        rows = fixture['contexts']
        revisions = {row['revision'] for row in rows}
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_native_file_traversal_values_and_refusals(self):
        run = self.run_probe(self.program())
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('PASS explicit script records:', run.stdout)

    def test_indexed_capacity_boundary_rejects_a_regression(self):
        if os.name != 'posix':
            self.skipTest('Native assertion control requires POSIX core-dump limits')
        import resource
        program = self.program()
        unused, port = self.paths()
        helper = (port / 'obor_script_file32.inc').read_text()
        expression = r'\(obor_profile_build >= [0-9]+\)'
        self.assertEqual(len(re.findall(expression, helper)), 1)
        mutated = re.sub(expression, '1', helper)
        program = program.replace('#include "obor_script_file32.inc"', mutated)
        before = resource.getrlimit(resource.RLIMIT_CORE)
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, before[1]))
            run = self.run_probe(program)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, before)
        self.assertLess(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('obor_script_file32_write', run.stderr)


if __name__ == '__main__':
    unittest.main()
