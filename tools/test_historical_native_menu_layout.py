"""Compare native menu frame routes and draws with source-owned views.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from historical_menu_layout import frame_prefix
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-native-menu-layout-contracts.json'
PLATFORMS = ('SDL', 'PSP', 'WII', 'DC', 'GP2X', 'OPENDINGUX', 'ANDROID')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own menu sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Original menu identities required')
    return data


def expected(row, scene, platform, menu):
    """Independent logical draw lists transcribed from each original view."""
    v, s = row['view'], scene
    draws, flags = [], [0] * 5
    def mid(font, y, text): draws.append([0, font, 0, y, text])
    def col(font, x, y, text): draws.append([1, font, x, y, text])
    def enabled(value): return 'Enabled' if value else 'Disabled'
    def on(value): return 'On' if value else 'Off'
    if menu == 'input':
        flags[2] = 1
        mid(2, v['input_col'] - 1, 'Control Options')
        if platform in ('psp', 'wii'):
            col(0, -4, -2, ('Analog Pad ' if platform == 'psp' else 'Nunchuk Analog ') + enabled(s['usejoy']))
        else:
            col(0, v['input_col'], -2, 'GamePads ' + enabled(s['usejoy']))
            if s['usejoy'] and not s['joy']:
                col(0, v['input_col'] + 11, -2, ' - Device Not Ready')
        for i in range(4): col(int(i == 0), v['input_col'], i - 1, 'Setup Player %d...' % (i + 1))
        mid(0, v['input_back'], 'Back')
    elif menu == 'video':
        flags[3] = 1
        a, b = v['video_col1'], v['video_col2']
        mid(2, -5, 'Video Options')
        for i, (name, value) in enumerate((('Brightness:', 3), ('Gamma:', 4), ('Window Offset:', 5))):
            col(int(i == 0), a, i - 3, name); col(int(i == 0), b, i - 3, str(value))
        if platform == 'opendingux':
            col(0, a, 0, 'Display Mode:'); col(0, b, 0, 'Full' if s['fullscreen'] else 'Window'); mid(0, 6, 'Back')
        elif platform in ('dreamcast', 'gp2x'):
            mid(0, 6, 'Back')
        elif platform == 'wii':
            col(0, a, 0, 'Display Mode:'); col(0, b, 0, 'Stretch to Screen' if s['stretch'] else 'Preserve Aspect Ratio'); mid(0, 6, 'Back')
        elif platform == 'sdl':
            col(0, a, 0, 'Display Mode:'); col(0, b, 0, 'Full' if s['fullscreen'] else 'Window')
            col(0, a, 1, 'Video Backend:'); col(0, b, 1, 'OpenGL')
            col(0, a, 2, 'Scale:')
            col(0, b, 2, 'Automatic' if s['fullscreen'] else '%4.2fx - %ix%i' %
                (s['scale'], int(320 * s['scale']), int(240 * s['scale'])))
            col(0, a, 3, 'Hardware Filter:')
            col(0, b, 3, ('Simple' if s['filter'] else 'Bilinear') if s['scale'] != 1 or s['fullscreen'] else 'Disabled')
            col(0, a, 4, 'Software Filter:')
            col(0, b, 4, ('Nearest' if not s['swfilter'] else 'Filter') if s['scale'] >= 2 or s['fullscreen'] else 'Disabled')
            if s['fullscreen']:
                col(0, a, 5, 'Fullscreen Type:'); col(0, b, 5, 'Stretch to Screen' if s['stretch'] else 'Preserve Aspect Ratio')
            mid(0, 7, 'Back')
        elif platform == 'psp':
            for y, name, value in ((0, 'Screen:', 'Window'), (1, 'Filters:', 'Filter%d' % s['filter']),
                                   (2, 'Display:', 'Display%d' % s['stretch'])):
                col(0, a, y, name); col(0, b, y, value)
            col(0, a, 3, 'Overscan:')
            for x in (1.5, 3.5, 5.5): col(0, b + x, 3, '.')
            for i in range(4): col(0, b + i * 2, 3, '%02d' % (i + 1))
            mid(0, 6, 'Back')
    elif menu == 'debug':
        if not v['debug_present']: return None
        mid(2, v['debug_title'], 'Debug Settings')
        items = [('Performance:', 0), ('Position:', 1)]
        if v['debug_features']: items.append(('Features:', 2))
        items += [('Collision Attack:', 3), ('Collision Body:', 4), ('Range:', 5)]
        for i, (name, bit) in enumerate(items):
            y = v['debug_title'] + 2 + i
            col(int(i == 0), v['debug_col1'], y, name)
            col(int(i == 0), v['debug_col2'], y, enabled(s['debug'] & (1 << bit)))
        mid(0, v['debug_back'], 'Back')
    elif menu == 'system':
        flags[4] = 1
        a, b = v['system_col1'], v['system_col2']
        mid(2, -6, 'System Options')
        for y, name, value in ((-4, 'Total RAM:', '123'), (-3, 'Used RAM:', '45')):
            col(0, a, y, name); col(0, b, y, value + ' ' + v['system_units'])
        if v['system_early']:
            col(1, a, -2, 'Debug Info:'); col(1, b, -2, enabled(s['debug'] & 1))
            col(0, a, -1, 'File Logging:'); col(0, b, -1, enabled(s['mode']))
            col(0, a, 0, 'Players:'); col(0, b, 0, '4 by Mod')
            damage_y, cheat_y, config_y = 1, 2, 3
        else:
            col(0, a, -2, 'Max Players:'); col(0, b, -2, '4')
            col(1, a, -1 + v['system_shift'], 'File Logging:')
            col(1, b, -1 + v['system_shift'], enabled(s['mode']))
            damage_y, cheat_y, config_y = v['system_shift'], 1 + v['system_shift'], 3 + v['system_shift']
        mod = 'Mod' if v['system_early'] else 'Module'
        damage = ('Disabled' if s['versus'] == 0 else 'Enabled') + ' by ' + mod
        if s['versus'] > 1: damage = 'Disabled' if s['mode'] else 'Enabled'
        col(0, a, damage_y, 'Versus Damage:'); col(0, b, damage_y, damage)
        col(0, a, cheat_y, 'Cheats:')
        col(0, b, cheat_y, 'Disabled by ' + mod if s['force'] else on(s['cheats']))
        excluded = int(bool(v['system_gate'] and s['nodebug']))
        if not v['system_early'] and not excluded:
            col(0, a, 2 + v['system_shift'], 'Debug Settings...')
        if platform != 'dreamcast':
            col(0, a, config_y - excluded, 'Config Settings' if v['system_early'] else 'Config Settings...')
        if platform == 'psp':
            col(0, a, 4 - excluded, 'CPU Speed:'); col(0, b, 4 - excluded, '222 MHz')
            if s['power']:
                col(0, a, 5 - excluded, 'Charging:'); col(0, b, 5 - excluded, '%d%% AC Power' % s['battery'])
            else:
                col(0, a, 5 - excluded, 'Battery:')
                text = 'Calculating...' if s['battery'] < 0 or s['life'] < 0 else '%d%% - %02d:%02d' % (s['battery'], s['life'] // 60, s['life'] % 60)
                col(0, b, 5 - excluded, text)
        mid(0, (7 if v['system_shift'] else 6) - excluded, 'Back')
    else:
        active = bool(s['cheats'] and not s['force'])
        if not v['root_merged'] and active:
            flags[1] = 1; mid(2, -5, 'Cheat Options')
            for i, (label, value) in enumerate((('Brightness:', '3'), ('Gamma:', '4'))):
                col(int(i == 0), -8, i - 3, label); col(int(i == 0), 6, i - 3, value)
            for i, text in enumerate(('Control Options...', 'Sound Options...', 'System Options...')): col(0, -8, i - 1, text)
            for i, text in enumerate(('Lives', 'Credits', 'Health')): col(0, -8, i + 2, 'Infinite ' + text + ' ' + on(s['infinite'] & (1 << i)))
            mid(0, 6, 'Back')
        elif not v['root_merged']:
            flags[0] = 1; mid(2, -1, 'Options')
            for i, text in enumerate(('Video Options...', 'Sound Options...', 'Control Options...', 'System Options...')): mid(int(i == 0), i + 1, text)
            mid(0, 6, 'Back')
        else:
            flags[0] = 1
            y = -1 - 3 * active + (v['root_pause_shift'] if active and s['level'] and s['pause'] > 0 else 0)
            mid(2, y - 1, 'Cheat Options' if active else 'Options')
            for i, text in enumerate(('Video Options...', 'Sound Options...', 'Control Options...', 'System Options...')): mid(int(i == 0), y + i, text)
            gap = v['root_spacer'] if active else 0
            if active:
                for i, text in enumerate(('Lives', 'Credits', 'Health')): col(0, -7, y + gap + 4 + i, 'Infinite ' + text + ' ' + on(s['infinite'] & (1 << i)))
            mid(0, y + gap + 6 + 3 * active, 'Back')
    return dict(draws=draws, flags=flags)


def program(data, config):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text(); header = (engine / 'openbor.h').read_text()
    names = ['menu_options_' + n for n in ('input', 'video', 'debug', 'system')]
    names += ['menu_options', 'obor_legacy_system_early', 'obor_legacy_system_debug',
              'obor_legacy_system_labels', 'obor_legacy_options', 'obor_legacy_cheatoptions']
    mapping = {n: 'frame_' + n for n in names}; frames = []
    for name in names:
        body = function(core, name)
        loop = re.search(r'\bwhile\s*\(\s*!quit\s*\)\s*\{', body)
        if not loop: raise ValueError('Native frame loop required')
        frame = body[:loop.end()] + frame_prefix(body, condition='!quit', boundary='update') + '\nreturn;\n}\n}\n'
        frame = rename_identifiers(frame, mapping)
        frame = re.sub(r'^(?:static\s+)?void\s+' + mapping[name] + r'\s*\(\s*\)',
                       'static void ' + mapping[name] + '(void)', frame)
        frame += ''.join('\n#undef ' + m for m in re.findall(r'^\s*#define\s+(\w+)', body, re.M)) + '\n'
        frames.append(frame)
    end = header.index('} e_key_def;') + len('} e_key_def;'); start = header.rfind('typedef enum', 0, end)
    if set(config['defines']) - set(PLATFORMS): raise ValueError('Explicit compiler symbols required')
    values = dict(DEFINES='\n'.join('#undef ' + n for n in PLATFORMS) + '\n' +
        '\n'.join('#define ' + n + ' 1' for n in config['defines']), FLAGS=header[start:end],
        CHEATS=function(core, 'is_cheat_actived'),
        PROTOTYPES='\n'.join('static void ' + mapping[n] + '(void);' for n in names),
        FUNCTIONS='\n'.join(frames),
        CALLS=','.join(mapping[n] for n in names[:5]),
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['view']['debug_present']) for r in data['sources']),
        CASES=','.join('{' + ','.join(str(c[k]) for k in data['case_fields']) + '}' for c in data['cases']))
    text = Path(__file__).with_name('native_menu_layout_contract.c.in').read_text()
    for k, v in values.items(): text = text.replace('@' + k + '@', v)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native menu dependency')
    return text


class NativeMenuLayoutContracts(unittest.TestCase):
    def test_source_owned_frames_and_real_legacy_routes(self):
        data = fixture_data()
        for config in data['compiler_conditions']:
            actual = [json.loads(line) for line in native_output(program(data, config), data).splitlines()]
            wanted = [(r, i, c, j, m, expected(r, c, config['name'], m))
                      for r in data['sources'] for i, c in enumerate(data['cases'])
                      for j, m in enumerate(data['menus']) if m != 'debug' or r['view']['debug_present']]
            self.assertEqual(len(actual), len(wanted), config['name'])
            for result, (row, i, scene, j, menu, oracle) in zip(actual, wanted):
                label = '%s revision=%s case=%s menu=%s' % (config['name'], row['revision'], i, menu)
                self.assertEqual((result['revision'], result['case'], result['menu']), (row['revision'], i, j), label)
                self.assertEqual(result['flags'], oracle['flags'], label)
                for index, (draw, correct) in enumerate(zip(result['draws'], oracle['draws'])):
                    self.assertEqual(draw, correct, label + ' draw=' + str(index))
                self.assertEqual(len(result['draws']), len(oracle['draws']), label)


if __name__ == '__main__':
    unittest.main()
