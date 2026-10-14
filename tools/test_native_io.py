#!/usr/bin/env python3
"""Exercise current file ABI layouts against incompatible legacy exports.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from run_guarded import require_limits

ROOT = Path(__file__).resolve().parents[1]


def exercise(port, fixtures, work):
    port, fixtures, work = map(Path, (port, fixtures, work))
    shim = fixtures / 'darwin_file_abi_shim.h'
    common = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
        '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-fPIC', '-D_GNU_SOURCE', '-I', str(port)]
    objects = []
    for name in ('obor_files', 'obor_paths', 'obor_loose'):
        obj = work / (name + '.o')
        flags = ['-include', str(shim)] if name == 'obor_files' else []
        subprocess.check_call(common + flags + ['-c', str(port / (name + '.c')),
                              '-o', str(obj)], timeout=30)
        objects.append(str(obj))
    engine, provider = work / 'engine.so', work / 'provider.so'
    compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
    subprocess.check_call(compiler + ['-shared'] + objects + ['-ldl', '-pthread',
                          '-o', str(engine)], timeout=30)
    subprocess.check_call(compiler + ['-shared', '-fPIC', '-std=gnu99', '-O1',
        '-Wall', '-Wextra', '-Werror', str(fixtures / 'darwin_file_abi_provider.c'),
        '-ldl', '-o', str(provider)], timeout=30)
    text = (port / 'libretroport.c').read_text()
    start = text.index('static int obor_make_dir(')
    helper = text[start:text.index('\n}\n', start) + 3]
    source = work / 'main.c'
    source.write_text((fixtures / 'darwin_file_abi.c').read_text().replace(
        '/* ANYBOR_DIRECTORY_HELPER */', helper))
    executable = work / 'probe'
    subprocess.check_call(common + ['-include', str(shim), str(source), '-rdynamic',
        str(engine), str(provider), '-Wl,-rpath,' + str(work), '-ldl', '-pthread',
        '-o', str(executable)], timeout=30)
    case = work / 'frontend-save-root'
    process = subprocess.run([str(executable), str(case)], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    if process.returncode or (case / 'Saves/session').read_text() != 'session':
        raise RuntimeError('Native file ABI/save-root regression: ' + process.stdout + process.stderr)
    return process.stdout


def main():
    require_limits()
    if not sys.platform.startswith('linux'):
        raise RuntimeError('This authored ABI control uses the Linux loader')
    with tempfile.TemporaryDirectory(prefix='anybor-native-io-') as temp:
        print(exercise(ROOT / 'src/port/libretro', ROOT / 'tests/host', temp))


if __name__ == '__main__':
    main()
