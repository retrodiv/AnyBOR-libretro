"""Check native playable-list refusal and preserved valid selection behavior.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import copy
import unittest

from historical_playable_models import render_playable_models
from test_model_constructor_ownership import run_native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class PlayableModelValidationTests(unittest.TestCase):
    def test_valid_selection_and_both_controlled_stop_modes(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for engine in pin['engines']:
            profiles = [p for p in pin['profiles'] if p['engine'] == engine['build']]
            fixture = dict(
                sources=[dict(profile=p['build'],
                              revision=int(p.get('revision', p['build'].split('-')[0])),
                              # The own-source reset change begins at3559.
                              reset_all_on_zero=int(p.get('revision', p['build'].split('-')[0])) >= 3559)
                         for p in profiles],
                missing_message="Player model '%s' is not loaded.\n",
                cache_message="Player model '%s' is not cached.\n",
                returning_stop_control=True, emit_counts=True)
            with self.subTest(engine=engine['build']):
                text = render_playable_models(ROOT / 'src/engines' / engine['build'],
                                              ROOT / 'src/port/libretro/libretroport.c', fixture)
                result = run_native(ROOT / 'src/engines' / engine['build'], text)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(profiles=len(profiles), scenarios=12*len(profiles)))

    def test_refuses_invalid_contexts(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / pin['engines'][0]['build']
        fixture = dict(sources=[dict(profile='bounded', revision=1)],
                       missing_message="Player model '%s' is not loaded.\n",
                       cache_message="Player model '%s' is not cached.\n")
        invalid = []
        value = copy.deepcopy(fixture);value['sources'] *= 2;invalid.append(value)
        value = copy.deepcopy(fixture);value['sources'][0]['profile'] = {};invalid.append(value)
        value = copy.deepcopy(fixture);value['sources'][0]['revision'] = 0;invalid.append(value)
        value = copy.deepcopy(fixture);value['returning_stop_control'] = 'yes';invalid.append(value)
        value = copy.deepcopy(fixture);value['sources'][0]['reset_all_on_zero'] = 1;invalid.append(value)
        value = copy.deepcopy(fixture);value['sources'] = [
            dict(profile=str(i), revision=i+1) for i in range(129)];invalid.append(value)
        for value in invalid:
            with self.assertRaises(ValueError):
                render_playable_models(engine, ROOT / 'src/port/libretro/libretroport.c', value)


if __name__ == '__main__':
    unittest.main()
