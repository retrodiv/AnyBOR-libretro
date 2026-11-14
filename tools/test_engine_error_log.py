"""Keep engine loading diagnostics distinct from shutdown accounting.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from runtime_evidence import record_process
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
GLUE = Path(os.environ.get('OBOR_ERROR_GLUE', ROOT / 'src/glue/libretro.cpp'))

MARKER = '********** An Error Occurred **********\n'
SUMMARY = (
    '*            Shutting Down            *\n\n'
    'Total Ram: 0 Bytes\n Free Ram: 1024 Bytes\n Used Ram: 512 Bytes\n\n'
    'Release level data...........\tDone!\n'
    'Release graphics data........\tDone!\n'
    'Release game data............\tDone!\n'
    'Release timer................\tDone!\n'
    '**************** Done *****************\n\n'
)


class EngineErrorLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='engine-error-log-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.glue_hash = hashlib.sha256(GLUE.read_bytes()).hexdigest()
        code = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static char g_game_dir[2048], g_logical_engine[64];
static int active;
static void *g_vtbl;
static const char *fault;
static bool p_get_fault_message(char *out, uint32_t cap) {
    if (!fault) return false;
    snprintf(out, cap, "%s", fault);
    return true;
}
@FUNCTION@
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    snprintf(g_game_dir, sizeof(g_game_dir), "%s", argv[1]);
    snprintf(g_logical_engine, sizeof(g_logical_engine), "%s", argv[2]);
    if (strcmp(argv[3], "-")) { fault = argv[3]; g_vtbl = &active; }
    char out[256] = "unchanged";
    unsigned long cap = strtoul(argv[4], NULL, 10);
    if (!cap || cap > sizeof(out)) return 3;
    bool found = engine_log_error(out, cap);
    printf("%u\n%s\n", (unsigned)found, out);
    return 0;
}
'''.replace('@FUNCTION@', function(GLUE.read_text(), 'engine_log_error'))
        source = cls.work / 'probe.cpp'
        source.write_text(code)
        cls.executable = cls.work / 'probe'
        compiler = shlex.split(os.environ.get('CXX', 'c++'))
        result = subprocess.run(
            [*compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
             str(source), '-o', str(cls.executable)],
            capture_output=True, text=True, timeout=60)
        record_process('engine-error-log', 'compile', result,
                       dict(glue_sha256=cls.glue_hash, compiler=compiler))
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def observe(self, text, *, profile='active', fault='-', capacity=256,
                written_profile=None):
        with tempfile.TemporaryDirectory(dir=self.work) as directory:
            if text is not None:
                path = Path(directory) / (written_profile or profile) / 'Logs/OpenBorLog.txt'
                path.parent.mkdir(parents=True)
                path.write_text(text)
            result = subprocess.run(
                [str(self.executable), directory, profile, fault, str(capacity)],
                capture_output=True, text=True, timeout=10)
            record_process('engine-error-log', self._testMethodName, result,
                           dict(glue_sha256=self.glue_hash, profile=profile))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, '')
            self.assertEqual(hashlib.sha256(GLUE.read_bytes()).hexdigest(), self.glue_hash)
            found, message = result.stdout.split('\n', 1)
            return found == '1', message.rstrip('\n')

    def test_reason_before_shutdown_is_preserved(self):
        self.assertEqual(self.observe(MARKER + 'Fixture image is unavailable.\n' + SUMMARY),
                         (True, 'Fixture image is unavailable.'))

    def test_reason_after_shutdown_accounting_is_reported(self):
        self.assertEqual(self.observe(MARKER + SUMMARY + 'Fixture font could not be loaded.\n'),
                         (True, 'Fixture font could not be loaded.'))

    def test_accounting_without_a_reason_is_not_an_error_message(self):
        self.assertEqual(self.observe(MARKER + SUMMARY), (False, 'unchanged'))

    def test_shutdown_accounting_with_megabyte_totals_is_skipped(self):
        summary = SUMMARY.replace('Total Ram: 0 Bytes',
                                  'Total Ram:           0 Bytes (     0 MB )')
        self.assertEqual(self.observe(MARKER + summary + 'Fixture image is unavailable.\n'),
                         (True, 'Fixture image is unavailable.'))

    def test_incomplete_shutdown_is_not_reported_as_a_reason(self):
        self.assertEqual(self.observe(MARKER + 'Total Ram: 0 Bytes\nRelease timer...\n'),
                         (False, 'unchanged'))

    def test_non_numeric_ram_diagnostic_remains_meaningful(self):
        self.assertEqual(self.observe(MARKER + 'Total Ram: required allocation is unavailable.\n'),
                         (True, 'Total Ram: required allocation is unavailable.'))

    def test_fault_callback_has_priority(self):
        self.assertEqual(self.observe(MARKER + 'Log reason.\n', fault='Controlled fault.'),
                         (True, 'Controlled fault.'))

    def test_other_profile_log_is_ignored(self):
        self.assertEqual(self.observe(MARKER + 'Stale reason.\n', written_profile='other'),
                         (False, 'unchanged'))

    def test_unmarked_log_is_not_reported_as_a_reason(self):
        self.assertEqual(self.observe('Loading assets...\n'), (False, 'unchanged'))

    def test_output_capacity_is_respected(self):
        self.assertEqual(self.observe(MARKER + SUMMARY + 'Fixture diagnostic.\n', capacity=8),
                         (True, 'Fixture'))


if __name__ == '__main__':
    unittest.main()
