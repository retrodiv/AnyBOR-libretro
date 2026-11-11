"""Check native slow-motion increment/reset boundaries with real storage types.

Only the native frame-counter section is executed. Clock and level are explicit
providers; the retained historical suite covers complete update-prefix ordering.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',HERE.parent))
FIXTURE=HERE/'fixtures/slowmotion-native-baseline.json'


def section(core):
    update=function(core,'update')
    declaration=re.search(r'(?m)^[^\n;]*\bslowmotion\s*(?:\[3\])?\s*=\s*[^;]*;',core)
    if not declaration:
        raise ValueError('Native slow-motion storage declaration required')
    compatibility=re.search(r'if\(obor_profile_build < (\d+)\)\s*\{\s*(?:unsigned counter;\s*)?if\(\(level_completed',update)
    first=compatibility.start() if compatibility else update.index('if((level_completed')
    end=re.search(r'if\(newtime\s*>',update[first:])
    if not end:
        raise ValueError('Native frame-counter boundary required')
    kind=('byte-array' if 'unsigned char' in declaration[0] else
          'unsigned-array' if re.search(r'unsigned\s+slowmotion',declaration[0]) else 'signed-record')
    return dict(declaration=declaration[0],section=update[first:first+end.start()],kind=kind,
                unsigned_before=int(compatibility[1]) if compatibility else 0)


def program(engine,profiles,*,wrong_reset=False):
    core=(engine/'openbor.c').read_text(encoding='latin1')
    current=section(core)
    original=load_contract_fixture(FIXTURE)['engines'][engine.name]
    if {k:v for k,v in current.items() if k!='section'}!={k:v for k,v in original.items() if k!='section'}:
        raise ValueError('Native storage and unsigned-profile routing must remain unchanged')
    native=current['section']
    if wrong_reset:
        if native.count('slowmotion.counter = 0;')!=1:
            raise ValueError('One signed reset required for the defined negative control')
        native=native.replace('slowmotion.counter = 0;','slowmotion.counter = 1;',1)
    array=current['kind']!='signed-record'
    values=dict(CONFIG='#include "config.h"' if (engine/'config.h').is_file() else '',
        INITIALIZER=current['declaration'],ORIGINAL=original['section'],CHECKED=native,
        TOGGLE='slowmotion[0]' if array else 'slowmotion.toggle',
        DURATION='slowmotion[1]' if array else 'slowmotion.duration',
        COUNTER='slowmotion[2]' if array else 'slowmotion.counter',
        BYTE=str(int(current['kind']=='byte-array')),
        UNSIGNED='1' if array else ('obor_profile_build<%du'%current['unsigned_before'] if current['unsigned_before'] else '0'),
        NO_SLOW='scene.boss_slow=noslow?BOSS_SLOW_OFF:BOSS_SLOW_ON;' if 'level->boss_slow' in native else 'scene.noslow=noslow;',
        PROFILES=','.join(str(int(p.get('revision',p['build'].split('-')[0])))+'u' for p in profiles))
    text=(HERE/'slowmotion_counter_bounds.c.in').read_text()
    for key,value in values.items():text=text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):raise ValueError('Unresolved counter input')
    return text


class SlowMotionCounterBoundsTests(unittest.TestCase):
    def test_native_increment_and_reset_keep_each_profiles_defined_results(self):
        pin=json.loads((ROOT/'src/pin.json').read_text())
        for entry in pin['engines']:
            engine=ROOT/'src/engines'/entry['build']
            profiles=[p for p in pin['profiles'] if p['engine']==engine.name]
            with self.subTest(engine=engine.name):
                result=run_native(engine,program(engine,profiles))
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                value=json.loads(result.stdout)
                self.assertEqual(value,dict(status='PASS',profiles=len(profiles),cases=3888*len(profiles)))

    def test_wrong_reset_fails_a_defined_result_control(self):
        pin=json.loads((ROOT/'src/pin.json').read_text())
        oracle=load_contract_fixture(FIXTURE)
        entry=next(e for e in pin['engines'] if oracle['engines'][e['build']]['kind']=='signed-record')
        engine=ROOT/'src/engines'/entry['build'];boundary=oracle['engines'][entry['build']]['unsigned_before']
        profile=next(p for p in pin['profiles'] if p['engine']==engine.name and int(p.get('revision',p['build'].split('-')[0]))>=boundary)
        result=run_native(engine,program(engine,[profile],wrong_reset=True))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('defined counter result',result.stderr)
        self.assertNotIn('runtime error:',result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer',result.stderr)


if __name__=='__main__':unittest.main()
