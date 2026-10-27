"""Partition runtime profile coverage without changing the test cases.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
import shlex


def select_profile_group(profiles, value):
    profiles = list(profiles)
    names = [entry['build'] for entry in profiles]
    if not names or len(set(names)) != len(names):
        raise ValueError('Profile inventory must be nonempty and unique')
    if value is None:
        return profiles
    match = re.fullmatch(r'([1-9][0-9]*)/([1-9][0-9]*)', value)
    if match is None:
        raise ValueError('Profile group must be a one-based INDEX/COUNT')
    index, count = map(int, match.groups())
    if not 1 <= index <= count <= len(profiles):
        raise ValueError('Profile group must be nonempty and within the inventory')
    return profiles[len(profiles) * (index - 1) // count:len(profiles) * index // count]


def expand_workflow_profile_groups(workflow):
    """Expand only each job's explicit JSON group matrix for static auditing.

    The local preflight consumes the same commands serially. CI runs each
    group on a separate runner; expanding a group never launches a process.
    """
    groups = None
    result = []
    expression = '${{ matrix.profile_group }}'
    for line in workflow.splitlines():
        if re.fullmatch(r'  [A-Za-z0-9_-]+:', line):
            groups = None
        match = re.fullmatch(r'        profile_group: (\[.*\])', line)
        if match:
            groups = json.loads(match[1])
            if (not groups or not all(isinstance(group, str) for group in groups)
                    or len(set(groups)) != len(groups)):
                raise ValueError('Invalid explicit CI profile group matrix')
        if expression in line:
            if not groups or not line.strip().startswith('python3 '):
                raise ValueError('Unbound CI profile group expression')
            result.extend(line.replace(expression, group) for group in groups)
        else:
            result.append(line)
    return '\n'.join(result) + '\n'


def check_workflow_groups(workflow, profiles):
    """Require complete bounded coverage in each native/emulated CI path."""
    scripts = ('tools/test_rewind.py', 'tools/test_state_options.py', 'tools/regression.py')
    paths = {(script, platform): [] for script in scripts
             for platform in ('linux', 'windows', 'macos')
             if script != 'tools/regression.py' or platform != 'windows'}
    for line in expand_workflow_profile_groups(workflow).splitlines():
        if not line.strip().startswith('python3 '):
            continue
        words = shlex.split(line)
        for script in scripts:
            if script not in words:
                continue
            if words.count(script) != 1:
                raise ValueError('Ambiguous runtime script')
            args = words[words.index(script) + 1:]
            if args.count('--profile-group') != 1:
                raise ValueError('CI runtime scripts require one explicit profile group')
            offset = args.index('--profile-group') + 1
            if offset == len(args):
                raise ValueError('Missing CI profile group')
            group = args[offset]
            platform = ('windows' if '--windows' in args else
                        'macos' if 'anybor_libretro.dylib' in args else 'linux')
            if (script, platform) not in paths:
                raise ValueError("Unexpected grouped runtime platform")
            paths[script, platform].append(group)
    names = [entry['build'] for entry in profiles]
    for (script, platform), selectors in paths.items():
        groups = [select_profile_group(profiles, value) for value in selectors]
        if not groups or any(len(group) > 8 for group in groups):
            raise ValueError('CI profile groups must contain at most eight profiles')
        if [entry['build'] for group in groups for entry in group] != names:
            raise ValueError('Incomplete or duplicate CI profile coverage: ' + script + ' / ' + platform)
