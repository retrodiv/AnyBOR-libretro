"""Execute complete native menu loops against original action policies.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import io
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-native-menu-actions-contracts.json'
DEBUG = ['debuginfo', 'debug_position', 'debug_features', 'debug_collision_attack',
         'debug_collision_body', 'debug_collision_range']
ROUTES = ('video', 'sound', 'control', 'system', 'debug', 'config')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own action sources and boundaries required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or row['debug_policy'] not in
                ('absent', 'unsigned', 'signed', 'explicit') or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Source-bound menu input policies required')
    return data


def items(row, scene, domain, platform):
    view = row['view']
    if domain == 'debug':
        if not view['debug_present']: return []
        return DEBUG[:2] + (DEBUG[2:3] if view['debug_features'] else []) + DEBUG[3:] + ['back']
    if domain == 'system':
        if view['system_early']:
            result = ['debuginfo', 'uselog', 'players', 'mode', 'cheats', 'config']
        else:
            result = ['uselog', 'mode', 'cheats']
            if not (view['system_gate'] and scene['nodebug']): result.append('debug')
            result.append('config')
        if platform == 'dreamcast': result[result.index('config')] = None
        if platform == 'psp': result.append('cpu')
        return result + ['back']
    active = bool(scene['cheats'] and not scene['force'])
    if not view['root_merged'] and active:
        return ['brightness', 'gamma', 'control', 'sound', 'system', 'lives', 'credits', 'health', 'back']
    return ['video', 'sound', 'control', 'system'] + (
        ['lives', 'credits', 'health'] if view['root_merged'] and active else []) + ['back']


def target(case, order, domain, platform):
    if domain not in case['domains'] or not order: return None
    slot = case['slot']
    if slot == -1: return len(order) - 1
    if slot < -1:
        name = {-2: 'system', -3: 'mode', -4: 'cpu'}[slot]
        return order.index(name) if name in order else None
    return slot if slot < len(order) else None


def expected(data, row, case, domain, platform):
    scene = data['scenes'][case['scene']]; view = row['view']
    order = items(row, scene, domain, platform); slot = target(case, order, domain, platform)
    if slot is None: return None
    events = ['D'] * slot + case['events']
    state = {'savedata.' + name: scene['debug'] & (1 << i) for i, name in enumerate(DEBUG)}
    state.update({'savedata.uselog': scene['mode'], 'savedata.mode': scene['mode'],
        'savedata.brightness': case['brightness'], 'savedata.gamma': case['gamma'],
        'cheats': scene['cheats'], 'forcecheatsoff': scene['force'],
        'livescheat': scene['infinite'] & 1, 'creditscheat': scene['infinite'] & 2,
        'healthcheat': scene['infinite'] & 4, 'pause': scene['pause'],
        'cpu_setting': case['cpu'] if platform == 'psp' else 0,
        'optionsMenu': 0, 'cheatoptionsMenu': 0, 'systemoptionsMenu': 0, 'bothnewkeys': 0})
    legacy_cheat = domain == 'root' and not view['root_merged'] and bool(scene['cheats'] and not scene['force'])
    legacy_plain = domain == 'root' and not view['root_merged'] and not legacy_cheat
    if domain == 'system': state['systemoptionsMenu'] = 1
    elif domain == 'root': state['cheatoptionsMenu' if legacy_cheat else 'optionsMenu'] = 1
    def flags(): return [state['optionsMenu'], state['cheatoptionsMenu'], 0, 0, state['systemoptionsMenu']]
    def active(): return bool(state['cheats'] and not state['forcecheatsoff'])
    y = -1 - 3 * active() + (view['root_pause_shift'] if active() and scene['level'] and state['pause'] > 0 else 0)
    gap = view['root_spacer'] if active() else 0
    last = len(order) - 1
    frames, effects, selector, step, system_calls, quit_menu = [], [], 0, 0, 0, False
    def toggle(name): state[name] = int(not state[name])
    def label(role):
        if role is None: return ''
        if role in ('lives', 'credits', 'health'):
            return 'Infinite ' + role.title() + (' On' if state[role + 'cheat'] else ' Off')
        names = dict(debuginfo='Debug Info:' if domain == 'system' else 'Performance:',
            debug_position='Position:', debug_features='Features:', debug_collision_attack='Collision Attack:',
            debug_collision_body='Collision Body:', debug_collision_range='Range:', uselog='File Logging:',
            players='Players:', mode='Versus Damage:', cheats='Cheats:', debug='Debug Settings...',
            config='Config Settings' if view['system_early'] else 'Config Settings...', cpu='CPU Speed:',
            video='Video Options...', sound='Sound Options...', control='Control Options...',
            system='System Options...', brightness='Brightness:', gamma='Gamma:', back='Back')
        return names[role]
    while not quit_menu:
        if step >= 128: raise ValueError('Original action recipe did not terminate')
        if domain == 'root' and view['root_merged']:
            role = 'back' if selector == last else (
                ['video', 'sound', 'control', 'system'][selector] if 0 <= selector < 4 else
                ['lives', 'credits', 'health'][selector - 4] if active() and 4 <= selector <= 6 else None)
            title, back = y - 1, y + gap + last + 2
        else:
            role = order[selector] if 0 <= selector < len(order) else None
            if domain == 'debug': title, back = view['debug_title'], view['debug_back']
            elif domain == 'system': title, back = -6, (7 if view['system_shift'] else 6) - int(bool(view['system_gate'] and scene['nodebug']))
            else: title, back = (-5 if legacy_cheat else -1), 6
        frames.append([label(role), title, back, flags()])
        if legacy_plain: selector = last if selector < 0 else 0 if selector > last else selector
        key = set(events[step] if step < len(events) else 'E'); step += 1
        beep, action_beep = case['samples']
        def sound(sample):
            if domain == 'system' or sample >= 0: effects.append(['sound', sample])
        if domain == 'debug' and row['debug_policy'] == 'explicit':
            if key & set('UDE'):
                sound(beep)
                if 'E' in key: quit_menu = True
                elif 'U' in key: selector = last if selector == 0 else selector - 1
                elif 'D' in key: selector = 0 if selector == last else selector + 1
        else:
            if 'E' in key: quit_menu = True
            for move, amount in [('U', -1), ('D', 1)]:
                if move not in key: continue
                if domain == 'root' and view['root_merged']:
                    selector = (last if selector <= 0 else selector - 1) if move == 'U' else (0 if selector >= last else selector + 1)
                else:
                    selector += amount
                    if domain == 'debug' and row['debug_policy'] == 'unsigned': selector %= 1 << 32
                sound(beep)
            if not legacy_plain and not (domain == 'root' and view['root_merged']):
                selector = last if selector < 0 else 0 if selector > last else selector
        if not key & set('LRA'): continue
        sound(action_beep)
        if domain == 'root' and view['root_merged']:
            action = 'back' if selector == last else (
                ['video', 'sound', 'control', 'system'][selector] if 0 <= selector < 4 else
                ['lives', 'credits', 'health'][selector - 4] if 4 <= selector <= 6 else None)
        else: action = order[selector] if 0 <= selector < len(order) else None
        if action == 'back' or action is None: quit_menu = True
        elif action in DEBUG: toggle('savedata.' + action)
        elif action == 'uselog': toggle('savedata.uselog')
        elif action == 'mode':
            if scene['versus'] > 1: toggle('savedata.mode')
        elif action == 'cheats': toggle('cheats')
        elif action in ('lives', 'credits', 'health'): toggle(action + 'cheat')
        elif action in ('brightness', 'gamma'):
            direction = -1 if 'L' in key else 1 if 'R' in key else 0
            field = 'savedata.' + action; state[field] = max(-256, min(256, state[field] + direction * 8))
            effects += [['vwait'], ['palette', state['savedata.gamma'], state['savedata.brightness']]]
        elif action == 'cpu':
            direction = -1 if 'L' in key else 1 if 'R' in key else 0
            value = state['cpu_setting'] + direction
            state['cpu_setting'] = 2 if value < 0 else 0 if value > 2 else value
            a, b = [(222, 111), (266, 133), (333, 166)][state['cpu_setting']]
            effects.append(['clock', a, a, b])
        elif action in ROUTES:
            effects.append(['menu', action, state['cheats'], state['forcecheatsoff'], state['pause'],
                            state['optionsMenu'], state['cheatoptionsMenu'], state['systemoptionsMenu']])
            if action == 'system':
                if system_calls < len(case['changes']): state['cheats'], state['forcecheatsoff'] = case['changes'][system_calls]
                system_calls += 1
                if domain == 'root' and view['root_merged']:
                    if not view['root_spacer']:
                        if active(): y -= 3; last += 3
                    else:
                        y = -1 - 3 * active() + (view['root_pause_shift'] if active() and scene['level'] and state['pause'] > 0 else 0)
                        gap, last = (1, 7) if active() else (0, 4)
    effects.append(['save', state['pause'], state['optionsMenu'], state['cheatoptionsMenu'], state['systemoptionsMenu']])
    if domain == 'root' and not legacy_cheat and state['pause'] == 1: state['pause'] = 2
    state['optionsMenu'] = state['cheatoptionsMenu'] = state['systemoptionsMenu'] = state['bothnewkeys'] = 0
    return dict(frames=frames, effects=effects, state=[state[n] for n in data['state_fields']])


def program(data, config):
    engine = ROOT / 'src/engines' / data['engine']; core = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text(); end = header.index('} e_key_def;') + len('} e_key_def;')
    start = header.rfind('typedef enum', 0, end)
    script = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
    declarations = re.search(r'(?s)typedef enum VariantType\s*\{.*?\}\s*VARTYPE;\s*typedef struct ScriptVariant\s*\{.*?\}\s*ScriptVariant;', variants)
    if declarations is None: raise ValueError('Native callback variant declarations required')
    names = ['menu_options_debug', 'menu_options_system', 'menu_options', 'obor_legacy_system_early',
             'obor_legacy_system_debug', 'obor_legacy_system_labels', 'obor_legacy_options', 'obor_legacy_cheatoptions']
    functions = []
    for name in names:
        body = function(core, name)
        if name.startswith('menu_options'):
            body = re.sub(r'^void\s+' + name + r'\s*\(\s*\)', 'static void run_' + name + '(void)', body)
        functions.append(body)
    cases = []
    for case in data['cases']:
        if any(set(event) - set('UDLRAE') for event in case['events']): raise ValueError('Explicit bounded keys required')
        if not 0 <= case['scene'] < len(data['scenes']) or len(case['changes']) > 4: raise ValueError('Bounded scene/delegate plan required')
        mask = sum(1 << data['domains'].index(n) for n in case['domains'])
        change_values = ','.join('{%d,%d}' % tuple(c) for c in case['changes']) or '{0,0}'
        cases.append('{%d,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d,{%s}}' % (
            case['slot'], case['scene'], mask, json.dumps('|'.join(case['events'])),
            *case['samples'], case['brightness'], case['gamma'], case['cpu'], len(case['events']),
            len(case['changes']), change_values))
    if any(not re.fullmatch(r'[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?', n) for n in data['state_fields']):
        raise ValueError('Named native state fields required')
    scenes = ','.join('{' + ','.join(str(s[k]) for k in data['case_fields']) + '}' for s in data['scenes'])
    values = dict(DEFINES='\n'.join('#undef ' + n for n in ('SDL', 'PSP', 'WII', 'DC', 'GP2X', 'OPENDINGUX', 'ANDROID')) +
        '\n' + '\n'.join('#define ' + n + ' 1' for n in config['defines']), FLAGS=header[start:end],
        VARIANT_TYPES=declarations[0],
        CALLBACK=rename_identifiers(function(script, 'openbor_menu_options'), {'menu_options': 'run_menu_options'}),
        FUNCTIONS='\n'.join(functions), CHEATS=function(core, 'is_cheat_actived'), SCENES=scenes,
        PROTOTYPES='\n'.join('static void ' + ('run_' + n if n.startswith('menu_options') else n) + '(void);' for n in names),
        CASES=','.join(cases),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d,%d}' % (r['revision'], r['view']['debug_present'],
            r['view']['debug_features'], r['view']['system_early'], r['view']['system_gate'],
            r['view']['root_merged']) for r in data['sources']),
        STATE=','.join('(int)' + n for n in data['state_fields']))
    text = Path(__file__).with_name('native_menu_actions_contract.c.in').read_text()
    for k, v in values.items(): text = text.replace('@' + k + '@', v)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native action dependency')
    return text


class NativeMenuActionContracts(unittest.TestCase):
    def test_complete_native_loops_and_source_owned_action_policies(self):
        data = fixture_data()
        for config in data['compiler_conditions']:
            raw = native_output(program(data, config), data)
            actual = iter(io.StringIO(raw))
            count = 0
            for row in data['sources']:
                for domain_index, domain in enumerate(data['domains']):
                    for case_index, case in enumerate(data['cases']):
                        correct = expected(data, row, case, domain, config['name'])
                        if correct is None: continue
                        line = next(actual, None); self.assertIsNotNone(line)
                        result = json.loads(line); count += 1
                        label = '%s revision=%s domain=%s case=%s:%s' % (config['name'], row['revision'], domain, case_index, case['name'])
                        self.assertEqual([result['revision'], result['domain'], result['case']], [row['revision'], domain_index, case_index], label)
                        self.assertEqual(result['state'], correct['state'], label + ' state')
                        for key in ('frames', 'effects'):
                            for i, (seen, wanted) in enumerate(zip(result[key], correct[key])):
                                self.assertEqual(seen, wanted, label + ' %s[%d]' % (key, i))
                            self.assertEqual(len(result[key]), len(correct[key]), label + ' ' + key)
            self.assertIsNone(next(actual, None), config['name'] + ' extra result')
            self.assertGreater(count, 0)


if __name__ == '__main__':
    unittest.main()
