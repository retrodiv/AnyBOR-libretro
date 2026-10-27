#!/usr/bin/env python3
"""Select the host packages needed by one CI role and bound network retries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import json
import os
import subprocess

BASE = ('build-essential', 'python3', 'pkg-config')
PACKAGES = {
    'focused': BASE + ('libpng-dev',),
    'linux-x86_64': BASE + ('nasm',),
    'linux-aarch64': BASE + ('gcc-aarch64-linux-gnu', 'g++-aarch64-linux-gnu'),
    'linux-riscv64': BASE + ('gcc-riscv64-linux-gnu', 'g++-riscv64-linux-gnu', 'qemu-user'),
    'windows-x86_64': BASE + ('nasm', 'gcc-mingw-w64-x86-64', 'g++-mingw-w64-x86-64', 'wine64', 'wine'),
    'android-arm64': BASE,
    'state-linux': ('build-essential', 'python3', 'ffmpeg'),
    'state-windows': ('python3', 'wine64', 'wine', 'gcc-mingw-w64-x86-64'),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True, choices=sorted(PACKAGES))
    parser.add_argument('--install', action='store_true', help='execute; otherwise print the exact commands only')
    args = parser.parse_args()
    commands = apt_commands(args.role, root=os.geteuid() == 0)
    print(json.dumps(dict(role=args.role, packages=PACKAGES[args.role], commands=commands), indent=2), flush=True)
    if args.install:
        # CI invokes this complete tree under run_guarded and a step deadline.
        # APT's own bounded network retries do not consume the whole build job.
        for command in commands:
            subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
