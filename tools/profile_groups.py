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
    if 'python3 tools/ci_focused.py' in workflow:
        # Suite cost is measured per command. A profile count alone is not a
        # reason to multiply runner setup or scarce native runner queues.
        from ci_focused import workflow_job
        for name in ('focused', 'macos-regressions', 'macos-arm64-regressions'):
            job = workflow_job(workflow, name)
            matrices = re.findall(r'^        suite_group: (\[.*\])$', job, re.M)
            if len(matrices) != 1:
                raise ValueError('Missing scalable suite matrix: ' + name)
            groups = json.loads(matrices[0])
            count = len(groups) if isinstance(groups, list) else 0
            if (not 1 <= count <= 128 or
                    groups != [str(n) + '/' + str(count) for n in range(1, count + 1)]):
                raise ValueError('Suite partitions require a complete one-based matrix: ' + name)
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
        limit = 24 if platform == 'macos' else 8
        if not groups or any(len(group) > limit for group in groups):
            raise ValueError('CI profile group exceeds platform budget: ' + platform)
        if [entry['build'] for group in groups for entry in group] != names:
            raise ValueError('Incomplete or duplicate CI profile coverage: ' + script + ' / ' + platform)
    # The ARM native job reuses the same steps but has its own matrix and
    # artifact dependency. Its matrix must remain complete after profile growth.
    marker = '\n  state-macos-arm64:\n'
    if marker in workflow:
        if workflow.count(marker) != 1:
            raise ValueError('Duplicate native ARM state job')
        job = re.split(r'\n  [a-zA-Z0-9_-]+:', workflow.split(marker, 1)[1], maxsplit=1)[0]
        matrices = re.findall(r'^        profile_group: (\[.*\])$', job, re.M)
        if (len(matrices) != 1 or '    steps: *native-macos-state-steps\n' not in job or
                '    needs: macos-arm64\n' not in job or
                '    steps: &native-macos-state-steps\n' not in workflow):
            raise ValueError('Unbound native ARM state coverage')
        selectors = json.loads(matrices[0])
        if not isinstance(selectors, list) or not selectors or not all(isinstance(x, str) for x in selectors):
            raise ValueError('Invalid native ARM state matrix')
        groups = [select_profile_group(profiles, value) for value in selectors]
        if (not groups or any(len(group) > 24 for group in groups) or
                [entry['build'] for group in groups for entry in group] != names):
            raise ValueError('Incomplete or oversized native ARM state coverage')
