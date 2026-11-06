"""Check native initial light, shadow depth and bounce predicates by profile.

Complete entity display uses fixed queue observations and controlled terrain.
Raster services, palette contents and entity allocation have separate tests.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-visual-defaults-contracts.json'


class PixelCopyContracts(unittest.TestCase):
    def test_native_screen_and_sprite_copy_pixels(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-pixel-copy-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        engine = ROOT / 'src/engines' / data['engine'] / 'source/gamelib'
        routines = []
        for bits in (16, 32):
            routines.append(function((engine / ('screen%d.c' % bits)).read_text(),
                                     'putscreenx8p%d' % bits))
        for filename, names in [
            ('sprite.c', [('putsprite_flip_', 'sprite8_flip'),
                          ('putsprite_remap_', 'sprite8_remap'),
                          ('putsprite_remap_flip_', 'sprite8_remap_flip')]),
            ('spritex8p16.c', [('putsprite_', 'sprite16_copy'),
                             ('putsprite_flip_', 'sprite16_flip')]),
            ('spritex8p32.c', [('putsprite_', 'sprite32_copy'),
                             ('putsprite_flip_', 'sprite32_flip')]),
        ]:
            source = (engine / filename).read_text()
            for name, renamed in names:
                text = function(source, name)
                self.assertEqual(text.count(name + '('), 1)
                routines.append(text.replace(name + '(', renamed + '(', 1))
        text = Path(__file__).with_name('pixel_copy_contract.c.in').read_text()
        parts = {'FUNCTIONS': '\n'.join(routines),
                 'PROFILES': ','.join('{%du,%d,%d}' % (r['revision'], r['screen_copy_max'] or 0,
                                         r['blended_key_uses_zero_only32'])
                                      for r in rows)}
        for label, key, parameters in [('SCREEN_CASES', 'screen_cases', 'screen_parameters'),
                                        ('SPRITE_CASES', 'sprite_cases', 'sprite_parameters')]:
            parts[label] = ',\n'.join('{' + ','.join(str(c[k]) for k in data[parameters]) + '}'
                                      for c in data[key])
        for key, value in parts.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [{'revision': r['revision'],
                                  'screen_cases': len(data['screen_cases']) * 2,
                                  'sprite_cases': len(data['sprite_cases']) * 7} for r in rows])


def one(pattern, source, label):
    matches = re.findall(pattern, source, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('One native ' + label + ' required')
    return matches[0]


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    globals_header = (engine / 'source/globals.h').read_text()
    startup = function(core, 'openborMain')
    if not re.search(r'\{\s*obor_profile_debug_init\(\);\s*'
                     r'obor_profile_light_init\(\);', startup):
        raise ValueError('Native light initialization must precede game services')
    if len(re.findall(r'\bobor_profile_light_init\s*\(', startup)) != 1:
        raise ValueError('One native light initialization call required')
    display = function(core, 'display_ents')
    prefix = display[:display.index('for(i=0; i<ent_max; i++)')]
    setup = one(r'(if\([^\n]+\)\s*shadowz\s*=\s*SHADOW_Z;\s*'
                r'else\s*shadowz\s*=\s*MIN_INT\s*\+\s*100;)', prefix,
                'shadow depth selection')
    uses = re.findall(r'(?m)^\s*z\s*=\s*shadowz;', display)
    if len(uses) != 3 or re.search(r'\bz\s*=\s*SHADOW_Z\s*;', display):
        raise ValueError('Three native shadow depth consumers required')
    bounce = one(r'(^#define tobounce\(e\)[^\n]*\\\n[^\n]+)', header,
                 'bounce predicate')
    shadow = one(r'(^#define[ \t]+SHADOW_Z[ \t]+[^\n]+)', header, 'shadow macro')
    minimum = one(r'(^#define[ \t]+MIN_INT[ \t]+[^\n]+)', globals_header,
                  'minimum depth macro')
    unload = function(core, 'unload_level')
    reset = '\n'.join(one(r'(^\s*light\[' + str(i) + r'\]\s*=[^;\n]+;)',
                         unload, 'light reset') for i in range(2))
    parts = dict(
        MACROS='\n'.join((bounce, shadow, minimum)),
        FUNCTIONS=function(core, 'diff') + '\n' + function(core, 'obor_profile_light_init'),
        SHADOW_SETUP=setup,
        SHADOW_USES='\n'.join(use + 'emit_int(z);' for use in uses),
        RESET=reset,
        PROFILES=','.join(str(r['revision']) + 'u' for r in data['sources']),
        VELOCITIES=','.join(str(v) + 'f' for v in data['velocities']),
        DEPTHS=','.join(str(v) for v in data['depths']),
        DAMAGES=','.join(str(v) for v in data['damage_on_landing']))
    text = Path(__file__).with_name('visual_defaults_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved visual defaults dependency')
    return text


def expected(data, row):
    contract = data['contracts'][row['contract']]
    bounce = [int(bool(enabled) and abs(velocity) > contract['bounce_threshold'] and
                  not ((autoland == 1 and damage == -1) or damage == -2))
              for enabled in (0, 1) for autoland in (0, 1)
              for damage in data['damage_on_landing'] for velocity in data['velocities']]
    shadows = [(-2147483648 + 100 if not level and contract['empty_level_shadow'] == 'minimum'
                else depth - 48)
               for level in (0, 1) for depth in data['depths'] for _ in range(3)]
    return dict(revision=row['revision'], initial=contract['initial_light'],
                reset=contract['unload_light'], bounce=bounce, shadows=shadows)


class VisualDefaultsContracts(unittest.TestCase):
    def test_native_display_alpha_and_table_selection_order(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-display-alpha-contracts.json')
        profiles, cases = data['sources'], data['cases']
        self.assertEqual(len(profiles), len({r['revision'] for r in profiles}))
        self.assertEqual({r['revision'] for r in profiles},
                         contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in profiles})
        self.assertTrue(all(type(r['contract']) is int and 0 <= r['contract'] < 3 for r in profiles))
        self.assertTrue(cases)
        self.assertEqual(len(cases), len({r['name'] for r in cases}))
        entries = []
        for case in cases:
            keys = ('initial_table', 'draw_alpha', 'model_alpha', 'remap',
                    'entity_colourmap', 'globalmap', 'level', 'current_palette')
            values = [case[k] for k in keys]
            self.assertTrue(all(type(v) is int for v in values))
            self.assertTrue(all(case[k] in (0, 1) for k in keys
                                if k not in ('draw_alpha', 'remap')))
            self.assertTrue(-8 <= case['draw_alpha'] <= 7)
            self.assertIn(case['remap'], (-1, 0, 1))
            self.assertEqual(len(case['expected']), 3)
            self.assertTrue(all(len(row) == 3 and all(type(v) is int for v in row)
                                for row in case['expected']))
            entries.append('{' + ','.join([json.dumps(case['name']), *map(str, values),
                '{' + ','.join('{' + ','.join(map(str, row)) + '}'
                              for row in case['expected']) + '}']) + '}')
        engine = ROOT / 'src/engines' / data['engine']
        display = function((engine / 'openbor.c').read_text(), 'display_ents')
        marker = 'drawmethod = &commonmethod;'
        self.assertEqual(display.count(marker), 1)
        start = display.index(marker) + len(marker)
        selection = display[start:display.index('if(e->dying)', start)]
        self.assertTrue(0 < len(selection) <= 16384)
        text = Path(__file__).with_name('display_alpha_contract.c.in').read_text()
        parts = dict(SELECT=selection, BLEND_COUNT=function(
            (engine / 'source/gamelib/pixelformat.c').read_text(), 'obor_profile_blend_count'),
            PROFILES=','.join('{%du,%d}' % (r['revision'], r['contract']) for r in profiles),
            CASES=',\n'.join(entries))
        for key, value in parts.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [{'revision': r['revision'], 'cases': len(cases)} for r in profiles])

    def test_native_entity_display_coordinates_depth_and_order(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-entity-display-contracts.json')
        profiles, cases, contracts = data['sources'], data['cases'], data['contracts']
        self.assertEqual(len(profiles), len({r['revision'] for r in profiles}))
        self.assertEqual({r['revision'] for r in profiles},
                         contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in profiles})
        self.assertTrue(cases)
        self.assertEqual(len(cases), len({r['name'] for r in cases}))
        self.assertEqual(len(contracts), len({r['key'] for r in contracts}))
        entries, observations = [], []
        for case in cases:
            ints = [case[k] for k in ('shadow', 'surface', 'direction', 'level', 'mirror',
                                     'vertical', 'relation', 'layer', 'hole')]
            self.assertTrue(all(type(v) is int and 0 <= v <= 16 for v in ints))
            self.assertEqual(len(case['advances']), 2)
            self.assertEqual(len(case['offsets']), 2)
            self.assertTrue(all(type(v) in (int, float) and -32768 <= v <= 32767
                                for v in case['advances'] + case['offsets']))
            entries.append('{' + ','.join([json.dumps(case['name']), *map(str, ints),
                *map(str, case['advances']), *map(str, case['offsets'])]) + '}')
        for contract in contracts:
            self.assertEqual(len(contract['expected']), len(cases))
            rows = []
            for result in contract['expected']:
                self.assertLessEqual(len(result), 6)
                self.assertTrue(all(len(row) == 5 and all(type(v) is int and
                    -2147483648 <= v <= 2147483647 for v in row) for row in result))
                rows.append('{%d,{%s}}' % (len(result), ','.join(
                    '{' + ','.join(map(str, row)) + '}' for row in result)))
            observations.append('{' + ','.join(rows) + '}')
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        plain = one(r'(^const s_drawmethod plainmethod\s*=\s*\{[^;]+\};)',
                    core, 'native plain draw method')
        parts = dict(DISPLAY=function(core, 'display_ents'), PLAIN=plain,
            CASES=',\n'.join(entries), EXPECTED=',\n'.join(observations),
            PROFILES=','.join('{%du,%d}' % (r['revision'], next(i for i, c in
                enumerate(contracts) if c['key'] == r['contract'])) for r in profiles),
            MIN_Z=str(data['geometry']['player_min_z']), MAX_Z=str(data['geometry']['player_max_z']),
            CAPACITY=str(data['geometry']['physical_capacity']),
            LEGACY_CAPACITY=str(data['geometry']['legacy_capacity']))
        text = Path(__file__).with_name('entity_display_contract.c.in').read_text()
        for key, value in parts.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [{'revision': r['revision'], 'cases': len(cases)} for r in profiles])

    def test_native_light_shadow_depth_and_bounce_for_each_profile(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']))
        for result, row in zip(actual, data['sources']):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, expected(data, row))


if __name__ == '__main__':
    unittest.main()
