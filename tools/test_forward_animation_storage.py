"""Check native frame rows, profile offsets and count-independent ownership.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles,load_contract_fixture
from test_historical_common_think import ROOT,native_output
from test_historical_player import function

FIXTURE=Path(__file__).with_name('fixtures')/'profile-forward-animation-storage-contracts.json'


def program(data,engine):
    source=(engine/'openbor.c').read_text()
    fields=data['frame_tables']
    if not fields or any(not re.fullmatch(r'[a-z_]+',name) for name in fields):
        raise ValueError('Explicit native frame table fields required')
    caller=function(source,'load_cached_model')
    call=re.search(r'curframe = addframe\([^;]+;\s*if\(!obor_animation_store_offset\(newanim, curframe - 1, offset\)\)',caller)
    if call is None:raise ValueError('Native parser must store the original offsets after its existing frame call')
    if not 3<=data['initial_frames']<data['grown_frames']<=8:
        raise ValueError('Bounded shrink/growth contract counts required')
    pieces=dict(
        HEADER='#include '+json.dumps(str(engine/'openbor.h')),
        MEMORY_ERROR=re.search(r'(?m)^static const char \*E_OUT_OF_MEMORY = [^;]+;',source)[0],
        FUNCTIONS='\n'.join(function(source,name) for name in
            ('obor_animation_alloc_table','obor_animation_reserve_frames','obor_animation_set_numframes',
             'obor_animation_store_offset','alloc_frames','free_frames','setDrawMethod','getDrawMethod','addframe')),
        CONTEXTS=','.join('{%d,%d}'%(row['revision'],row['offset']) for row in data['sources']),
        SAFETY_CONTROLS=','.join(str(n)+'u' for n in data['ported_safety_controls']),
        INITIAL=str(data['initial_frames']),GROWN=str(data['grown_frames']),
        COUNT_TABLES='+'.join('!!a->'+name for name in fields),
        CHECK_EMPTY='\n'.join('CHECK(!a->'+name+');' for name in fields),
        CHECK_EXTENTS='\n'.join('if(a->%s)CHECK(allocation_bytes(a->%s)==(size_t)a->obor_frame_capacity*sizeof(*a->%s));'%(name,name,name) for name in fields))
    text=Path(__file__).with_name('forward_animation_storage_contract.c.in').read_text()
    for key,value in pieces.items():text=text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):raise ValueError('Unresolved animation frame storage input')
    return text


class ForwardAnimationStorageTests(unittest.TestCase):
    def test_native_rows_growth_refusal_offsets_and_owned_release(self):
        data=load_contract_fixture(FIXTURE)
        revisions={row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual((min(revisions),max(revisions)),tuple(data['range']))
        self.assertTrue(set(data['boundary_controls'])<=revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'],data['engine'])
            self.assertIs(type(row['offset']),bool)
        for profile in contract_profiles(data,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(profile.get('revision',profile['build']))
            if profile['engine']==data['engine'] and data['range'][0]<=revision<=data['range'][1]:
                self.assertIn(revision,revisions)
        engine=Path(os.environ.get('OBOR_ANIMATION_STORAGE_ENGINE',ROOT/'src/engines'/data['engine']))
        actual=[json.loads(line) for line in native_output(program(data,engine),data).splitlines()]
        self.assertEqual(actual,[dict(revision=row['revision'],status='PASS') for row in data['sources']]+
            [dict(safety_control=n,status='PASS') for n in data['ported_safety_controls']])


if __name__=='__main__':unittest.main()
