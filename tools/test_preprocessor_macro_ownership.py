"""Check complete native macro refusal cleanup and parameter diagnostics.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from test_preprocessor_concatenation import ROOT, compile_native, program


def case(source, *, accepted=True, tokens='', diagnostic=''):
    return dict(source=source, accepted=accepted, tokens=tokens, diagnostic=diagnostic, exact='')


CASES = [
    case('#define OBJECT 7\nOBJECT\n', tokens='7'),
    case('#define FIRST(a,b) a\nFIRST(2,3)\n', tokens='2'),
    case('#define BAD(a,4) a\n', accepted=False,
         diagnostic="unexpected token '4' in #define parameter list"),
    case('#define TWO(a,b) a\nTWO(' + 'x + ' * 300 + 'x,2)\n', accepted=False,
         diagnostic="parameter 1 of function 'TWO' exceeds max length of 1023 characters"),
    case('#define TWO(a,b) a\nTWO(1,' + 'x + ' * 300 + 'x)\n', accepted=False,
         diagnostic="parameter 2 of function 'TWO' exceeds max length of 1023 characters"),
    case('#define TWO(a,b) a\nTWO(1)\n', accepted=False,
         diagnostic="not enough parameters to function 'TWO'"),
    case('#define TWO(a,b) a\nTWO(1,2,3)\n', accepted=False,
         diagnostic="too many parameters to function 'TWO'"),
    case('#define TWO(a,b) a\nTWO(1,2', accepted=False,
         diagnostic="unexpected end of file in parameter list for function 'TWO'"),
]


class MacroOwnershipTests(unittest.TestCase):
    def test_native_refusal_cleanup_and_diagnostics_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for engine in pin['engines']:
            build = engine['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                source = ROOT / 'src/engines' / build
                case_sets = {}
                for profile in profiles:
                    revision = int(profile.get('revision', profile['build'].split('-')[0]))
                    # Native counter increment order changes in the newer
                    # collector. Retain its own value in the diagnostic.
                    counter = int(build in ('3400', '3741') or build == '3842' and revision < 3802)
                    records = [dict(c) for c in CASES]
                    records[3]['diagnostic'] = (
                        "parameter %d of function 'TWO' exceeds max length of 1023 characters" % counter)
                    records[4]['diagnostic'] = (
                        "parameter %d of function 'TWO' exceeds max length of 1023 characters" % (counter + 1))
                    case_sets[profile['build']] = records
                result = compile_native(source, program(source, profiles, CASES, case_sets))
                revisions = {int(p.get('revision', p['build'].split('-')[0])) for p in profiles}
                self.assertEqual(result, dict(contexts=len(revisions),
                                              cases=len(profiles) * len(CASES), status='PASS'))

    def test_case_records_refuse_missing_or_unbounded_fields(self):
        valid = CASES[0]
        invalid = [[], {}, [dict(valid, accepted=1)], [dict(valid, source='x' * 8193)],
                   [dict(valid, extra='field')], [dict(valid, tokens=None)]]
        for records in invalid:
            with self.subTest(records=type(records).__name__), self.assertRaises(ValueError):
                program(Path('not-opened'), [], records)
        for mapping in ([], {}, {1: CASES}, {'': CASES}, {'x' * 81: CASES}, {'build': []}):
            with self.subTest(mapping=type(mapping).__name__), self.assertRaises(ValueError):
                program(Path('not-opened'), [], CASES, mapping)
        with self.assertRaisesRegex(ValueError, 'Required native preprocessor'):
            compile_native(Path('not-opened'), 'not compiled')


if __name__ == '__main__':
    unittest.main()
