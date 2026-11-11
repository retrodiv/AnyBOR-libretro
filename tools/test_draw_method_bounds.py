"""Check native drawing-method tables with both historical assertion policies.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_header_fixtures import assertion_refusals
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/profile-draw-diagnostics.json'


def diagnostic_profiles(pin):
    return contract_profiles(load_contract_fixture(FIXTURE), pin['profiles'])


def display_lookup(source):
    display = function(source, 'display_ents')
    masked = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\r\n]*|/\*.*?\*/',
                    lambda m: re.sub(r'[^\r\n]', ' ', m.group()), display, flags=re.S)
    matches = list(re.finditer(
        r'drawmethod\s*=\s*e->animation->drawmethods\s*\?[^;]*;', masked))
    if len(matches) != 1:
        raise ValueError('One active native drawing-method lookup required')
    return display[matches[0].start():matches[0].end()]


def program(engine, profiles, *, release=False, remove_guard=False,
            tamper_line=False, refuse_assertions=False):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    methods = function(source, 'setDrawMethod') + '\n' + function(source, 'getDrawMethod')
    if remove_guard:
        guard = 'if(!a || index < 0 || index >= a->numframes || !a->drawmethods) return NULL;'
        if methods.count(guard) != 1:
            raise ValueError('One native table-read guard required')
        methods = methods.replace(guard, '', 1)
    # The oldest family has a production hook carrying its source-owned
    # diagnostics. Other families use their actual globals/port assertion policy.
    hook = ''
    if '#include "obor_frame_assert.h"' in source:
        hooks = re.findall(r'(?m)^#define assert\(value\)[^\n]*', source)
        if len(hooks) != 2 or len(set(hooks)) != 1:
            raise ValueError('Actual paired frame assertion hooks required')
        hook = '#include "obor_frame_assert.h"\n#undef assert\n' + hooks[0]
    utils = (engine / 'source/utils.c').read_text(encoding='latin1')
    port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
    fixture = load_contract_fixture(FIXTURE)
    oracles = {(row['engine'], row['profile']): row for row in fixture['sources']}
    if len(oracles) != len(fixture['sources']):
        raise ValueError('Unique own-source drawing identities required')
    contexts = []
    for profile in profiles:
        row = oracles.get((engine.name, profile['build']))
        revision = int(profile.get('revision', profile['build'].split('-')[0]))
        if (row is None or row['revision'] != revision or len(row['lines']) != 7 or
                any(type(n) is not int or not 0 <= n < 1000000 for n in row['lines']) or
                type(row['logged']) is not bool):
            raise ValueError('Explicit own-source drawing coordinates and policy required')
        lines = list(row['lines'])
        if tamper_line:
            lines[0] += 1
        contexts.append('{%du,%d,%d,{%s}}' % (revision, any(row['lines']), row['logged'],
                                             ','.join(str(n)+'u' for n in lines)))
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
                  ASSERTION_POLICY='#define NDEBUG 1' if release else '#undef NDEBUG',
                  STOP=function(port, 'borExit'), PORT_ASSERT=function(port, 'obor_port_assert'),
                  NATIVE_ASSERT=function(utils, 'exitIfFalse') if 'void exitIfFalse(' in utils else '',
                  HOOK=hook, METHODS=methods, LOOKUP=display_lookup(source), CONTEXTS=','.join(contexts))
    if refuse_assertions:
        values.update(PORT_ASSERT=assertion_refusals(), NATIVE_ASSERT='')
    text = (HERE / 'draw_method_bounds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class DrawMethodBoundsTests(unittest.TestCase):
    def test_native_tables_in_each_profile_and_assertion_mode(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            profiles = [p for p in diagnostic_profiles(pin) if p['engine'] == row['build']]
            engine = ROOT / 'src/engines' / row['build']
            for release in (False, True):
                with self.subTest(engine=row['build'], release=release):
                    result = run_native(engine, program(engine, profiles, release=release))
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertEqual(json.loads(result.stdout),
                                     dict(profiles=len(profiles), cases=27*len(profiles)))

    def test_missing_read_guard_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = next(row for row in pin['engines'] if row['build'] != pin['engines'][0]['build'])
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == row['build'])
        # Spare physical slots keep this control bounded. A logical frame-end
        # lookup must be rejected even when assertions are disabled.
        result = run_native(engine, program(engine, [profile], release=True, remove_guard=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('draw-method contract', result.stderr)

    def test_assertion_policy_boundary_preserves_full_diagnostics(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = [r for r in fixture['sources'] if r['revision'] in fixture['boundary_controls']]
        self.assertEqual({r['revision'] for r in rows}, set(fixture['boundary_controls']))
        engine = ROOT / 'src/engines' / rows[0]['engine']
        self.assertTrue(all(r['engine'] == engine.name for r in rows))
        profiles = [dict(build=r['profile'], revision=r['revision']) for r in rows]
        for release in (False, True):
            result = run_native(engine, program(engine, profiles, release=release))
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout), dict(profiles=len(rows), cases=27*len(rows)))

    def test_incorrect_source_coordinate_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][1]
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in diagnostic_profiles(pin) if p['engine'] == row['build'])
        result = run_native(engine, program(engine, [profile], tamper_line=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('draw-method contract', result.stderr)

    def test_isolated_contract_refuses_unexpected_assertion(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][1]
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in diagnostic_profiles(pin) if p['engine'] == row['build'])
        result = run_native(engine, program(engine, [profile], refuse_assertions=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected native assertion in valid-only contract', result.stderr)


if __name__ == '__main__':
    unittest.main()
