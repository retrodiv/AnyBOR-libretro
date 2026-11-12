"""Engine identification uses executable facts, with bounded adjacent scans.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import re
import subprocess
import tempfile
import unittest
from native_sanitizers import sanitizer_environment

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
GLUE = Path(os.environ.get('OBOR_GLUE_DIR', ROOT / 'src/glue'))


class EngineIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='anybor-engine-identity-')
        cls.directory = Path(cls.work.name)
        source = cls.directory / 'probe.cpp'
        # Synthetic executable bytes are data, never a runnable program.
        a, b, c, d = (hashlib.sha256(value).hexdigest() for value in
                      (b'engine A', b'engine B', b'engine C', b'engine D'))
        source.write_text(r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define OBOR_ENGINE_EXECUTABLES_H
typedef struct { const char *sha256; int build; const char *variant; unsigned bytes; } obor_engine_executable;
static const obor_engine_executable obor_engine_executables[] = {
    @ROWS@
};
#include "anybor_engine_identity.h"
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    obor_engine_identity id = obor_engine_for_content(argv[1], atoi(argv[2]) != 0);
    printf("%d %d %s\n", id.status, id.status == OBOR_ENGINE_IDENTIFIED ? id.engine->build : 0,
           id.evidence);
}
'''.replace('@ROWS@', ',\n'.join('    {"%s", %d, "%s", 8}' % row
                  for row in sorted(((a, 4000, ''), (b, 4100, ''), (c, 4000, 'mod'),
                                     (d, 4000, ''), (d, 4200, ''))))))
        cls.binary = cls.directory / 'probe'
        subprocess.run([*shlex.split(os.environ.get('HOST_CXX', 'c++')), '-std=c++11',
            '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-g',
            '-fsanitize=address,undefined', '-I', str(GLUE), str(source), '-o', str(cls.binary)],
            check=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.directory)
        self.folder = Path(self.case.name)

    def tearDown(self):
        self.case.cleanup()

    def identify(self, path=None, raw=False):
        run = subprocess.run([str(self.binary), str(path or self.folder / 'game.pak'), str(int(raw))],
                             check=True, capture_output=True, text=True, timeout=20,
                             env=sanitizer_environment())
        parts = run.stdout.strip().split(' ', 2)
        return tuple(map(int, parts[:2]))

    def test_no_executable_unknown_and_tool_files_preserve_unknown(self):
        self.assertEqual(self.identify(), (0, 0))
        (self.folder / 'utility.exe').write_bytes(b'unknown tool')
        (self.folder / 'notes.txt').write_bytes(b'engine A')
        self.assertEqual(self.identify(), (0, 0))

    def test_shipped_engine_facts_match_the_lookup_table(self):
        manifest = Path(os.environ.get('OBOR_ENGINE_MANIFEST', ROOT / 'docs/ENGINE_EXECUTABLES.json'))
        rows = json.loads(manifest.read_text())['executables']
        header = (GLUE / 'anybor_engine_executables.h').read_text()
        actual = [(digest, int(build), variant, int(size)) for digest, build, variant, size in
                  re.findall(r'\{"([0-9a-f]{64})", ([0-9]+), "([a-z0-9-]*)", ([0-9]+)U\}', header)]
        expected = [(row['sha256'], row['build'], row['variant'], row['bytes']) for row in rows]
        self.assertEqual(actual, expected)
        self.assertEqual(actual, sorted(actual))
        self.assertTrue(actual)
        self.assertEqual(len(actual), len(set(actual)))
        sizes = {}
        for digest, _, _, size in actual:
            self.assertEqual(sizes.setdefault(digest, size), size)

    def test_exact_engine_hash_is_independent_of_filename_and_banner(self):
        (self.folder / 'arbitrary.EXE').write_bytes(b'engine A')
        self.assertEqual(self.identify(), (1, 4000))
        (self.folder / 'utility.exe').write_bytes(b'unknown tool')
        self.assertEqual(self.identify(), (1, 4000))

    def test_duplicates_agree_but_distinct_builds_are_ambiguous(self):
        (self.folder / 'a.exe').write_bytes(b'engine A')
        (self.folder / 'copy.exe').write_bytes(b'engine A')
        self.assertEqual(self.identify(), (1, 4000))
        (self.folder / 'b.exe').write_bytes(b'engine B')
        self.assertEqual(self.identify(), (2, 0))

    def test_only_the_content_directory_is_scanned(self):
        (self.folder / 'a.exe').write_bytes(b'engine A')
        child = self.folder / 'Paks'; child.mkdir()
        self.assertEqual(self.identify(child / 'game.pak'), (0, 0))
        self.assertEqual(self.identify(self.folder, raw=True), (1, 4000))
        nested = self.folder / 'data'; nested.mkdir()
        (nested / 'b.exe').write_bytes(b'engine B')
        self.assertEqual(self.identify(self.folder, raw=True), (1, 4000))

    def test_distinct_variants_of_one_build_are_ambiguous(self):
        (self.folder / 'official.exe').write_bytes(b'engine A')
        (self.folder / 'variant.exe').write_bytes(b'engine C')
        self.assertEqual(self.identify(), (2, 0))

    @unittest.skipIf(os.name == 'nt', 'Unix symlink control')
    def test_symlinks_do_not_supply_an_engine(self):
        target = self.folder / 'engine.dat'; target.write_bytes(b'engine A')
        (self.folder / 'link.exe').symlink_to(target)
        self.assertEqual(self.identify(), (0, 0))

    def test_executable_and_entry_limits_return_inconclusive(self):
        for i in range(17):
            (self.folder / ('tool-%d.exe' % i)).write_bytes(b'engine A')
        self.assertEqual(self.identify(), (3, 0))
        for file in self.folder.iterdir(): file.unlink()
        (self.folder / 'a.exe').write_bytes(b'engine A')
        for i in range(1025):
            (self.folder / ('entry-%d.txt' % i)).touch()
        self.assertEqual(self.identify(), (3, 0))

    def test_oversized_files_are_not_hashed(self):
        with (self.folder / 'large.exe').open('wb') as stream:
            stream.truncate((64 << 20) + 1)
        self.assertEqual(self.identify(), (3, 0))

    def test_multiplatform_engine_names_use_only_verified_facts(self):
        for name in ('OpenBOR', 'openbor-arm64', 'OpenBOR-x86', 'OpenBOR_x64',
                     'engine.AppImage', 'engine.apk', 'boot.dol', 'EBOOT.PBP',
                     '1ST_READ.BIN', 'OpenBOR.elf', 'OpenBOR.gpe', 'OpenBOR.dge',
                     'engine.opk'):
            with self.subTest(name=name):
                candidate = self.folder / name; candidate.write_bytes(b'engine A')
                self.assertEqual(self.identify(), (1, 4000))
                candidate.unlink()
        (self.folder / 'utility.apk').write_bytes(b'unknown tool')
        self.assertEqual(self.identify(), (0, 0))

    def test_multiplatform_content_files_never_supply_engine_facts(self):
        for name in ('OpenBOR.pak', 'OpenBOR.zip', 'OpenBOR.txt', 'game.spk',
                     'OpenBOR-icon.png', 'notes.bin'):
            (self.folder / name).write_bytes(b'engine A')
        self.assertEqual(self.identify(), (0, 0))

    def test_multiplatform_shared_payload_does_not_invent_one_build(self):
        (self.folder / 'OpenBOR').write_bytes(b'engine D')
        self.assertEqual(self.identify(), (2, 0))

    def test_multiplatform_scan_keeps_file_count_and_size_limits(self):
        for number in range(17):
            (self.folder / ('OpenBOR-' + str(number))).write_bytes(b'engine A')
        self.assertEqual(self.identify(), (3, 0))
        for path in self.folder.iterdir(): path.unlink()
        with (self.folder / 'large.AppImage').open('wb') as stream:
            stream.truncate((64 << 20) + 1)
        self.assertEqual(self.identify(), (3, 0))

    def test_multiplatform_loose_scan_stays_beside_content(self):
        (self.folder / 'OpenBOR').write_bytes(b'engine A')
        child = self.folder / 'Paks'; child.mkdir()
        self.assertEqual(self.identify(child / 'game.pak'), (0, 0))
        self.assertEqual(self.identify(self.folder, raw=True), (1, 4000))


if __name__ == '__main__':
    unittest.main()
