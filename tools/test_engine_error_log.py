"""Keep engine loading diagnostics distinct from shutdown accounting.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
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
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "anybor_file_io.h"
static char g_game_dir[2048], g_logical_engine[64];
static int active;
static bool g_engine_error_context, g_engine_log_fresh;
static void *g_vtbl;
static const char *fault;
static bool p_get_fault_message(char *out, uint32_t cap) {
    if (!fault) return false;
    snprintf(out, cap, "%s", fault);
    return true;
}
@BEGIN@
@FUNCTION@
int main(int argc, char **argv) {
    if (argc != 7) return 2;
    snprintf(g_game_dir, sizeof(g_game_dir), "%s", argv[1]);
    snprintf(g_logical_engine, sizeof(g_logical_engine), "%s", argv[2]);
    if (strcmp(argv[3], "-")) { fault = argv[3]; g_vtbl = &active; }
    g_engine_error_context = atoi(argv[5]) != 0;
    g_engine_log_fresh = atoi(argv[6]) != 0;
    if (atoi(argv[5]) == 2) engine_log_begin();
    char out[256] = "unchanged";
    unsigned long cap = strtoul(argv[4], NULL, 10);
    if (!cap || cap > sizeof(out)) return 3;
    bool found = engine_log_error(out, cap);
    printf("%u\n%s\n", (unsigned)found, out);
    return 0;
}
'''.replace('@FUNCTION@', function(GLUE.read_text(), 'engine_log_error')).replace('@BEGIN@', function(GLUE.read_text(), 'engine_log_begin'))
        source = cls.work / 'probe.cpp'
        source.write_text(code)
        cls.executable = cls.work / 'probe'
        compiler = shlex.split(os.environ.get('CXX', 'c++'))
        result = subprocess.run(
            [*compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
             '-I', str(ROOT / 'src/glue'), str(source), '-o', str(cls.executable)],
            capture_output=True, text=True, timeout=60)
        record_process('engine-error-log', 'compile', result,
                       dict(glue_sha256=cls.glue_hash, compiler=compiler))
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def observe(self, text, *, profile='active', fault='-', capacity=256,
                written_profile=None, context=1, fresh=1, fifo=False):
        with tempfile.TemporaryDirectory(dir=self.work) as directory:
            if text is not None:
                path = Path(directory) / (written_profile or profile) / 'Logs/OpenBorLog.txt'
                path.parent.mkdir(parents=True)
                if fifo: os.mkfifo(path)
                else: path.write_text(text)
            result = subprocess.run(
                [str(self.executable), directory, profile, fault, str(capacity), str(context), str(fresh)],
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

    def test_large_log_only_reads_a_bounded_tail(self):
        self.assertEqual(self.observe('x' * 70000 + '\n' + MARKER + 'Tail failure.\n'),
                         (True, 'Tail failure.'))
        self.assertEqual(self.observe(MARKER + 'Old reason.\n' + 'x' * 70000),
                         (False, 'unchanged'))

    def test_inactive_context_ignores_old_callback_and_log(self):
        self.assertEqual(self.observe(MARKER + 'Old reason.\n', fault='Old callback.', context=0),
                         (False, 'unchanged'))

    def test_explicit_reason_does_not_require_a_readable_log(self):
        self.assertEqual(self.observe(None, fault='Unable to allocate a fixture buffer.', fresh=0),
                         (True, 'Unable to allocate a fixture buffer.'))

    def test_new_session_removes_the_previous_log(self):
        self.assertEqual(self.observe(MARKER + 'Previous reason.\n', context=2),
                         (False, 'unchanged'))

    def test_fifo_log_does_not_block(self):
        self.assertEqual(self.observe('', fifo=True), (False, 'unchanged'))

    def test_each_native_shutdown_captures_the_reason_before_cleanup(self):
        port = Path(os.environ.get('OBOR_CONTENT_ERROR_PORT', ROOT / 'src/port/libretro/libretroport.c')).read_text()
        callback = function(port, 'obor_content_reason_v')
        # Execute the actual formatting/capture prefix, before delegated cleanup.
        for engine in json.loads((ROOT / 'src/pin.json').read_text())['engines']:
            build = engine['build']
            source = (ROOT / 'src/engines' / build / 'openbor.c').read_text()
            name = 'borShutdown' if build in ('6391', '7142', '7533', '8023') else 'shutdown'
            body = function(source, name)
            end = body.index('if(!disablelog)')
            prefix = body[:end]
            if build == '8023': prefix += 'va_end(arglist);\n'
            prefix += '}\n'
            code = r'''#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#define LIBRETRO 1
static char engine_content_message[512];
@CALLBACK@
@PREFIX@
static void capture(const char *format,...) {va_list ap;va_start(ap,format);obor_content_reason_v(format,ap);va_end(ap);}
int main(void) {
 @SHUTDOWN@(1,"Unable to load font #%d!",1);
 assert(!strcmp(engine_content_message,"Unable to load font #1!"));
 capture("Secondary cleanup failure");assert(!strcmp(engine_content_message,"Unable to load font #1!"));
 engine_content_message[0]=0;capture("  \n\t");assert(!engine_content_message[0]);
 capture("Unable to allocate %u bytes",64u);assert(!strcmp(engine_content_message,"Unable to allocate 64 bytes"));
 engine_content_message[0]=0;char large[4096];memset(large,'a',sizeof(large)-1);large[4095]=0;capture("%s",large);assert(strlen(engine_content_message)==511);
 puts("native_shutdown_reason=1");return 0;
}
'''.replace('@CALLBACK@', callback).replace('@PREFIX@', prefix).replace('@SHUTDOWN@', name)
            with self.subTest(engine=build), tempfile.TemporaryDirectory(dir=self.work) as directory:
                unit, exe = Path(directory) / 'shutdown.c', Path(directory) / 'shutdown'
                unit.write_text(code)
                result = subprocess.run(['cc', '-std=gnu99', '-O1', str(unit), '-o', str(exe)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('native_shutdown_reason=1', result.stdout)


if __name__ == '__main__':
    unittest.main()
