#!/usr/bin/env python3
"""Run a command in a bounded Linux cgroup, including all of its children.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def require_limits(max_memory_mib=1024):
    """Fail closed before a hostile-input suite starts, even under discovery."""
    if sys.platform != 'linux' or os.environ.get('ANYBOR_TEST_GUARD') != '1':
        raise RuntimeError('Run this suite through code-builder/run_guarded.py')
    group = next((line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines()
                  if line.startswith('0::/')), None)
    if group is None:
        raise RuntimeError('A cgroup v2 memory limit is required')
    root = Path('/sys/fs/cgroup').resolve()
    folder = (root / group.lstrip('/')).resolve()
    folder.relative_to(root)
    memory = (folder / 'memory.max').read_text().strip()
    swap = (folder / 'memory.swap.max').read_text().strip()
    tasks = (folder / 'pids.max').read_text().strip()
    if (memory == 'max' or int(memory) > max_memory_mib * 1024 * 1024
            or swap != '0' or tasks == 'max' or int(tasks) > 128):
        raise RuntimeError('Missing or excessive cgroup limits; use run_guarded.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--memory-mib', type=int, default=1024)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.memory_mib < 64 or args.seconds < 1:
        parser.error('provide a command, at least 64 MiB and a positive timeout')
    if args.child:
        os.environ['ANYBOR_TEST_GUARD'] = '1'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        require_limits(args.memory_mib)
        os.execvp(command[0], command)
    if sys.platform != 'linux' or not shutil.which('systemd-run'):
        parser.error('Linux cgroup v2 and a working systemd user manager are required; no unlimited fallback')
    unit = 'anybor-guard-' + uuid.uuid4().hex + '.scope'
    invocation = ['systemd-run', '--user', '--scope', '--quiet', '--unit=' + unit,
                  '-p', 'MemoryMax=%dM' % args.memory_mib, '-p', 'MemorySwapMax=0',
                  '-p', 'OOMPolicy=kill', '-p', 'TasksMax=128',
                  '-p', 'RuntimeMaxSec=%ds' % args.seconds,
                  sys.executable, str(Path(__file__).resolve()), '--child',
                  '--memory-mib', str(args.memory_mib), '--seconds', str(args.seconds),
                  '--'] + command
    print('Guard: %d MiB total, no swap, %ds, <=128 tasks' %
          (args.memory_mib, args.seconds), flush=True)
    try:
        result = subprocess.run(invocation, timeout=args.seconds + 5)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except subprocess.TimeoutExpired:
        print('Guard timeout; stopping the entire process tree', file=sys.stderr)
        return 124
    finally:
        subprocess.run(['systemctl', '--user', 'stop', unit],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)


if __name__ == '__main__':
    sys.exit(main())
