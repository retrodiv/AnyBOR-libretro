"""Controls for the real-frontend rewind performance gate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import csv
from pathlib import Path
import tempfile
import unittest

from check_frontend_cadence import compare, measure


class FrontendCadenceTests(unittest.TestCase):
    def profile(self, directory, name, fps=60, rewind=False, failed=False,
                skip_frame=None, granularity=10):
        path = Path(directory) / (name + '.csv')
        with path.open('w', newline='') as stream:
            fields = ('event', 'frame', 'begin_ns', 'core_end_ns', 'end_ns',
                      'capacity', 'written', 'heap', 'ok', 'context')
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for frame in range(1000, 2001):
                if frame == skip_frame:
                    continue
                now = round(frame * 1e9 / fps)
                writer.writerow(dict(event='run', frame=frame, begin_ns=now,
                                     core_end_ns=now+400000, end_ns=now+1000000,
                                     capacity=0, written=0, heap=0, ok=1, context=0))
                if rewind and frame % granularity == 0:
                    writer.writerow(dict(event='serialize', frame=frame,
                                         begin_ns=now+1000000, core_end_ns=now+6000000,
                                         end_ns=now+6000000, capacity=134217728,
                                         written=0 if failed else 64000000, heap=0,
                                         ok=0 if failed else 1, context=0))
        return path

    def test_fast_core_does_not_hide_frontend_regression(self):
        with tempfile.TemporaryDirectory() as temp:
            control = measure(self.profile(temp, 'off'), 1000, 2000)
            for fps in (58, 59, 59.95, 200):
                with self.subTest(fps=fps):
                    candidate = measure(self.profile(temp, 'on', fps, True), 1000, 2000, 10)
                    if fps == 59.95:
                        self.assertTrue(compare(control, candidate)['passed'])
                    else:
                        with self.assertRaises(ValueError):
                            compare(control, candidate)

    def test_missing_failed_or_disabled_captures_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            for options in ({}, dict(rewind=True, failed=True),
                            dict(rewind=True, granularity=20),
                            dict(rewind=True, skip_frame=1503)):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    measure(self.profile(temp, 'invalid', **options), 1000, 2000, 10)

    def test_fast_forward_is_not_a_control(self):
        with self.assertRaises(ValueError):
            compare(dict(fps=200), dict(fps=60))


if __name__ == '__main__':
    unittest.main()
