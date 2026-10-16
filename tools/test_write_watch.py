#!/usr/bin/env python3
"""Exercise native protected pages, kernel I/O and foreign-signal chaining.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import release


def main():
    if sys.platform not in ('linux', 'darwin'):
        raise RuntimeError('The native protected-page backend requires POSIX')
    port = release.ROOT / 'src/port/libretro'
    with tempfile.TemporaryDirectory(prefix='anybor-native-watch-') as folder:
        executable = Path(folder) / 'watch'
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        flags = ['-Wl,--wrap=read', '-Wl,--wrap=fread'] if sys.platform == 'linux' else []
        subprocess.run([*compiler, '-O2', '-pthread', '-DOBOR_WRITE_WATCH_TEST=1',
            '-D_DARWIN_C_SOURCE=1', '-I', str(port),
            str(release.ROOT / 'tests/host/write_watch_test.c'),
            str(port / 'obor_fault.c'), str(port / 'obor_write_watch.c'),
            *flags, '-o', str(executable)], check=True, timeout=45)
        for mode in ('cpu', 'read', 'fread', 'growth', 'fault', 'errno', 'lease', 'worker', 'registered'):
            result = subprocess.run([str(executable), mode], capture_output=True,
                                    text=True, timeout=15)
            log = result.stdout + result.stderr
            expected = 73 if mode == 'worker' else 0
            if result.returncode != expected or (not expected and 'write_watch_passed=1' not in log):
                raise RuntimeError('Native watcher ' + mode + ': ' + log)
            print('PASS native write watch', mode, flush=True)


if __name__ == '__main__':
    main()
