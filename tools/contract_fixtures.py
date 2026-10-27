"""Load declared contract fixtures and their retained profile witnesses.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path

MAX_FIXTURE_BYTES = 32 << 20


def fixture_path(path):
    path = Path(path)
    if path.parent.name != 'fixtures' or not path.name or path.name in ('.', '..'):
        raise ValueError('Expected a direct contract fixture path')
    override = os.environ.get('ANYBOR_CONTRACT_FIXTURE_DIR')
    if override:
        root = Path(override)
        if not root.is_absolute() or not root.is_dir():
            raise ValueError('Private fixture directory must be absolute and present')
        path = root / path.name
        if not path.is_file():
            raise ValueError('Missing declared private fixture: ' + path.name)
    return path


def at_path(value, path):
    if not isinstance(path, list) or not path or len(path) > 32:
        raise ValueError('Invalid fixture witness path')
    for key in path:
        if type(key) not in (str, int) or type(key) is int and key < 0:
            raise ValueError('Invalid fixture witness selector')
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError('Missing retained fixture witness') from error
    return value


def load_contract_fixture(path):
    with fixture_path(path).open('rb') as stream:
        raw = stream.read(MAX_FIXTURE_BYTES + 1)
    if len(raw) > MAX_FIXTURE_BYTES:
        raise ValueError('Contract fixture exceeds its input limit')
    value = json.loads(raw)
    boundary = value.get('_contract_boundaries') if isinstance(value, dict) else None
    if boundary is not None:
        if (not isinstance(boundary, dict) or not {'schema', 'profiles', 'ranges', 'witnesses', 'counts'} <= set(boundary)
                or set(boundary) - {'schema', 'profiles', 'ranges', 'witnesses', 'counts', 'labels'}
                or boundary['schema'] != 1 or type(boundary['schema']) is not int):
            raise ValueError('Invalid contract boundary metadata')
        profiles = boundary['profiles']
        if (not isinstance(profiles, list) or not profiles or
                any(not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str)
                    or type(row[1]) is not int or row[1] <= 0 for row in profiles) or
                len({tuple(row) for row in profiles}) != len(profiles)):
            raise ValueError('Invalid retained profile inventory')
        ranges = boundary['ranges']
        if (not isinstance(ranges, list) or not ranges or
                any(not isinstance(row, list) or len(row) != 3 or not isinstance(row[0], str)
                    or type(row[1]) is not int or type(row[2]) is not int or not 0 < row[1] <= row[2]
                    for row in ranges) or len({row[0] for row in ranges}) != len(ranges) or
                any(not any(engine == row[0] and row[1] <= revision <= row[2] for row in ranges)
                    for engine, revision in profiles)):
            raise ValueError('Invalid original contract scope')
        if 'labels' in boundary:
            labels = boundary['labels']
            if (not isinstance(labels, list) or not labels or
                    any(not isinstance(row, list) or len(row) != 3 or not isinstance(row[0], str)
                        or type(row[1]) is not int or not isinstance(row[2], str) for row in labels) or
                    len({tuple(row) for row in labels}) != len(labels) or
                    {tuple(row[:2]) for row in labels} != {tuple(row) for row in profiles}):
                raise ValueError('Invalid retained profile labels')
        for witness in boundary['witnesses']:
            if set(witness) != {'path', 'value'} or at_path(value, witness['path']) != witness['value']:
                raise ValueError('Retained fixture identity changed')
        for count in boundary['counts']:
            if set(count) != {'path', 'size'} or len(at_path(value, count['path'])) != count['size']:
                raise ValueError('Retained fixture collection changed')
    return value


def contract_profiles(path, profiles):
    """Public boundaries or the complete inventory in a private fixture run."""
    fixture = path if isinstance(path, dict) else load_contract_fixture(path)
    boundary = fixture.get('_contract_boundaries') if isinstance(fixture, dict) else None
    if boundary is None:
        return list(profiles)
    retained = {tuple(row) for row in boundary['profiles']}
    labels = {tuple(row) for row in boundary['labels']} if 'labels' in boundary else None
    result = []
    for row in profiles:
        engine = row['engine']
        revision = int(row.get('revision', row.get('build', row.get('profile'))))
        scoped = any(engine == item[0] and item[1] <= revision <= item[2]
                     for item in boundary['ranges'])
        selected = ((engine, revision, row.get('build', row.get('profile'))) in labels
                    if labels is not None else (engine, revision) in retained)
        # Generic tests can also exercise families outside this source fixture.
        # Their existing coverage is independent of its historical projection.
        if not scoped or selected:
            result.append(row)
    return result


def contract_revisions(fixture, revisions):
    """Scope an original source-coverage assertion to the public projection.

    Explicit boundary controls remain mandatory. Private matrices have no
    projection metadata and keep the complete original coverage assertion.
    """
    required = set(revisions)
    boundary = fixture.get('_contract_boundaries')
    if boundary is None:
        return required
    retained = {revision for _, revision in boundary['profiles']}
    retained.update(row['value'] for row in boundary['witnesses']
                    if row['path'][-1] == 'revision' and type(row['value']) is int)
    controls = set(fixture.get('boundary_controls', []))
    return {revision for revision in required
            if revision in retained or revision in controls or
            not any(low <= revision <= high for _, low, high in boundary['ranges'])}
