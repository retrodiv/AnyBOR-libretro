#!/usr/bin/env python3
"""Select the host packages needed by one CI role and bound network retries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

BASE = ('build-essential', 'python3', 'pkg-config')
PACKAGES = {
    'focused': BASE + ('libpng-dev',),
    'linux-x86_64': BASE + ('nasm',),
    'linux-aarch64': BASE + ('gcc-aarch64-linux-gnu', 'g++-aarch64-linux-gnu'),
    'linux-riscv64': BASE + ('gcc-riscv64-linux-gnu', 'g++-riscv64-linux-gnu', 'qemu-user'),
    'windows-x86_64': BASE + ('nasm', 'gcc-mingw-w64-x86-64', 'g++-mingw-w64-x86-64', 'wine64', 'wine'),
    'android-arm64': BASE,
    'state-linux': ('build-essential', 'python3', 'ffmpeg'),
    'state-windows': ('python3', 'wine64', 'wine', 'gcc-mingw-w64-x86-64-posix'),
}


def apt_commands(role, *, root=False):
    if role not in PACKAGES:
        raise ValueError('Unknown CI package role')
    prefix = ([] if root else ['sudo']) + [
        'apt-get', '-o', 'Acquire::Retries=3',
        '-o', 'Acquire::http::Timeout=30', '-o', 'Acquire::https::Timeout=30',
        '-o', 'DPkg::Lock::Timeout=60', '-o', 'Dpkg::Use-Pty=0']
    packages = list(PACKAGES[role])
    return [prefix + ['update'],
            prefix + ['install', '-y', '--no-install-recommends', *packages]]


def bounded_command(command, seconds):
    """Keep root APT and its download workers within the same timed scope."""
    prefix = ['sudo'] if command[0] == 'sudo' else []
    return prefix + ['timeout', '--kill-after=5s', str(seconds)] + command[len(prefix):]


def run_phase(command, seconds, *, phase, attempt):
    started = time.monotonic()
    code = None
    try:
        subprocess.run(bounded_command(command, seconds), check=True)
        code = 0
    except subprocess.CalledProcessError as error:
        code = error.returncode
        raise
    finally:
        print(json.dumps(dict(phase=phase, attempt=attempt, exit=code,
                              seconds=round(time.monotonic()-started, 3))), flush=True)


def install_packages(role):
    """Retry only acquisition, before invoking the offline package installer."""
    commands = apt_commands(role, root=os.geteuid() == 0)
    with tempfile.TemporaryDirectory(prefix='anybor-apt-') as directory:
        for attempt in range(2):
            selected = commands
            if attempt:
                info = platform.freedesktop_os_release()
                codename = info.get('VERSION_CODENAME', '')
                if info.get('ID') != 'ubuntu' or not codename.isalpha():
                    raise RuntimeError('Official mirror recovery requires an Ubuntu runner')
                source = Path(directory) / 'ubuntu.list'
                source.write_text('\n'.join(
                    'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
                    + url + ' ' + suite + ' main restricted universe multiverse'
                    for url, suite in (
                        ('https://archive.ubuntu.com/ubuntu', codename),
                        ('https://archive.ubuntu.com/ubuntu', codename + '-updates'),
                        ('https://security.ubuntu.com/ubuntu', codename + '-security'))) + '\n')
                # Override this invocation only; preserve the runner's sources.
                options = ['-o', 'Dir::Etc::sourcelist=' + str(source),
                           '-o', 'Dir::Etc::sourceparts=-']
                selected = [cmd[:-1] + options + cmd[-1:] if cmd[-1] == 'update'
                            else cmd[:cmd.index('install')] + options + cmd[cmd.index('install'):]
                            for cmd in commands]
                print('APT recovery: official Ubuntu archive and security mirrors', flush=True)
            update, install = selected
            try:
                run_phase(update, 60, phase='index', attempt=attempt+1)
                run_phase(install + ['--download-only'], 180 if not attempt else 240,
                          phase='download', attempt=attempt+1)
            except subprocess.CalledProcessError:
                if attempt:
                    raise
                print('APT acquisition failed or exceeded its budget; retrying acquisition once', flush=True)
                continue
            # No mirror retry after unpacking starts. The outer guard remains
            # authoritative, and a package configuration error is a real failure.
            run_phase(install + ['--no-download'], 180, phase='install', attempt=attempt+1)
            return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True, choices=sorted(PACKAGES))
    parser.add_argument('--install', action='store_true', help='execute; otherwise print the exact commands only')
    args = parser.parse_args()
    commands = apt_commands(args.role, root=os.geteuid() == 0)
    print(json.dumps(dict(role=args.role, packages=PACKAGES[args.role], commands=commands), indent=2), flush=True)
    if args.install:
        install_packages(args.role)


if __name__ == '__main__':
    main()
