"""Verify syntax-scoped routing with complete authored PACK inputs.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import os
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
from content_selection_probe import compile_probe

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
GLUE = Path(os.environ.get('OBOR_SELECTION_GLUE', ROOT / 'src/glue'))


def pack(members):
    content = bytearray(b'PACK\0\0\0\0')
    entries = bytearray()
    for name, body in members.items():
        name = name.encode() + b'\0'
        entries += struct.pack('<III', len(name) + 12, len(content), len(body)) + name
        content += body
    return content + entries + struct.pack('<I', len(content))


class ContentTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anybor-content-triage-')
        cls.root = Path(cls.temp.name)
        cls.host = cls.root / 'selector'
        compile_probe(GLUE / 'libretro.cpp', GLUE / 'anybor_engines.h', GLUE,
                      ROOT / 'src/third_party', cls.host, sanitizers=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def select(self, tag, members=None):
        path = self.root / ('authored' + (' [Build ' + tag + ']' if tag else '') + '.pak')
        path.write_bytes(pack(members or {'data/models.txt': b'load hero data/chars/hero.txt\n',
                                         'data/chars/hero.txt': b'name hero\n'}))
        run = subprocess.run([str(self.host), str(path)], capture_output=True, text=True,
                             check=True, timeout=8)
        result = re.search(r'selection_profile=([A-Za-z0-9_-]+) selection_engine=(\d+)', run.stdout)
        self.assertIsNotNone(result, run.stdout)
        return int(result[1]) if result[1].isdigit() else result[1], run.stdout

    def script(self, tag, source):
        return self.select(tag, {'data/scripts/update.c': source.encode()})

    def test_exact_tags_never_run_triage(self):
        for tag, expected in (('3741',3741),('3780',3780),('6330',6330),
                              ('6392',6392),('6412',6412),('6453',6453),('6453-dev',6453),
                              ('6997',6997),('6997-dev',6997),('7039',7039),('7039-dev',7039),
                              ('7091',7091),('7091-dev',7091),
                              ('7369',7369),('7369-dev',7369),('7391',7391),('7391-dev',7391),
                              ('7420',7420),('7420-dev',7420),
                              ('7612',7612),('7612-dev',7612),('8020',8020),('8020-dev',8020)):
            profile, log = self.script(tag, 'void main(){ movie_load("x"); }')
            self.assertEqual(profile, expected)
            self.assertNotIn('filename triage', log)

    def test_missing_exact_profile_checks_literal_entity_animation_getter(self):
        for tag in ('4199', '4300', '4444'):
            profile, log = self.script(tag, 'void main(){getentityproperty(self,"animation");}')
            self.assertEqual(profile, 4153, log)
            self.assertIn('name=animation bounds=1-4201', log)

    def test_missing_exact_profile_checks_proved_model_requirements(self):
        profile, log = self.select('4444', {'data/chars/hero.txt': b'colourdepth 16bit\n'})
        self.assertEqual(profile, 4456, log)
        self.assertIn('name=16bit bounds=', log)

    def test_missing_exact_historical_tag_checks_content_before_alias_priority(self):
        profile, log = self.script('3810', 'void main(){getlevelproperty("type");}')
        self.assertEqual(profile, 3822, log)
        self.assertIn('candidate 3814 conflicts', log)
        self.assertIn('name=type bounds=3820-', log)

    def test_missing_exact_profile_keeps_a_compatible_candidate(self):
        profile, log = self.script('4047', 'void main(){getentityproperty(self,"animation");}')
        self.assertEqual(profile, 4051, log)
        self.assertNotIn('filename exact triage', log)
        self.assertNotIn('candidate 4051 conflicts', log)

    def test_missing_exact_profile_requires_one_candidate_to_satisfy_all_facts(self):
        profile, log = self.script('4199',
            'void main(){getentityproperty(self,"animation");movie_load("x");}')
        self.assertEqual(profile, 4213, log)
        self.assertIn('no profile satisfies all proved requirements', log)
        self.assertIn('name=animation bounds=1-4201', log)
        self.assertIn('name=movie_load bounds=', log)
        self.assertNotIn('closest compatible profile', log)

    def test_missing_exact_profile_keeps_the_existing_legacy_preflight(self):
        profile, log = self.script('4300', 'void main(){getentityproperty(self,"attack",0);}')
        self.assertEqual(profile, 4153, log)
        self.assertIn('legacy-attack bounds=1-4166', log)

    def test_missing_exact_profile_tag_grammar_keeps_leading_zeroes(self):
        source = 'void main(){getentityproperty(self,"animation");}'
        self.assertEqual(self.script('00004199', source)[0], 4153)
        # Separated unknown variants retain their normal numeric tag contract.
        self.assertEqual(self.script('4199_extra', source)[0], 4153)
        for tag in ('4199extra', '4199-'):
            _, log = self.script(tag, source)
            self.assertNotIn('filename exact triage', log, tag)

    def test_missing_exact_profile_incomplete_scan_retains_only_proved_facts(self):
        members = {'data/chars/first.txt': b'colourdepth 16bit\n',
                   'data/scripts/first.c': b'void main(){getentityproperty(self,"animation");}'}
        members.update(('data/unused/%d.txt' % i, b'name unused\n') for i in range(805))
        profile, log = self.select('4444', members)
        self.assertEqual(profile, 4456, log)
        self.assertIn('scan incomplete', log)
        self.assertIn('name=16bit bounds=', log)
        self.assertNotIn('name=animation bounds=', log)

    def test_available_exact_profiles_keep_their_existing_selection(self):
        pins = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pins['profiles']:
            tag = str(row['build'])
            control, _ = self.select(tag)
            actual, log = self.script(tag, 'void main(){getentityproperty(self,"animation");}')
            self.assertEqual(actual, control, (tag, log))
            self.assertNotIn('filename triage', log)

    def test_entity_animation_requirement_needs_the_complete_native_getter_argument(self):
        for source in (
                '// getentityproperty(self,"animation");\nvoid main(){}',
                'void main(){log("getentityproperty(self, animation)");}',
                'void main(){changeentityproperty(self,"animation",0);}',
                'void main(){getentityproperty(self,"animationid");}',
                'void main(){getentityproperty(self,8);}',
                'void main(){getentityproperty(self,"animation" + suffix);}',
                'void getentityproperty(int a,int b){} void main(){getentityproperty(0,"animation");}',
                '#define ALIAS 1\nvoid main(){getentityproperty(self,"animation");}'):
            self.assertEqual(self.script('4199', source)[0], 4213, source)
        profile, log = self.script('4199',
            'void main(){getentityproperty(getlocalvar("self"),"animation");}')
        self.assertEqual(profile, 4153, log)

    def test_animation_getter_contract_matches_each_profile_source_observation(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures' /
                              'profile-entity-animation-contracts.json')
        pins = json.loads((ROOT / 'src/pin.json').read_text())
        self.assertEqual({(str(p['build']), p['engine'], int(p.get('revision', p['build'])))
                          for p in contract_profiles(fixture, pins['profiles'])},
                         {(p['profile'], p['engine'], int(p.get('revision', p['profile'])))
                          for p in contract_profiles(fixture, fixture['profiles'])})
        rules = subprocess.check_output([str(self.host), '--rules'], text=True, timeout=8)
        rule = next(row.split() for row in rules.splitlines()
                    if row.split()[1:3] == ['10', 'animation'])
        for row in contract_profiles(fixture, fixture['profiles']):
            actual = subprocess.check_output([str(self.host), '--rule-probe', rule[0],
                                             str(row.get('revision', row['profile'])), row['engine']],
                                            text=True, timeout=8)
            self.assertEqual(bool(int(actual)), row['supported'], row)

    def test_official_automatic_build_coverage(self):
        for tag, expected in (('3401',3406),('3406',3406),('3407',3411),('3411',3411),
                              ('3449',3449),('3450',3454),('3482',3482),('3483',3500),
                              ('3500',3500),('3501',3509),('3509',3509),('3555',3557),
                              ('3608',3608),('3609',3609),('3612',3614),
                              ('3664',3664),('3665',3665),('3666',3666),
                              ('3668',3669),('3740',3740),('3741',3741),
                              ('3742',3742),('3742-3742',3769),('3743',3769),
                              ('3761',3761),('3762',3769),('3769',3769),
                              ('3770',3773),('3773',3773),('3774',3780),
                              ('4087',4107),('4088',4088),('4089',4107),
                              ('4107',4107),('4108',4111),('4111',4111),
                              ('4112',4129),('4129',4129),('4130',4153),
                              ('4153',4153),('4154',4213),
                              ('4433',4453),('4452',4453),('4453',4453),
                              ('4454',4454),('6000',6119),('6330',6330),
                              ('6331',6385),('6385',6385),('6386',6390),
                              ('6390',6390),('6391',6391),('6393',6391),('6411',6391)):
            with self.subTest(tag=tag):
                self.assertEqual(self.select(tag)[0], expected)

    def test_early_api_requirements_match_each_own_source(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures' /
                                        'profile-early-content-contracts.json')
        rules = subprocess.check_output([str(self.host), '--rules'], text=True, timeout=8)
        ids = {(int(parts[1]), parts[2]): parts[0]
               for parts in (line.split() for line in rules.splitlines())}
        for row in fixture['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['supported']), len(fixture['rules']))
            for rule, expected in zip(fixture['rules'], row['supported']):
                actual = subprocess.check_output([str(self.host), '--rule-probe',
                    ids[(rule['kind'], rule['name'])], str(row['revision']), row['engine']],
                    text=True, timeout=8)
                self.assertEqual(bool(int(actual)), expected, (row['revision'], rule))
        for row in fixture['controls']:
            actual = subprocess.check_output([str(self.host), '--rule-probe',
                ids[(row['kind'], row['name'])], str(row['revision']), row['engine']],
                text=True, timeout=8)
            self.assertEqual(bool(int(actual)), row['supported'], row)

    def test_later_script_registration_bounds_match_own_sources(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures' /
                                        'profile-late-script-registry-contracts.json')
        rules = subprocess.check_output([str(self.host), '--rules'], text=True, timeout=8)
        ids = {parts[2]: parts[0] for parts in
               (line.split() for line in rules.splitlines()) if parts[1] == '0'}
        for row in fixture['sources']:
            # Own native registration contracts cover every context in this era.
            for name, expected in [('changeattackproperty', row['attack_mapper'])] + [
                    (name, row['revision'] < 3845)
                    for name in ('settexture', 'setvertex', 'trianglelist')]:
                actual = subprocess.check_output([str(self.host), '--rule-probe', ids[name],
                    str(row['revision']), fixture['engine']], text=True, timeout=8)
                self.assertEqual(bool(int(actual)), expected, (row['revision'], name))
        for name, bounds in [('changeattackproperty', (3843, 4166)),
                             ('settexture', (3381, 3844)), ('setvertex', (3381, 3844)),
                             ('trianglelist', (3381, 3844))]:
            lower, upper = bounds
            for revision in (lower - 1, lower, upper, upper + 1):
                actual = subprocess.check_output([str(self.host), '--rule-probe', ids[name],
                    str(revision), '3842'], text=True, timeout=8)
                self.assertEqual(bool(int(actual)), lower <= revision <= upper,
                                 (name, revision))

    def test_modern_api_requirements_match_each_own_source(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures' /
                                        'profile-modern-content-contracts.json')
        rules = subprocess.check_output([str(self.host), '--rules'], text=True, timeout=8)
        ids = {(int(parts[1]), parts[2]): parts[0]
               for parts in (line.split() for line in rules.splitlines())}
        for row in fixture['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['supported']), len(fixture['rules']))
            for rule, expected in zip(fixture['rules'], row['supported']):
                actual = subprocess.check_output([str(self.host), '--rule-probe',
                    ids[(rule['kind'], rule['name'])], str(row['revision']), row['engine']],
                    text=True, timeout=8)
                self.assertEqual(bool(int(actual)), expected, (row['revision'], rule))

    def test_unlabelled_modern_requirements_use_available_official_profiles(self):
        for source, expected in (
                ('void main(){get_global_config_property(0);}', 8023),
                ('void main(){log(openborconstant("GLOBAL_CONFIG_PROPERTY_AJSPECIAL"));}', 8023),
                ('void main(){load_palette(0,"x");}', 8023),
                ('void main(){get_flash_property(0);}', 8023),
                ('void main(){get_music_channel_property(0);}', 7735)):
            self.assertEqual(self.script('', source)[0], expected, source)

    def test_unlabelled_native_registry_intersects_discontinuous_availability(self):
        cases = (
            ('getanimationproperty(self, 0, "animhits");', 4213),
            ('srand(7); getanimationproperty(self, 0, "animhits");', 4079),
            ('srand(7);', 6391),
            ('getbglayerproperty(0, "xratio");', 3482),
            ('get_recursive_damage_property(0, 0);', 7735),
        )
        for calls, expected in cases:
            with self.subTest(calls=calls):
                profile, log = self.script('', 'void main(){' + calls + '}')
                self.assertEqual(profile, expected, log)
        profile, log = self.script('', 'void main(){getbglayerproperty(0,"xratio");movie_load("x");}')
        self.assertEqual(profile, 6391, log)
        self.assertIn('no common automatic profile', log)

    def test_legacy_attack_route_uses_other_requirements_to_refine_untagged_content(self):
        source = 'void main(){getentityproperty(self,"attack","damage",0,0);getpixel(screen,0,0,0);}'
        profile, log = self.script('', source)
        self.assertEqual(profile, 3626, log)
        self.assertIn('(legacy script API)', log)
        self.assertIn('legacy-attack bounds=1-4166', log)

    def test_unlabelled_bound_names_ignore_dormant_shadowed_and_conditional_source(self):
        for call in (b'getbglayerproperty(0,"xratio");', b'getpixel(screen,0,0,0);'):
            dormant = {'data/scripts/unused.c': b'void main(){' + call + b'}'}
            self.assertEqual(self.select('', dormant)[0], 6391)
        for script in (
                b'#if CUSTOM\ngetbglayerproperty(0,"xratio");\n#endif\n',
                b'#define getbglayerproperty other\ngetbglayerproperty(0,"xratio");\n',
                b'void getbglayerproperty(int n, char key){}\n'
                b'void main(){getbglayerproperty(0,"xratio");}',
                b'void main(){log("getbglayerproperty(0, xratio)");}'):
            with self.subTest(script=script):
                profile, log = self.select('', {'data/scripts/update.c': script})
                self.assertEqual(profile, 6391, log)

    def test_unlabelled_bound_import_retains_api_facts_across_scan_limits(self):
        members = {f'data/unused/{i}.txt': b'# unused\n' for i in range(805)}
        members['data/scripts/update.c'] = b'#import "helper.c"\nvoid main(){helper();}'
        members['data/scripts/helper.c'] = b'void helper(){getplayerproperty(0,"weaponum");}'
        profile, log = self.select('', members)
        self.assertEqual(profile, 3818, log)
        self.assertIn('name=weaponum bounds=1-3820', log)
        self.assertIn('scan incomplete', log)

    def test_unlabelled_constant_is_a_complete_literal_of_the_native_call(self):
        profile, log = self.script('', 'void main(){openborconstant("PLAYER_MAX_Z");}')
        self.assertEqual(profile, 7142, log)
        profile, log = self.script('', 'void main(){openborconstant("MAX_PANELS");}')
        self.assertEqual(profile, 3994, log)
        self.assertIn('bound native constant max_panels', log)
        for source in (
                'void main(){log("MAX_PANELS");}',
                'void main(){openborconstant("MAX_PANELS"+suffix);}',
                '#define openborconstant local\nvoid main(){openborconstant("MAX_PANELS");}'):
            self.assertEqual(self.script('', source)[0], 6391, source)

    def test_unlabelled_entity_getter_and_system_query_require_literal_properties(self):
        profile, log = self.script('', 'void main(){getentityproperty(self,"grabdistance");}')
        self.assertEqual(profile, 8023, log)
        self.assertIn('bound native entity getter grabdistance', log)
        profile, log = self.script('', 'void main(){openborvariant("cheats");}')
        self.assertEqual(profile, 7142, log)
        self.assertIn('bound native system query cheats', log)
        for source in ('getentityproperty(self, "grabdistance" + suffix);',
                       'getentityproperty(self, key);', 'openborvariant("grabdistance");'):
            self.assertEqual(self.script('', 'void main(){' + source + '}')[0], 6391)

    def test_unlabelled_registry_follows_referenced_models_and_their_scripts(self):
        members = {'data/models.txt': b'load hero "data/chars/hero name.txt"\n',
                   'data/chars/hero name.txt': b'name hero\nthinkscript data/scripts/think.c\n',
                   'data/scripts/think.c': b'void main(){getbglayerproperty(0,"xratio");}'}
        self.assertEqual(self.select('', members)[0], 3482)
        members['data/chars/hero name.txt'] = (
            b'name hero\nanim idle\n@script\ngetbglayerproperty(0,"xratio");\n@end\n')
        self.assertEqual(self.select('', members)[0], 3482)

    def test_unlabelled_registry_follows_scripts_of_declared_levels(self):
        members = {'data/levels.txt': b'set test\nfile data/levels/stage.txt\n',
                   'data/levels/stage.txt': b'levelscript data/scripts/stage.c\n',
                   'data/scripts/stage.c': b'void main(){getpixel(screen,0,0,0);}'}
        self.assertEqual(self.select('', members)[0], 3626)
        members['data/levels.txt'] = b'set test\n'
        self.assertEqual(self.select('', members)[0], 6391)

    def test_unlabelled_playsample_argument_count_controls_compatibility(self):
        for args, expected in (('0,0,100,100,100,0', 3554),
                               ('getglobalvar("sound,index")', 6391)):
            with self.subTest(args=args):
                profile, log = self.script('', 'void main(){openborvariant("canvas");'
                                           'playsample(' + args + ');}')
                self.assertEqual(profile, expected, log)
                if expected == 6391:
                    self.assertIn('no common automatic profile', log)

    def test_unlabelled_model_rules_are_scoped_to_their_command_and_argument(self):
        members = {'data/models.txt': b'load hero data/chars/hero.txt\n',
                   'data/chars/hero.txt': b'name hero\nanim idle\njumpframe 0 3 2\n',
                   'data/scripts/update.c': b'void main(){getpixel(screen,0,0,0);}'}
        self.assertEqual(self.select('', members)[0], 3626)
        members['data/chars/hero.txt'] = b'name hero\nanim idle\njumpframe this 3 2\n'
        profile, log = self.select('', members)
        self.assertEqual(profile, 6391, log)
        self.assertIn('no common automatic profile', log)
        members['data/chars/hero.txt'] = b'name hero\ngrabdistance 20\n'
        self.assertEqual(self.select('', members)[0], 3626)
        members['data/models.txt'] += b'grabdistance 20\n'
        profile, log = self.select('', members)
        self.assertEqual(profile, 6391, log)
        self.assertIn('no common automatic profile', log)

    def test_unlabelled_uses_early_offscreen_factor_boundary_in_models_index(self):
        members = {'data/models.txt': b'offscreen_noatk_factor 0.5\n',
                   'data/scripts/update.c': b'void main(){openborvariant("usesave");}'}
        profile, log = self.select('', members)
        self.assertEqual(profile, 3854, log)
        self.assertIn('name=offscreen_noatk_factor bounds=3683-', log)
        members['data/chars/loose.txt'] = members.pop('data/models.txt')
        profile, log = self.select('', members)
        self.assertEqual(profile, 3854, log)
        self.assertNotIn('offscreen_noatk_factor bounds=', log)

    def test_missing_modern_profiles_respect_api_additions_and_retirements(self):
        for name in ('copy_palette', 'get_palette_property', 'set_palette_property',
                     'load_palette', 'get_flash_property', 'set_flash_property'):
            profile, log = self.script('7500', 'void main(){' + name + '(0);}')
            self.assertEqual(profile, 7735, log)
            self.assertIn('name=' + name + ' bounds=', log)
        profile, log = self.script('7600', 'void main(){free_drawmethod(0);}')
        self.assertEqual(profile, 7556, log)
        self.assertIn('name=free_drawmethod bounds=6982-7581', log)
        for source in ('void main(){get_music_channel_property(0);}',
                       'void main(){set_music_channel_property(0,1);}',
                       'void main(){openborvariant("music_channel");}'):
            profile, log = self.script('7900', source)
            self.assertEqual(profile, 7735, log)
            self.assertIn('bounds=7590-7887', log)
        # An exact available declaration keeps its established authority.
        self.assertEqual(self.script('7530', 'void main(){load_palette(0,"x");}')[0], 7530)

    def test_unavailable_tags_respect_later_script_retirements(self):
        for name in ('settexture', 'setvertex', 'trianglelist'):
            profile, log = self.script('3843', 'void main(){' + name + '(0);}')
            self.assertEqual(profile, 3842, log)
            self.assertIn('name=' + name + ' bounds=3381-3844', log)
            # An available exact tag still has the documented authority.
            self.assertEqual(self.script('3842', 'void main(){' + name + '(0);}')[0], 3842)
        profile, log = self.script('4167', 'void main(){changeattackproperty("damage",1);}')
        self.assertEqual(profile, 4153, log)
        self.assertIn('name=changeattackproperty bounds=3843-4166', log)

    def test_contract_inspection_preserves_positive_facts_and_uncertainty(self):
        path = self.root / 'authored-inspection.pak'
        path.write_bytes(pack({'data/scripts/main.c':
            b'void main(){settexture(0);changeattackproperty("damage",1);}'}))
        def inspect():
            return json.loads(subprocess.check_output([str(self.host), '--inspect-contracts',
                str(path), '3842', '3842'], text=True, timeout=8))
        result = inspect()
        self.assertTrue(result['complete'])
        self.assertFalse(result['script_bindings_ambiguous'])
        facts = {row['name']: row['supported'] for row in result['facts']}
        self.assertEqual(facts, {'settexture': True, 'changeattackproperty': False})
        path.write_bytes(pack({'data/scripts/main.c':
            b'#define UNKNOWN 1\nvoid main(){settexture(0);}'}))
        result = inspect()
        self.assertTrue(result['script_bindings_ambiguous'])
        self.assertEqual(result['facts'], [])

    def test_sprite_offset_requirements_distinguish_reads_and_writes(self):
        for name in ('offsetx', 'offsety'):
            profile, log = self.script('3500-3665',
                'void main(){getentityproperty(self,"spritea","' + name + '",0,0);}')
            self.assertEqual(profile, 3608, log)
            self.assertIn('name=' + name + ' bounds=3350-', log)
            self.assertEqual(self.script('3500-3665',
                'void main(){changeentityproperty(self,"spritea","' + name + '",0,0,1);}')[0], 3608)
            for source in (
                    'void main(){log("getentityproperty(self,spritea,' + name + ')");}',
                    'void main(){getentityproperty(self,"spritea","' + name + '"+suffix);}',
                    'void getentityproperty(int a,int b,int c){} void main(){getentityproperty(0,"spritea","' + name + '");}'):
                self.assertEqual(self.script('3500-3665', source)[0], 3665, source)

    def test_early_graphics_calls_need_literal_syntax_and_keep_exact_profiles(self):
        calls = ('changedrawmethod(self,"xrepeat",2);', 'openborvariant("viewportx");',
                 'getpixel(screen,0,0,0);', 'zoom(0,0,320,240,1);')
        for call in calls:
            profile, log = self.script('3500', 'void main(){' + call + '}')
            self.assertEqual(profile, 3500, log)
            self.assertNotIn('filename exact triage', log)
        for source in ('void main(){log("openborvariant(viewportx)");}',
                       'void main(){openborvariant("viewportx"+suffix);}',
                       'void main(){changedrawmethod(self,"xrepeat"+suffix,2);}'):
            _, log = self.script('3500-3665', source)
            self.assertNotIn('name=viewportx bounds=', log)
            self.assertNotIn('name=xrepeat bounds=', log)

    def test_pain_time_aiflag_contract_matches_each_early_source(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures' /
                                        'profile-early-entity-namespaces.json')
        rules = subprocess.check_output([str(self.host), '--rules'], text=True, timeout=8)
        rule = next(row.split() for row in rules.splitlines()
                    if row.split()[1:3] == ['7', 'pain_time'])
        observed = set()
        for row in fixture['sources']:
            expected = 'pain_time' in row['namespaces']['aiflag']['names']
            observed.add(expected)
            actual = subprocess.check_output([str(self.host), '--rule-probe', rule[0],
                                             str(row['revision']), row['engine']],
                                            text=True, timeout=8)
            with self.subTest(profile=row['profile']):
                self.assertEqual(bool(int(actual)), expected)
        self.assertEqual(observed, {False, True})

    def test_missing_early_exact_tag_respects_pain_time_introduction(self):
        pins = json.loads((ROOT / 'src/pin.json').read_text())
        compatible = [int(row.get('revision', row['build'])) for row in pins['profiles']
                      if row['engine'] == '3400' and row.get('automatic', True) and
                      int(row.get('revision', row['build'])) >= 3367]
        self.assertTrue(compatible)
        profile, log = self.script('3060',
            'void main(){getentityproperty(self,"aiflag","pain_time");}')
        self.assertEqual(profile, min(compatible), log)
        # Explicit tags with their own profile retain authority over content.
        if any(row['build'] == '3366' for row in pins['profiles']):
            profile, log = self.script('3366',
                'void main(){getentityproperty(self,"aiflag","pain_time");}')
            self.assertEqual(profile, 3366, log)
            self.assertNotIn('conflicts with proved content', log)

    def test_weak_old_minimum_keeps_unlabelled_fallback_policy(self):
        pins = json.loads((ROOT / 'src/pin.json').read_text())
        fallback = int(pins['fallback_build'])
        for tag in (None, 'XXXX'):
            for command in (b'spdirection 1\n', b'maxattacks 2\n', b'offscreenkill 100\n'):
                profile, log = self.select(tag, {'data/chars/hero.txt': command})
                with self.subTest(tag=tag, command=command):
                    self.assertEqual(profile, fallback, log)
            profile, log = self.select(tag,
                {'data/chars/hero.txt': b'spdirection 1\ncounterframe 1 1 0\n'})
            self.assertEqual(profile, 4213, log)

    def test_early_compatible_alias_retains_filename_priority_over_legacy_preflight(self):
        profile, log = self.script('4108',
            'void main(){getentityproperty(self,"attack",0);}')
        self.assertEqual(profile, 4111, log)
        self.assertIn('(filename tag)', log)

    def test_exact_only_profile_does_not_enter_weak_tag_triage(self):
        self.assertEqual(self.select('4088')[0], 4088)
        self.assertEqual(self.select('4088-4088')[0], 4107)
        self.assertEqual(self.select('408X')[0], 4086)
        exact_only = (3185, 3787, 3792, 3826, 3880, 3896, 3968, 3970, 4077, 4097,
                      6453, 6997, 7039, 7091, 7369, 7391, 7420, 7612, 8020)
        for revision in exact_only:
            with self.subTest(revision=revision):
                self.assertEqual(self.select(str(revision))[0], revision)
                for suffix in (' dev', '-DEV', '_Dev'):
                    self.assertEqual(self.select(str(revision) + suffix)[0], revision)
                self.assertNotIn(self.select('%d-%d' % (revision, revision))[0], exact_only)
        self.assertNotIn(self.select('396X')[0], (3968, 3970))
        self.assertNotEqual(self.select('645X')[0], 6453)

    def test_early_development_tags_select_the_existing_engine(self):
        for revision, engine in ((3185, 3400), (3787, 3842), (3792, 3842),
                                 (3826, 3842), (3880, 3842), (3896, 3842),
                                 (4077, 4086), (4097, 4086)):
            with self.subTest(revision=revision):
                profile, log = self.script(f'{revision}-dev', 'void main(){ movie_load("x"); }')
                self.assertEqual(profile, revision)
                self.assertIn(f'selection_profile={revision} selection_engine={engine}', log)
                self.assertNotIn('filename triage', log)

    def test_palette_requirement_excludes_only_the_incompatible_revision(self):
        for text in (b'colourdepth 8bit\n', b'colourdepth 16bit\n', b'remap a.gif b.gif\n'):
            profile, log = self.select('44XX', {'data/chars/hero.txt': text})
            self.assertEqual(profile,4456)
            self.assertIn('content rule',log)
            self.assertEqual(self.select('6XXX', {'data/chars/hero.txt': text})[0],6391)
        video = {'data/video.txt': b'colourdepth 32bit\n'}
        self.assertEqual(self.select('44XX', video)[0], 4456)
        self.assertEqual(self.select('4453', video)[0], 4453)

    def test_model_and_binding_boundaries_choose_supported_stable_then_dev(self):
        for text, expected in ((b'boomerang 1\n',6330),(b'ebox 1 2 3 4\n',6391),
                               (b'on_bind_update_other_to_self_script data/scripts/hook.c\n',6510)):
            self.assertEqual(self.select('6XXX', {'data/chars/hero.txt': text})[0],expected)
        for script, expected in (( 'unload_model("hero");',6510),
                                 ('openborconstant("BINDING_ANI_NONE");',6412),
                                 ('openborconstant("BINDING_MATCHING_NONE");',6510)):
            self.assertEqual(self.script('6XXX','void main(){'+script+'}')[0],expected)

    def test_historical_property_and_constant_syntax(self):
        for tag, source, expected in (
                ('3780-3839','getplayerproperty(0,"weaponum");',3818),
                ('3780-3839','getentityproperty(self,"aiflag","freezetime");',3793),
                ('3780-3831','openborconstant("ATK_LAND");',3831),
                ('3780-3839','exit(0);',3839),
                ('3780-3839','openborvariant("sample_play_id");',3839),
                ('3792-3911','getlevelproperty("type");',3854)):
            profile,log=self.script(tag,'void main(){'+source+'}')
            self.assertEqual(profile,expected,log)

    def test_label_wins_a_contradiction_with_a_visible_reason(self):
        profile,log=self.script('3780-3831','void main(){exit(0);}')
        self.assertEqual(profile,3831)
        self.assertIn('content contradicts tag',log)
        self.assertIn('tag-conflict',log)

    def test_legacy_api_intersects_the_declared_interval(self):
        profile,log=self.script('4XXX','void main(){getentityproperty(self,"attack",0);}')
        self.assertEqual(profile,4153)
        self.assertIn('legacy-attack bounds=1-4166',log)

    def test_comments_prose_dynamic_arguments_and_local_binding_are_inconclusive(self):
        for source in ('// openborconstant("BINDING_ANI_NONE");\nvoid main(){}',
                       '/* unload_model("x"); */ void main(){}',
                       'void main(){log("unload_model and BINDING_ANI_NONE");}',
                       'void main(){getplayerproperty(0,"weaponum" + suffix);}',
                       'void unload_model(int x){} void main(){unload_model(0);}',
                       '#define CUSTOM 1\nvoid main(){unload_model(0);}'):
            self.assertEqual(self.script('6XXX',source)[0],6391,source)

    def test_scan_limits_keep_positive_model_facts_with_and_without_tag(self):
        members={'data/chars/first.txt':b'boomerang 1\n'}
        members.update(('data/unused/%d.txt'%i,b'name unused\n') for i in range(805))
        profile,log=self.select('6XXX',members)
        self.assertEqual(profile,6330)
        self.assertIn('scan incomplete',log)
        self.assertIn('name=boomerang bounds=',log)
        self.assertEqual(self.select('',members)[0],6330)
        members['data/chars/first.txt']=b'remap first.gif second.gif\n'
        self.assertEqual(self.select('44XX',members)[0],4456)

    def test_incomplete_scan_cannot_prove_native_script_binding(self):
        members={'data/scripts/first.c':b'void main(){unload_model(0);}\n'}
        members.update(('data/unused/%d.txt'%i,b'name unused\n') for i in range(805))
        members['data/scripts/last.c']=b'void unload_model(int value){}\n'
        profile,log=self.select('6XXX',members)
        self.assertEqual(profile,6391)
        self.assertIn('scan incomplete',log)
        self.assertNotIn('name=unload_model bounds=',log)

    def test_oversized_later_file_does_not_erase_a_complete_model_fact(self):
        members={'data/chars/first.txt':b'colourdepth 16bit\n',
                 'data/oversized.txt':b' '*(2*1024*1024+1)}
        profile,log=self.select('44XX',members)
        self.assertEqual(profile,4456)
        self.assertIn('scan incomplete',log)

    def test_unlabelled_content_applies_literal_property_constraints(self):
        self.assertEqual(self.script('', 'void main(){getplayerproperty(0,"weaponum");}')[0], 3818)
        self.assertEqual(self.script('', 'void main(){getplayerproperty(0,"weapnum");}')[0], 6391)

    def test_every_rule_has_a_syntactic_probe_and_checked_native_boundaries(self):
        rules=subprocess.check_output([str(self.host),'--rules'],text=True,timeout=8).splitlines()
        self.assertGreater(len(rules),30)
        names=[row.split()[2] for row in rules]
        self.assertEqual(names,sorted(names))
        for row in rules:
            ident,kind,name,lower,upper,flags,gap_lower,gap_upper=row.split()
            kind,lower,upper,flags,gap_lower,gap_upper=map(int,(kind,lower,upper,flags,gap_lower,gap_upper))
            controls={max(1,lower-1),lower,min(99999,upper),min(99999,upper+1),4453,7086,7091,7123,7142}
            if gap_lower: controls.update((gap_lower-1,gap_lower,gap_upper,gap_upper+1))
            for build in controls:
                for engine in {build,7142}:
                    expected=(lower<=build<=upper and not(flags&1 and build==4453) and
                              not(gap_lower and gap_lower<=build<=gap_upper))
                    if flags&2 and engine==7142 and build in (7086,7091,7123):expected=True
                    actual=subprocess.check_output([str(self.host),'--rule-probe',ident,str(build),str(engine)],
                                                   text=True,timeout=8)
                    self.assertEqual(int(actual),int(expected),(row,build,engine))
            if kind >= 14:
                continue  # Dedicated unlabelled dependency tests exercise these observations.
            if kind==0: source='void main(){'+name+'();}'
            elif kind==1: source='void main(){openborconstant("'+name+'");}'
            elif kind==3: source='void main(){getplayerproperty(0,"'+name+'");}'
            elif kind==4: source='void main(){changeplayerproperty(0,"'+name+'",0);}'
            elif kind==5: source='void main(){getlevelproperty("'+name+'");}'
            elif kind==6: source='void main(){openborvariant("'+name+'");}'
            elif kind==7: source='void main(){getentityproperty(self,"aiflag","'+name+'");}'
            elif kind==10: source='void main(){getentityproperty(self,"'+name+'");}'
            elif kind==11: source='void main(){changedrawmethod(self,"'+name+'",0);}'
            elif kind==12: source='void main(){getentityproperty(self,"spritea","'+name+'",0,0);}'
            elif kind==13: source='void main(){changeentityproperty(self,"spritea","'+name+'",0,0,0);}'
            else: source=None
            if source is not None:
                _,log=self.script('1000-99999',source)
            else:
                body=(name+' 1\n' if kind==2 else 'defense '+name+' 1\n' if kind==8 else 'colourdepth '+name+'\n')
                _,log=self.select('1000-99999',{'data/chars/hero.txt':body.encode()})
            self.assertIn('name='+name+' bounds=',log,row)


if __name__ == '__main__':
    unittest.main()
