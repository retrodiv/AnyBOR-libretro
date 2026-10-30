"""Check each selected profile against its own original palette contract.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PUBLIC = (HERE.parent / 'src/pin.json').is_file()
if PUBLIC:
    DEFAULT_SOURCE = HERE.parent
    FIXTURE = HERE / 'fixtures/profile-palette-contracts.json'
else:
    sys.path.insert(0, str(HERE.parent))
    sys.path.insert(0, str(HERE.parent / 'templates/public/tools'))
    DEFAULT_SOURCE = HERE.parents[2] / 'AnyBOR-libretro'
    FIXTURE = HERE / 'fixtures/profile-palette-contracts.json'
from palette_probe import program
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from contract_fixtures import load_contract_fixture, contract_profiles

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', DEFAULT_SOURCE))
CONTRACT_FIXTURE = load_contract_fixture(FIXTURE)
CONTRACTS = CONTRACT_FIXTURE['profiles']


class ProfilePaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform == 'linux':
            from run_guarded import require_limits
            require_limits()
        cls.temporary = tempfile.TemporaryDirectory(prefix='anybor-profile-palettes-')
        cls.work = Path(cls.temporary.name)
        cls.executables = {}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_profile_registry_is_complete(self):
        profiles = json.loads((SOURCE / 'src/pin.json').read_text())['profiles']
        self.assertEqual([(p['build'], p['engine'], int(p.get('revision', p['build'])))
                          for p in contract_profiles(CONTRACT_FIXTURE, profiles)],
                         [(p['profile'], p['engine'], int(p.get('revision', p['profile'])))
                          for p in CONTRACTS])
        for contract in CONTRACTS:
            self.assertGreaterEqual(len(contract['cases']), 6, contract['profile'])

    @classmethod
    def executable(cls, contract):
        engine = SOURCE / 'src/engines' / contract['engine']
        harness = program((engine / 'source/gamelib/loadimg.c').read_text(),
                          (engine / 'openbor.c').read_text())
        harness = bind_named_allocation_support(harness, engine)
        digest = hashlib.sha256(harness.encode()).hexdigest()
        if digest not in cls.executables:
            source = cls.work / (digest + '.c')
            source.write_text(harness)
            executable = cls.work / digest
            flags = ['-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-parameter',
                     '-Wno-unused-but-set-variable', '-Wno-sign-compare',
                     '-Wno-deprecated-declarations']
            if sys.platform == 'linux':
                # Keep older host ASan runtimes away from randomized PIE mappings.
                # The source and all sanitizer instrumentation stay unchanged.
                flags += ['-fno-pie', '-no-pie']
            if sys.platform in ('linux', 'darwin'):
                flags.append('-fsanitize=address,undefined')
            compiler = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
            subprocess.run([*compiler, *flags, str(source), '-o', str(executable)],
                           check=True, timeout=60)
            cls.executables[digest] = executable
        return cls.executables[digest]


def profile_test(contract):
    def check(self):
        executable = self.executable(contract)
        revision = int(contract.get('revision', contract['profile']))
        for expected in contract['cases']:
            with self.subTest(palette_bytes=expected['bytes'], filename=expected['filename'],
                              authored_byte65=expected['authored_byte65']):
                completed = subprocess.run([str(executable), str(revision), str(expected['bytes']),
                                            expected['filename'], str(expected['authored_byte65'])],
                                           capture_output=True, text=True, timeout=10,
                                           env=sanitizer_environment())
                self.assertEqual(completed.returncode, 0, completed.stderr)
                actual = json.loads(completed.stdout.strip().splitlines()[-1])
                self.assertEqual(actual['profile'], revision)
                self.assertEqual(actual['loaded'], expected['loaded'], contract['model_reference'])
                self.assertEqual(hashlib.sha256(bytes.fromhex(actual['palette'])).hexdigest(),
                                 expected['palette_sha256'], contract['model_reference'])
                self.assertEqual(actual['outside_bytes_changed'], 0, 'Palette stores must respect declared capacity')
                self.assertEqual(actual['sprite_probe'], 0, 'Raw RGB palette bytes must not become sprite dimensions')
    return check


for _contract in CONTRACTS:
    setattr(ProfilePaletteTests, 'test_profile_' + _contract['profile'], profile_test(_contract))


if __name__ == '__main__':
    unittest.main()
