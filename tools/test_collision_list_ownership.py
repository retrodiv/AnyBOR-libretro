"""Check native collision table ownership and partial-frame cleanup.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'fixtures/collision-list-capacity.json'


def render(engine, source, kinds, counts, profiles, *, release_source=None):
    stop = re.search(r'(?m)^void\s+(borShutdown|shutdown)\s*\(', source)
    if stop is None:
        raise ValueError('Native engine stop definition required')
    allocations, fixtures = [], []
    for kind in kinds:
        matches = []
        for owner in ('a', 'data->animation'):
            field = owner + '->collision_' + kind
            pattern = r'(?ms)^[ \t]*if\(!' + re.escape(field) + r'\).*?' + re.escape(
                field + '[currentframe]->instance = collision_alloc_' + kind + '_list();') + (
                r'\s*' + re.escape(field + '[currentframe]->obor_instance_capacity') +
                r'\s*=[^;]+;')
            matches.extend(re.findall(pattern, source))
        if len(matches) != 1:
            raise ValueError('Complete native frame table allocation block required')
        block = matches[0].replace('data->animation', 'a').replace('data->framecount', 'framecount')
        allocations.append('static void allocate_' + kind +
            '(s_anim *a, ptrdiff_t currentframe, int framecount)\n{\n'
            '    size_t size_col_on_frame, size_col_on_frame_struct;\n' + block + '\n}\n')
        extra = 'record->defense = &borrowed_defense;' if kind == 'body' else ''
        if kind == 'attack':
            extra += '''
                record->recursive = calloc(1, sizeof(*record->recursive));
                record->recursive->mode = 1;
                preserve_payload(record->recursive);'''
        fixture = (HERE / 'collision_list_owner_case.c.in').read_text()
        fixtures.append(fixture.replace('@KIND@', kind).replace('@EXTRA@', extra).replace(
            '@ATTACK_CAPACITY@', 'animation.obor_attack_frame_capacity = 3;' if kind == 'attack' else ''))
    replacements = {
        'CONSTRUCTORS': '\n'.join(function(source, 'collision_alloc_' + kind + '_list') for kind in kinds),
        'RELEASE': function(source if release_source is None else release_source, 'free_frames'),
        'ALLOCATIONS': '\n'.join(allocations), 'FIXTURES': '\n'.join(fixtures),
        'SHUTDOWN': stop[1], 'COUNTS': ','.join(map(str, counts)),
        'PROFILES': ','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u' for p in profiles),
        'CHECKS': '\n'.join('            check_' + k + '(partial);' for k in kinds),
        'REFUSALS': '\n'.join('            refuse_' + k + '(attempt);' for k in kinds),
        'BORROWED_DECL': 'static __typeof__(*((s_collision_body *)0)->defense) borrowed_defense;'
                         if 'body' in kinds else '',
    }
    code = (HERE / 'collision_list_ownership_contract.c.in').read_text()
    for name, value in replacements.items():
        code = code.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unfilled collision owner contract')
    return code


class CollisionListOwnershipTests(unittest.TestCase):
    def test_native_owned_tables_records_and_partial_frames_by_profile(self):
        data = load_contract_fixture(FIXTURE)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        counts = [n for n in data['counts'] if n >= 2]
        self.assertTrue(counts)
        for engine, kinds in data['families'].items():
            profiles = [p for p in pin['profiles'] if p['engine'] == engine]
            self.assertTrue(profiles)
            source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text(encoding='latin1')
            expected = dict(status='PASS', profiles=len(profiles),
                            checks=len(profiles) * len(kinds) * (3 * len(counts) + 3))
            with self.subTest(engine=engine):
                actual = native_output(render(engine, source, kinds, counts, profiles), {'engine': engine})
                self.assertEqual(json.loads(actual), expected)

    def test_native_linked_and_collection_frames_release_owned_entries(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for engine in ('7533', '8023'):
            source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text(encoding='latin1')
            profiles = [p for p in pin['profiles'] if p['engine'] == engine]
            collection = 'void collision_collection_free(' in source
            services = ['child_spawn_free_node', 'child_spawn_free_list']
            if collection:
                services += ['collision_instance_free', 'collision_collection_free',
                             'frame_sound_free', 'frame_sound_collection_free']
            else:
                services += ['collision_attack_free_node', 'collision_attack_free_list',
                             'collision_body_free_node', 'collision_body_free_list']
            parts = dict(ALLOC=function(source, 'alloc_frames'), RELEASE=function(source, 'free_frames'),
                         SERVICES='\n'.join(function(source, name) for name in services),
                         COLLECTIONS=str(int(collection)),
                         PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                                           for p in profiles))
            code = (HERE / 'animation_frame_ownership_contract.c.in').read_text()
            for key, value in parts.items():
                code = code.replace('@' + key + '@', value)
            with self.subTest(engine=engine):
                actual = json.loads(native_output(code, {'engine': engine}))
                self.assertEqual(actual, dict(checks=2*len(profiles)))


if __name__ == '__main__':
    unittest.main()
