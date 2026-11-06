"""Compare native entity spawn/kill functions against own-source profile oracles.

Compile once per physical source/expectation group and run each revision fresh.
Pool growth/free callers use owned native records; entity constructors, scripts,
colourmap services and AI initialization remain controlled providers.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_entity_spawn import render_entity_spawn
from native_sanitizers import sanitizer_environment
from test_historical_player import function
from test_historical_common_think import native_output

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-entity-spawn-contracts.json'


class MusicSpawnContracts(unittest.TestCase):
    def test_native_music_volume_order_and_player_count_eligibility(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-music-spawn-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        values = dict(FUNCTIONS='\n'.join(function(core, n) for n in ('check_music', 'smartspawn')),
                      PROFILES=','.join(str(r['revision'])+'u' for r in rows))
        for name in ('music', 'spawn'):
            values[name.upper()+'_CASES'] = ',\n'.join('{'+','.join(str(c[k]) for k in
                data[name+'_fields'])+'}' for c in data[name+'_cases'])
        text = Path(__file__).with_name('music_spawn_contract.c.in').read_text()
        for key, value in values.items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, result in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'], **data['contracts'][row['contract']]))


class GrabWallContracts(unittest.TestCase):
    def test_native_jumpable_wall_and_grab_position_boundary(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-grab-wall-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        body = function(core, 'testmove')
        text = Path(__file__).with_name('grab_wall_contract.c.in').read_text()
        values = dict(WALL=body[body.index('// ------------------ wall checking'):],
                      GRAB=function(core, 'adjust_grabposition'),
                      PROFILES=','.join(str(r['revision'])+'u' for r in rows))
        for name in ('wall', 'grab'):
            values[name.upper()+'_CASES'] = ',\n'.join('{'+','.join(str(c[k]) for k in
                data[name+'_parameters'])+'}' for c in data[name+'_cases'])
        for key, value in values.items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, result in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'], **data['contracts'][row['contract']]))


class WaypointLifecycleContracts(unittest.TestCase):
    def test_native_entity_destruction_and_recycle_cleanup(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-waypoint-lifecycle-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        body = function(core, 'spawn')
        start = body.index('clear_all_scripts(e->scripts, 1);')
        end = body.index('memset(e, 0, sizeof(entity));', start)+len('memset(e, 0, sizeof(entity));')
        region = body[start:end]
        self.assertEqual(region.count('if(e->waypoints) free(e->waypoints);'), 1)
        text = Path(__file__).with_name('waypoint_lifecycle_contract.c.in').read_text()
        for key, value in dict(FREE_ENT=function(core, 'free_ent'), RECYCLE=region,
                              PROFILES=','.join(str(r['revision'])+'u' for r in rows)).items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], **data['contracts'][r['contract']]) for r in rows])


class ItemHeldScheduleContracts(unittest.TestCase):
    def test_native_pickup_tail_preserves_historical_clocks(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-item-held-schedule-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        body = function(core, 'didfind_item')
        marker = 'if(other->modeldata.subtype != SUBTYPE_WEAPON && other->modeldata.subtype != SUBTYPE_PROJECTILE)'
        self.assertEqual(body.count(marker), 1)
        region = body[body.index(marker):body.rfind('}')]
        self.assertTrue(region.rstrip().endswith('other->z = 100000;'))
        text = Path(__file__).with_name('item_held_schedule_contract.c.in').read_text()
        for key, value in dict(REGION=region,
                              PROFILES=','.join(str(r['revision'])+'u' for r in rows),
                              CASES=',\n'.join('{'+','.join(str(c[k])+'u' if k in
                                  ('clock', 'nextthink', 'nextanim') else str(c[k])
                                  for k in data['parameters'])+'}' for c in data['cases'])).items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        expected = [dict(revision=r['revision'], case=i, **v) for r in rows
                    for i, v in enumerate(data['contracts'][r['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], case=oracle['case']):
                self.assertEqual(result, oracle)


class WeaponDropContracts(unittest.TestCase):
    def test_native_dropped_weapon_animation_and_schedule(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-weapon-drop-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        text = Path(__file__).with_name('weapon_drop_contract.c.in').read_text()
        for key, value in dict(FUNCTION=function(core, 'dropweapon'),
                              PROFILES=','.join(str(r['revision'])+'u' for r in rows),
                              CASES=',\n'.join('{'+','.join(str(c[k]) for k in data['parameters'])+'}'
                                              for c in data['cases'])).items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        expected = [dict(revision=r['revision'], case=i, **v) for r in rows
                    for i, v in enumerate(data['contracts'][r['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], case=oracle['case']):
                self.assertEqual(result, oracle)


class EntityFlashContracts(unittest.TestCase):
    def test_native_final_flash_state_across_hits(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-attack-flash-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        regions = re.findall(r'// if #054\s*if\([^\n]+\)\s*\{[\s\S]*?\}//end of if #054',
                             function(core, 'do_attack'))
        self.assertEqual(len(regions), 1)
        text = Path(__file__).with_name('attack_flash_contract.c.in').read_text()
        for key, value in {'REGION': regions[0],
                           'PROFILES': ','.join(str(r['revision']) + 'u' for r in rows),
                           'CASES': ',\n'.join('{' + ','.join(str(c[k]) for k in data['parameters']) + '}'
                                             for c in data['cases'])}.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, result in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, {'revision': row['revision'],
                    'results': data['contracts'][row['contract']]})


class EntityCapacityContracts(unittest.TestCase):
    def data(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-entity-capacity-contracts.json')
        rows = data['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        self.assertTrue(all(type(r['dynamic_capacity']) is bool and
            type(r['kill_resets_count_without_shrink']) is bool and
            type(r['capacity']) is int and 0 < r['capacity'] <= 1024 and
            r['effect_autokill'] in (1, 2) for r in rows))
        return data

    def test_native_entity_pool_capacity_and_lifecycle(self):
        data = self.data()
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        text = Path(__file__).with_name('entity_capacity_contract.c.in').read_text()
        parts = dict(PROFILES=','.join('{%du,%d,%d,%d}' % (r['revision'], r['dynamic_capacity'],
            r['kill_resets_count_without_shrink'], r['capacity']) for r in data['sources']),
            PLAINMETHOD='const s_drawmethod plainmethod={0};', DRAW_GLOBALS='',
            DRAW_CHECK='', DRAW_ONLY='0', DRAW_MAIN='',
            FAILURES=str(int(data['failure_controls'])),
            ROUTINES='\n'.join(function(core, name) for name in
                ('free_ents', 'alloc_ents', 'spawn', 'kill_all', 'findent', 'count_ents')),
            HELPERS='\n'.join(function(core, name) for name in
                ('obor_scene_counters_active', 'obor_scene_counter_adjust')))
        for key, value in parts.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [{'revision': r['revision'], 'capacity': r['capacity'],
            'dynamic': int(r['dynamic_capacity']), 'reset': int(r['kill_resets_count_without_shrink'])}
            for r in data['sources']])

    def test_native_effect_cleanup_values(self):
        data = self.data()
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        statements = []
        for name, count in [('update_frame', 1), ('do_attack', 1),
                            ('check_gravity', 2), ('common_try_jumpattack', 1)]:
            stores = re.findall(r'\b(?:dust|flash)->autokill\s*=[^;]+;', function(core, name))
            self.assertEqual(len(stores), count)
            statements += stores
        body = '''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
uint32_t obor_profile_build;
int main(void){entity child,*dust=&child,*flash=&child;
const struct {unsigned revision;int value;} profiles[]={@PROFILES@};
for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p){
obor_profile_build=profiles[p].revision;
@STORES@
printf("{\\"revision\\":%u,\\"stores\\":5}\\n",obor_profile_build);
}return 0;}'''
        checks = []
        for statement in statements:
            checks.append('memset(&child,0,sizeof(child));' + statement +
                'if(child.autokill!=profiles[p].value){fprintf(stderr,'
                '"Effect cleanup mismatch revision=%u\\n",obor_profile_build);abort();}')
        body = body.replace('@PROFILES@', ','.join('{%du,%d}' %
            (r['revision'], r['effect_autokill']) for r in data['sources'])).replace('@STORES@', '\n'.join(checks))
        actual = [json.loads(line) for line in native_output(body, data).splitlines()]
        self.assertEqual(actual, [{'revision': r['revision'], 'stores': 5} for r in data['sources']])


class SpawnDrawMethodContracts(unittest.TestCase):
    def test_native_spawn_defaults_before_initialization_and_after_reuse(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-spawn-drawmethod-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        core = (SOURCE / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        initializers = re.findall(r'(?ms)^const s_drawmethod plainmethod\s*=\s*\{.*?^\};', core)
        self.assertEqual(len(initializers), 1)
        contracts = list(data['contracts'])
        checks = []
        for index, name in enumerate(contracts):
            statements = []
            for field, value in data['contracts'][name].items():
                self.assertRegex(field, r'^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?$')
                self.assertIs(type(value), int)
                statements.append('assert(ent->drawmethod.' + field + '==' + str(value) + ');')
            checks.append('case '+str(index)+':'+''.join(statements)+'break;')
        globals_code = ('static unsigned draw_contract,draw_checks;\n'
            'static const unsigned draw_contracts[]={' + ','.join(str(contracts.index(r['contract']))
            for r in rows) + '};\nstatic void check_draw(entity *ent){++draw_checks;'
            'switch(draw_contract){'+''.join(checks)+'default:abort();}}')
        main = '''for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p){
profile=profiles+p;obor_profile_build=profile->revision;draw_contract=draw_contracts[p];
draw_checks=0;phase="drawing-defaults";begin();
for(unsigned round=0;round<2;++round){entity *ent=create();assert(ent);
ent->drawmethod.scalex=7;ent->drawmethod.alpha=3;ent->drawmethod.xrepeat=5;
kill_all();}
assert(draw_checks==2);finish();
printf("{\\"revision\\":%u,\\"drawchecks\\":2}\\n",obor_profile_build);
}'''
        parts = dict(PROFILES=','.join('{%du,0,0,MAX_ENTS}' % r['revision'] for r in rows),
            FAILURES='0', PLAINMETHOD=initializers[0], DRAW_GLOBALS=globals_code,
            DRAW_CHECK='check_draw(ent);', DRAW_ONLY='1', DRAW_MAIN=main,
            ROUTINES='\n'.join(function(core, n) for n in
                ('free_ents','alloc_ents','spawn','kill_all','findent','count_ents')),
            HELPERS='\n'.join(function(core, n) for n in
                ('obor_scene_counters_active','obor_scene_counter_adjust')))
        text = Path(__file__).with_name('entity_capacity_contract.c.in').read_text()
        for key, value in parts.items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text,data).splitlines()]
        self.assertEqual(actual,[dict(revision=r['revision'],drawchecks=2) for r in rows])


def source_parts(engine):
    source = (SOURCE / 'src/engines' / engine / 'openbor.c').read_bytes().decode(
        'utf-8', 'surrogateescape')
    parts = {name: function(source, name) for name in ('spawn', 'kill')}
    parts['helpers'] = '\n'.join(function(source, name) for name in (
        'obor_scene_counters_active', 'obor_scene_counter_adjust')) if \
        'obor_scene_counters_active' in source else ''
    return parts


def program(engine, rows, contracts):
    if (not isinstance(rows, list) or not rows or
            any(not isinstance(row, dict) or not {'engine', 'contract', 'revision'} <= set(row)
                or type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff
                for row in rows)):
        raise ValueError('Explicit native entity spawn contract rows required')
    first = rows[0]
    if (first['engine'] != engine or first['contract'] not in contracts or
            any((row['engine'], row['contract']) != (engine, first['contract']) for row in rows)
            or [row['revision'] for row in rows] != sorted({row['revision'] for row in rows})
            or not isinstance(contracts[first['contract']], dict)
            or set(contracts[first['contract']]) != {'contract', 'cases'}):
        raise ValueError('One engine/expectation group with unique sorted revisions required')
    code = render_entity_spawn(source_parts(engine), revision=first['revision'],
        factor_layout='record', scripts_pointer=True, flag_member=True,
        **contracts[first['contract']])
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One authored entity-spawn entry required')
    entry = '''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@', ','.join(str(row['revision']) for row in rows))
    return code.replace(marker, entry)


class EntitySpawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = load_contract_fixture(CONTRACT_PATH)
        cls.rows, cls.contracts = fixture['sources'], fixture['contracts']
        cls.coverage = fixture['covered_profile_ranges']
        cls.groups, cls.executables = {}, {}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'], row['contract']), []).append(row)
        temporary = tempfile.TemporaryDirectory(prefix='anybor-entity-spawn-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host_flags = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        for index, (key, rows) in enumerate(cls.groups.items()):
            root = SOURCE / 'src/engines' / key[0]
            includes = [root, SOURCE / 'src/port/libretro', SOURCE / 'src/glue', root / 'source',
                        *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
            code = work / ('contract-%d.c' % index)
            executable = code.with_suffix('')
            code.write_bytes(program(key[0], rows, cls.contracts).encode('utf-8', 'surrogateescape'))
            compiled = subprocess.run(compiler + ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare', '-Wno-error=misleading-indentation',
                '-Wno-error=implicit-fallthrough', '-Wno-unused-variable',
                '-Wno-unused-function', '-Wno-unused-parameter', *warnings,
                '-O1', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + key[0],
                *host_flags, '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                str(code), *links, '-lm', '-o', str(executable)],
                capture_output=True, text=True, timeout=60)
            if compiled.stdout:
                sys.stderr.write(compiled.stdout)
            if compiled.stderr:
                sys.stderr.write(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError('Native entity spawn compilation failed')
            cls.executables[key] = executable

    def test_registered_profiles_have_own_source_contracts(self):
        by_revision = {row['revision']: row for row in self.rows}
        self.assertEqual(len(by_revision), len(self.rows))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-entity-spawn-contracts.json', pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(profile['engine'] == span['engine'] and span['first'] <= revision <= span['last']
                   for span in self.coverage):
                self.assertEqual(by_revision[revision]['engine'], profile['engine'])
        for row in self.rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIsInstance(row['counter_updates'], bool)
            self.assertEqual(set(row['source_parts_sha256']), {'spawn', 'kill'})
            for digest in row['source_parts_sha256'].values():
                if digest is not None:
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_native_entity_spawn_for_each_profile_and_boundary_context(self):
        for key, rows in self.groups.items():
            expected = dict(status='PASS', cases=len(self.contracts[key[1]]['cases']))
            for row in rows:
                with self.subTest(engine=row['engine'], revision=row['revision']):
                    observed = subprocess.check_output([str(self.executables[key]), str(row['revision'])],
                        timeout=15, text=True, env=sanitizer_environment())
                    self.assertEqual(json.loads(observed), expected)


if __name__ == '__main__':
    unittest.main()
