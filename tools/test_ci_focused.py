"""Keep complete, unique suite coverage and refuse unbounded execution plans.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci_focused import load_suites, select_suites, completed_test_failure, run_suites, verify_workflow, workflow_job
# unittest collects the imported controls in this shared CI suite as well.
from test_profile_groups import ProfileGroupsTests


class FocusedPlanTests(unittest.TestCase):
    def test_workflow_covers_each_shared_partition_and_keeps_native_proxy_tests(self):
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        workflow = (root / '.github/workflows/ci.yml').read_text()
        self.assertEqual(verify_workflow(workflow, load_suites()), ['1/4', '2/4', '3/4', '4/4'])
        for bad in (workflow.replace('"1/4", ', '', 1),
                    workflow.replace('run_check python3 tools/test_native_sanitizers.py\n', '', 1),
                    workflow.replace('        suite_group: ["1/4", "2/4", "3/4", "4/4"]',
                                     '        suite_group: ["1/4", "2/4", "3/4"]'),
                    workflow.replace('      ANYBOR_CI_SUITE_GROUP: ${{ matrix.suite_group }}\n', '', 1),
                    workflow.replace(' --output .build/ci-focused\n',
                                     ' --output .build/ci-focused\n          python3 tools/unguarded.py\n', 1)):
            with self.assertRaises(ValueError):
                verify_workflow(bad, load_suites())

    def test_runtime_jobs_wait_only_for_their_actual_artifact_producer(self):
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        workflow = (root / '.github/workflows/ci.yml').read_text()
        for platform, target in (('linux', 'linux-x86_64'), ('windows', 'windows-x86_64')):
            job = workflow_job(workflow, 'state-' + platform)
            self.assertIn('    needs: build-' + platform + '\n', job)
            producer = workflow_job(workflow, 'build-' + platform)
            self.assertIn('target: ["' + target + '"]', producer)
            self.assertNotIn('needs: build-cross', job)
        self.assertIn('steps: &ubuntu-build-steps', workflow_job(workflow, 'build-linux'))
        for job in ('build-windows', 'build-cross'):
            self.assertIn('steps: *ubuntu-build-steps', workflow_job(workflow, job))
        self.assertIn('    needs: macos\n', workflow_job(workflow, 'state-macos'))
        self.assertIn('    needs: macos-arm64\n', workflow_job(workflow, 'state-macos-arm64'))
        self.assertIn('steps: *native-macos-state-steps', workflow_job(workflow, 'state-macos-arm64'))
        self.assertIn('steps: *native-macos-build-steps', workflow_job(workflow, 'macos-arm64'))
        self.assertIn('steps: *native-macos-regression-steps', workflow_job(workflow, 'macos-arm64-regressions'))
        self.assertNotIn('apt-get', workflow)

    def test_every_shared_suite_occurs_once_across_groups_and_local_keeps_native_proxies(self):
        suites = load_suites()
        shared = select_suites(suites)
        local = select_suites(suites, local=True)
        self.assertEqual(local, suites)
        self.assertEqual({r['id'] for r in local} - {r['id'] for r in shared},
                         {'test_native_sanitizers', 'test_ci_regressions'})
        for count in (1, 2, 4, len(shared)):
            groups = [select_suites(suites, str(n) + '/' + str(count)) for n in range(1, count + 1)]
            observed = [r['id'] for group in groups for r in group]
            self.assertEqual(sorted(observed), sorted(r['id'] for r in shared))
            self.assertEqual(len(observed), len(set(observed)))
            self.assertTrue(all(groups))

    def test_invalid_partition_never_silently_drops_suites(self):
        suites = load_suites()
        for group in ('', '0/4', '1/0', '5/4', '01/4', '1/04', '1', '1/99999', ' 1/4'):
            with self.subTest(group=group), self.assertRaises(ValueError):
                select_suites(suites, group)

    def test_mutated_plan_refuses_commands_limits_duplicates_and_unknown_fields(self):
        original = dict(schema=1, suites=load_suites())
        mutations = []
        for key, value in (('memory_mib', 99999), ('seconds', 0), ('seconds', True),
                           ('command', ['bash', '-c', 'true']), ('ci', 'unknown')):
            data = copy.deepcopy(original)
            data['suites'][0][key] = value
            mutations.append(data)
        data = copy.deepcopy(original)
        data['suites'].append(copy.deepcopy(data['suites'][0]))
        mutations.append(data)
        data = copy.deepcopy(original)
        data['suites'][0]['unguarded'] = True
        mutations.append(data)
        mutations.extend((dict(schema=1, suites=[]), dict(schema=True, suites=original['suites'])))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.json'
            for data in mutations:
                with self.subTest(data=str(data)[:80]), self.assertRaises(ValueError):
                    path.write_text(json.dumps(data))
                    load_suites(path)
            for raw in (b'{"schema":1,"schema":1,"suites":[]}', b'x' * ((256 << 10) + 1)):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    load_suites(path)

    def exercise(self, folder, outcomes):
        calls = []
        suites = [dict(id='case-' + str(i), command=['python3', 'tools/test_case.py'],
                       memory_mib=512, seconds=60) for i in range(len(outcomes))]

        def execute(command, **kwargs):
            calls.append(command)
            code, output = outcomes[len(calls) - 1]
            kwargs['stdout'].write(output)
            return subprocess.CompletedProcess(command, code)

        def run():
            with patch('ci_focused.subprocess.run', side_effect=execute), contextlib.redirect_stdout(io.StringIO()):
                return run_suites(suites, Path(folder) / 'evidence', root=Path(folder))
        return calls, run

    def test_completed_failures_collect_every_suite_and_still_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            failed = (1, 'Ran 1 test in 0.1s\n\nFAILED (failures=1)\n')
            calls, run = self.exercise(temp, [failed, (0, 'OK\n'), failed])
            with self.assertRaisesRegex(RuntimeError, 'case-0.*case-2'):
                run()
            self.assertEqual(len(calls), 3)
            self.assertTrue(all('--memory-mib' in cmd and '--seconds' in cmd for cmd in calls))
            receipt = json.loads((Path(temp) / 'evidence/results.json').read_text())
            self.assertTrue(receipt['complete'])
            self.assertEqual(receipt['failed'], ['case-0', 'case-2'])

    def test_resource_guard_and_incomplete_failures_stop_immediately(self):
        failed = 'Ran 1 test in 0.1s\n\nFAILED (errors=1)\n'
        for code, output in ((137, failed), (124, failed), (1, 'Guard timeout\n' + failed),
                             (1, 'MemoryError\n' + failed), (1, 'internal compiler error\n' + failed),
                             (1, 'SIGBUS\n' + failed), (1, 'No completed unittest result\n')):
            with self.subTest(code=code, output=output), tempfile.TemporaryDirectory() as temp:
                calls, run = self.exercise(temp, [(code, output), (0, 'OK\n')])
                with self.assertRaises(RuntimeError):
                    run()
                self.assertEqual(len(calls), 1)
                self.assertFalse(json.loads((Path(temp) / 'evidence/results.json').read_text())['complete'])

    def test_success_requires_every_declared_suite_and_keeps_timings(self):
        with tempfile.TemporaryDirectory() as temp:
            calls, run = self.exercise(temp, [(0, 'first\n'), (0, 'second\n')])
            result = run()
            self.assertEqual(len(calls), 2)
            self.assertTrue(result['complete'])
            self.assertFalse(result['failed'])
            self.assertTrue(all(r['elapsed_seconds'] >= 0 and len(r['log_sha256']) == 64
                                for r in result['results']))


if __name__ == '__main__':
    unittest.main()
