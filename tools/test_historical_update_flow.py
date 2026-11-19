"""Execute complete native update and return-to-menu methods.

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
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-update-flow-contracts.json'
SCREEN_FLAGS = ('selectScreen', 'titleScreen', 'hallOfFame', 'gameOver',
    'showComplete', 'currentScene', 'enginecreditsScreen', 'menuScreen',
    'startgameMenu', 'newgameMenu', 'loadgameMenu', 'optionsMenu',
    'controloptionsMenu', 'soundoptionsMenu', 'videooptionsMenu', 'systemoptionsMenu')
CASE_FIELDS = ('ingame', 'screen', 'pause', 'always', 'nopause', 'entities',
    'starters', 'flag', 'wait', 'screenshot', 'background', 'request_stage',
    'request_count', 'request_value', 'interval', 'format')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions) or
            tuple(data['case_fields']) != CASE_FIELDS or tuple(data['screens']) != SCREEN_FLAGS):
        raise ValueError('Own update sources, complete screen union and boundaries required')
    for row in data['sources']:
        if (not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', s) for s in row['source_sha256'].values()) or
                not all(type(row[k]) is bool for k in ('request_available', 'inner_frame',
                    'entity_screens', 'key_screens', 'fixed_format'))):
            raise ValueError('Source-owned request and screen policies required')
    for case in data['cases']:
        if (len(case) != len(CASE_FIELDS) or any(type(v) is not int for v in case) or
                case[0] not in (0, 1, 2) or not -1 <= case[1] < len(SCREEN_FLAGS) or
                case[2] not in (0, 1, 2) or any(case[i] not in (0, 1) for i in (3, 4, 8, 9, 10)) or
                any(not 0 <= case[i] <= 15 for i in (5, 6, 7)) or not 0 <= case[11] <= 4 or
                not 0 <= case[12] <= 2 or not 0 <= case[13] <= 7 or
                case[14] not in (0, 1, 3) or case[15] not in (0, 1, 2, 4)):
            raise ValueError('Bounded native frame/provider recipes required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    end = header.index('} e_key_def;') + len('} e_key_def;')
    start = header.rfind('typedef enum', 0, end)
    screen = re.search(r'^#define\s+inScreen\b(?:[^\n]*\\\n)*[^\n]*', header, re.M)
    speed = re.search(r'^#define\s+GAME_SPEED\s+\d+[^\n]*', header, re.M)
    if screen is None or speed is None:
        raise ValueError('Complete native screen macro and clock scale required')
    types = (engine / 'source/gamelib/types.h').read_text()
    pixel = re.search(r'^#define\s+PIXEL_32\s+\d+[^\n]*', types, re.M)
    if pixel is None: raise ValueError('Native screen format required')
    savedata = (engine / 'source/savedata.h').read_text()
    players = re.search(r'^#define\s+MAX_PLAYERS\s+\d+[^\n]*', savedata, re.M)
    slow = re.search(r'typedef enum\s*\{[^{}]*\}\s*e_slow_motion_enable;', header)
    if players is None or slow is None:
        raise ValueError('Native player count and slow-motion switch required')
    values = dict(FLAGS=header[start:end], SCREEN_UNION=screen[0], GAME_SPEED=speed[0],
        PIXEL_FORMAT=pixel[0], PLAYERS=players[0], SLOW_SWITCH=slow[0], SCREEN_DECLARATIONS='\n'.join(
            ('static char *' if n == 'currentScene' else 'static int ') + n + ';' for n in SCREEN_FLAGS),
        SCREEN_RESET='\n'.join(n + '=0;' for n in SCREEN_FLAGS),
        SCREEN_SET='\n'.join('if(c[1]==%d)%s=%s;' % (i, n,
            '"scene"' if n == 'currentScene' else '1') for i, n in enumerate(SCREEN_FLAGS)),
        METHODS='\n'.join(re.sub(r'^void\s+static\s+', 'static void ', function(core, n))
                          for n in ('goto_mainmenu', 'backto_mainmenu', 'update')),
        CONTEXTS=','.join('{%du,%d,%d}' % (r['revision'], r['request_available'], r['fixed_format'])
                          for r in data['sources']),
        CASES=','.join('{' + ','.join(map(str, c)) + '}' for c in data['cases']),
        SETTERS=','.join(str(c['value']) for c in data['setter_cases']))
    text = Path(__file__).with_name('update_flow_contract.c.in').read_text()
    for key, value in values.items(): text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text): raise ValueError('Unresolved native update dependency')
    return text


def event_digest(events):
    """Platform-independent receipt of ordered callback names and signed fields."""
    value = 14695981039346656037
    for event in events:
        raw = event[0].encode('ascii') + b'\0'
        raw += b''.join((v & 0xffffffff).to_bytes(4, 'little') for v in event[1:])
        for byte in raw:
            value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return '%016x' % value


def expected(row, case):
    scene = dict(zip(CASE_FIELDS, case))
    state = dict(pause=scene['pause'], flag=scene['flag'], time=0, end=0,
                 keys=scene['screenshot'], lives=[7, 8, 9, 10], remaining=scene['request_count'])
    events = []
    def emit(name, a=0, b=0):
        events.append([name, a, b, state['pause'], state['flag'], state['time'],
                       state['end'], state['keys'], *state['lives']])
    def service(name, stage=0):
        emit(name)
        if stage and scene['request_stage'] == stage and state['remaining']:
            state['remaining'] -= 1
            state['flag'] = 1 | (scene['request_value'] << 1)
            emit('request', scene['request_value'])
    def finish_frame(wait):
        emit('queue_draw', 0)
        if state['pause'] != 2 and state['keys']: emit('screenshot')
        if wait: emit('wait')
        for name in ('video', 'queue_clear', 'music', 'music_update'): emit(name)
    def return_to_menu(depth):
        emit('allocate', 320, 4 if row['fixed_format'] else scene['format'])
        emit('copy', 1, 0)
        emit('queue_draw', 1)
        emit('queue_clear')
        emit('queue_screen', 1)
        emit('lock')
        emit('music_pause', 1)
        emit('sample_pause', 1)
        state['pause'] = 2
        if row['inner_frame']:
            state['flag'] &= ~1
            frame(1, 0, depth + 1)
        state['lives'] = [0, 0, 0, 0]
        state['end'] = 2
        if not row['inner_frame']: state['flag'] &= ~1
        state['pause'], state['keys'] = 0, 0
        emit('unlock')
        emit('queue_clear')
        emit('free', 1)
    def frame(ingame, wait, depth=0):
        if depth > 3: raise ValueError('Request recipe exceeds its declared bound')
        emit('interval')
        service('input', 1)
        if (not state['pause'] and ingame == 1) or scene['always']: service('pre', 2)
        screen = scene['screen'] >= 0
        if not state['pause']:
            if ingame == 1 or (screen if row['key_screens'] else scene['screen'] == 0): service('keys', 3)
            for _ in range(scene['interval']):
                if ingame == 1:
                    emit('scroll')
                    emit('background_update')
                if ingame == 1 or (screen if row['entity_screens'] else scene['screen'] == 0): emit('entities')
                state['time'] += 1
        emit('clear')
        if ingame == 1 and not state['pause']:
            emit('background_draw')
            emit('text')
        if ingame == 0 and scene['background']: emit('queue_screen', 2)
        if not state['pause'] and (ingame == 1 or (screen if row['entity_screens'] else scene['screen'] == 0)):
            emit('display')
        if ingame == 1 or scene['always']: service('post', 4)
        wants_pause = (ingame == 1 and not state['pause'] and not scene['nopause'] and
                       bool(scene['entities'] & scene['starters']))
        if wants_pause and (not row['request_available'] or not state['flag'] & 1):
            emit('music_pause', 1)
            emit('sample_pause', 1)
            emit('pause_sample', 7, 37)
            emit('pause_menu')
            return
        if ingame == 1 and row['request_available'] and state['flag'] & 1:
            return_to_menu(depth)
            return
        finish_frame(wait)
    frame(scene['ingame'], scene['wait'])
    final = [state['pause'], state['flag'], state['time'], state['end'], state['keys'],
             *state['lives'], state['remaining']]
    return dict(events=len(events), digest=event_digest(events), state=final)


class UpdateFlowContracts(unittest.TestCase):
    def test_native_screen_scripts_pause_request_and_inner_frame_order(self):
        data = fixture_data()
        actual = iter(io.StringIO(native_output(program(data), data)))
        for row in data['sources']:
            if row['request_available']:
                for index, case in enumerate(data['setter_cases']):
                    value = (1 | ((case['value'] & 0xffffffff) << 1)) & 0xffffffff
                    if value >= 0x80000000: value -= 0x100000000
                    self.assertEqual(json.loads(next(actual)), dict(revision=row['revision'],
                        setter=index, flag=value))
            for index, case in enumerate(data['cases']):
                line = next(actual, None)
                self.assertIsNotNone(line)
                self.assertEqual(json.loads(line), dict(revision=row['revision'],
                    case=index, **expected(row, case)), 'revision=%d case=%d recipe=%s' %
                    (row['revision'], index, dict(zip(CASE_FIELDS, case))))
        self.assertIsNone(next(actual, None))


if __name__ == '__main__':
    unittest.main()
