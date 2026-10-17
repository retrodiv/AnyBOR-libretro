"""Require complete, unique coverage across bounded runtime groups.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
import unittest
from pathlib import Path
from profile_groups import select_profile_group, check_workflow_groups


class ProfileGroupsTests(unittest.TestCase):
    def test_all_sizes_counts_and_no_selection(self):
        for size in (1, 9, 13, 27, 32, 37):
            inventory = [dict(build=str(n), engine=str(n % 9)) for n in range(size)]
            self.assertEqual(select_profile_group(inventory, None), inventory)
            for count in range(1, size + 1):
                groups = [select_profile_group(inventory, str(index) + '/' + str(count))
                          for index in range(1, count + 1)]
                self.assertEqual([entry for group in groups for entry in group], inventory)
                self.assertTrue(all(group for group in groups))
                self.assertLessEqual(max(map(len, groups)) - min(map(len, groups)), 1)

    def test_invalid_group_or_inventory_never_silently_drops_cases(self):
        profiles = [dict(build='one'), dict(build='two')]
        for value in ('', '0/2', '1/0', '3/2', '1/3', '1', '-1/2', '1/2/3',
                      '01/2', '1/02', ' 1/2', '1/2 ', '1.0/2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                select_profile_group(profiles, value)
        for entries in ([], [profiles[0], profiles[0]]):
            with self.assertRaises(ValueError):
                select_profile_group(entries, None)

    def test_each_workflow_path_requires_complete_bounded_groups(self):
        profiles = [dict(build=str(n)) for n in range(27)]
        lines = []
        for script in ('test_rewind', 'test_state_options'):
            for flags in ('', '--windows --runner wine', '--core anybor_libretro.dylib'):
                for group in range(1, 5):
                    lines.append('python3 tools/' + script + '.py ' + flags +
                                 ' --profile-group ' + str(group) + '/4')
        workflow = '\n'.join(lines)
        check_workflow_groups(workflow, profiles)
        for bad in ('\n'.join(lines[1:]), workflow + '\n' + lines[0],
                    workflow.replace('--profile-group 1/4', '--profile-group 2/4', 1),
                    workflow.replace('--profile-group 1/4', '', 1),
                    workflow.replace('--profile-group 1/4', '--profile-group 1/1', 1)):
            with self.subTest(bad=bad[-50:]), self.assertRaises(ValueError):
                check_workflow_groups(bad, profiles)

    def test_current_workflow_partition(self):
        import json
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        check_workflow_groups((root / '.github/workflows/ci.yml').read_text(),
                              json.loads((root / 'src/pin.json').read_text())['profiles'])


if __name__ == '__main__':
    unittest.main()
