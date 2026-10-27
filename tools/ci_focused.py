#!/usr/bin/env python3
"""Run one complete partition of the shared, target-independent CI checks.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate focused-plan key: ' + key)
        result[key] = value
    return result


def load_suites(path=HERE / 'ci_focused.json'):
    with Path(path).open('rb') as stream:
        raw = stream.read((256 << 10) + 1)
    if len(raw) > 256 << 10:
        raise ValueError('Focused plan is too large')
    data = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or set(data) != {'schema', 'suites'} or
            type(data['schema']) is not int or data['schema'] != 1 or
            not isinstance(data['suites'], list) or not 1 <= len(data['suites']) <= 1024):
        raise ValueError('Expected a bounded focused suite plan, schema 1')
    names, commands = set(), set()
    for row in data['suites']:
        if not isinstance(row, dict) or set(row) != {'id', 'memory_mib', 'seconds', 'command', 'ci'}:
            raise ValueError('Unexpected focused suite fields')
        if (not isinstance(row['id'], str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,79}', row['id']) or
                row['id'] in names or row['ci'] not in ('shared', 'native-macos') or
                type(row['memory_mib']) is not int or not 64 <= row['memory_mib'] <= 2048 or
                type(row['seconds']) is not int or not 1 <= row['seconds'] <= 900):
            raise ValueError('Invalid or duplicate focused suite identity/limits')
        cmd = row['command']
        if (not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd) or
                not (cmd == ['make', 'check'] or len(cmd) == 2 and cmd[0] == 'python3' and
                     re.fullmatch(r'tools/test_[a-z0-9_]+\.py', cmd[1])) or tuple(cmd) in commands):
            raise ValueError('Unrecognized or duplicate focused command')
        names.add(row['id'])
        commands.add(tuple(cmd))
    if data['suites'][0]['command'] != ['make', 'check'] or data['suites'][0]['ci'] != 'shared':
        raise ValueError('Distribution checks must be first')
    return data['suites']


def select_suites(suites, group=None, *, local=False):
    selected = [row for row in suites if local or row['ci'] == 'shared']
    if group is None:
        return selected
    match = re.fullmatch(r'([1-9][0-9]*)/([1-9][0-9]*)', group) if isinstance(group, str) else None
    if not match:
        raise ValueError('Suite group must be one-based INDEX/COUNT')
    index, count = map(int, match.groups())
    if not 1 <= index <= count <= len(selected):
        raise ValueError('Suite group must be nonempty and within the plan')
    # Interleave modules rather than concentrating consecutive heavy families.
    return selected[index - 1::count]


def workflow_job(workflow, name):
    marker = '\n  ' + name + ':\n'
    if workflow.count(marker) != 1:
        raise ValueError('Expected one CI job: ' + name)
    return re.split(r'\n  [a-zA-Z0-9_-]+:', workflow.split(marker, 1)[1], maxsplit=1)[0]


def verify_workflow(workflow, suites):
    """Bind the actual CI partition and the retained native policy checks."""
    job = workflow_job(workflow, 'focused')
    matches = re.findall(r'^        suite_group: (\[.*\])$', job, re.M)
    if len(matches) != 1:
        raise ValueError('Expected one explicit focused suite matrix')
    groups = json.loads(matches[0])
    if not isinstance(groups, list) or not groups or not all(isinstance(x, str) for x in groups):
        raise ValueError('Invalid focused suite matrix')
    selected = [row['id'] for group in groups for row in select_suites(suites, group)]
    expected = [row['id'] for row in select_suites(suites)]
    if sorted(selected) != sorted(expected) or len(selected) != len(set(selected)):
        raise ValueError('Incomplete or duplicate focused suite coverage')
    marker = '      - name: Check distribution and focused regression tests\n'
    if workflow.count(marker) != 1 or marker not in job:
        raise ValueError('Focused checks must have one shared CI owner')
    block = job.split(marker, 1)[1].split('      - ', 1)[0]
    body = block.split('        run: |\n', 1)[1]
    commands = [shlex.split(line) for line in body.splitlines() if line.strip()]
    if commands != [['python3', 'tools/ci_focused.py', '--group', '${{ matrix.suite_group }}',
                     '--output', '.build/ci-focused']]:
        raise ValueError('Unexpected or unguarded shared focused command')
    native = workflow_job(workflow, 'macos-regressions')
    for name in ('macos-regressions', 'macos-arm64-regressions'):
        native_job = workflow_job(workflow, name)
        matrices = re.findall(r'^        suite_group: (\[.*\])$', native_job, re.M)
        if len(matrices) != 1:
            raise ValueError('Expected one explicit native suite matrix: ' + name)
        native_groups = json.loads(matrices[0])
        if not isinstance(native_groups, list) or not native_groups:
            raise ValueError('Empty native suite matrix: ' + name)
        count = len(native_groups)
        if count > 128 or native_groups != [str(i) + '/' + str(count) for i in range(1, count + 1)]:
            raise ValueError('Incomplete native suite coverage: ' + name)
        if 'ANYBOR_CI_SUITE_GROUP: ${{ matrix.suite_group }}' not in native_job:
            raise ValueError('Native suite matrix is not passed to the collector: ' + name)
    if ('steps: &native-macos-regression-steps' not in native or
            'steps: *native-macos-regression-steps' not in workflow_job(workflow, 'macos-arm64-regressions')):
        raise ValueError('Native architectures must use the same regression collector')
    for row in suites:
        if row['ci'] == 'native-macos' and native.count('run_check ' + ' '.join(row['command']) + '\n') != 1:
            raise ValueError('Missing native CI coverage: ' + row['id'])
    return groups


def completed_test_failure(code, path):
    if code != 1 or path.stat().st_size > 8 << 20:
        return False
    text = path.read_text(errors='replace')
    if re.search(r'SIGKILL|SIGBUS|MemoryError|internal compiler error|Killed signal|'
                 r'Guard timeout|cgroup limits|Failed to (?:start|connect)|no unlimited fallback', text):
        return False
    return bool(re.search(r'(?m)^Ran \d+ tests? in [0-9.]+s$', text) and
                re.search(r'(?m)^FAILED \(', text))


def run_suites(suites, output, *, root=ROOT):
    if not suites:
        raise ValueError('Refusing an empty focused run')
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=1, complete=False, results=[])
    failures = []
    for row in suites:
        cmd = list(row['command'])
        if cmd[0] == 'python3':
            cmd[0] = sys.executable
        guarded = [sys.executable, str(root / 'tools/run_guarded.py'),
                   '--memory-mib', str(row['memory_mib']), '--seconds', str(row['seconds']), '--', *cmd]
        log = output / (row['id'] + '.log')
        print('RUN ' + row['id'], flush=True)
        started = time.monotonic()
        with log.open('x') as stream:
            process = subprocess.run(guarded, cwd=root, stdout=stream, stderr=subprocess.STDOUT)
        elapsed = time.monotonic() - started
        with log.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        result = dict(id=row['id'], command=row['command'], memory_mib=row['memory_mib'],
                      seconds=row['seconds'], elapsed_seconds=elapsed, exit=process.returncode,
                      log=log.name, log_sha256=digest)
        receipt['results'].append(result)
        (output / 'results.json').write_text(json.dumps(receipt, indent=2) + '\n')
        # Detailed logs remain in the uploaded evidence; cap console replay.
        with log.open('rb') as stream:
            sys.stdout.write(stream.read(8 << 20).decode('utf-8', errors='replace'))
        print('RESULT {0} exit={1} seconds={2:.3f}'.format(row['id'], process.returncode, elapsed), flush=True)
        if process.returncode:
            failures.append(row['id'])
            if not completed_test_failure(process.returncode, log):
                raise RuntimeError('Guard/resource or incomplete suite failure: ' + row['id'])
    receipt.update(complete=True, failed=failures)
    (output / 'results.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if failures:
        raise RuntimeError('Completed focused suite failures: ' + ', '.join(failures))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', required=True, help='one-based INDEX/COUNT shared-suite partition')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run_suites(select_suites(load_suites(), args.group), args.output)


if __name__ == '__main__':
    main()
