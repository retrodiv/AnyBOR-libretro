#!/usr/bin/env python3
"""Check the native Windows encoder and write tracking under Wine.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import release
from run_guarded import require_limits


def exercise(port, fixtures, exported, build):
    port, fixtures, exported, build = map(Path, (port, fixtures, exported, build))
    deps = build / 'deps/windows-x86_64'
    if not (deps / 'lib/libz.a').is_file():
        raise RuntimeError('Build the Windows target before its native worker checks')
    with tempfile.TemporaryDirectory(prefix='anybor-encoder-wine-', dir='/var/tmp') as folder:
        root = Path(folder)
        (root / 'wine').mkdir()
        env = dict(os.environ, WINEPREFIX=str(root / 'wine'), WINEDEBUG='-all',
                   WINEDLLOVERRIDES='winedbg.exe=d')
        try:
            subprocess.run(['wineserver', '-p'], env=env, check=True, timeout=15)
            subprocess.run(['wineboot', '--init'], env=env, check=True, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            executable = root / 'arena-probe.exe'
            subprocess.run(['x86_64-w64-mingw32-gcc', '-O2', '-std=c99',
                '-Wall', '-Wextra', '-Werror', '-static', '-I', str(fixtures),
                '-I', str(exported), str(fixtures / 'arena_probe_test.c'),
                '-o', str(executable)], check=True, timeout=60)
            result = subprocess.run(['wine', str(executable)], env=env, cwd=root,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stdout + result.stderr
            assert 'arena_probe_occupied_refused=1 clear_released=1' in result.stdout
            print('PASS Windows arena release probe: occupied refused, clear released', flush=True)
            executable = root / 'block-worker.exe'
            subprocess.run(['x86_64-w64-mingw32-gcc', '-O2', '-std=c99',
                '-Wall', '-Wextra', '-Werror', '-static',
                '-DOBOR_BLOCK_STATE_CAPACITY=8388608', '-I', str(port),
                '-I', str(exported), '-I', str(deps / 'include'),
                str(fixtures / 'block_worker_test.c'),
                str(port / 'obor_block_state.c'), str(exported / 'lz4.c'),
                str(deps / 'lib/libz.a'),
                '-Wl,--wrap=__imp_CreateThread',
                '-Wl,--wrap=__imp_WaitForSingleObject',
                '-Wl,--wrap=__imp_GetThreadTimes',
                '-o', str(executable)], check=True, timeout=60)
            imports = subprocess.check_output(
                ['x86_64-w64-mingw32-objdump', '-p', str(executable)], text=True)
            assert 'libwinpthread-1.dll' not in imports.lower()
            assert 'libgcc_s_seh-1.dll' not in imports.lower()
            for mode in ([], ['--deny-thread'], ['--deny-cpu-clock']):
                result = subprocess.run(['wine', str(executable), *mode],
                    env=env, cwd=root, capture_output=True, text=True, timeout=60)
                log = result.stdout + result.stderr
                assert result.returncode == 0, log
                for marker in ('equivalent_images=39 cold_decodes=43 adaptive_phases=6',
                               'old_independent=4 overflow_drained=1', 'failure_drained=1',
                               'unwind_drained=' + ('0' if '--deny-thread' in mode else '5')):
                    assert marker in log, log
                print('PASS Windows native helper', mode, result.stdout.strip(), flush=True)
            (root / 'gamelib').mkdir()
            (root / 'gamelib/threads.h').write_text(
                'typedef struct bor_thread bor_thread;\n'
                'typedef struct bor_mutex bor_mutex;\n'
                'typedef struct bor_cond bor_cond;\n'
                'bor_thread *thread_create(int (*)(void *), const char *, void *);\n'
                'void thread_join(bor_thread *);\n')
            for asynchronous in (False, True):
                executable = root / ('watch-async.exe' if asynchronous else 'watch-classic.exe')
                subprocess.run(['x86_64-w64-mingw32-gcc', '-O2', '-static',
                    '-Wall', '-Wextra', '-Werror',
                    *(['-DOBOR_HAS_MOVIE_PLAYBACK=1'] if asynchronous else []),
                    '-I', str(root), '-I', str(port),
                    str(fixtures / 'windows_worker_watch_test.c'),
                    str(port / 'threads.c'), '-Wl,--wrap=__imp_WaitForSingleObject',
                    '-o', str(executable)], check=True, timeout=30)
                for mode in ('default', 'disabled', 'failed-join'):
                    result = subprocess.run(['wine', str(executable), mode], env=env,
                        cwd=root, capture_output=True, text=True, timeout=30)
                    log = result.stdout + result.stderr
                    assert result.returncode == (91 if mode == 'failed-join' else 0), log
                    marker = ('join_failure_kept_live_worker=1' if mode == 'failed-join' else
                              'native_write_watch_worker_passed=1 captures_require_join=1 cycles=16')
                    assert marker in log, log
                    print('PASS Windows worker watch', 'async=' + str(int(asynchronous)), mode, flush=True)
        finally:
            subprocess.run(['wineserver', '-k'], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            subprocess.run(['wineserver', '-w'], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)


def main():
    require_limits()
    if sys.platform != 'linux':
        raise RuntimeError('This bounded Windows regression runs under Wine on Linux')
    port = release.ROOT / 'src/port/libretro'
    exercise(port, release.ROOT / 'tests/host', port,
             Path(os.environ.get('OBOR_BUILD_ROOT', release.ROOT / '.build')))


if __name__ == '__main__':
    main()
