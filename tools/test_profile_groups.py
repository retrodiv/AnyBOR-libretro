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
        for script in ('test_rewind', 'test_state_options', 'regression'):
            for flags in ('', '--windows --runner wine', '--core anybor_libretro.dylib'):
                if script == 'regression' and '--windows' in flags:
                    continue
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

    def test_model_warning_preserves_historical_spare_slot(self):
        from regression import model_attack_warning
        for engine in ("3400", "3741", "3842", "4086", "4432", "6391", "7142", "7533", "8023"):
            profile = dict(engine=engine)
            spare = engine in ("3741", "3842")
            for declared in (None, 12):
                boundary = 10 if declared is None else declared
                self.assertFalse(model_attack_warning(profile, boundary, declared))
                self.assertEqual(model_attack_warning(profile, boundary + 1, declared), not spare)
                self.assertTrue(model_attack_warning(profile, boundary + 2, declared))

    def test_current_workflow_partition(self):
        import json
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        check_workflow_groups((root / '.github/workflows/ci.yml').read_text(),
                              json.loads((root / 'src/pin.json').read_text())['profiles'])

    def test_suite_matrices_are_complete_without_a_profile_count_multiplier(self):
        import json
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        workflow = (root / '.github/workflows/ci.yml').read_text()
        profiles = json.loads((root / 'src/pin.json').read_text())['profiles']
        import re
        for name in ('focused', 'macos-regressions', 'macos-arm64-regressions'):
            marker = '\n  ' + name + ':\n'
            before, job = workflow.split(marker, 1)
            single = re.sub(r'^        suite_group: \[.*\]$',
                            '        suite_group: ["1/1"]', job, count=1, flags=re.M)
            check_workflow_groups(before + marker + single, profiles)
            job = re.sub(r'^        suite_group: \[.*\]$',
                         '        suite_group: ["1/2"]', job, count=1, flags=re.M)
            with self.subTest(job=name), self.assertRaisesRegex(ValueError, 'complete one-based matrix'):
                check_workflow_groups(before + marker + job, profiles)

    def test_growth_still_requires_complete_bounded_runtime_coverage(self):
        import json
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        workflow = (root / '.github/workflows/ci.yml').read_text()
        with self.assertRaisesRegex(ValueError, 'platform budget'):
            check_workflow_groups(workflow, [dict(build=str(n)) for n in range(248)])


if __name__ == '__main__':
    unittest.main()
