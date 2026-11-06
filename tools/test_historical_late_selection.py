"""Observe complete historical selection/join callers and native map rotation.

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


FIXTURE=Path(__file__).with_name('fixtures')/'profile-late-selection-contracts.json'


def program(data):
    engine=ROOT/'src/engines'/data['engine']
    source=(engine/'openbor.c').read_text();header=(engine/'openbor.h').read_text()
    names=['MAX_PLAYERS','MAX_NAME_LEN','MAX_ARG_LEN','ANI_PICK','TYPE_PLAYER','TYPE_ENEMY',
           'TYPE_ENDLEVEL','GAME_SPEED','COUNTER_SPEED','FLAG_ANYBUTTON','FLAG_START',
           'FLAG_MOVELEFT','FLAG_MOVERIGHT','FLAG_MOVEUP','FLAG_MOVEDOWN','FLAG_ESC',
           'FLAG_ATTACK','FLAG_ATTACK2','FLAG_ATTACK3','FLAG_ATTACK4','FLAG_JUMP','FLAG_SPECIAL']
    constants='\n'.join(re.search(r'(?m)^#define\s+'+name+r'\s+[^\n]+',header)[0] for name in names)
    names=['nextplayermodel','prevplayermodel','obor_colourmap_step','nextcolourmap','prevcolourmap',
           'nextplayermodeln','prevplayermodeln','spawnexample','updatestatus','selectplayer','playlevel']
    loader=function(source,'load_levelorder');start=loader.index('\tif(!set)\n')
    defaults=loader[start:loader.index('\n\tlCleanup:',start)]
    parts={'CONSTANTS':constants,'NATIVE':'\n'.join(function(source,name) for name in names),
        'DEFAULTS':defaults,'CONTEXTS':','.join('{%du,%d}'%(x['revision'],x['map_helpers']) for x in data['sources']),
        'PALETTES':','.join('{%d,%d,%d,%d,%d}'%tuple(x[k] for k in ['maps','c','frozen','low','high']) for x in data['palette_cases']),
        'ROSTERS':','.join('{%d,%d,%d,%d,{%s}}'%(x['current'],x['slot'],x['nosame'],x['count'],
            ','.join(json.dumps(n) for n in x['names'])) for x in data['roster_cases']),
        'MENUS':','.join('{%d,%d,%d,%d,%d}'%tuple(x[k] for k in ['players','pick','action','file','custom']) for x in data['menu_cases'])}
    result=Path(__file__).with_name('late_selection_contract.c.in').read_text()
    for key,value in parts.items():result=result.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',result):raise ValueError('Unresolved selection provider')
    return result


def palette(case,source,backwards):
    # Direct own-source iteration is independent of the core's run skipping.
    value=case['c'];seen=set();first=source['first_map']
    while True:
        value+=-1 if backwards else 1
        if backwards and value<first:value=case['maps']
        elif not backwards and value>case['maps']:value=first
        if value in seen:return 0  # Original has no terminating selection.
        seen.add(value)
        if case['frozen']>0 and value==case['frozen']:continue
        if (not source['guard_hidden_zero'] or case['low']>0) and case['low']<=value<=case['high']:continue
        return value


def roster(case,backwards):
    names=['one','two','three','four'];step=-1 if backwards else 1
    selected=(case['current']+step)%4
    if case['current']<0:selected=3 if backwards else 0
    if case['nosame']:
        for slot in range(case['count']):
            if slot!=case['slot'] and names[selected].casefold()==case['names'][slot].casefold():
                selected=(selected+step)%4
    return selected


def position(slot,players,ready=False):
    # Source integer division is positive in these authored layouts.
    if players>2:
        return [(95 if ready else 111)-players*14+slot*(320-166//players)//players+14,
                (225 if ready else 230)-6]
    return [(67 if ready else 83)+7+slot*169,(225 if ready else 230)-6]


def menu(case,source):
    players,pick,action=case['players'],case['pick'],case['action'];nonblocking=source['nonblocking'];delay=source['exit_delay']
    extra=2*bool(action)
    if players==1:
        ticks=([3,4,7] if nonblocking and not delay else [6,7,10])[pick]+extra
        ready=0 if nonblocking and not delay else 3
        picked=[1+extra,0];completed=[3+extra if pick==1 else 0,0]
        last_ready=0
    else:
        if pick!=1 or action:raise ValueError('Two-player boundary control uses finite pick animations')
        ticks=8 if delay else 5 if nonblocking else 9
        ready=7 if delay else 1 if nonblocking else 6
        picked=[1,2 if nonblocking else 3];completed=[3,4 if nonblocking else 5]
        last_ready=0 if nonblocking and not delay else 1
    cached=source['cached_positions'];custom=case['custom']
    spawn_position=[31,77] if custom else position(0,4 if cached else players)
    ready_position=([9,12] if custom else position(last_ready,4 if cached else players,True)) if ready else [0,0]
    first_maps=players*(1+int(case['file'] and source['initial_map_applied']))
    color=(2 if action==2 else (2 if source['first_map']==1 else 1) if action==1 else source['first_map'])
    if not source['map_helpers']:color=2 if action==2 else 1 if action==1 else 0
    name='entity-alias' if not source['stores_preview_name'] else ['one','two','four'][action]
    return {'result':1,'ticks':ticks,'time':900+ticks*100 if nonblocking else 400,
        'ready':ready,'ready_position':ready_position,'spawn_position':spawn_position,
        'first_spawns':players*(1+case['file']),'first_maps':first_maps,
        'first_name':int(source['stores_preview_name']),'maps':first_maps+2*players*bool(action),
        'color':color,'name':name,'picked':picked,'completed':completed}


class LaterSelectionContracts(unittest.TestCase):
    def test_native_selection_join_and_palette_boundaries(self):
        data=load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data,data['expected_revisions']))
        sources={row['revision']:row for row in data['sources']}
        rows=[json.loads(line) for line in native_output(program(data),data).splitlines()]
        expected=[]
        for source in data['sources']:
            revision=source['revision']
            def add(domain,index,**values):expected.append(dict(revision=revision,domain=domain,case=index,**values))
            if source['map_helpers']:
                for i,case in enumerate(data['palette_cases']):
                    add('palette',i,values=[palette(case,source,False),palette(case,source,True)])
                for i,case in enumerate(data['roster_cases']):
                    add('roster',i,values=[roster(case,False),roster(case,True)])
            for i,case in enumerate(data['menu_cases']):add('menu',i,**menu(case,source))
            for i in range(4):
                joins=source['stores_preview_name'] and i in (0,3)
                add('join',i,joined=int(joins),joining=int(not joins),lives=3 if joins else 0,
                    drop=int(joins),timeleft=12000 if joins else 2000)
            add('level',0,joining=[0 if source['stores_preview_name'] else 1,1],
                spawn_joining=0 if source['stores_preview_name'] else 1)
            for i in range(3):
                values=sum((position(p,4)+position(p,4,True) for p in range(4)),[]) if i==0 and source['cached_positions'] else [0]*16
                if i==1:values[0]=10
                add('positions',i,values=values)
            for i in range(9):
                name='four' if i in (0,6,7) else 'two' if i==1 else 'one'
                if i in (0,1,4,6,7):color=source['first_map'] if source['map_helpers'] else 2
                elif i==5:color=1
                elif i==8:color=2
                else:color=source['first_map'] if source['map_helpers'] else 0
                add('join-input',i,name=name,map=color,keys=16 if i==5 else 0,
                    joining=1,credits=4 if i==4 else 5,timeleft=12000 if i==4 else 2000)
        self.assertEqual(len(rows),len(expected))
        for actual,wanted in zip(rows,expected):
            with self.subTest(revision=actual['revision'],domain=actual['domain'],case=actual['case']):
                self.assertEqual(actual,wanted)


if __name__=='__main__':unittest.main()
