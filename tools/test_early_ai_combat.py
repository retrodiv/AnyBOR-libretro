"""Check source-defined AI item/attack choices, actions, timing and RNG calls.

Actual decision functions run with finite target, animation, energy, spawning
and script providers. This is not whole AI movement, physics or game acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-ai-combat.json'
FUNCTIONS = ['normal_find_item', 'common_try_runattack', 'common_try_normalattack',
             'common_try_jumpattack', 'common_runoff', 'common_attack_finish']


class EarlyAICombatTests(unittest.TestCase):
    def test_registry_and_source_controls(self):
        fixture = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in fixture['sources']:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']), set(FUNCTIONS))
            for value in row['source_sha256'].values():
                self.assertRegex(value, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_decisions_actions_timing_and_service_order(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        speed = re.search(r'(?m)^#define\s+GAME_SPEED\s+\d+\b[^\n]*', header)
        self.assertIsNotNone(speed)
        bodies = '\n'.join(function(core, name) for name in ['diff', *FUNCTIONS])
        checks = '\n'.join('check(%d,%d,%d);' % (r['revision'], r['modern_decisions'], r['game_speed'])
                           for r in fixture['sources'])
        ranges = ',\n'.join('{%s}' % ','.join(str(row[k]) for k in
            ('width', 'distance', 'old', 'modern')) for row in fixture['item_ranges'])
        delays = ',\n'.join('{%s}' % ','.join(str(row[k]) for k in
            ('aggression', 'old', 'modern')) for row in fixture['finish_delays'])
        code = (FIXTURE.parent / 'early_ai_combat.c').read_text()
        for key, value in dict(FUNCTIONS=bodies, SPEED=speed[0], CHECKS=checks,
                               RANGES=ranges, DELAYS=delays).items():
            code = code.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-ai-combat-') as directory:
            source, binary = Path(directory) / 'probe.c', Path(directory) / 'probe'
            source.write_text(code)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            compile_checked(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu11', '-O0', '-g', '-fsigned-char', '-fno-omit-frame-pointer',
                '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                str(source), *links, '-o', str(binary)])
            result = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30,
                                    env=sanitizer_environment())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('early_ai_combat=1', result.stdout)


if __name__ == '__main__':
    unittest.main()
