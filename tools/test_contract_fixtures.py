"""Retain explicit public witnesses and load full private matrices locally.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions, fixture_path


class ContractFixtureTests(unittest.TestCase):
    def fixture(self):
        return dict(contexts=[dict(engine='physical', revision=2, expected='unchanged')],
                    _contract_boundaries=dict(schema=1, profiles=[['physical', 2]], ranges=[['physical', 1, 3]],
                        witnesses=[dict(path=['contexts', 0, 'revision'], value=2)],
                        counts=[dict(path=['contexts'], size=1)]))

    def test_retained_contexts_execute_and_private_matrix_preserves_full_scope(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder)
            public, private = root / 'fixtures', root / 'private'
            public.mkdir(); private.mkdir()
            path = public / 'sample.json'
            path.write_text(json.dumps(self.fixture()))
            profiles = [dict(engine='physical', build=str(n)) for n in (1, 2, 3)]
            self.assertEqual(contract_profiles(path, profiles), [profiles[1]])
            (private / path.name).write_text(json.dumps(dict(contexts=[dict(revision=n) for n in (1, 2, 3)])))
            with patch.dict(os.environ, ANYBOR_CONTRACT_FIXTURE_DIR=str(private)):
                self.assertEqual(contract_profiles(path, profiles), profiles)
                self.assertEqual(len(load_contract_fixture(path)['contexts']), 3)

    def test_generic_checks_outside_the_historical_fixture_scope_keep_their_coverage(self):
        fixture = self.fixture()
        profiles = [dict(engine='physical', build=str(n)) for n in (1, 2, 3, 4)]
        profiles.append(dict(engine='another-physical-family', build='9'))
        self.assertEqual(contract_profiles(fixture, profiles), [profiles[1], profiles[3], profiles[4]])

    def test_source_coverage_assertions_follow_projection_but_private_keeps_every_context(self):
        fixture = self.fixture()
        required = {1, 2, 3, 9}
        self.assertEqual(contract_revisions(fixture, required), {2, 9})
        self.assertEqual(contract_revisions({}, required), required)

    def test_explicit_boundary_controls_remain_required_even_if_their_row_is_missing(self):
        fixture = self.fixture()
        fixture['boundary_controls'] = [1, 3]
        self.assertEqual(contract_revisions(fixture, {1, 2, 3}), {1, 2, 3})

    def test_removed_or_changed_retained_identity_is_never_silently_skipped(self):
        fixture = self.fixture()
        mutations = []
        for change in ('drop', 'revision', 'count'):
            data = copy.deepcopy(fixture)
            if change == 'drop':
                data['contexts'].clear()
            elif change == 'revision':
                data['contexts'][0]['revision'] = 3
            else:
                data['contexts'].append(dict(revision=9))
            mutations.append(data)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder) / 'fixtures'; root.mkdir()
            path = root / 'sample.json'
            for data in mutations:
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    load_contract_fixture(path)

    def test_private_override_never_falls_back_to_a_smaller_public_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.dict(os.environ, ANYBOR_CONTRACT_FIXTURE_DIR=str(root)):
                with self.assertRaises(ValueError):
                    fixture_path(root / 'fixtures/missing.json')
            with patch.dict(os.environ, ANYBOR_CONTRACT_FIXTURE_DIR='relative'):
                with self.assertRaises(ValueError):
                    fixture_path(root / 'fixtures/missing.json')


if __name__ == '__main__':
    unittest.main()
