#!/usr/bin/env python3
"""Exercise the LP64D context and fault boundary under an explicit user emulator.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

import release
import make_fixture
from runtime_evidence import record_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='riscv64-linux-gnu-gcc')
    parser.add_argument('--runner', default='qemu-riscv64 -L /usr/riscv64-linux-gnu')
    parser.add_argument('--core', help='Also verify fixed-base cold state loads and rewind')
    args = parser.parse_args()
    root = release.ROOT
    port = root / 'src/port/libretro'
    cc, runner = shlex.split(args.cc), shlex.split(args.runner)
    if not runner:
        parser.error('An explicit RISC-V execution command is required')
    with tempfile.TemporaryDirectory(prefix='anybor-riscv64-') as temp:
        work = Path(temp)
        def compile_run(name, sources, options=(), cases=((),)):
            binary = work / name
            subprocess.run(cc + ['-O2', '-fomit-frame-pointer', '-pthread',
                '-I', str(port), '-I', str(root / 'src/glue'),
                *map(str, sources), *options, '-o', str(binary)], check=True, timeout=60)
            for case in cases:
                result = subprocess.run(runner + [str(binary), *case],
                    capture_output=True, text=True, timeout=30)
                expected = 73 if case in (('frontend',), ('worker',), ('worker-fault',),
                                         ('worker-execute',), ('foreign',)) else 0
                if result.returncode != expected:
                    raise RuntimeError(name + ': ' + result.stdout + result.stderr)
                print(result.stdout, end='', flush=True)
                print('PASS RISC-V ' + name + ' ' + ' '.join(case), flush=True)
        compile_run('context', [root / 'tests/host/riscv64_context_test.c', port / 'obor_libco.c'],
                    ['-Wall', '-Wextra', '-Werror'])
        compile_run('fault', [root / 'tests/host/fault_guard_test.c', port / 'obor_fault.c',
            port / 'obor_libco.c', port / 'obor_write_watch.c'],
            ['-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=2', '-Wl,--wrap=read', '-Wl,--wrap=fread'],
            cases=((), ('upper-stack',), ('frontend',), ('worker',), ('user',), ('sigbus',)))
        # No test override enables the backend or bypasses its fixed arena.
        compile_run('watch', [root / 'tests/host/write_watch_test.c', port / 'obor_fault.c',
            port / 'obor_write_watch.c'], ['-Wl,--wrap=read', '-Wl,--wrap=fread'],
            cases=tuple((name,) for name in ('cpu', 'read', 'fread', 'growth', 'fault',
                'execute', 'execute-boundary', 'errno', 'lease', 'worker', 'registered')))
        interface = work / 'gamelib'
        interface.mkdir()
        (interface / 'threads.h').write_text('''
typedef struct bor_thread bor_thread;
typedef struct bor_mutex bor_mutex;
typedef struct bor_cond bor_cond;
bor_thread *thread_create(int (*)(void *), const char *, void *);
void thread_join(bor_thread *);
''')
        compile_run('worker-watch', [root / 'tests/host/worker_watch_test.c',
            port / 'obor_fault.c', port / 'obor_write_watch.c', port / 'threads.c'],
            ['-I', str(work), '-Wl,--wrap=read', '-Wl,--wrap=fread', '-Wl,--wrap=pthread_create'],
            cases=tuple((name,) for name in ('default', 'user', 'worker-fault',
                'worker-execute', 'foreign', 'frontend', 'disabled', 'inactive')))
        if args.core:
            core, host = Path(args.core).resolve(), work / 'host'
            subprocess.run(cc + ['-O2', '-I', str(root / 'src/glue'),
                '-I', str(root / 'src/third_party'), str(root / 'tests/host/libretro_host.c'),
                '-ldl', '-o', str(host)], check=True, timeout=60)
            pak = work / 'diagnostic.pak'
            make_fixture.write_pak(pak, make_fixture.files())
            for profile in ('3400', '8023'):
                state = work / (profile + '.state')
                outputs = []
                for label, settings in (
                    ('save', dict(OBOR_SAVE_AT='120', OBOR_SAVE_STATE=str(state))),
                    ('cold', dict(OBOR_LOAD_AT='120', OBOR_LOAD_STATE=str(state))),
                    ('rewind', dict(OBOR_RAREWIND='151,4', OBOR_RAREWIND_START='110',
                        OBOR_RAREWIND_EVERY='10', OBOR_RAREWIND_BUFFERS='4',
                        OBOR_HOST_THROTTLE='rewind', OBOR_EXPECT_REVERSE_PRESENTATION='1'))):
                    system = work / (profile + label)
                    system.mkdir()
                    env = {k: v for k, v in os.environ.items() if not k.startswith('OBOR_')}
                    env.update(OBOR_ENGINE=profile, OBOR_REPLAY_TRACE='121,320', **settings)
                    process = subprocess.run(runner + [str(host), str(core), str(pak),
                        str(system), '350'], env=env, capture_output=True, text=True, timeout=90)
                    log = process.stdout + process.stderr
                    record_process('riscv64', profile + '-' + label, process)
                    if process.returncode or 'host_core_module_base=0x3000000000' not in log or \
                            'arena_released=1' not in log or 'FAILED' in log or 'MISMATCH' in log:
                        raise RuntimeError(profile + ' ' + label + ': ' + log)
                    if label == 'cold' and 'load state at frame 120: ok' not in log:
                        raise RuntimeError('Cold state did not load: ' + log)
                    if label == 'save' and (not state.is_file() or
                            'saved state (' not in log or ' at frame 120' not in log):
                        raise RuntimeError('Reference state was not captured: ' + log)
                    if label == 'rewind' and log.count(' MATCH') != 4:
                        raise RuntimeError('Rewind did not replay four prior frames: ' + log)
                    outputs.append([line for line in log.splitlines() if line.startswith('replay_frame ')])
                    print('PASS RISC-V ' + profile + ' ' + label, flush=True)
                if len(outputs[0]) != 200 or outputs[0] != outputs[1]:
                    raise RuntimeError('RISC-V cold video/audio continuation differs')


if __name__ == '__main__':
    main()
