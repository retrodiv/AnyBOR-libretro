"""Validate logical profile keys independently of upstream revision numbers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

PROFILE_FEATURES = {'attack_history_four': 1, 'selection_escape_9': 2}
REVISION = re.compile(r'[1-9][0-9]{3,4}')
VARIANT = re.compile(r'[a-z][a-z0-9]*')


def profile_revision(profile):
    value = profile.get('revision', profile['build'])
    if not isinstance(value, str) or not REVISION.fullmatch(value):
        raise RuntimeError('Invalid upstream profile revision: ' + repr(value))
    return int(value)


def profile_stage(profile, physical=None):
    value = profile.get('stage', (physical or {}).get('stage', ''))
    if not isinstance(value, str) or (value and not VARIANT.fullmatch(value)):
        raise RuntimeError('Invalid engine release stage: ' + repr(value))
    return value


def profile_feature_mask(profile):
    names = profile.get('features', [])
    if (not isinstance(names, list) or any(not isinstance(name, str) for name in names) or
            len(set(names)) != len(names) or any(name not in PROFILE_FEATURES for name in names)):
        raise RuntimeError('Invalid logical profile features')
    return sum(PROFILE_FEATURES[name] for name in names)


def profile_sort_key(profile):
    revision = profile_revision(profile)
    return revision, profile['build'] != str(revision), profile['build']


def validate_profile(profile, physical=None):
    revision = profile_revision(profile)
    key = profile['build']
    stage = profile_stage(profile, physical)
    if (not isinstance(key, str) or len(key) >= 48 or
            key not in (str(revision), str(revision) + '-' + stage)):
        raise RuntimeError('Invalid logical profile key: ' + repr(key))
    until = profile.get('auto_until', str(revision))
    if (type(until) not in (str, int) or not REVISION.fullmatch(str(until)) or
            int(until) < revision):
        raise RuntimeError('Automatic profile range ends before its build or is invalid')
    for flag in ('automatic', 'tagged', 'triage'):
        if type(profile.get(flag, True)) is not bool:
            raise RuntimeError('Logical profile flag must be boolean: ' + flag)
    profile_feature_mask(profile)


def profile_display(profile, physical=None):
    validate_profile(profile, physical)
    major = profile.get('major', (physical or {}).get('major', ''))
    if major not in ('', 'v3', 'v4', 'v3.0', 'v4.0'):
        raise RuntimeError('Invalid profile major version')
    display = (major + ' ' + str(profile_revision(profile))).strip()
    stage = profile_stage(profile, physical)
    display += '-' + stage if stage else ''
    if len(display) >= 48:
        raise RuntimeError('Logical profile display exceeds the option capacity')
    return display
