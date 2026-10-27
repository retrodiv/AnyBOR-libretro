"""Check historical combat and runtime contracts using the actual C bodies.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/3842'))


def attack_domain_revisions():
    fixture = load_contract_fixture(Path(__file__).parent /
        'fixtures/profile-attack-domain-contracts.json')
    rows = fixture['sources']
    revisions = [row['revision'] for row in rows]
    if len(revisions) != len(set(revisions)) or not (
            contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= set(revisions)):
        raise ValueError('Own attack-domain profiles and boundary controls required')
    for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
        if profile['engine'] == '3842' and int(profile.get('revision', profile['build'])) not in revisions:
            raise ValueError('Registered profile missing its own attack-domain source')
    for row in rows:
        revision = row['revision']
        if (row['base_slots'] != (16 if revision < 3830 else 20) or
                row['special_slots'] != (6 if revision < 3831 else 10) or
                row['zero_tail'] != (revision < 3831) or
                row['environment_types'] != (revision >= 3830) or
                not re.fullmatch(r'[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch(r'[0-9a-f]{64}', digest) for digest in row['source_sha256'].values())):
            raise ValueError('Invalid own-source attack-domain contract')
    return revisions


def native(program, include_dirs=(), extra_flags=()):
    with tempfile.TemporaryDirectory(prefix='anybor-historical-behavior-') as temp:
        work = Path(temp)
        source = work / 'probe.c'
        source.write_text(program)
        includes = [item for directory in include_dirs for item in ('-I', str(directory))]
        subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + includes + [
            '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations', '-g', *extra_flags,
            '-fsanitize=address,undefined', str(source), '-o', str(work / 'probe')],
            check=True, timeout=60)
        subprocess.run([str(work / 'probe')], check=True, timeout=20, cwd=work,
                       stdout=subprocess.DEVNULL)


class HistoricalBehaviorTests(unittest.TestCase):
    def test_release_assertions_cover_late_header_includes(self):
        from historical_assertions import render_late_assertions
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-assertion-contracts.json')
        port = ROOT / 'src/port/libretro'
        with patch.dict(os.environ, sanitizer_environment()):
            for enabled in (True, False):
                with self.subTest(assertions_enabled=enabled):
                    native(render_late_assertions(port, fixture, assertions_enabled=enabled),
                           include_dirs=(port,),
                           extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_every_engine_build_enables_controlled_assertions(self):
        for engine in json.loads((ROOT / 'src/pin.json').read_text())['engines']:
            with self.subTest(engine=engine['build']):
                text = (ROOT / 'src/engines' / engine['build'] / 'Makefile.libretro').read_text()
                self.assertIn('-DOBOR_CONTROLLED_ASSERTIONS=1', text)

    def test_assertion_diagnostics_and_safe_stop_match_source_profiles(self):
        from historical_assertions import render_assertions
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-assertion-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(fixture['safe_engine_termination'])
        self.assertTrue(contract_revisions(fixture, {3400, 3741, 3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] in ('3400', '3741', '3842'):
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['diagnostic_style'], 'logged_assert' if row['revision'] >= 3811 else 'c_assert')
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            for debug_assertions in (True, False):
                with self.subTest(debug_assertions=debug_assertions):
                    program = render_assertions(ROOT / 'src/engines/3842', ROOT / 'src/engines/3741',
                                                ROOT / 'src/port/libretro', fixture,
                                                assertions_enabled=debug_assertions)
                    native(program, extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_fade_pixels_and_frame_counts_match_source_profiles(self):
        from historical_fade import render_fade
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-fade-pixel-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            revision = row['revision']
            self.assertEqual(row['fade_kind'], 'legacy_mixed_gamma' if revision < 3774 else
                             'legacy_equal_gamma' if revision < 3775 else
                             'buffer_delta' if revision < 3777 else 'buffer_capped')
            self.assertEqual(row['capped_iterations'], revision >= 3777)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                if digest is not None:
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_fade(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-Wno-unused-parameter', '-Wno-sign-compare',
                                '-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_modelcopy_script_loading_and_callback_match_source_profiles(self):
        from historical_model_callbacks import render_modelcopy_callback
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-modelcopy-callback-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['modelcopy_available'], row['revision'] >= 3793)
            self.assertEqual(row['source_sha256']['callback'] is not None, row['modelcopy_available'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_modelcopy_callback(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-Wno-error=misleading-indentation',
                                '-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_callback_entry_storage_matches_each_source_profile(self):
        from historical_script_callbacks import render_callback_storage
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-callback-storage-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['creation_slot_original'], row['revision'] >= 3762)
            self.assertEqual(row['create_name'], None if row['revision'] < 3762 else
                             'init' if row['revision'] < 3767 else 'oncreate')
            self.assertEqual(row['destroy_name'], 'clear' if row['revision'] < 3767 else 'ondestroy')
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_callback_storage(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_video_parser_modes_and_spawn_coordinates_match_source_profiles(self):
        from historical_video_modes import render_video_spawn
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-video-spawn-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        self.assertTrue(fixture['standard_blocks_identical'])
        self.assertEqual(len(fixture['standard_modes']), 7)
        self.assertTrue(all(len(row) == 10 for row in fixture['standard_modes']))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['direct_dimensions'], row['revision'] >= 3784)
            self.assertEqual(row['direct_offset'], row['revision'] >= 3785)
            self.assertEqual(row['spawn_z_clamp'], row['revision'] < 3800)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_video_spawn(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsigned-char', '-fsanitize=pointer-overflow',
                                '-fno-sanitize-recover=all'))

    def test_menu_key_names_and_unknown_commands_match_source_profiles(self):
        from historical_keyboard_names import render_keyboard_names
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-keyboard-names-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['escape_key_name'], row['revision'] >= 3777)
            self.assertEqual('SDID_ESC' in row['indices'], row['escape_key_name'])
            self.assertEqual(row['unknown_menu_command_warning'], row['revision'] < 3766)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_keyboard_names(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_selection_icon_zero_map_matches_each_source_profile(self):
        from historical_hud_icons import render_selection_icon
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-selection-icon-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['zero_map_uses_sprite_palette'], row['revision'] < 3673)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_selection_icon(ROOT / 'src/engines/3741', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_selection_names_and_final_player_countdown_match_source_profiles(self):
        from historical_selection_runtime import render_selection_runtime
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-selection-runtime-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['names_casefold_full'], row['revision'] >= 3831)
            self.assertEqual(row['join_gates_half_counter'], row['revision'] >= 3820)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_selection_runtime(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_saved_game_playable_reset_matches_source_profiles(self):
        from historical_model_selectors import render_playable_reset
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-playable-reset-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['saved_game_resets_playable'], row['revision'] < 3822)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_playable_reset(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_unsigned_score_and_ai_sentinels_match_source_profiles(self):
        from historical_unsigned_scalars import render_unsigned_scalars
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-unsigned-scalar-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['sentinel_equality'], row['revision'] >= 3791)
            self.assertTrue(row['unsigned_model_ai'])
            self.assertTrue(row['unsigned_spawn_score'])
            self.assertTrue(row['signed_spawn_multiple'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_unsigned_scalars(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-Wno-sign-compare', '-fsanitize=pointer-overflow',
                                '-fno-sanitize-recover=all'))

    def test_player_defaults_and_input_extent_match_source_profiles(self):
        from historical_player_extent import render_player_extent
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-player-extent-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['global_player_default'], row['revision'] >= 3667)
            self.assertEqual(row['refresh_all_ports'], row['revision'] >= 3668)
            self.assertTrue(row['movie_disabled'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_player_extent(ROOT / 'src/engines/3741', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_buffered_file_precedence_matches_each_source_profile(self):
        from historical_file_precedence import render_file_precedence
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-external-file-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['direct_loose_first'], row['revision'] >= 3777)
            self.assertTrue(row['uncached_loose_override'])
            self.assertTrue(row['cached_reads_archive_index'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_file_precedence(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_model_cache_selectors_match_each_source_profile(self):
        from historical_model_selectors import render_model_selectors
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-model-selector-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['name_lookup_selector'], row['revision'] >= 3822)
            self.assertTrue(row['getter_case1_falls_into_name'])
            self.assertTrue(row['setter_cases0to3_fall_into_selectable'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_model_selectors(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-Wno-implicit-fallthrough', '-fsanitize=pointer-overflow',
                                '-fno-sanitize-recover=all'))

    def test_animation_locals_and_table_capacity_match_source_profiles(self):
        from historical_animation_locals import render_animation_locals
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-animation-local-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['setter_requires_initialized_owner'], row['revision'] < 3814)
            self.assertEqual(row['setter_collects_at_capacity'], row['revision'] >= 3815)
            self.assertEqual(row['animation_saves_local_context'], row['revision'] >= 3813)
            self.assertEqual(row['animation_rebinds_current_model'], row['animation_saves_local_context'])
            self.assertEqual(row['nested_option_registered'], row['revision'] >= 3806)
            self.assertEqual(row['cmd_option_registered'], row['revision'] >= 3823)
            self.assertTrue(row['getter_requires_initialized_owner'])
            self.assertTrue(row['copy_initializes_destination'])
            self.assertTrue(row['copy_clear_preserves_locals_when_zero'])
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_animation_locals(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_model_constant_loading_phase_matches_each_source_profile(self):
        from historical_model_load_phase import render_model_load_phase
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-model-load-phase-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        header = (ROOT / 'src/engines/3842/openbor.h').read_text()
        constants = {name: int(value) for name, value in re.findall(
            r'^#define\s+(MAX_\w+)\s+(\d+)\b', header, re.M)}
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['facts'], fixture['fact_sets'])
            self.assertEqual(row['early_constants'], row['revision'] >= 3828)
            for name, value in fixture['fact_sets'][row['facts']]['defaults'].items():
                if name not in {'MAX_ATKS', 'STA_ATKS'}:
                    self.assertEqual(constants[name], value)
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_model_load_phase(ROOT / 'src/engines/3842', fixture),
                   extra_flags=('-Wno-sign-compare', '-fsanitize=pointer-overflow',
                                '-fno-sanitize-recover=all'))

    def test_gif_wire_and_persisted_record_layouts_match_source_profiles(self):
        from historical_gif_layout import render_gif_record_layout
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-gif-record-layout-contracts.json')
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(contract_revisions(fixture, {3666, 3726, 3727, 3728, 3741}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == '3741' and revision <= 3728:
                self.assertIn(revision, revisions)
        for row in fixture['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertTrue(row['record_packing_is_unconditional'])
            self.assertEqual(row['wire_read_lengths'], [13, 9])
            self.assertEqual(row['record_constants'], {'MAX_PLAYERS': '4', 'MAX_NAME_LEN': '40'})
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        engine = ROOT / 'src/engines/3741'
        decoder = (engine / 'source/gamelib/anigif.c').read_text()
        self.assertRegex(decoder,
            r'readpackfile\(info->handle,\s*&info->gif_header,\s*sizeof_gifheaderstruct\)')
        self.assertRegex(decoder,
            r'readpackfile\(info->handle,\s*&iblock,\s*sizeof_iblock\)')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_gif_record_layout(engine, fixture),
                   (engine / 'source/gamelib',),
                   ('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_explicit_model_sync_follows_source_availability(self):
        from historical_animation_names import render_model_sync
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixtures = Path(__file__).parent / 'fixtures'
        animation = load_contract_fixture(fixtures / 'profile-animation-name-contracts.json')
        sync = load_contract_fixture(fixtures / 'profile-model-sync-contracts.json')
        revisions = {row['revision'] for row in sync['sources']}
        self.assertEqual(len(sync['sources']), len(revisions))
        self.assertTrue(contract_revisions(sync, {3761, 3769, 3773, *sync['boundary_controls']}) <= revisions)
        for profile in contract_profiles(sync, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        engine = ROOT / 'src/engines/3842'
        loader = function((engine / 'openbor.c').read_text(), 'load_cached_model')
        first = loader.rindex('\n\t\t\t\tdefault:')
        default = loader[first:loader.index('\n\t\t\t}', first)]
        for row in sync['sources']:
            self.assertEqual(row['registered_sync'], row['revision'] >= 3841)
            self.assertEqual(row['explicit_sync'], row['registered_sync'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['default_clause'], hashlib.sha256(default.encode()).hexdigest())
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_model_sync(engine, animation, sync),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_animation_names_and_defaults_match_each_source_profile(self):
        from historical_animation_names import render_animation_names
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-animation-name-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        engine = ROOT / 'src/engines/3842'
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        constants = {key: int(value) for key, value in re.findall(
            r'^#define\s+(ANI_\w+)\s+(\d+)\b', header, re.M)}
        start = source.index('case CMD_MODEL_ANIM:')
        command = source[start:source.index('case CMD_MODEL_LOOP:', start)]
        prefix = command[:re.search(r'newanim->sync\s*=\s*-1;', command).end()]
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(constants, fixture['constant_sets'][row['constant_set']])
            self.assertEqual(hashlib.sha256(prefix.encode()).hexdigest(), row['prefix_sha256'])
            for name, digest in row['handler_sha256'].items():
                self.assertEqual(hashlib.sha256(function(source, name).encode()).hexdigest(), digest)
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_animation_names(engine, fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_hud_icon_palettes_follow_each_source_owner(self):
        from historical_hud_icons import render_hud_icons
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-hud-icon-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['icon_usemap_selection'], row['revision'] >= 3776)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_hud_icons(ROOT / 'src/engines/3842', rows),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_camera_progress_limits_and_centering_match_each_source_profile(self):
        from historical_camera import render_camera
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-camera-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_camera(ROOT / 'src/engines/3842', rows))

    def test_attack_drop_defaults_match_each_source_profile(self):
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-attack-drop-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        definitions = []
        constant_sets = []
        names = ['normal', 'blast', 'kill', 'check_lost', 'kill_all_enemies', 'time_over']
        pattern = (r'attack\.dropv\[0\]\s*=[^;]+;\s*'
                   r'attack\.dropv\[1\]\s*=[^;]+;\s*attack\.dropv\[2\]\s*=[^;]+;')
        for engine in ('3741', '3842'):
            source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text()
            header = (ROOT / 'src/engines' / engine / 'openbor.h').read_text()
            constant_sets.append('\n'.join(re.search(r'^#define\s+'+name+r'\b[^\n]*',
                header, re.M)[0] for name in ('ATK_NORMAL', 'ATK_BLAST', 'ATK_FREEZE',
                'ATK_STEAL', 'TYPE_ITEM', 'TYPE_ENEMY', 'GAME_SPEED')))
            model = function(source, 'load_cached_model')
            blocks = re.findall(pattern, model)
            self.assertEqual(len(blocks), 2)
            for name in names[2:]:
                found = re.findall(pattern, function(source, name))
                if engine == '3842' and name == 'check_lost':
                    # The later engine splits pit/lifespan callers. The
                    # earlier profiles enter the first branch for both.
                    self.assertEqual(len(found), 2)
                    self.assertEqual(found[0], found[1])
                    found = found[:1]
                self.assertEqual(len(found), 1)
                blocks += found
            for name, block in zip(names, blocks):
                definitions.append('static s_attack drop_'+engine+'_'+name+
                    '(void) {s_attack attack=emptyattack;'+block+'return attack;}')
            definitions.append(function(source, 'lcmHandleCommandSmartbomb').replace(
                'lcmHandleCommandSmartbomb', 'smartbomb_'+engine, 1))
        self.assertEqual(constant_sets[0], constant_sets[1])
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        contexts = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            contexts.append('{%d,%d,smartbomb_%s,{%s}}' % (
                row['revision'], row['configured_drop'], row['engine'],
                ','.join('drop_'+row['engine']+'_'+name for name in names)))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Attack defaults revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
@CONSTANTS@
typedef struct {float dropv[3];int attack_force,attack_type,attack_drop,blast,freeze,forcemap,steal,freezetime;} s_attack;
typedef struct {s_attack *smartbomb;int type,dofreeze;} s_model;
typedef struct {char *args[5];} ArgList;
#define GET_ARGP(i) (arglist->args[i])
static s_attack emptyattack;
static float default_model_dropv[3];
static void shutdown(int code,const char *fmt,const char *filename) {(void)code;(void)fmt;(void)filename;abort();}
@DEFINITIONS@
int main(void) {
 const struct {unsigned revision;int configured;void (*smartbomb)(ArgList*,s_model*,char*);s_attack (*drop[6])(void);} rows[]={@ROWS@};
 const float defaults[][3]={{3.0f,1.2f,0.0f},{9.0f,-2.0f,4.0f},{-1.0f,0.375f,-7.0f}};
 for(unsigned r=0;r<sizeof(rows)/sizeof(*rows);++r) {
  obor_profile_build=rows[r].revision;
  for(unsigned d=0;d<sizeof(defaults)/sizeof(*defaults);++d) {
   memcpy(default_model_dropv,defaults[d],sizeof(default_model_dropv));
   emptyattack=(s_attack){.dropv={11,12,13}};
   for(unsigned kind=0;kind<6;++kind) {
    ++test_case;s_attack attack=rows[r].drop[kind]();
    assert(attack.dropv[0]==(rows[r].configured?defaults[d][0]:3.0f));
    assert(attack.dropv[1]==(rows[r].configured?(kind==1?defaults[d][1]*2.083f:defaults[d][1]):(kind==1?2.5f:1.2f)));
    assert(attack.dropv[2]==(kind==1?0.0f:rows[r].configured?defaults[d][2]:0.0f));
   }
   const int types[]={ATK_NORMAL,ATK_BLAST,ATK_FREEZE,ATK_STEAL};
   for(int t=0;t<4;++t)for(int item=0;item<2;++item) {
    int type=types[t];
    ++test_case;char number[8];snprintf(number,sizeof(number),"%d",type);
    ArgList args={{"smartbomb","17",number,"2","4"}};
    s_model model={.type=item?TYPE_ITEM:TYPE_ENEMY};rows[r].smartbomb(&args,&model,"fixture");
    s_attack *attack=model.smartbomb;assert(attack);
    assert(attack->dropv[0]==(rows[r].configured?defaults[d][0]:3.0f));
    assert(attack->dropv[1]==(rows[r].configured?(type==ATK_BLAST?defaults[d][1]*2.083f:defaults[d][1]):(type==ATK_BLAST?2.5f:1.2f)));
    assert(attack->dropv[2]==13 && attack->attack_force==17 && attack->attack_type==type);
    assert(attack->blast==(type==ATK_BLAST) && attack->freeze==(type==ATK_FREEZE));
    assert(attack->steal==(type==ATK_STEAL) && attack->attack_drop==(type!=ATK_FREEZE));
    assert(model.dofreeze==(item?0:2) && attack->freezetime==(item?2:4)*GAME_SPEED);
    free(attack);
   }
  }
 }
 assert(test_case==sizeof(rows)/sizeof(*rows)*42);return 0;
}
'''.replace('@DEFINITIONS@', '\n'.join(definitions)).replace('@ROWS@', ','.join(contexts)).replace('@CONSTANTS@', constant_sets[0])
        with patch.dict(os.environ, sanitizer_environment()):
            native(program)

    def test_difficulty_menu_paging_matches_each_source_profile(self):
        from historical_difficulty_menu import render_difficulty_menu
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-difficulty-menu-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
        engines = {e: ROOT / 'src/engines' / e for e in ('3741', '3842')}
        for engine in engines:
            with self.subTest(engine=engine), patch.dict(os.environ, sanitizer_environment()):
                native(render_difficulty_menu(engines,
                    [row for row in rows if row['engine'] == engine]))

    def test_level_table_and_stream_cleanup_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-level-table-cleanup.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        script = (root / 'openborscript.c').read_text()
        initializer = function(source, 'obor_level_fixed_tables_initialize') if 'obor_level_fixed_tables_initialize' in source else 'static int obor_level_fixed_tables_initialize(s_level *lv) {(void)lv;return 1;}'
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d,%d);' % (
                row['revision'], row['legacy_fixed_tables'], row['clears_level_streams']))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Level cleanup: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
enum {R_LEVEL=1,R_TABLE,R_BLEND,R_TEXT,R_PIXELS,R_STREAM,R_SPAWN,R_CACHE,R_SCRIPT,R_NAME};
static struct {void *pointer;int role,live,cleared;} owned[1024];
static int owned_count,phase,in_destructor,clear_calls,clear_streams,fail_allocation=-1,init_calls;
static s_level *active_level;
static s_screen background_storage,*background=&background_storage;
static s_filestream stream_storage[50],*filestreams=stream_storage;
static int numfilestreams=50;
static int filled[50],factory_calls,factory_failure;
int pixelformat=PIXEL_8;
int obor_profile_blend_count(void) {return MAX_BLENDINGS;}
static void *take(size_t bytes,int role) {
 assert(bytes && bytes<=1024*1024 && owned_count<1024);
 void *p=calloc(1,bytes);assert(p);owned[owned_count].pointer=p;
 owned[owned_count].role=role;owned[owned_count].live=1;owned[owned_count].cleared=0;
 ++owned_count;return p;
}
static int live_role(int role) {
 int n=0;for(int i=0;i<owned_count;++i)n+=owned[i].live && owned[i].role==role;return n;
}
static void *initialize_calloc(size_t n,size_t bytes) {
 int call=init_calls++;if(call==fail_allocation)return NULL;
 assert(n && bytes && n<=1024*1024/bytes);return take(n*bytes,R_TABLE);
}
static void release(void *p) {
 if(!p)return;
 int index=-1;for(int i=0;i<owned_count;++i)if(owned[i].pointer==p && owned[i].live){index=i;break;}
 assert(index>=0);int role=owned[index].role;
 if(in_destructor) {
  int next=role==R_BLEND?0:role==R_PIXELS?1:role==R_TEXT?2:role==R_STREAM?3:
   role==R_SPAWN?5:role==R_SCRIPT || role==R_NAME || role==R_CACHE?6:role==R_TABLE?7:8;
  assert(next>=phase);phase=next;
  if(role==R_SPAWN){s_spawn_script_list_node *node=p;assert(!node->next && !node->spawn_script);}
  if(role==R_CACHE){s_spawn_script_cache_node *node=p;assert(!node->next && !node->filename && !node->cached_spawn_script);}
  if(role==R_SCRIPT)assert(owned[index].cleared);
 }
 owned[index].live=0;free(p);
}
void Script_Clear(Script *script,int localclear) {
 assert(in_destructor && localclear==2);
 if(clear_calls<5) {
  Script *slots[]={&active_level->update_script,&active_level->updated_script,&active_level->key_script,
   &active_level->level_script,&active_level->endlevel_script};
  assert(script==slots[clear_calls] && phase<=4);phase=4;
  assert(!live_role(R_BLEND) && !live_role(R_PIXELS) && !live_role(R_TEXT));
  for(int i=0;i<50;++i) {
   assert(filestreams[i].pos==i%5 && filestreams[i].size==(size_t)(17+i));
   assert(!!filestreams[i].buf==(filled[i] && !clear_streams));
   assert(filestreams[i].obor_capacity==(size_t)(filled[i] && !clear_streams?32:0));
  }
 } else {
  assert(phase<=6);phase=6;int found=0;
  for(int i=0;i<owned_count;++i)if(owned[i].pointer==script && owned[i].live && owned[i].role==R_SCRIPT) {
   assert(!owned[i].cleared);owned[i].cleared=1;++found;
  }
  assert(found==1);
 }
 ++clear_calls;
}
static unsigned char *table_factory(unsigned char *palette) {
 assert(palette);int call=factory_calls++;
 return call==factory_failure?NULL:take(16,R_BLEND);
}
static unsigned char *(*factories[OBOR_BLEND_STORAGE])(unsigned char*)={
 table_factory,table_factory,table_factory,table_factory,table_factory,table_factory,table_factory};
#define blending_table_functions factories
#define calloc initialize_calloc
#define free release
@TEXT_INITIALIZER@
@TABLE_INITIALIZER@
@CREATOR@
@STREAM_CLEAR@
@FREE_LEVEL@
static void begin(int stream_mode) {
 assert(!in_destructor);owned_count=phase=clear_calls=init_calls=0;fail_allocation=-1;
 memset(stream_storage,0,sizeof(stream_storage));memset(filled,0,sizeof(filled));
 for(int i=0;i<50;++i) {
  filestreams[i].pos=i%5;filestreams[i].size=17+i;
  filled[i]=stream_mode==2 || (stream_mode==1 && (i==0 || i==49));
  if(filled[i]){filestreams[i].buf=take(32,R_STREAM);strcpy(filestreams[i].buf,"stream");filestreams[i].obor_capacity=32;}
 }
 active_level=take(sizeof(*active_level),R_LEVEL);
}
static void finish(int expected_caches) {
 in_destructor=1;free_level(active_level);in_destructor=0;active_level=NULL;
 assert(clear_calls==5+expected_caches && !live_role(R_LEVEL) && !live_role(R_TABLE));
 assert(!live_role(R_BLEND) && !live_role(R_TEXT) && !live_role(R_PIXELS));
 assert(!live_role(R_SPAWN) && !live_role(R_CACHE) && !live_role(R_SCRIPT) && !live_role(R_NAME));
 for(int i=0;i<50;++i){release(filestreams[i].buf);filestreams[i].buf=NULL;}
 for(int i=0;i<owned_count;++i)assert(!owned[i].live);
}
static void check(int fixed,int stream_boundary) {
 clear_streams=stream_boundary;
 int palettes[]={0,1,39,40,47};
 for(int count=0;count<(fixed?4:5);++count)for(int streams=0;streams<3;++streams)
 for(int spawns=0;spawns<2;++spawns)for(int caches=0;caches<2;++caches) {
  ++test_case;begin(streams);s_level *lv=active_level;lv->numpalettes=palettes[count];
  int palette_slots=fixed?40:lv->numpalettes;
  if(palette_slots){lv->palettes=take(palette_slots*sizeof(*lv->palettes),R_TABLE);lv->blendings=take(palette_slots*sizeof(*lv->blendings),R_TABLE);}
  if(lv->numpalettes) {
   lv->blendings[0][0]=take(16,R_BLEND);
   if(lv->numpalettes>1)lv->blendings[lv->numpalettes-1][2]=take(16,R_BLEND);
  }
  if(fixed) {
   if(lv->numpalettes<40) {
    factory_calls=0;factory_failure=3;
    assert(!create_blending_tables(lv->palettes[lv->numpalettes],lv->blendings[lv->numpalettes],NULL));
    assert(factory_calls==4 && lv->blendings[lv->numpalettes][0] && lv->blendings[lv->numpalettes][2]);
   }
   lv->blendings[39][5]=take(16,R_BLEND);
  }
  lv->numlayers=4;lv->layers=take(4*sizeof(*lv->layers),R_TABLE);
  lv->layers[1].gfx.handle=take(16,R_PIXELS);lv->layers[2].gfx.handle=background;
  lv->numtextobjs=fixed?50:3;lv->textobjs=take(lv->numtextobjs*sizeof(*lv->textobjs),R_TABLE);
  lv->textobjs[0].text=take(16,R_TEXT);lv->textobjs[lv->numtextobjs-1].text=take(16,R_TEXT);
  lv->numspawns=spawns;int spawn_slots=fixed?600:spawns;
  if(spawn_slots)lv->spawnpoints=take(spawn_slots*sizeof(*lv->spawnpoints),R_TABLE);
  Script *cached=NULL;
  if(caches)for(int c=0;c<2;++c) {
   s_spawn_script_cache_node *node=take(sizeof(*node),R_CACHE);
   node->cached_spawn_script=take(sizeof(Script),R_SCRIPT);node->filename=take(16,R_NAME);
   strcpy(node->filename,"script");node->next=lv->spawn_script_cache_head;lv->spawn_script_cache_head=node;cached=node->cached_spawn_script;
  }
  if(spawns)for(int entry=0;entry<(fixed?2:1);++entry) {
   int index=entry?599:0;
   for(int c=0;c<2;++c) {
    s_spawn_script_list_node *node=take(sizeof(*node),R_SPAWN);node->spawn_script=cached;
    node->next=lv->spawnpoints[index].spawn_script_list_head;lv->spawnpoints[index].spawn_script_list_head=node;
   }
  }
  lv->layersref=take(sizeof(*lv->layersref),R_TABLE);
  lv->panels=take(sizeof(*lv->panels),R_TABLE);lv->frontpanels=take(sizeof(*lv->frontpanels),R_TABLE);
  lv->bglayers=take(sizeof(*lv->bglayers),R_TABLE);lv->fglayers=take(sizeof(*lv->fglayers),R_TABLE);
  lv->genericlayers=take(sizeof(*lv->genericlayers),R_TABLE);lv->waters=take(sizeof(*lv->waters),R_TABLE);
  lv->holes=take(sizeof(*lv->holes),R_TABLE);lv->walls=take(sizeof(*lv->walls),R_TABLE);
  finish(caches?2:0);
 }
 /* Allocation refusals exercise only the new constructor. Original fixed
    records had these slots inside their already allocated level object. */
 if(fixed)for(int failure=0;failure<4;++failure) {
  ++test_case;begin(1);fail_allocation=failure;
  assert(!(obor_textobjs_initialize(active_level) && obor_level_fixed_tables_initialize(active_level)));
  fail_allocation=-1;finish(0);
 }
 ++test_case;begin(1);
 assert(obor_textobjs_initialize(active_level) && obor_level_fixed_tables_initialize(active_level));
 assert(!!active_level->palettes==fixed && !!active_level->blendings==fixed && !!active_level->spawnpoints==fixed);
 assert(active_level->numtextobjs==(fixed?50:0) && !active_level->numpalettes && !active_level->numspawns);
 int calls=init_calls;assert(obor_level_fixed_tables_initialize(active_level) && calls==init_calls);finish(0);
}
int main(void) {@CHECKS@assert(test_case==@CASE_COUNT@);return 0;}
'''.replace('@TEXT_INITIALIZER@', function(source, 'obor_textobjs_initialize'))
           .replace('@TABLE_INITIALIZER@', initializer).replace('@CREATOR@', function(source, 'create_blending_tables'))
           .replace('@STREAM_CLEAR@', function(script, 'obor_filestream_level_clear'))
           .replace('@FREE_LEVEL@', function(source, 'free_level')).replace('@CHECKS@', '\n'.join(checks))
           .replace('@CASE_COUNT@', str(sum(53 if row['legacy_fixed_tables'] else 61 for row in rows))), includes, flags)

    def test_layer_reference_routing_and_absence_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-layer-reference-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        script = (root / 'openborscript.c').read_text()
        loader = function(source, 'load_level')
        start = loader.index('if(level->numlayers) {')
        brace = loader.index('{', start)
        wrapper = function('void selected(void) ' + loader[brace:], 'selected')
        binding = loader[start:brace] + wrapper[wrapper.index('{'):]
        helpers = '\n'.join(function(source, n) for n in ('obor_layer_encode', 'obor_layer_decode')) if 'obor_layer_encode' in source else ''
        enum = re.search(r'enum getlt_enum\s*\{[\s\S]*?\};', script)
        memory_error = re.search(r'static const char\* E_OUT_OF_MEMORY\s*=\s*"[^"\n]*";', source)
        self.assertIsNotNone(enum)
        self.assertIsNotNone(memory_error)
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key in ('load_level_normalized_sha256', 'layer_lookup_normalized_sha256', 'layer_enum_normalized_sha256'):
                self.assertRegex(row[key], r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d,%d);' % (
                row['revision'], row['legacy_frontpanel_destination'], row['preserve_absent_layers']))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation', '-Wno-error=implicit-fallthrough']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Layer reference: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static s_level storage,*level=&storage;
static s_screen background_storage={.width=64,.height=32},*background;
static int (*panels)[3],*order,panelcount=2,frontpanels_loaded,panel_width,panel_height;
static char *errormessage;
@MEMORY_ERROR@
static void load_layer_service(char *name,int index) {
 assert(!name && index>=0 && index<level->numlayers);
}
#define load_layer load_layer_service
@HELPERS@
@ENUM@
@GETLAYER@
static int bind_layers(void) {
 int i,j;s_layer *bgl;s_drawmethod *dm;
 if(0)goto lCleanup;
 @BINDING@
 return 1;
lCleanup:return 0;
}
static void reset(void) {
 free(level->layers);free(level->layersref);free(level->panels);
 free(level->frontpanels);free(level->bglayers);free(level->fglayers);
 free(level->genericlayers);free(level->waters);free(panels);free(order);
 memset(level,0,sizeof(*level));panels=NULL;order=NULL;errormessage=NULL;
 frontpanels_loaded=panel_width=panel_height=0;background=NULL;
}
static int append(bgloldtype kind) {
 int index=level->numlayers++;assert(index>=0 && index<64);
 s_layer *p=level->layers+index;p->oldtype=kind;p->enabled=1;
 p->width=64+index;p->height=32+index;return index;
}
static void oracle(int legacy_route,int preserve_absent) {
 int maps[_glt_the_end][100],counts[_glt_the_end]={0};
 for(int t=0;t<_glt_the_end;++t)for(int i=0;i<100;++i)maps[t][i]=-1;
 s_layer expected[128];memset(expected,0,sizeof(expected));int n=0;
 /* The authored input records already went through the native normalization
    pass. This independent model uses the original direct-pointer ordering. */
 for(int i=0;i<level->numlayers;++i)if(level->layers[i].oldtype==bgt_background) {
  expected[n]=level->layers[i];maps[_glt_background][0]=n++;
 }
 for(int i=0;i<level->numlayers;++i) {
  s_layer *p=&level->layers[i];if(p->oldtype==bgt_panel || p->oldtype==bgt_background)continue;
  expected[n]=*p;
  int type=-1;
  if(p->oldtype==bgt_bglayer)type=_glt_bglayer;
  if(p->oldtype==bgt_fglayer)type=_glt_fglayer;
  if(p->oldtype==bgt_generic)type=_glt_generic;
  if(p->oldtype==bgt_water)type=_glt_water;
  if(type>=0)maps[type][counts[type]++]=n;
  if(p->oldtype==bgt_frontpanel) {
   int index=counts[_glt_frontpanel]++;
   expected[n].xoffset=index*p->width;expected[n].xspacing=(frontpanels_loaded-1)*p->width;
   maps[legacy_route?_glt_bglayer:_glt_frontpanel][index]=n;
  }
  ++n;
 }
 counts[_glt_neon]=counts[_glt_panel]=counts[_glt_screen]=level->numpanels;
 for(int i=0;i<level->numpanels;++i)for(int j=0;j<3;++j)if(panels[order[i]][j]) {
  expected[n]=level->layers[panels[order[i]][j]];expected[n].xoffset=panel_width*i;
  maps[j==0?_glt_panel:j==1?_glt_neon:_glt_screen][i]=n++;
 }
 assert(n>0 && level->numlayersref==n && !memcmp(level->layersref,expected,n*sizeof(*expected)));
 assert(level->numbglayers==counts[_glt_bglayer] && level->numfglayers==counts[_glt_fglayer]);
 assert(level->numfrontpanels==counts[_glt_frontpanel] && level->numgenericlayers==counts[_glt_generic]);
 assert(level->numwaters==counts[_glt_water]);
 for(int type=0;type<_glt_the_end;++type) {
  int indices[]={-1,0,counts[type]-1,counts[type],counts[type]+1};
  for(unsigned k=0;k<sizeof(indices)/sizeof(*indices);++k) {
   int index=indices[k],valid=type==_glt_background || (index>=0 && index<counts[type]);
   int ref=valid?maps[type][type==_glt_background?0:index]:-1;
   if(valid && ref<0 && !preserve_absent)ref=0;
   s_layer *wanted=ref<0?NULL:level->layersref+ref,*actual=_getlayer(type,index);
   assert(actual==wanted);
   if(actual) {
    int old=actual->xoffset,mark=1000+type*13+index;actual->xoffset=mark;
    assert(level->layersref[ref].xoffset==mark);
    for(int other=0;other<_glt_the_end;++other) {
     s_layer *alias=_getlayer(other,0);if(alias==actual)assert(alias->xoffset==mark);
    }
    actual->xoffset=old;
   }
  }
 }
 assert(!_getlayer(_glt_the_end,0));
 if(legacy_route)for(int i=0;i<level->numfrontpanels;++i)assert(!level->frontpanels[i]);
}
static void check(int legacy_route,int preserve_absent) {
 static const bgloldtype routes[6][4]={
  {bgt_bglayer,bgt_frontpanel},{bgt_frontpanel,bgt_bglayer},
  {bgt_bglayer,bgt_bglayer,bgt_frontpanel},{bgt_frontpanel,bgt_frontpanel,bgt_bglayer},
  {bgt_bglayer,bgt_frontpanel,bgt_bglayer,bgt_frontpanel},
  {bgt_frontpanel,bgt_bglayer,bgt_bglayer,bgt_frontpanel}};
 static const int lengths[]={2,2,3,3,4,4};
 for(int has_bg=0;has_bg<2;++has_bg)for(int aux=0;aux<4;++aux)
 for(int route=0;route<6;++route)for(int arrangement=0;arrangement<4;++arrangement) {
  ++test_case;reset();level->layers=calloc(64,sizeof(*level->layers));assert(level->layers);
  if(has_bg){background=&background_storage;append(bgt_background);}
  else level->numlayers=1; /* Native panel parser reserves an empty first layer. */
  panels=calloc(2,sizeof(*panels));assert(panels);
  for(int i=0;i<2;++i) {
   panels[i][0]=append(bgt_panel);int mask=i?((aux&1)<<1)|((aux&2)>>1):aux;
   if(mask&1){panels[i][1]=append(bgt_panel);level->layers[panels[i][1]].neon=1;}
   if(mask&2)panels[i][2]=append(bgt_panel);
  }
  for(int i=0;i<lengths[route];++i){append(routes[route][i]);if(routes[route][i]==bgt_frontpanel)++frontpanels_loaded;}
  append(bgt_fglayer);append(bgt_generic);append(bgt_water);
  level->numpanels=arrangement?2:1;
  order=calloc(level->numpanels,sizeof(*order));level->panels=calloc(level->numpanels,sizeof(*level->panels));assert(order && level->panels);
  if(arrangement==2)order[1]=1;
  if(arrangement==3)order[0]=1;
  assert(bind_layers() && !errormessage);oracle(legacy_route,preserve_absent);
 }
 reset();
}
int main(void) {@CHECKS@assert(test_case==@CASE_COUNT@);return 0;}
'''.replace('@MEMORY_ERROR@', memory_error[0]).replace('@HELPERS@', helpers)
           .replace('@ENUM@', enum[0]).replace('@GETLAYER@', function(script, '_getlayer'))
           .replace('@BINDING@', binding).replace('@CHECKS@', '\n'.join(checks))
           .replace('@CASE_COUNT@', str(len(rows)*192)), includes, flags)

    def test_level_loading_caps_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-level-loading-caps.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        loader = function(source, 'load_level')
        selected = []
        for first, following in (
                ('BACKGROUND', 'WATER'), ('WATER', 'DIRECTION'),
                ('FRONTPANEL', 'STAGENUMBER'), ('ORDER', 'HOLE'),
                ('HOLE', 'WALL'), ('WALL', 'PALETTE'),
                ('PALETTE', 'UPDATESCRIPT'), ('AT', None)):
            start = loader.index('case CMD_LEVEL_' + first + ':')
            end = loader.index('case CMD_LEVEL_' + following + ':', start) if following else loader.index('default:', start)
            selected.append(loader[start:end])
        plain = re.search(r'const s_drawmethod plainmethod\s*=\s*\{[\s\S]*?\};', source)
        self.assertIsNotNone(plain)
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['load_level_normalized_sha256'], r'^[0-9a-f]{64}$')
            caps = row['declared_limit_constants']
            self.assertEqual(caps, dict(LAYERS=100, PANELS=100, HOLES=40, WALLS=40, PALETTES=40, SPAWNS=600))
            if row['legacy_fixed_caps']:
                self.assertEqual(len(row['guards']), 9)
                self.assertIn('LEVEL_MAX_PANELS', row['order_loop'])
            else:
                self.assertEqual(row['guards'], [])
                self.assertNotIn('LEVEL_MAX_PANELS', row['order_loop'])
            checks.append('obor_profile_build=%d;check(%s);' % (row['revision'], ','.join(
                [str(int(row['legacy_fixed_caps']))] + [str(caps[k]) for k in
                ('LAYERS', 'PANELS', 'HOLES', 'WALLS', 'PALETTES', 'SPAWNS')])))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack', '-Wno-error=single-bit-bitfield-constant-conversion'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <limits.h>
#include "openbor.h"
#include "commands.h"
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Level caps: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static s_level storage,*level=&storage;
static int (*panels)[3],*order,panelcount,frontpanels_loaded;
static int PLAYER_MIN_Z=160,PLAYER_MAX_Z=232;
static s_spawn_entry next;
static char arguments[24][1024],bgPath[128],*errormessage;
static int allocations,layer_calls,layer_indices[8],image_calls,palette_calls,blend_calls;
static int holesprite=1,blendfx_is_set=1,blendfx[OBOR_BLEND_STORAGE];
int pixelformat=PIXEL_8;
int obor_profile_blend_count(void) {return MAX_BLENDINGS;}
@PLAIN@
static void *bounded_realloc(void *old,size_t size) {
 assert(size && size<=1024*1024);++allocations;
 void *out=realloc(old,size);assert(out);return out;
}
/* Retain the header's actual realloc-and-zero macro; bound its test service. */
#define realloc bounded_realloc
#undef GET_ARG
#undef GET_INT_ARG
#undef GET_FLOAT_ARG
#define GET_ARG(n) (arguments[(n)])
#define GET_INT_ARG(n) (atoi(GET_ARG(n)))
#define GET_FLOAT_ARG(n) (strtof(GET_ARG(n),NULL))
#ifndef MIN_INT
#define MIN_INT INT_MIN
#endif
#define NaN 0xAAAAAAAA
#define stricmp strcasecmp
static void layer_service(char *name,int index) {
 assert(*name && index==level->numlayers && layer_calls<8);
 layer_indices[layer_calls++]=index;
}
static int image_service(void) {++image_calls;return 17;}
static int palette_service(unsigned char *palette,char *name) {
 assert(*name && palette==level->palettes[level->numpalettes]);
 ++palette_calls;palette[0]=0x4a;return 1;
}
static int blending_service(unsigned char *palette,unsigned char **tables,int *usemap) {
 assert(palette[0]==0x4a && tables==level->blendings[level->numpalettes]);
 for(int i=0;i<OBOR_BLEND_COUNT;++i)assert(usemap[i]==0);
 ++blend_calls;return 1;
}
#define load_layer layer_service
#undef testpackfile
#define testpackfile(...) 1
#define loadsprite(...) image_service()
#define load_palette palette_service
#define create_blending_tables blending_service
static int command(levelCommands cmd) {
 int i=0,j=0,usemap[OBOR_BLEND_STORAGE]={0};char *value;
 s_layer *bgl;s_drawmethod *dm;
 switch(cmd) {@CASES@ default:assert(0);}
 return 1;
lCleanup:return 0;
}
static void reset(void) {
 free(level->layers);free(level->panels);free(level->holes);free(level->walls);
 free(level->palettes);free(level->blendings);free(level->spawnpoints);free(panels);free(order);
 memset(level,0,sizeof(*level));memset(&next,0,sizeof(next));
 panels=NULL;order=NULL;panelcount=frontpanels_loaded=0;
 memset(arguments,0,sizeof(arguments));*bgPath=0;errormessage=NULL;
 allocations=layer_calls=image_calls=palette_calls=blend_calls=0;holesprite=1;
}
static void order_step(int fixed,int limit,const char *text) {
 int initial=level->numpanels,expected=initial,accepted=0,bad=0;
 for(int k=0;text[k] && (!fixed || expected<limit);++k) {
  int c=(unsigned char)text[k];
  if(!((c>='A' && c<='Z')||(c>='a' && c<='z'))){bad=1;break;}
  ++expected;++accepted;
 }
 strcpy(arguments[1],text);allocations=0;errormessage=NULL;
 assert(command(CMD_LEVEL_ORDER)==!bad && level->numpanels==expected);
 assert(allocations==accepted*2);
 assert(!!errormessage==bad);
 if(bad)assert(!strcmp(errormessage,"Illegal character in panel order!"));
 for(int k=0;k<accepted;++k) {
  int c=(unsigned char)text[k];int index=c>='a'?c-'a':c-'A';
  assert(order[initial+k]==index);
  for(int j=0;j<3;++j)assert(!level->panels[initial+k][j]);
 }
}
static void check(int fixed,int layer_limit,int panel_limit,int hole_limit,int wall_limit,int palette_limit,int spawn_limit) {
 const levelCommands layer_commands[]={CMD_LEVEL_BACKGROUND,CMD_LEVEL_BGLAYER,CMD_LEVEL_LAYER,
  CMD_LEVEL_FGLAYER,CMD_LEVEL_WATER,CMD_LEVEL_PANEL,CMD_LEVEL_FRONTPANEL};
 const int layer_counts[]={0,1,layer_limit-3,layer_limit-2,layer_limit-1,layer_limit,layer_limit+1};
 for(unsigned cmd_index=0;cmd_index<sizeof(layer_commands)/sizeof(*layer_commands);++cmd_index)
 for(unsigned v=0;v<sizeof(layer_counts)/sizeof(*layer_counts);++v)
 for(int aux=0;aux<(layer_commands[cmd_index]==CMD_LEVEL_PANEL?4:1);++aux) {
  ++test_case;reset();levelCommands cmd=layer_commands[cmd_index];
  int initial=layer_counts[v],is_panel=cmd==CMD_LEVEL_PANEL || cmd==CMD_LEVEL_FRONTPANEL;
  level->numlayers=initial;if(initial){level->layers=calloc(initial,sizeof(*level->layers));assert(level->layers);}
  strcpy(arguments[1],"image");
  if(is_panel){strcpy(arguments[2],aux&1?"neon":"none");strcpy(arguments[3],aux&2?"screen":"none");}
  int expected=initial,added=0,requested=1+!!(aux&1)+!!(aux&2);
  int first=initial?initial:is_panel?1:0;
  if(is_panel && !initial)expected=1;
  while(added<requested && (!fixed || expected<layer_limit)){++expected;++added;}
  int allowed=added==requested;
  assert(command(cmd)==allowed && level->numlayers==expected);
  assert(!!errormessage==!allowed);
  if(!allowed)assert(!strcmp(errormessage,"Too many layers in level (check LEVEL_MAX_LAYERS)!"));
  assert(layer_calls==(cmd==CMD_LEVEL_BACKGROUND?0:added));
  for(int j=0;j<layer_calls;++j)assert(layer_indices[j]==first+j);
  if(!added)assert(!allocations);
  if(cmd==CMD_LEVEL_PANEL) {
   assert(panelcount==!!added);
   if(added) {
    assert(panels[0][0]==first);
    assert(panels[0][1]==((aux&1) && added>=2?first+1:0));
    assert(panels[0][2]==((aux&2) && added==requested?first+requested-1:0));
   }
  }
  if(cmd==CMD_LEVEL_FRONTPANEL)assert(frontpanels_loaded==!!added);
 }
 const levelCommands other_commands[]={CMD_LEVEL_HOLE,CMD_LEVEL_WALL,CMD_LEVEL_PALETTE,CMD_LEVEL_AT};
 const int limits[]={hole_limit,wall_limit,palette_limit,spawn_limit};
 const char *messages[]={"Too many holes in level (check LEVEL_MAX_HOLES)!",
  "Too many walls in level (check LEVEL_MAX_WALLS)!","Too many palettes in level (check LEVEL_MAX_PALETTES)!",
  "too many spawn entries (see LEVEL_MAX_SPAWNS)"};
 for(int kind=0;kind<4;++kind)for(int position=0;position<4;++position)
 for(int sprite=0;sprite<(kind==0?2:1);++sprite) {
  ++test_case;reset();int count=position==0?0:limits[kind]+position-2;
  int allowed=!fixed || count<limits[kind];int *size=NULL;
  if(kind==0) {
   size=&level->numholes;level->holes=count?calloc(count,sizeof(*level->holes)):NULL;
   holesprite=sprite?-1:1;strcpy(arguments[1],"7");
  } else if(kind==1) {
   size=&level->numwalls;level->walls=count?calloc(count,sizeof(*level->walls)):NULL;
   for(int j=1;j<=8;++j)snprintf(arguments[j],sizeof(arguments[j]),"%d",j);
  } else if(kind==2) {
   size=&level->numpalettes;int slots=fixed?palette_limit:count;
   level->palettes=slots?calloc(slots,sizeof(*level->palettes)):NULL;
   level->blendings=slots?calloc(slots,sizeof(*level->blendings)):NULL;strcpy(arguments[1],"palette");
  } else {
   size=&level->numspawns;int slots=fixed?spawn_limit:count;
   level->spawnpoints=slots?calloc(slots,sizeof(*level->spawnpoints)):NULL;
   next.at=91;next.name=(char*)"entry";strcpy(arguments[1],"31");
  }
  *size=count;assert(command(other_commands[kind])==allowed && *size==count+allowed);
  assert(!!errormessage==!allowed);if(!allowed)assert(!strcmp(errormessage,messages[kind]));
  assert(allocations==(allowed?(fixed && kind>=2?0:kind==2?2:1):0));
  if(kind==0) {
   assert(image_calls==sprite && holesprite==(sprite?17:1));
   if(allowed){const float fields[]={7,240,12,1,200,287,45};assert(!memcmp(level->holes[count],fields,sizeof(fields)));}
  }
  if(kind==1 && allowed)for(int j=0;j<8;++j)assert(level->walls[count][j]==j+1);
  if(kind==2){assert(palette_calls==allowed && blend_calls==allowed);if(allowed)assert(level->palettes[count][0]==0x4a);}
  if(kind==3) {
   if(allowed){s_spawn_entry zero={0};assert(level->spawnpoints[count].at==31 && !strcmp(level->spawnpoints[count].name,"entry"));assert(!memcmp(&next,&zero,sizeof(next)));}
   else assert(next.at==31 && !strcmp(next.name,"entry"));
  }
 }
 const int initial_counts[]={0,panel_limit-1,panel_limit,panel_limit+1};
 for(unsigned c=0;c<sizeof(initial_counts)/sizeof(*initial_counts);++c)for(int pattern=0;pattern<7;++pattern) {
  ++test_case;reset();int initial=initial_counts[c];level->numpanels=initial;
  if(initial){order=calloc(initial,sizeof(*order));level->panels=calloc(initial,sizeof(*level->panels));assert(order && level->panels);}
  char text[1024]={0};
  if(pattern==1)strcpy(text,"aZ");
  if(pattern==2)strcpy(text,"*");
  if(pattern>=3) {
   int n=pattern==3?panel_limit+2:panel_limit-initial+(pattern-5);
   if(n<0)n=0;
   memset(text,'a',n);text[n]=pattern==3?0:'*';
  }
  order_step(fixed,panel_limit,text);
 }
 for(unsigned c=0;c<sizeof(initial_counts)/sizeof(*initial_counts);++c) {
  ++test_case;reset();int initial=initial_counts[c];level->numpanels=initial;
  if(initial){order=calloc(initial,sizeof(*order));level->panels=calloc(initial,sizeof(*level->panels));assert(order && level->panels);}
  order_step(fixed,panel_limit,"a");order_step(fixed,panel_limit,"bZ*");
 }
 reset();
}
int main(void) {@CHECKS@assert(test_case==@CASE_COUNT@);return 0;}
'''.replace('@PLAIN@', plain[0]).replace('@CASES@', '\n'.join(selected))
           .replace('@CHECKS@', '\n'.join(checks)).replace('@CASE_COUNT@', str(len(rows)*122)), includes, flags)

    def test_takedamage_pain_threshold_uses_each_profiles_factor_owner(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-pain-threshold-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        default = re.search(r'const\s+s_defense\s+default_defense\s*=\s*\{[^}]*\};', source)
        self.assertIsNotNone(default)
        helper = default[0] + '\n' + function(source, 'obor_combat_defense')
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['common_takedamage_sha256'], r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d);' % (
                row['revision'], row['factor_target'] == 'model'))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Pain threshold: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
static int max_attack_types=24,grab_allowed=1,pain_calls,damage_calls;
static void previous(void) {abort();}
static void pain_action(void) {abort();}
static void fall_action(void) {abort();}
static void grab_action(void) {abort();}
static void damage_service(entity *other,s_attack *attack) {
 assert(other && attack && self->health==100);++damage_calls;
}
static int pain_service(entity *e,int type,int reset) {
 assert(e==self && type==self->damagetype && reset==1 && self->takeaction==pain_action);
 ++pain_calls;return 1;
}
#undef time
#define time 37u
#define common_pain pain_action
#define common_fall fall_action
#define common_grabattack grab_action
#define checkgrab(...) grab_allowed
#define checkdamagedrop(...) ((void)0)
#define dropweapon(...) ((void)0)
#define checkdamageeffects(...) ((void)0)
#define checkdamageflip(...) ((void)0)
#define checkmpadd(...) ((void)0)
#define checkhitscore(...) ((void)0)
#define checkdamage damage_service
#define checkdeath(...) ((void)0)
#define control_rumble(...) ((void)0)
#define player_die(...) abort()
#undef kill
#define kill(...) abort()
#define ent_unlink(...) ((void)0)
#define set_death(...) ((void)0)
#define toss(...) ((void)0)
#define set_fall(...) 1
#define set_pain pain_service
@HELPER@
@OPPONENT@
@METHOD@
static void check(int model_target) {
 s_defense model[25]={0},personal[24]={0};
 const float model_values[]={0,5,15,30,-2},personal_values[]={0,7,17};
 const int forces[]={-3,0,6,14,30},selectors[]={0,1,15,23};
 for(unsigned m=0;m<sizeof(model_values)/sizeof(*model_values);++m)
 for(unsigned p=0;p<sizeof(personal_values)/sizeof(*personal_values);++p)
 for(unsigned f=0;f<sizeof(forces)/sizeof(*forces);++f)
 for(unsigned t=0;t<sizeof(selectors)/sizeof(*selectors);++t)for(int gates=0;gates<8;++gates) {
  ++test_case;entity actor={0},attacker={0};self=&actor;s_attack attack={0};
  for(int i=0;i<25;++i)model[i].pain=model_values[m];
  for(int i=0;i<24;++i)personal[i].pain=personal_values[p];
  self->modeldata.defense=model;self->defense=personal;self->health=100;
  self->modeldata.type=TYPE_ENEMY;self->takeaction=previous;self->a=0;
  self->frozen=!!(gates&1);self->modeldata.nopain=!!(gates&2);attack.no_pain=!!(gates&4);
  attack.attack_force=forces[f];attack.attack_type=selectors[t];attacker.grabbing=self;
  pain_calls=damage_calls=0;
  float factor=model_target?model_values[m]:personal_values[p];
  int expected=!gates && !(factor && forces[f]<factor);
  assert(common_takedamage(&attacker,&attack)==1 && damage_calls==1 && pain_calls==expected);
  assert(self->damagetype==selectors[t] && self->opponent==&attacker && attacker.opponent==self);
  assert(self->takeaction==(expected?pain_action:previous) && self->health==100);
 }
 for(int early=0;early<3;++early) {
  ++test_case;entity actor={0},attacker={0};s_attack attack={0};self=&actor;
  self->dead=early==0;self->toexplode=early==1?2:0;grab_allowed=early!=2;
  pain_calls=damage_calls=0;
  assert(common_takedamage(&attacker,&attack)==0 && !pain_calls && !damage_calls);
 }
 grab_allowed=1;
}
int main(void) {@CHECKS@return 0;}
'''.replace('@HELPER@', helper).replace('@OPPONENT@', function(source, 'set_opponent'))
           .replace('@METHOD@', function(source, 'common_takedamage'))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def _block_pain_inputs(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-block-pain-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        root = ROOT / 'src/engines/3842'
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3842', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else ['-Wno-error=multistatement-macros']
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        return rows, (root / 'openbor.c').read_text(), includes, flags

    def test_block_hold_and_blockpain_match_each_source_profile(self):
        rows, source, includes, flags = self._block_pain_inputs()
        thinker = function(source, 'player_think')
        marker = thinker.index('// New block code for players')
        start = thinker.rfind('if(', 0, marker)
        brace = thinker.index('{', marker)
        wrapper = function('void selected(void) ' + thinker[brace:], 'selected')
        primary = thinker[start:brace] + wrapper[wrapper.index('{'):]
        # The old held-key path is immediately before running logic. Extract
        # its actual profile gate, not an independently rewritten algorithm.
        stop = thinker.index('//dang long run checking logic')
        match = list(re.finditer(r'if\(obor_profile_build < 3798\)\s*\{', thinker[:stop]))
        tail = ''
        if match:
            start = match[-1].start()
            brace = thinker.index('{', start)
            wrapper = function('void selected(void) ' + thinker[brace:], 'selected')
            tail = thinker[start:brace] + wrapper[wrapper.index('{'):]
        macro = source[source.index('#define painflags'):source.index('\nint set_blockpain', source.index('#define painflags'))]
        checks = []
        for row in rows:
            checks.append('obor_profile_build=%d;check(%s);' % (row['revision'], ','.join(
                str(int(row[k])) for k in ('legacy_block', 'ignore_pain', 'hold_pain_bit',
                'block_recovery', 'legacy_player_hold', 'blockpain_mode', 'max_atks'))))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Block contract: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
static s_player player[MAX_PLAYERS];
static int max_attack_types,block_ids[64],*animblkpains=block_ids;
static int animations_seen,idles,unfreezes,seen_flags,seen_pain;
static int last_animation,last_reset;
static void previous(void) {abort();}
void common_pain(void) {abort();}
static int status(entity *e) {
 return e->idling | (e->falling<<1) | (e->projectile<<2) | (e->drop<<3) |
  (e->attacking<<4) | (e->getting<<5) | (e->charging<<6) | (e->jumping<<7) | (e->blocking<<8);
}
int set_idle(entity *e) {assert(e==self && !e->blocking && !e->takeaction);++idles;return 1;}
void ent_set_colourmap(entity *e,unsigned int map) {
 assert(e->frozen && map==(unsigned int)e->map);++unfreezes;seen_flags=status(e);seen_pain=e->inpain;
}
void ent_set_anim(entity *e,int animation,int reset) {
 assert(validanim(e,animation));++animations_seen;last_animation=animation;last_reset=reset;
 seen_flags=status(e);seen_pain=e->inpain;
}
@PAINFLAGS@
@COMMON@
@BLOCKPAIN@
static int primary(s_player *pl,int notinair) {
 if(pl->playkeys & FLAG_SPECIAL) {@PRIMARY@}
 return 0;
endthinkcheck:return 1;
}
static int held(s_player *pl,int notinair) {
 if(0)goto endthinkcheck;
 @TAIL@
 return 0;
endthinkcheck:return 1;
}
static void init(entity *e,s_anim **animations) {
 memset(e,0,sizeof(*e));e->modeldata.animation=animations;e->modeldata.animation_capacity=512;
 e->takeaction=previous;e->xdir=3;e->zdir=-2;e->combostep[0]=9;
 e->idling=e->falling=e->projectile=e->drop=e->attacking=e->getting=e->charging=e->jumping=e->blocking=e->inpain=1;
 e->map=7;e->frozen=1;e->freezetime=90;
 animations_seen=idles=unfreezes=0;last_animation=last_reset=-1;seen_flags=seen_pain=-1;
}
static void check(int legacy,int ignore,int painbit,int recovery,int old_player,int bp_mode,int attack_count) {
 s_anim animation={0};animation.numframes=1;s_anim *animations[512]={0};
 entity actor,other;self=&actor;max_attack_types=attack_count;
 for(int i=0;i<64;++i)block_ids[i]=i?300+i:ANI_BLOCKPAIN;
 for(int hold=0;hold<4;++hold)for(int type=0;type<2;++type)for(int pain=0;pain<2;++pain)
 for(int animate=0;animate<2;++animate)for(int key=0;key<2;++key)for(int valid=0;valid<2;++valid) {
  ++test_case;init(self,animations);self->modeldata.holdblock=hold;
  self->modeldata.type=type?TYPE_PLAYER:TYPE_ENEMY;self->inpain=pain;self->animating=animate;
  animations[ANI_BLOCK]=valid?&animation:NULL;player[0].keys=key?FLAG_SPECIAL:0;
  self->takeaction=common_block;
  int hb=hold && type && (ignore || !pain || (painbit && (hold&2)));
  int rec=!legacy && recovery && pain && (hold&2) && !animate && valid;
  int finish=legacy?!animate:!rec && ((hb&&!key)||(!animate&&(!hb||!key)));
  common_block();assert(idles==finish && animations_seen==rec);
  assert(self->blocking==!finish && self->takeaction==(finish?NULL:common_block));
  assert(self->inpain==(rec?0:pain));
 }
 /* Defined handling of a player slot outside the table is separate from
    the original's valid-slot oracle. */
 init(self,animations);self->playerindex=MAX_PLAYERS;self->modeldata.type=TYPE_PLAYER;
 self->modeldata.holdblock=1;self->inpain=0;self->animating=1;common_block();
 assert(idles==!legacy);
 for(int hold=0;hold<4;++hold)for(int valid=0;valid<2;++valid)for(int ground=0;ground<2;++ground)
 for(int pressed=0;pressed<2;++pressed)for(int was_blocking=0;was_blocking<2;++was_blocking) {
  ++test_case;init(self,animations);self->modeldata.holdblock=hold;
  self->blocking=was_blocking;animations[ANI_BLOCK]=valid?&animation:NULL;
  player[0].playkeys=(pressed?FLAG_SPECIAL:0)|FLAG_ATTACK;
  int entered=pressed && valid && ground && (!old_player||!hold);
  assert(primary(&player[0],ground)==entered && animations_seen==entered);
  assert(player[0].playkeys==(unsigned int)((pressed&&!entered?FLAG_SPECIAL:0)|FLAG_ATTACK));
  assert(self->takeaction==(entered?common_block:previous));
  assert(self->xdir==(entered?0:3) && self->zdir==(entered?0:-2));
  assert(self->combostep[0]==(entered?0:9) && self->idling==!entered);
  assert(self->blocking==(entered?1:was_blocking));
  init(self,animations);self->modeldata.holdblock=hold;self->blocking=was_blocking;
  player[0].keys=(pressed?FLAG_SPECIAL:0)|FLAG_ATTACK;player[0].playkeys=FLAG_ATTACK;
  int active=old_player && valid && hold && pressed && ground;
  int changed=active && !was_blocking;
  assert(held(&player[0],ground)==active && animations_seen==changed);
  assert(self->blocking==(old_player?active:was_blocking));
  assert(self->takeaction==previous && self->idling==1 && self->combostep[0]==9);
  assert(self->xdir==(changed?0:3) && self->zdir==(changed?0:-2));
  assert(player[0].keys==(unsigned int)((pressed?FLAG_SPECIAL:0)|FLAG_ATTACK) && player[0].playkeys==FLAG_ATTACK);
 }
 int selectors[]={-1,0,1,attack_count-1,attack_count};
 for(int base=0;base<2;++base)for(int typed=0;typed<2;++typed)
 for(unsigned t=0;t<sizeof(selectors)/sizeof(*selectors);++t)
 for(int same=0;same<2;++same)for(int reset=0;reset<2;++reset)
 for(int initial=0;initial<2;++initial)for(int inp=0;inp<2;++inp) {
  ++test_case;memset(animations,0,sizeof(animations));init(&actor,animations);init(&other,animations);
  if(!initial) {
   actor.idling=actor.falling=actor.projectile=actor.drop=actor.attacking=actor.getting=actor.charging=actor.jumping=actor.blocking=0;
   other.idling=other.falling=other.projectile=other.drop=other.attacking=other.getting=other.charging=other.jumping=other.blocking=0;
  }
  actor.inpain=other.inpain=inp;
  self=same?&actor:&other;entity *target=&actor;int selector=selectors[t];
  animations[ANI_BLOCKPAIN]=base?&animation:NULL;
  for(int i=1;i<attack_count;++i)animations[block_ids[i]]=typed?&animation:NULL;
  int chosen=selector<0 || selector>=attack_count || !validanim(target,block_ids[selector])?0:selector;
  int fallback=bp_mode==0 && !base;
  int played=!fallback && !!validanim(target,block_ids[chosen]);
  assert(set_blockpain(target,selector,reset)==(fallback||played));
  assert(animations_seen==played && unfreezes==(played && bp_mode==1));
  assert(target->takeaction==(fallback || (played&&bp_mode==1)?common_pain:played?common_block:previous));
  int original_flags=initial?511:0;
  int target_flags=!played || fallback?original_flags:bp_mode==0?(original_flags&~1)|16:bp_mode==1?0:same?(original_flags&~1)|256:original_flags;
  int expected_pain=played && bp_mode>=1?1:inp;
  assert(status(target)==target_flags && target->inpain==expected_pain);
  if(played)assert(last_animation==block_ids[chosen] && last_reset==reset && seen_flags==target_flags && seen_pain==expected_pain);
  assert(target->frozen==!(played && bp_mode==1));
  if(!same)assert(status(self)==(played&&bp_mode==2?(original_flags&~1)|256:original_flags));
  self=&actor;
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@PAINFLAGS@', macro).replace('@COMMON@', function(source, 'common_block'))
           .replace('@BLOCKPAIN@', function(source, 'set_blockpain')).replace('@PRIMARY@', primary)
           .replace('@TAIL@', tail).replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_pain_guard_and_callback_order_match_each_source_profile(self):
        rows, source, includes, flags = self._block_pain_inputs()
        macro = source[source.index('#define painflags'):source.index('\nint set_blockpain', source.index('#define painflags'))]
        checks = ['obor_profile_build=%d;check(%d,%d);' % (
            row['revision'], row['early_guard_reset'], row['max_atks']) for row in rows]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Pain order: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int max_attack_types,pain_ids[64],*animpains=pain_ids;
static int animations_seen,scripts,unfreezes,seen_guard,seen_max,seen_flags;
static int seen_pain,last_animation,last_reset,mutation,unfreeze_pain;
static int script_guard,script_pain;
static int status(entity *e) {
 return e->idling | (e->falling<<1) | (e->projectile<<2) | (e->drop<<3) |
  (e->attacking<<4) | (e->getting<<5) | (e->charging<<6) | (e->jumping<<7) | (e->blocking<<8);
}
void ent_set_colourmap(entity *e,unsigned int map) {
 assert(e->frozen && map==(unsigned int)e->map && status(e)==0);
 ++unfreezes;unfreeze_pain=e->inpain;
}
void ent_set_anim(entity *e,int animation,int reset) {
 assert(validanim(e,animation) && !e->xdir && !e->zdir && !e->tossv);
 ++animations_seen;last_animation=animation;last_reset=reset;
 seen_guard=e->modeldata.guardpoints.current;seen_max=e->modeldata.guardpoints.maximum;
 seen_flags=status(e);seen_pain=e->inpain;
 if(mutation==1)e->modeldata.guardpoints.current=0;
 if(mutation==2)e->modeldata.guardpoints.current=7;
 if(mutation==3)e->modeldata.guardpoints.maximum=37;
}
void execute_onpain_script(entity *e,int type,int reset) {
 (void)type;assert(reset==last_reset && !e->frozen && !e->freezetime && status(e)==0);
 ++scripts;script_guard=e->modeldata.guardpoints.current;script_pain=e->inpain;
}
@PAINFLAGS@
@METHOD@
static void check(int early,int attack_count) {
 s_anim animation={0};animation.numframes=1;s_anim *animations[512]={0};
 max_attack_types=attack_count;for(int i=0;i<64;++i)pain_ids[i]=250+i;
 int selectors[]={-1,0,1,attack_count-1,attack_count};
 for(int broken=0;broken<3;++broken)for(unsigned t=0;t<sizeof(selectors)/sizeof(*selectors);++t)
 for(int mask=0;mask<8;++mask)for(mutation=0;mutation<4;++mutation)
 for(int frozen=0;frozen<2;++frozen)for(int reset=0;reset<2;++reset) {
  ++test_case;entity actor={0};int selector=selectors[t];
  actor.modeldata.animation=animations;actor.modeldata.animation_capacity=512;
  actor.modeldata.guardpoints.maximum=broken==2?0:20;
  actor.modeldata.guardpoints.current=broken==0?0:5;
  actor.xdir=3;actor.zdir=-2;actor.tossv=7;actor.map=9;actor.frozen=frozen;actor.freezetime=90;
  actor.idling=actor.falling=actor.projectile=actor.drop=actor.attacking=actor.getting=actor.charging=actor.jumping=actor.blocking=1;
  actor.inpain=0;
  memset(animations,0,sizeof(animations));
  int pain=broken==0?ANI_GUARDBREAK:selector==-1 || selector>=attack_count?ANI_GRABBED:pain_ids[selector];
  animations[pain]=mask&1?&animation:NULL;
  animations[pain_ids[0]]=mask&2?&animation:NULL;
  animations[ANI_IDLE]=mask&4?&animation:NULL;
  int chosen=validanim(&actor,pain)?pain:validanim(&actor,pain_ids[0])?pain_ids[0]:validanim(&actor,ANI_IDLE)?ANI_IDLE:-1;
  int played=chosen>=0,initial=broken==0?0:5;
  int expected_guard=early && broken==0?20:initial;
  animations_seen=scripts=unfreezes=0;seen_guard=seen_flags=seen_pain=last_animation=last_reset=-1;
  unfreeze_pain=script_guard=script_pain=-1;
  assert(set_pain(&actor,selector,reset)==played);
  assert(animations_seen==played && scripts==played && unfreezes==(played && frozen));
  assert(!actor.xdir && !actor.zdir && !actor.tossv);
  int expected_max=broken==2?0:20;
  if(played) {
   assert(last_animation==chosen && last_reset==reset && seen_guard==expected_guard && seen_max==expected_max);
   assert(seen_flags==511 && seen_pain==0);
   if(mutation==1)expected_guard=0;
   if(mutation==2)expected_guard=7;
   if(mutation==3)expected_max=37;
   if(!early && expected_max>0 && expected_guard<=0)expected_guard=expected_max;
   assert(status(&actor)==0 && actor.inpain==(pain!=ANI_GRABBED));
   assert(script_guard==expected_guard && script_pain==actor.inpain);
   if(frozen)assert(unfreeze_pain==(early?1:pain!=ANI_GRABBED));
   assert(!actor.frozen && !actor.freezetime);
  } else {
   assert(status(&actor)==511 && actor.inpain==0 && actor.frozen==frozen);
   assert(actor.freezetime==90);
  }
  assert(actor.modeldata.guardpoints.current==expected_guard && actor.modeldata.guardpoints.maximum==expected_max);
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@PAINFLAGS@', macro).replace('@METHOD@', function(source, 'set_pain'))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_historical_filter_requests_preserve_unfiltered_pixels(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        contexts = {}
        for profile in pin['profiles']:
            contexts.setdefault(profile['engine'], []).append(
                int(profile.get('revision', profile['build'])))
        if 'OBOR_HISTORICAL_ENGINE' in os.environ:
            contexts = {ENGINE.name: contexts.get(ENGINE.name, [])}
        # Pending private profiles extend the explicit engine context. Default
        # CI still covers every registered engine and logical profile.
        extra = json.loads(os.environ.get('OBOR_TEST_PROFILE_BUILDS', '[]'))
        self.assertIsInstance(extra, list)
        self.assertLessEqual(len(extra), 512)
        self.assertTrue(all(type(p) is int and 0 < p <= 0xffffffff for p in extra))
        if extra:
            profiles = contexts.setdefault(ENGINE.name, [])
            profiles += sorted(set(extra) - set(profiles))
        self.assertTrue(contexts)
        for engine, profiles in contexts.items():
            root = ENGINE if engine == ENGINE.name else ROOT / 'src/engines' / engine
            with self.subTest(engine=engine, profiles=len(profiles)):
                self.assertTrue(profiles)
                self._check_filter_context(root, profiles)

    def _check_filter_context(self, engine, profiles):
        video = (ROOT / 'src/port/libretro/video.c').read_text()
        declarations = re.search(
            r'^static s_videomodes mode;[\s\S]*?(?=\n#ifdef OBOR_HAS_YUV)', video, re.M)
        self.assertIsNotNone(declarations)
        methods = '\n'.join(function(video, name) for name in (
            'ensure_fb', 'vga_setpalette', 'video_set_mode', 'video_restore_mode',
            'convert_screen', 'video_copy_screen'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
DECLARATIONS
static int yuv_mode;
static const unsigned expected[4]={0xff0000,0x00ff00,0x0000ff,0xffffff};
static unsigned submitted,yielded;
static uint32_t obor_profile_build;
static void obor_port_submit_frame(const unsigned *pixels,int w,int h,int pitch) {
    assert(obor_profile_build && w==2 && h==2 && pitch==2);
    assert(!memcmp(pixels,expected,sizeof(expected)));
    ++submitted;
}
static void obor_yield_frame(void) { ++yielded; }
METHODS
int main(void) {
    static const uint32_t profiles[]={PROFILES};
    unsigned char palette[768]={0};
    palette[3]=255;palette[7]=255;palette[11]=255;
    palette[12]=palette[13]=palette[14]=255;
    vga_setpalette(palette);
    s_screen *screen=calloc(1,sizeof(*screen)+16);
    assert(screen);
    screen->width=2;screen->height=2;
    const unsigned pixels32[4]={0x0000ff,0x00ff00,0xff0000,0xffffff};
    const unsigned short pixels16[4]={0x001f,0x07e0,0xf800,0xffff};
    const unsigned char pixels8[4]={1,2,3,4};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(int filter=-128;filter<=127;++filter) {
            for(int display=0;display<3;++display) {
                s_videomodes requested={0};
                requested.hRes=2;requested.vRes=2;
                requested.filter=(__typeof__(requested.filter))filter;
                requested.mode=(__typeof__(requested.mode))display;
                assert(video_set_mode(requested)==1);
                assert(video_restore_mode()==1);
                assert(!yuv_mode && mode.filter==requested.filter);
                for(int format=0;format<4;++format) {
                    screen->palette=0;
                    if(format==0) {
                        screen->pixelformat=PIXEL_32;
                        memcpy(screen->data,pixels32,sizeof(pixels32));
                    } else if(format==1) {
                        screen->pixelformat=PIXEL_16;
                        memcpy(screen->data,pixels16,sizeof(pixels16));
                    } else {
                        screen->pixelformat=PIXEL_8;
                        memcpy(screen->data,pixels8,sizeof(pixels8));
                        if(format==2)screen->palette=palette;
                    }
                    unsigned old_submitted=submitted,old_yielded=yielded;
                    assert(video_copy_screen(screen)==1);
                    assert(state_source==screen);
                    assert(submitted==old_submitted+1 && yielded==old_yielded+1);
                }
            }
        }
    }
    free(screen);free(fb);
    return 0;
}
'''.replace('DECLARATIONS', declarations[0]).replace('METHODS', methods).replace(
            'PROFILES', ','.join(map(str, profiles))),
            include_dirs=(engine / 'source/gamelib',), extra_flags=('-fsigned-char',))



    def test_projected_shadow_queue_palette_matches_each_source_profile(self):
        fixture=load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-shadow-palette-contracts.json')
        rows=fixture['sources'];revisions={row['revision'] for row in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for row in rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertIs(type(row['uses_entity_palette']),bool)
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
        for engine in sorted({row['engine'] for row in rows}):
            with self.subTest(engine=engine):
                root=ROOT/'src/engines'/engine
                source=(root/'openbor.c').read_text();types=(root/'source/gamelib/types.h').read_text()
                records=[]
                for name in ('water_transform','s_drawmethod'):
                    match=re.search(r'\}\s*'+re.escape(name)+r'\b[^;]*;',types)
                    self.assertIsNotNone(match,name)
                    start=types.rfind('typedef struct',0,match.start());records.append(types[start:match.end()])
                body=function(source,'display_ents');start=body.index('shadowmethod = plainmethod;')
                first=body.index('spriteq_add_sprite(',start);second=body.index('spriteq_add_sprite(',first+1)
                stop=body.index('}',body.index(';',second))+1;block=body[start:stop]
                profiles=','.join('{%d,%d}'%(row['revision'],row['uses_entity_palette'])
                                  for row in rows if row['engine']==engine)
                native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@TYPES@
static uint32_t obor_profile_build;static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Shadow palette revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
static s_drawmethod plainmethod;
static int shadowcolor,shadowalpha,light[2],alty;
static struct {int x,y,z,frame,sort;s_drawmethod method;} queue[2];
static int submitted;
static unsigned char base_palette[256],entity_palette[256];
static void spriteq_add_sprite(int x,int y,int z,int frame,s_drawmethod *method,int sort) {
 assert(submitted<2);queue[submitted].x=x;queue[submitted].y=y;queue[submitted].z=z;
 queue[submitted].frame=frame;queue[submitted].sort=sort;queue[submitted].method=*method;++submitted;
}
static void project(s_drawmethod *drawmethod,int use_mirror) {
 int qx=31,qy=41,z=5,f=7,sy=-41,sz=9;s_drawmethod shadowmethod;
 @BLOCK@
}
static void check(int takes_entity,int base_map,int actor_map,int colour,int alpha,
                  int vertical_light,int scale,int flips,int rotation,int mirror,int altitude) {
 memset(&plainmethod,0,sizeof(plainmethod));plainmethod.table=base_map?base_palette:NULL;
 /* All-bits-set is true for both signed one-bit and full-width flags. */
 plainmethod.centerx=17;plainmethod.centery=13;plainmethod.flag=-1;
 s_drawmethod actor;memset(&actor,0,sizeof(actor));actor.table=actor_map?entity_palette:NULL;
 actor.scalex=384;actor.scaley=scale;actor.flipx=!!(flips&1);actor.flipy=!!(flips&2);
 actor.rotate=rotation;actor.shiftx=11;actor.centerx=99;
 shadowcolor=colour;shadowalpha=alpha;light[0]=73;light[1]=vertical_light;alty=altitude;
 submitted=0;project(&actor,mirror);assert(submitted==1+mirror);
 unsigned char *palette=takes_entity?actor.table:plainmethod.table;
 int expected_scale=vertical_light*scale/256;
 int expected_center=plainmethod.centery+altitude,expected_flip=!!actor.flipy;
 if(expected_flip)expected_center=-expected_center;
 if(expected_scale<0){expected_scale=-expected_scale;expected_flip=!expected_flip;}
 for(int i=0;i<submitted;++i){
  s_drawmethod *method=&queue[i].method;
  assert(queue[i].x==31 && queue[i].y==(i?-41:41) && queue[i].z==(i?9:5));
  assert(queue[i].frame==7 && queue[i].sort==0 && method->table==palette);
  if(palette)assert(method->table[7]==(palette==base_palette?41:91));
  assert(method->fillcolor==(unsigned)(colour>0?colour:0) && method->alpha==alpha);
  assert(method->scalex==actor.scalex && method->scaley==expected_scale);
  assert(!!method->flipx==!!actor.flipx && !!method->flipy==(i?!expected_flip:expected_flip));
  assert(method->centery==(i?-expected_center:expected_center) && method->centerx==17);
  assert(method->rotate==rotation && method->shiftx==84 && !!method->flag);
 }
}
int main(void) {
 const struct {unsigned revision;int takes_entity;} profiles[]={@PROFILES@};
 const int colours[]={-9,0,19},alphas[]={1,6},lights[]={-256,128,256},scales[]={128,256},rotations[]={-135,0,135};
 base_palette[7]=41;entity_palette[7]=91;
 for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p){
  obor_profile_build=profiles[p].revision;test_case=0;
  for(int base=0;base<2;++base)for(int actor=0;actor<2;++actor)
  for(int colour=0;colour<3;++colour)for(int alpha=0;alpha<2;++alpha)
  for(int light=0;light<3;++light)for(int scale=0;scale<2;++scale)
  for(int flips=0;flips<4;++flips)for(int rotate=0;rotate<3;++rotate)
  for(int mirror=0;mirror<2;++mirror)for(int altitude=0;altitude<2;++altitude){
   ++test_case;check(profiles[p].takes_entity,base,actor,colours[colour],alphas[alpha],
                    lights[light],scales[scale],flips,rotations[rotate],mirror,altitude?7:0);
  }
 }
 return 0;
}
'''.replace('@TYPES@','\n'.join(records)).replace('@BLOCK@',block).replace('@PROFILES@',profiles),
                       extra_flags=['-DLIBRETRO=1'])

    def test_model_clip_frame_and_submission_coordinate_boundary(self):
        source = (ENGINE / 'openbor.c').read_text()
        types = (ENGINE / 'source/gamelib/types.h').read_text()
        records = []
        for name in ('water_transform', 's_drawmethod'):
            match = re.search(r'\}\s*' + re.escape(name) + r'\b[^;]*;', types)
            self.assertIsNotNone(match, name)
            start = types.rfind('typedef struct', 0, match.start())
            records.append(types[start:match.end()])
        helpers = '\n'.join(function(source, name) for name in (
            'obor_model_clip_coordinate', 'obor_model_clip_frame', 'obor_model_clip_screen'))
        start = source.index('if(drawmethod.flag)')
        stop = source.index('else dm.flag = 0;', start) + len('else dm.flag = 0;')
        frame_code = source[start:stop]
        start = source.index('obor_model_clip_screen(drawmethod,', source.index('void display_ents()'))
        stop = source.index('spriteq_add_sprite(', start)
        submission = source[start:source.index(';', stop)+1]
        self.assertEqual(source.count('obor_model_clip_frame(&dm, offset);'), 1)
        self.assertEqual(source.count('obor_model_clip_screen(drawmethod,'), 1)
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
TYPES
static uint32_t obor_profile_build;
HELPERS
static int submitted_x,submitted_y,submissions;
static s_drawmethod submitted_method;
static void spriteq_add_sprite(int x,int y,int z,int f,s_drawmethod *method,int sortid) {
    assert(z==13 && f==17 && sortid==19);
    submitted_x=x;submitted_y=y;submitted_method=*method;++submissions;
}
static s_drawmethod frame(s_drawmethod drawmethod,int x,int y) {
    int offset[2]={x,y};s_drawmethod dm={0};
    FRAME
    return dm;
}
typedef struct { float x,z,a; } entity;
static void submit(s_drawmethod *drawmethod,entity *e,float scrx,float scry) {
    int z=13,f=17,sortid=19;
    SUBMISSION
}
int main(void) {
    const int clips[2][2]={{75,-20},{-20,40}};
    const int offsets[2][2]={{11,-7},{-3,4}};
    const int frame_expected[2][2]={{64,-13},{-17,36}};
    const int screen_expected[2][2]={{79,10},{-24,35}};
    entity positions[2]={{18.75f,30.5f,2.25f},{-2.75f,-1.25f,3.0f}};
    const float cameras[2][2]={{3.5f,4.75f},{5.0f,-2.5f}};
    const int projected[2][2]={{15,23},{-7,-1}};
    const int widths[3]={0,23,-5};
    /* Every requested logical build and every existing pre-3842 profile is
       exercised; this does not register profiles or admit pre-3746 clip syntax. */
    for(uint32_t profile=3666;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(int test=0;test<2;++test) for(unsigned w=0;w<3;++w) {
            s_drawmethod input={0};input.flag=1;input.alpha=3;input.rotate=45;
            input.clipx=clips[test][0];input.clipy=clips[test][1];
            input.clipw=widths[w];input.cliph=31;
            s_drawmethod method=frame(input,offsets[test][0],offsets[test][1]);
            const int *expected=(profile>=3842 && input.clipw)?frame_expected[test]:clips[test];
            assert(method.clipx==expected[0] && method.clipy==expected[1]);
            submissions=0;submit(&method,&positions[test],cameras[test][0],cameras[test][1]);
            expected=(profile>=3842 && input.clipw)?screen_expected[test]:clips[test];
            assert(submissions==1 && submitted_x==projected[test][0] && submitted_y==projected[test][1]);
            assert(submitted_method.clipx==expected[0] && submitted_method.clipy==expected[1]);
            assert(submitted_method.flag==1 && submitted_method.alpha==3 && submitted_method.rotate==45);
            assert(submitted_method.clipw==input.clipw && submitted_method.cliph==31);
        }
        s_drawmethod disabled={0};disabled.clipw=23;
        assert(frame(disabled,11,-7).flag==0);
    }
}
'''.replace('TYPES', '\n'.join(records)).replace('HELPERS', helpers)
   .replace('FRAME', frame_code).replace('SUBMISSION', submission), extra_flags=('-DLIBRETRO',))

    def test_model_clip_integer_extremes_remain_bounded(self):
        source = (ENGINE / 'openbor.c').read_text()
        helpers = '\n'.join(function(source, name) for name in (
            'obor_model_clip_coordinate', 'obor_model_clip_frame', 'obor_model_clip_screen'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
typedef struct { int clipx,clipy,clipw; } s_drawmethod;
static uint32_t obor_profile_build;
HELPERS
int main(void) {
    assert(obor_model_clip_coordinate(INT_MIN,1,1)==INT_MIN);
    assert(obor_model_clip_coordinate(INT_MAX,1,0)==INT_MAX);
    assert(obor_model_clip_coordinate(0,INT_MIN,1)==INT_MAX);
    assert(obor_model_clip_coordinate(0,INT_MIN,0)==INT_MIN);
    assert(obor_model_clip_coordinate(0,INT_MAX,1)==-INT_MAX);
    for(uint32_t profile=3666;profile<=3842;++profile) {
        obor_profile_build=profile;
        s_drawmethod method={INT_MAX,INT_MIN,23};int offset[2]={-1,1};
        obor_model_clip_frame(&method,offset);
        obor_model_clip_screen(&method,1,-1);
        assert(method.clipx==INT_MAX && method.clipy==INT_MIN && method.clipw==23);
    }
}
'''.replace('HELPERS', helpers))

    def test_upstream_sdk_deprecations_remain_visible_warnings(self):
        native('int legacy(void) __attribute__((deprecated("SDK API")));\n'
               'int legacy(void) { return 0; }\n'
               'int main(void) { return legacy(); }\n')

    def test_unrelated_probe_warnings_remain_errors(self):
        with self.assertRaises(subprocess.CalledProcessError):
            native('int main(void) { int unused; return 0; }\n')

    def test_unary_numeric_and_unsupported_value_boundary(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-unary-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, 3827, 3828}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['clear_non_numeric'], row['revision'] < 3828)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        source = (ENGINE / 'source/scriptlib/ScriptVariant.c').read_text()
        methods = '\n'.join(function(source, name) for name in ('ScriptVariant_Pos', 'ScriptVariant_Neg'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef int32_t LONG;
enum { VT_EMPTY,VT_INTEGER,VT_DECIMAL,VT_STR,VT_PTR };
typedef struct { union { LONG lVal; double dblVal; void *ptrVal; }; int vt; } ScriptVariant;
static uint32_t obor_profile_build;
static int cleared;
static void ScriptVariant_Clear(ScriptVariant *v) { ++cleared;memset(v,0,sizeof(*v)); }
METHODS
int main(void) {
    const unsigned profiles[]={PROFILES};
    for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);++i) {
        unsigned profile=profiles[i];
        obor_profile_build=profile;
        for(int kind=0;kind<5;++kind) {
            ScriptVariant v={.lVal=7,.vt=kind},before=v;cleared=0;
            if(kind==VT_DECIMAL)v.dblVal=before.dblVal=1.25;
            ScriptVariant_Pos(&v);
            if(profile<3828 && kind!=VT_INTEGER && kind!=VT_DECIMAL)
                assert(v.vt==VT_EMPTY && cleared==1);
            else assert(!memcmp(&v,&before,sizeof(v)) && cleared==0);
            v=before;cleared=0;ScriptVariant_Neg(&v);
            if(kind==VT_INTEGER)assert(v.vt==VT_INTEGER && v.lVal==-7 && cleared==0);
            else if(kind==VT_DECIMAL)assert(v.vt==VT_DECIMAL && v.dblVal==-1.25 && cleared==0);
            else if(profile<3828)assert(v.vt==VT_EMPTY && cleared==1);
            else assert(!memcmp(&v,&before,sizeof(v)) && cleared==0);
        }
        if(profile<3828) {
            ScriptVariant v={.lVal=INT32_MIN,.vt=VT_INTEGER};
            ScriptVariant_Neg(&v);assert(v.lVal==INT32_MIN && v.vt==VT_INTEGER);
            v=(ScriptVariant){.dblVal=0.1,.vt=VT_DECIMAL};
            ScriptVariant_Neg(&v);assert(v.dblVal==-0.1 && v.vt==VT_DECIMAL);
        }
    }
}
'''.replace('METHODS', methods).replace('PROFILES', ','.join(str(row['revision']) for row in rows)))

    def test_model_switch_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-model-switch-contracts.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(fixture['boundary_controls']) <= {r['revision'] for r in rows})
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(s['engine'] == profile['engine'] and s['first'] <= revision <= s['last']
                   for s in fixture['coverage']):
                self.assertIn(revision, {r['revision'] for r in rows})
        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text()
                functions = '\n'.join(function(source, n) for n in ('ent_set_model', 'set_model_ex'))
                counters = '' if engine != '3741' else '\n'.join(function(source, n) for n in (
                    'obor_scene_counters_active', 'obor_scene_counter_adjust'))
                checks = []
                for row in rows:
                    if row['engine'] == engine:
                        self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                        self.assertEqual(row['wrapper_uses_sync_api'], row['sync_api'])
                        checks.append('obor_profile_build=%d;check(%d,%d,%d,%d,%d,%d);' % (
                            row['revision'], row['sync_api'], row['sync_requires_animation'],
                            row['sync_updates_frame'], row['sync_schedules_delay'],
                            row['modelcopy_callback'], row['platform_counter']))
                program = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define TYPE_PLAYER 1
#define TYPE_ENEMY 2
#define ANI_IDLE 0
#define ANI_SPAWN 1
#define ANI_RESPAWN 2
#define ANI_SELECT 3
#define MODEL_NO_COPY 1
#define MODEL_NO_SCRIPT_COPY 2
#define MODEL_NO_WEAPON_COPY 4
typedef struct {int numframes,id;} s_anim;
typedef struct {int initialized;} Script;
typedef struct {Script *onmodelcopy_script;} Scripts;
typedef struct {int marker;float factor;} s_defense;
typedef struct Model {
 char *name;int type,model_flag,hasPlatforms,animation_capacity;
 float speed,runspeed,runjumpheight,runjumpdist,runupdown,runhold;
 struct {int def,pain,get,die;} icon;
 int shadow,knife,pshotno,bomb,star,flash,bflash,dust[2],diesound;
 int weapnum,*weapon,numweapons;
 s_anim **animation;Scripts *scripts;s_defense *defense;float *offense_factors;
} s_model;
typedef struct Entity {
 s_model *model,modeldata;s_anim *animation;
 int animnum,animpos,attacking,nextanim,map,exists;
 Scripts *scripts;s_defense *defense;float *offense_factors;char name[32];
} entity;
static unsigned obor_profile_build,cases;
static int time,selectScreen,numPlatforms,max_attack_types=3;
static s_model old_model,new_model;
static entity live;
static s_anim old_animations[8],new_animations[8],*old_slots[8],*new_slots[8];
static Script old_callback,new_callback,live_callback;
static Scripts old_scripts,new_scripts,live_scripts;
static s_defense old_defense[5],new_defense[5],live_defense[5];
static float old_offense[5],new_offense[5],live_offense[5];
static int old_weapons[3],new_weapons[2];
static struct {s_model *model;} model_cache[1];
static int lookups,uninit_calls,colours,sets,frames,delays,clears,copies,callback_checks,callbacks;
@COUNTERS@
static void shutdown(int code,const char *message,...) {(void)code;(void)message;abort();}
static s_model *findmodel(const char *name) {
 ++lookups;assert(!strcmp(name,"old") || !strcmp(name,"new"));return !strcmp(name,"old")?&old_model:&new_model;
}
static int obor_model_copy(s_model *out,const s_model *in) {*out=*in;return 1;}
static void ent_copy_uninit(entity *ent,s_model *old) {assert(ent==&live && old->name==old_model.name);++uninit_calls;}
static void ent_set_colourmap(entity *ent,int map) {assert(ent==&live && map==2);++colours;}
static int validanim(entity *ent,int index) {
 return index>=0 && index<ent->modeldata.animation_capacity && ent->modeldata.animation[index] && ent->modeldata.animation[index]->numframes>0;
}
static void update_frame(entity *ent,int frame) {
 ++frames;assert(ent->animation);
 if(frame>=ent->animation->numframes)return;
 assert(frame>=0);ent->animpos=frame;ent->nextanim=900+frame;
}
static void ent_set_anim(entity *ent,int index,int reset) {
 assert(reset==0 && validanim(ent,index));++sets;ent->animnum=index;ent->animation=ent->modeldata.animation[index];
 ent->animpos=0;update_frame(ent,0);
}
static int calculate_edelay(entity *ent,int frame) {
 assert(ent->animation && frame>=0 && frame<ent->animation->numframes);++delays;return 20+frame;
}
static void clear_all_scripts(Scripts *scripts,int mode) {assert(scripts==&live_scripts && !mode);++clears;scripts->onmodelcopy_script->initialized=0;}
static void copy_all_scripts(Scripts *source,Scripts *dest,int mode) {
 assert(source==&new_scripts && dest==&live_scripts && !mode);++copies;
 if(source->onmodelcopy_script->initialized)dest->onmodelcopy_script->initialized=1;
}
static int Script_IsInitialized(Script *script) {++callback_checks;return script->initialized;}
static void execute_onmodelcopy_script(entity *ent,entity *before) {
 ++callbacks;assert(ent==&live && before->exists==1 && before->model==&old_model);
 assert(before->animation==&old_animations[4] && before->attacking==1);
 assert(before->defense!=ent->defense && before->offense_factors!=ent->offense_factors);
 for(int i=0;i<3;++i){assert(before->defense[i].marker==70+i && before->defense[i].factor==71+i);assert(before->offense_factors[i]==81+i);}
}
static int model_animation_reserve(s_model *model,int last) {assert(model==&new_model && last==7 && model->animation_capacity==8);return 1;}
@FUNCTIONS@
static void reset(int mask,int has_current,int fallback,int kind,int elapsed,int screen,int enemy,int position,int callback) {
 memset(&old_model,0,sizeof(old_model));memset(&new_model,0,sizeof(new_model));memset(&live,0,sizeof(live));
 for(int i=0;i<8;++i){old_animations[i]=(s_anim){3,100+i};new_animations[i]=(s_anim){2,200+i};old_slots[i]=&old_animations[i];new_slots[i]=NULL;}
 new_slots[0]=&new_animations[0];for(int i=1;i<4;++i)if(fallback&(1<<(i-1)))new_slots[i]=&new_animations[i];
 if(has_current)new_slots[4]=&new_animations[4];
 old_callback.initialized=live_callback.initialized=0;new_callback.initialized=callback;
 old_scripts.onmodelcopy_script=&old_callback;new_scripts.onmodelcopy_script=&new_callback;live_scripts.onmodelcopy_script=&live_callback;
 old_model.name="old";new_model.name="new";old_model.type=TYPE_PLAYER;new_model.type=enemy?TYPE_ENEMY:TYPE_PLAYER;
 old_model.animation=old_slots;new_model.animation=new_slots;old_model.animation_capacity=new_model.animation_capacity=8;
 old_model.scripts=&old_scripts;new_model.scripts=&new_scripts;new_model.model_flag=mask;
 old_model.speed=1.5f;old_model.runspeed=2.5f;old_model.runjumpheight=3;old_model.runjumpdist=4;old_model.runupdown=5;old_model.runhold=6;
 new_model.speed=kind?8:0;new_model.runspeed=kind?9:0;
 new_model.runjumpheight=new_model.runjumpdist=new_model.runupdown=new_model.runhold=11;
 old_model.icon.def=3;old_model.icon.pain=4;old_model.icon.get=5;old_model.icon.die=6;
 new_model.icon.def=new_model.icon.pain=new_model.icon.get=new_model.icon.die=kind?9:-1;
 old_model.shadow=old_model.knife=old_model.pshotno=old_model.bomb=old_model.star=old_model.flash=old_model.bflash=old_model.dust[0]=old_model.dust[1]=old_model.diesound=3;
 new_model.shadow=new_model.knife=new_model.pshotno=new_model.bomb=new_model.star=new_model.flash=new_model.bflash=new_model.dust[0]=new_model.dust[1]=new_model.diesound=kind?9:-1;
 old_model.weapon=old_weapons;old_model.numweapons=3;old_model.weapnum=7;
 new_model.weapon=kind?new_weapons:NULL;new_model.numweapons=2;new_model.weapnum=5;new_model.hasPlatforms=!kind;
 for(int i=0;i<5;++i){old_defense[i]=(s_defense){10+i,11+i};new_defense[i]=(s_defense){30+i,31+i};live_defense[i]=(s_defense){70+i,71+i};old_offense[i]=21+i;new_offense[i]=41+i;live_offense[i]=81+i;}
 old_model.defense=old_defense;new_model.defense=new_defense;old_model.offense_factors=old_offense;new_model.offense_factors=new_offense;
 live.model=&old_model;live.modeldata=old_model;live.animation=&old_animations[4];live.animnum=4;live.animpos=position;
 live.attacking=1;live.nextanim=777;live.map=2;live.exists=1;strcpy(live.name,"entity");live.scripts=&live_scripts;
 live.defense=live_defense;live.offense_factors=live_offense;model_cache[0].model=&new_model;
 time=elapsed?100:0;selectScreen=screen;numPlatforms=100;
 lookups=uninit_calls=colours=sets=frames=delays=clears=copies=callback_checks=callbacks=0;
}
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Model switch revision=%u case=%u line=%d\n",obor_profile_build,cases,__LINE__);abort();}}while(0)
static void check(int sync_api,int require_animation,int refresh,int schedule,int callback_api,int count_platforms) {
 for(int wrapper=0;wrapper<2;++wrapper)for(int flag=0;flag<2;++flag)
 for(int mask=0;mask<8;++mask)for(int has_current=0;has_current<2;++has_current)
 for(int fallback=0;fallback<8;++fallback)for(int kind=0;kind<2;++kind)
 for(int elapsed=0;elapsed<2;++elapsed)for(int screen=0;screen<2;++screen)
 for(int enemy=0;enemy<2;++enemy)for(int position=0;position<=2;position+=2) {
  ++cases;reset(mask,has_current,fallback,kind,elapsed,screen,enemy,position,1);
  int inherit=wrapper && !(mask&MODEL_NO_COPY),legacy_bypass=wrapper && !sync_api && !flag;
  s_anim *expected_current=has_current?&new_animations[4]:inherit?&old_animations[4]:NULL;
  int synced=sync_api && flag && (!require_animation || expected_current!=NULL);
  int chosen=4;
  if(!legacy_bypass && !synced) {
   int spawn=inherit || (fallback&1),respawn=inherit || (fallback&2),select=inherit || (fallback&4);
   if((!screen && !elapsed) || enemy)chosen=spawn?ANI_SPAWN:ANI_IDLE;
   else if(!screen && elapsed)chosen=respawn?ANI_RESPAWN:spawn?ANI_SPAWN:ANI_IDLE;
   else chosen=select?ANI_SELECT:ANI_IDLE;
   expected_current=(inherit && chosen>0 && !(fallback&(1<<(chosen-1))))?&old_animations[chosen]:&new_animations[chosen];
  }
  if(wrapper)set_model_ex(&live,"new",-1,&new_model,flag);
  else ent_set_model(&live,"new",flag);
  assert(live.model==&new_model && live.modeldata.name==new_model.name);
  assert(live.modeldata.type==(wrapper?TYPE_PLAYER:(enemy?TYPE_ENEMY:TYPE_PLAYER)));
  assert(live.animation==expected_current && live.animnum==chosen);
  int expected_pos=legacy_bypass || synced?position:0;
  if(synced && schedule && expected_pos>=expected_current->numframes)expected_pos=expected_current->numframes-1;
  assert(live.animpos==expected_pos);
  assert(live.attacking==((!synced && sync_api) || (wrapper && !sync_api && flag)?0:1));
  assert(uninit_calls==1 && colours==(wrapper?legacy_bypass?1:2:1));
  assert(sets==(!legacy_bypass && !synced));
  int expected_frames=legacy_bypass?0:synced?refresh:1;
  assert(frames==expected_frames && delays==(synced && schedule));
  int next=777;
  if(expected_frames && expected_current && expected_pos<expected_current->numframes)next=900+expected_pos;
  if(synced && schedule)next=time+20+expected_pos;
  assert(live.nextanim==next && numPlatforms==100+(count_platforms && new_model.hasPlatforms));
  assert(copies==wrapper && clears==(wrapper && (mask&MODEL_NO_SCRIPT_COPY)!=0));
  assert(callback_checks==(wrapper && callback_api?2:0) && callbacks==(wrapper && callback_api));
  for(int i=0;i<5;++i){int copied=wrapper && sync_api && i<3;assert(live_defense[i].marker==(copied?30:70)+i);assert(live_defense[i].factor==(copied?31:71)+i);assert(live_offense[i]==(copied?41:81)+i);}
  assert(new_model.speed==(inherit && !kind?1.5f:kind?8:0));
  assert(new_model.runspeed==(inherit && !kind?2.5f:kind?9:0));
  assert(new_model.runjumpheight==(inherit && !kind?3:11));
  assert(new_model.icon.def==(inherit && !kind?3:kind?9:-1));
  assert(new_model.icon.pain==(inherit && !kind?4:kind?9:-1));
  int weapon_copy=inherit && !(mask&MODEL_NO_WEAPON_COPY);
  assert(new_model.weapnum==(weapon_copy?7:5));
  assert(new_model.weapon==(kind?new_weapons:weapon_copy?old_weapons:NULL));
  assert(new_model.numweapons==(weapon_copy && !kind?3:2));
 }
 /* A wrapper targeting its current model returns before copying or callbacks. */
 ++cases;reset(0,1,7,1,1,0,0,2,1);set_model_ex(&live,"old",-1,&old_model,1);
 assert(live.model==&old_model && live.animation==&old_animations[4] && live.attacking==1 && live.animpos==2);
 assert(!uninit_calls && !colours && !copies && !callbacks && numPlatforms==100);
}
int main(void) {@CHECKS@assert(cases==@TOTAL@);return 0;}
'''
                for key, value in {'COUNTERS': counters, 'FUNCTIONS': functions,
                    'CHECKS': '\n'.join(checks), 'TOTAL': str(16385 * len(checks))}.items():
                    program = program.replace('@' + key + '@', value)
                program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4), program, flags=re.MULTILINE)
                native(program, extra_flags=('-Wno-unused-function', '-Wno-unused-variable',
                    '-Wno-error=misleading-indentation'))

    def test_campaign_and_selection_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-campaign-contracts.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(fixture['boundary_controls']) <= {r['revision'] for r in rows})
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(s['engine'] == profile['engine'] and s['first'] <= revision <= s['last']
                   for s in fixture['coverage']):
                self.assertIn(revision, {r['revision'] for r in rows})

        def expression(body, marker):
            start = body.index('(', body.index(marker))
            depth = 0
            for i in range(start, len(body)):
                depth += (body[i] == '(') - (body[i] == ')')
                if not depth:
                    return body[start + 1:i]
            raise AssertionError('Unclosed native condition: ' + marker)

        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text()
                game, level, select, status, update, order, main, scroll = (
                    function(source, n) for n in ('playgame', 'playlevel', 'selectplayer',
                        'updatestatus', 'update', 'load_levelorder', 'openborMain', 'update_scroller'))
                begin = game[game.index('memset(player,'):game.index('if((useSavedGame')]
                phase = level[level.index('kill_all();'):level.index('time = 0;')]
                finish = game[game.index('bonus += save->times_completed++;'):]
                finish = finish[:finish.index('\n\t\t}')]
                level_fade = next(line for line in level.splitlines() if 'fade_out(0, 0);' in line)
                skip_case = order.split('case CMD_LEVELORDER_SKIPSELECT:', 1)[1].split('break;', 1)[0]
                noselect = expression(select, 'if(obor_profile_build < 3698 ?' if 'if(obor_profile_build < 3698 ?' in select
                    else 'if(skipselect[0][0] || set->noselect)')
                if 'if(obor_profile_build < 3698)' in select:
                    start = select.index('if(obor_profile_build < 3698)')
                    name_copy = select[start:select.index('//else continue;', start)]
                else:
                    name_copy = 'strncpy(player[i].name, skipselect[i], MAX_NAME_LEN);'
                join = expression(status, 'if((player[i].playkeys')
                start = status.index('model = obor_profile_build < 3698 ?' if 'model = obor_profile_build < 3698 ?' in status
                    else 'model = skipselect[i][0]?')
                lookup = status[start:status.index(';', start) + 1]
                timer = expression(update, 'if(level->settime > 0')
                status_calls = '\n'.join(next(line for line in update.splitlines() if re.search(r'\b' + name + r'\(\);', line))
                    for name in ('updatestatus', 'predrawstatus', 'drawstatus'))
                scroller = expression(scroll, 'if(!findent(TYPE_ENDLEVEL)')
                quick = expression(game, 'if(obor_profile_build >= 3700 && useSave)' if 'if(obor_profile_build >= 3700 && useSave)' in game
                    else 'if(useSave)')
                start = main.index('if(obor_profile_build >= 3700) loadGameFile();') if 'if(obor_profile_build >= 3700) loadGameFile();' in main else main.index('loadGameFile();\n\t\t\tplaygame(')
                stop = main.index(';', main.index('playgame(', start)) + 1
                skip_start = main[start:stop]
                success = re.search(r'return [^;]+;\s*//4player', level)
                self.assertIsNotNone(success)
                success = success[0].split(';', 1)[0] + ';'
                checks = []
                for row in rows:
                    if row['engine'] != engine:
                        continue
                    self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                    phase_id = {'new_game': 0, 'nosave': 1, 'post_load': 2}[row['save_phase']]
                    flag_id = {'new_game': 0, 'nosave_else': 1, 'nosave_always': 2}[row['game_initial_flag']]
                    checks.append('obor_profile_build=%d;check(%d,%d,%d,%d,%d,%d,%d,%d);' % (
                        row['revision'], row['runtime_skipselect'], row['restore_flag_required'],
                        phase_id, flag_id, row['type2_status_gate'], row['fade_gate'],
                        row['completion_hof_gate'], row['quick_exit']))
                program = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_PLAYERS 4
#define MAX_NAME_LEN 31
#define FLAG_ANYBUTTON 4
#define TYPE_ITEM 1
#define TYPE_OBSTACLE 2
#define TYPE_ENDLEVEL 4
static unsigned obor_profile_build,cases;
static int obor_profile_new_game,nosave,nofadeout,useSave,skiptoset;
typedef struct {int lives,score,colourmap,weapnum,spawnhealth,spawnmp,playkeys;void *ent;char name[32];} s_player;
static s_player player[4];static char skipselect[4][32];
static struct {char *skipselect[4];int maxplayers,noselect,noshowhof;} set_record,*set=&set_record;
static struct {int flag,level,stage,pLives[4],pScores[4],pColourmap[4],pWeapnum[4],pSpawnhealth[4],pSpawnmp[4],credits,times_completed;char pName[4][32];} save_record,*save=&save_record;
static struct {int type,settime;} level_record,*level=&level_record;
static int current_level,current_stage,credits,bonus,level_override,freezeall,nojoin,presence,status_count;
static char trace[64],lookup_name[32];
static void event(char ch) {size_t n=strlen(trace);assert(n+1<sizeof(trace));trace[n]=ch;trace[n+1]=0;}
static int loadScriptFile(void) {event('R');return 1;}
static void reset_playable_list(int mode) {assert(mode==1);event('P');}
static void kill_all(void) {event('K');}
static void savelevelinfo(void) {event('I');}
static void saveGameFile(void) {event('G');}
static void saveHighScoreFile(void) {event('H');}
static void saveScriptFile(void) {event('S');}
static void load_level(char *filename) {assert(!strcmp(filename,"level"));event('L');nosave=level_override;}
static void fade_out(int a,int b) {assert(!a && !b);event('F');}
static void hallfame(int mode) {assert(mode==1);event('T');}
static void updatestatus(void) {++status_count;}
static void predrawstatus(void) {++status_count;}
static void drawstatus(void) {++status_count;}
static int findent(int mask) {return (presence&mask)!=0;}
typedef struct {int dummy;} Model;
static Model storage,*model;
static Model *findmodel(const char *name) {snprintf(lookup_name,sizeof(lookup_name),"%s",name);return &storage;}
static Model *nextplayermodel(void *unused) {assert(!unused);strcpy(lookup_name,"<next>");return &storage;}
static void begin_game(int useSavedGame) {int i;@BEGIN@}
static void phase(void) {char *filename="level";@PHASE@}
static void finish(void) {@FINISH@}
static void level_fade(void) {@FADE@}
static int select_without_file(void) {return (@NOSELECT@);}
static void copy_name(int i) {@COPY@}
static int join(int i) {return (@JOIN@);}
static void choose(int i) {@LOOKUP@(void)model;}
static int timer(void) {return (@TIMER@);}
static void statuses(void) {@STATUSES@}
static int scroller(void) {return (@SCROLLER@);}
static int campaign_exit_requested(void) {return (@QUICK@);}
static int level_success(int type) {@SUCCESS@}
static struct {int count;} arglist;
static char *arguments[5];
#define GET_ARG(i) arguments[i]
#define NAME(s) (s)
#define CHKDEF assert(set)
static void parse_skip(void) {int i;char *arg;switch(0){case 0:@SKIP_CASE@break;}}
static int restore_argument,start_loads;
static int loadGameFile(void) {++start_loads;return 1;}
static void playgame(int *players,int target,int restore) {(void)players;assert(target==skiptoset);restore_argument=restore;}
static void skip_start(void) {int players[4]={0};@SKIP_START@}
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Campaign revision=%u case=%u line=%d\n",obor_profile_build,cases,__LINE__);abort();}}while(0)
static void check(int runtime,int saved_flag,int save_phase,int initial_flag,int type2,int faded,int hof,int quick) {
 for(int restored=0;restored<2;++restored)for(int flag=0;flag<3;++flag)
 for(int new_before=0;new_before<2;++new_before)for(int nosave_before=0;nosave_before<2;++nosave_before)
 for(int kind=0;kind<3;++kind) {
  ++cases;memset(set,0,sizeof(*set));memset(save,0,sizeof(*save));set->maxplayers=4;
  for(int i=0;i<4;++i){set->skipselect[i]=kind==0?NULL:kind==1?"":"owner";strcpy(skipselect[i],"stale");save->pLives[i]=3+i;save->pScores[i]=101+i;save->pColourmap[i]=2+i;save->pWeapnum[i]=4+i;save->pSpawnhealth[i]=61+i;save->pSpawnmp[i]=21+i;snprintf(save->pName[i],32,"saved%d",i);}
  save->flag=flag;save->level=8;save->stage=9;save->credits=14;
  current_level=0;current_stage=1;credits=17;obor_profile_new_game=new_before;nosave=nosave_before;*trace=0;
  begin_game(restored);int loaded=restored && (!saved_flag || flag);
  assert(!strcmp(trace,loaded?(flag==2?"RP":"R"):""));
  assert(current_level==(loaded?8:0) && current_stage==(loaded?9:1) && credits==(loaded && flag==2?14:17));
  assert(obor_profile_new_game==(initial_flag==0 && !loaded?1:new_before));
  assert(nosave==(initial_flag==2 || (initial_flag==1 && !loaded)?1:nosave_before));
  for(int i=0;i<4;++i) {
   assert(!strcmp(skipselect[i],runtime?(kind==2?"owner":""):"stale"));
   assert(player[i].lives==(loaded && flag==2?3+i:0) && player[i].score==(loaded && flag==2?101+i:0));
   assert(player[i].colourmap==(loaded && flag==2?2+i:0) && player[i].weapnum==(loaded && flag==2?4+i:0));
   assert(player[i].spawnhealth==(loaded && flag==2?61+i:0) && player[i].spawnmp==(loaded && flag==2?21+i:0));
   assert(!strcmp(player[i].name,loaded && flag==2?save->pName[i]:""));
  }
 }
 for(int initial_new=0;initial_new<2;++initial_new)for(int initial_nosave=0;initial_nosave<2;++initial_nosave)
 for(level_override=0;level_override<2;++level_override) {
  obor_profile_new_game=initial_new;nosave=initial_nosave;
  for(int repeat=0;repeat<2;++repeat) {
   ++cases;int before=save_phase==0?obor_profile_new_game:nosave;*trace=0;phase();
   assert(!strcmp(trace,save_phase==2?(level_override?"KIL":"KILGHS"):(before?"KL":"KIGHSL")));
   assert(obor_profile_new_game==(save_phase==0?0:initial_new));
   assert(nosave==(save_phase==2?0:level_override));
  }
 }
 for(nofadeout=0;nofadeout<2;++nofadeout)for(set->noshowhof=0;set->noshowhof<2;++set->noshowhof) {
  ++cases;save->times_completed=3;bonus=7;*trace=0;finish();
  char wanted[16]="G";if(!faded || !nofadeout)strcat(wanted,"F");if(!hof || !set->noshowhof)strcat(wanted,"T");
  assert(!strcmp(trace,wanted) && bonus==10 && save->times_completed==4);
  *trace=0;level_fade();assert(!strcmp(trace,!faded || !nofadeout?"F":""));
 }
 const char *owners[]={NULL,"","owner"};
 for(int owner=0;owner<3;++owner)for(int cached=0;cached<2;++cached)
 for(int key=0;key<2;++key)for(freezeall=0;freezeall<2;++freezeall)for(nojoin=0;nojoin<2;++nojoin) {
  ++cases;for(int i=0;i<4;++i){set->skipselect[i]=(char*)owners[owner];strcpy(skipselect[i],cached?"cache":"");player[i].playkeys=key?FLAG_ANYBUTTON:0;strcpy(player[i].name,"prior");}
  int selected=runtime?cached:owner!=0;
  assert(join(0)==((key || selected) && !freezeall && !nojoin));
  *lookup_name=0;choose(0);assert(!strcmp(lookup_name,selected?(runtime?"cache":owners[owner]):"<next>"));
  for(set->noselect=0;set->noselect<2;++set->noselect)assert(select_without_file()==(runtime?(cached || set->noselect):owner!=0));
  for(int i=0;i<4;++i){copy_name(i);assert(!strcmp(player[i].name,runtime?(cached?"cache":""):owner?owners[owner]:"prior"));}
 }
 for(int count=1;count<4;++count)for(int before=0;before<2;++before) {
  ++cases;arglist.count=count;set->noselect=before;
  for(int i=0;i<5;++i)arguments[i]="";
  if(count>1)arguments[1]="alpha";
  if(count>2)arguments[2]="beta";
  for(int i=0;i<4;++i)set->skipselect[i]="prior";
  parse_skip();assert(set->noselect==(runtime && count==1?1:before));
  for(int i=0;i<4;++i)assert(!strcmp(set->skipselect[i],i+1<count?arguments[i+1]:"prior"));
 }
 for(level->type=-1;level->type<4;++level->type)for(level->settime=0;level->settime<2;++level->settime)
 for(int active=0;active<2;++active) {
  ++cases;for(int i=0;i<4;++i){player[i].ent=active?&storage:NULL;player[i].lives=active;}
  assert(timer()==(level->settime>0 || ((!type2 || level->type!=2) && !active)));
  status_count=0;statuses();assert(status_count==(!type2 || level->type!=2?3:0));
  assert(level_success(level->type)==((type2 && level->type==2) || active));
  for(presence=0;presence<8;++presence) {
   int expected=!(presence&TYPE_ENDLEVEL) && (type2?(!(presence&(TYPE_ITEM|TYPE_OBSTACLE)) && level->type==1) || level->type==0:
     (!(presence&(TYPE_ITEM|TYPE_OBSTACLE)) && level->type) || level->type!=1);
   assert(scroller()==expected);
  }
 }
 for(useSave=0;useSave<2;++useSave) {
  ++cases;assert(campaign_exit_requested()==(quick && useSave));skiptoset=7;start_loads=0;restore_argument=-1;skip_start();
  assert(start_loads==quick && restore_argument==(quick?useSave:0));
 }
}
int main(void) {@CHECKS@assert(cases==@TOTAL@);return 0;}
'''
                replacements = {'BEGIN': begin, 'PHASE': phase, 'FINISH': finish,
                    'FADE': level_fade, 'NOSELECT': noselect, 'COPY': name_copy, 'JOIN': join,
                    'LOOKUP': lookup, 'TIMER': timer, 'STATUSES': status_calls, 'SCROLLER': scroller,
                    'QUICK': quick, 'SUCCESS': success, 'SKIP_CASE': skip_case,
                    'SKIP_START': skip_start, 'CHECKS': '\n'.join(checks), 'TOTAL': str(168 * len(checks))}
                for key, value in replacements.items():
                    program = program.replace('@' + key + '@', value)
                program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4), program, flags=re.MULTILINE)
                native(program)

    def test_animation_script_append_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-animation-script-append.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(fixture['boundary_controls']) <= {r['revision'] for r in rows})
        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text()
                model = function(source, 'load_cached_model')
                case = model.split('case CMD_MODEL_AT_SCRIPT:', 1)[1].split('case CMD_MODEL_AT_CMD:', 1)[0]
                start = re.search(r'static const char(?:\*\s*|\s+)pre_text', model).start()
                constants = model[start:model.index('modelCommands cmd;', start)]
                init_start = model.index('sbsize = size+1;')
                init_end = model.index('scriptbuf = (char*)malloc(sbsize);', init_start) + len('scriptbuf = (char*)malloc(sbsize);')
                checks = []
                for row in rows:
                    if row['engine'] == engine:
                        self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                        self.assertRegex(row['script_case_sha256'], r'^[0-9a-f]{64}$')
                        checks.append('obor_profile_build=%d;check(%d);' % (row['revision'], row['character_copy']))
                program = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
static unsigned obor_profile_build,cases;
static int diagnostics;
int record_diagnostic(const char *format,...) {(void)format;++diagnostics;return 0;}
#define printf record_diagnostic
static void shutdown(int code,const char *format,...) {(void)code;(void)format;abort();}
#define starts_with(a,b) (!strncmp((a),(b),strlen(b)))
#define strclen(s) strlen(s)
@APPEND@
static char *scriptbuf,filename[]="model",namebuf[256],buf[128];
static size_t sbsize,scriptlen,len;
static ptrdiff_t pos;
static int script_id,ani_id;
static struct {int index;} animation={7},*newanim=&animation;
@CONSTANTS@
static void initialize(size_t size) {@INITIALIZER@assert(scriptbuf);*scriptbuf=0;scriptlen=0;}
static void generate(void) {switch(0){case 0:@CASE@}}
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Script append revision=%u case=%u line=%d\n",obor_profile_build,cases,__LINE__);abort();}}while(0)
static void check(int character_copy) {
 const char payloads[][8]={{'\n','A','\n'},{'\n','A',0,'B','\n'},{0}};
 const size_t lengths[]={3,5,0};
 const char *prefix="void main()\n{\n    int frame = getlocalvar(\"frame\");\n    int animhandle = getlocalvar(\"animhandle\");\n";
 const char *animation_prefix="    if(animhandle==7)\n    {\n";
 const char *animation_suffix="        return;\n    }\n";
 for(int animated=0;animated<2;++animated)for(int payload=0;payload<3;++payload) {
  ++cases;initialize(4096);assert(sbsize==(character_copy?8193:4097));
  diagnostics=0;script_id=-1;ani_id=animated?0:-1;
  const char *body=payload==0?"\nA\n":payload==1?(character_copy?"\nAB\n":"\nA"):"";
  for(int repeat=1;repeat<=2;++repeat) {
   ++cases;memset(buf,0,sizeof(buf));memcpy(buf,"prefix @script",14);
   memcpy(buf+14,payloads[payload],lengths[payload]);
   memcpy(buf+14+lengths[payload],"@end_script",12);pos=0;
   generate();char expected[1024];strcpy(expected,prefix);
   if(animated)strcat(expected,animation_prefix);
   for(int j=0;j<repeat;++j)strcat(expected,body);
   if(animated)strcat(expected,animation_suffix);
   strcat(expected,"\n}\n");
   assert(!strcmp(scriptbuf,expected) && scriptlen==strlen(expected));
   assert(pos==(ptrdiff_t)(14+lengths[payload]+11) && !diagnostics);
   assert(script_id==(animated?ani_id:-1));
  }
  free(scriptbuf);scriptbuf=NULL;
 }
}
int main(void) {@CHECKS@return 0;}
'''
                for key, value in {'APPEND': function(source, 'buffer_append'), 'CONSTANTS': constants,
                    'INITIALIZER': model[init_start:init_end], 'CASE': case, 'CHECKS': '\n'.join(checks)}.items():
                    program = program.replace('@' + key + '@', value)
                program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4), program, flags=re.MULTILINE)
                native(program, extra_flags=('-Wno-unused-const-variable', '-Wno-unused-variable'))

    def test_text_inclusion_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-text-inclusion-contracts.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(fixture['boundary_controls']) <= {r['revision'] for r in rows})
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(s['engine'] == profile['engine'] and s['first'] <= revision <= s['last']
                   for s in fixture['coverage']):
                self.assertIn(revision, {r['revision'] for r in rows})
        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text()
                dispatch = []
                for name in ('load_cached_model', 'load_level'):
                    body = function(source, name)
                    use = body.index('handle_txt_include(command')
                    start = body.rfind('if(command && command[0])', 0, use)
                    self.assertGreaterEqual(start, 0)
                    brace = body.index('{', start)
                    wrapper = function('void selected(void) ' + body[brace:], 'selected')
                    dispatch.append(body[start:brace] + wrapper[wrapper.index('{'):])
                checks = []
                for row in rows:
                    if row['engine'] != engine:
                        continue
                    self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                    checks.append('obor_profile_build=%d;check(%d,%d,%d);' % (
                        row['revision'], row['model_include'], row['level_include'], row['missing_file_fatal']))
                program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <setjmp.h>
#define stricmp strcasecmp
typedef struct {char *args[2];} ArgList;
#define GET_ARGP(N) (arglist->args[N])
#define GET_INT_ARGP(N) atoi(GET_ARGP(N))
static unsigned obor_profile_build,cases;
static char diagnostic[512];static jmp_buf stop;
static int loads,fatal;
static int record_diagnostic(const char *format,...) {
 va_list ap;va_start(ap,format);size_t n=strlen(diagnostic);
 int result=vsnprintf(diagnostic+n,sizeof(diagnostic)-n,format,ap);va_end(ap);
 assert(result>=0 && (size_t)result<sizeof(diagnostic)-n);return result;
}
#define printf record_diagnostic
static void shutdown(int code,const char *format,...) {
 assert(code==1);va_list ap;va_start(ap,format);
 vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);fatal=1;longjmp(stop,1);
}
static int buffer_pakfile(char *name,char **out,size_t *size) {
 ++loads;*out=NULL;*size=0;
 if(!strcmp(name,"missing"))return 0;
 assert(!strcmp(name,"child"));*size=strlen("inside\n");*out=malloc(*size+1);assert(*out);
 memcpy(*out,"inside\n",*size+1);return 1;
}
@HELPER@
static char *command,*filename,fnbuf[128],*buf;
static ArgList arglist;static ptrdiff_t pos;static size_t size;
static void model_dispatch(void) {@MODEL@}
static void level_dispatch(void) {@LEVEL@}
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Text inclusion revision=%u case=%u line=%d\n",obor_profile_build,cases,__LINE__);abort();}}while(0)
static void check(int model_support,int level_support,int missing_fatal) {
 const char *commands[]={"@include","@include","@jump","@end","@filename","unknown",""};
 const char *values[]={"child","missing","7","","other","",""};
 const char *initial="head\n@include child\n";
 for(int level=0;level<2;++level)for(int q=0;q<7;++q) {
  ++cases;size=strlen(initial);buf=malloc(size+1);assert(buf);memcpy(buf,initial,size+1);
  size_t initial_size=size;pos=5;filename="main";*fnbuf=0;*diagnostic=0;loads=fatal=0;
  command=(char*)commands[q];arglist.args[0]=command;arglist.args[1]=(char*)values[q];
  int support=level?level_support:model_support;
  if(!setjmp(stop)){if(level)level_dispatch();else model_dispatch();}
  assert(fatal==(support && q==1 && missing_fatal));
  assert(loads==(support && q<2));
  if(fatal)assert(!strcmp(diagnostic,"Can't find file 'missing' to include.\n"));
  else if(*command && (!support || q==1 || q==5)) {
   char wanted[256];
   if(support)snprintf(wanted,sizeof(wanted),"Command '%s' not understood in file 'main'!\n",command);
   else if(level)snprintf(wanted,sizeof(wanted),"Command '%s' not understood!",command);
   else snprintf(wanted,sizeof(wanted),"Command '%s' not understood in file 'main'!",command);
   assert(!strcmp(wanted,diagnostic));
  } else assert(!*diagnostic);
  if(support && q==0) {
   const char *expected="head\n#include child\r\n@end\r\n@filename child\r\ninside\n\r\n@filename main\r\n@jump 5\r\n";
   assert(!strcmp(buf,expected) && size==strlen(expected) && pos==(ptrdiff_t)(initial_size+6));
  } else {
   assert(!strcmp(buf,initial) && size==initial_size);
   assert(pos==(support && q==2?7:support && q==3?(ptrdiff_t)size:5));
  }
  assert(!strcmp(filename,support && q==4?"other":"main"));
  free(buf);buf=NULL;
 }
}
int main(void) {@CHECKS@return 0;}
'''
                for key, value in {'HELPER': function(source, 'handle_txt_include'),
                    'MODEL': dispatch[0], 'LEVEL': dispatch[1], 'CHECKS': '\n'.join(checks)}.items():
                    program = program.replace('@' + key + '@', value)
                program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4), program, flags=re.MULTILINE)
                native(program, extra_flags=('-Wno-unused-variable', '-Wno-unused-parameter'))

    def test_own_system_property_domains_and_native_effects(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-system-property-contracts.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(s['engine'] == profile['engine'] and s['first'] <= revision <= s['last']
                   for s in fixture['coverage']):
                self.assertIn(revision, {r['revision'] for r in rows})
        fields = ('current_stage', 'current_set', 'current_level', 'nofadeout',
                  'nopause', 'nosave', 'noscreenshot', 'skiptoset', 'useSave',
                  'blockade', 'shadowalpha', 'shadowcolor', 'scrollminz',
                  'scrollmaxz', 'scrollminx', 'scrollmaxx', 'slowmotion[0]', 'slowmotion[1]')
        query_fields = {'usesave': 'useSave', 'slowmotion': 'slowmotion[0]',
                        'slowmotion_duration': 'slowmotion[1]'}
        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                root = ROOT / 'src/engines' / engine
                script = (root / 'openborscript.c').read_text()
                main = (root / 'openbor.c').read_text()
                header = (root / 'openborscript.h').read_text()
                variants = (root / 'source/scriptlib/ScriptVariant.c').read_text()
                variant_header = (root / 'source/scriptlib/ScriptVariant.h').read_text()
                records = []
                for tag, alias in (('enum VariantType', 'VARTYPE'), ('struct ScriptVariant', 'ScriptVariant')):
                    start = variant_header.index('typedef ' + tag)
                    end = re.search(r'\}\s*' + alias + r'\s*;', variant_header[start:])
                    self.assertIsNotNone(end)
                    records.append(variant_header[start:start + end.end()])
                start = header.index('enum systemvariant_enum')
                enum = header[start:header.index('};', start) + 2]
                start = script.index('static const char* svlist[]')
                names = script[start:script.index('};', start) + 2]
                start = script.index('#define MAPSTRINGS(')
                macro = script[start:script.index('\n\n', start)]
                methods = '\n'.join(function(script, n) for n in (
                    'obor_systemvariant_available', 'obor_systemvariant_native',
                    'mapstrings_systemvariant', 'openbor_systemvariant', 'openbor_changesystemvariant'))
                converters = '\n'.join(function(variants, n) for n in (
                    'ScriptVariant_ChangeType', 'ScriptVariant_Clear',
                    'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue'))
                callbacks = '\n'.join(function(main, n) for n in (
                    'getsyspropertybyindex', 'changesyspropertybyindex'))
                contexts, definitions = [], []
                for row in rows:
                    if row['engine'] != engine:
                        continue
                    self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                    tag = 'profile_' + str(row['revision'])
                    definitions.append('static const char *%s[]={%s};' % (
                        tag, ','.join(json.dumps(n) for n in row['names'])))
                    contexts.append('obor_profile_build=%d;domains(%s,%d);' % (
                        row['revision'], tag, len(row['names'])))
                    for name in sorted(set(row['getters']) | set(row['setters'])):
                        if name not in row['names']:
                            continue
                        get = row['getters'].get(name)
                        put = row['setters'].get(name)
                        key = query_fields.get(name, name)
                        index = fields.index(key) if key in fields else -1
                        target = fields.index(put['target']) if put else -1
                        narrow = put is not None and put['cast'] == 'unsigned char'
                        contexts.append('effect(%s,%d,%d,%d,%d,%d);' % (
                            json.dumps(name), bool(get), index, get is not None and get['kind'] == 'decimal',
                            target, narrow))
                read_fields = '\n'.join('case %d:return %s;' % (i, name) for i, name in enumerate(fields))
                initializers = '\n'.join('%s=%d;' % (name, 201 + i) for i, name in enumerate(fields))
                program = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
typedef int32_t LONG;typedef double DOUBLE;typedef void VOID;typedef int HRESULT;
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
#define stricmp strcasecmp
@RECORDS@
static unsigned obor_profile_build,cases;
static char cache[4][256],diagnostic[512];static int collects;
static char *StrCache_Get(int index) {assert(index>=0 && index<4);return cache[index];}
static int StrCache_Pop(void) {return 0;}
static void StrCache_Collect(int index) {assert(index>=0 && index<4);++collects;}
@CONVERTERS@
static int record_diagnostic(const char *format,...) {
 va_list ap;va_start(ap,format);size_t n=strlen(diagnostic);
 int result=vsnprintf(diagnostic+n,sizeof(diagnostic)-n,format,ap);va_end(ap);
 assert(result>=0 && (size_t)result<sizeof(diagnostic)-n);return result;
}
#define printf record_diagnostic
@ENUM@
@NAMES@
@SEARCH@
@MACRO@
typedef struct {int unused;} entity;
static entity player[4],*self,*smartbomber,*textbox;
static struct {int width,numpalettes,pos,waiting;} level_record,*level=&level_record;
static struct {int effectvol,musicvol,soundvol;} savedata;
static struct {int hRes,vRes;} videomodes;
static struct {int maxplayers;struct {char *branchname;} levelorder[1];} levelsets[1];
static int ent_count,ent_max,gameOver,selectScreen,titleScreen,hallOfFame,showComplete,menuScreen;
static int optionsMenu,systemoptionsMenu,cheatoptionsMenu,controloptionsMenu,soundoptionsMenu;
static int videooptionsMenu,startgameMenu,newgameMenu,loadgameMenu;
static int time,pause,gfx_x_offset,gfx_y_offset,gfx_y_offset_adj,lasthitc,lasthitt;
static int current_set,current_level,current_palette,current_stage,panel_height;
static int max_entity_vars,max_global_vars,max_indexed_vars,max_script_vars,models_cached,models_loaded;
static int nofadeout,nojoin,nopause,nosave,noscreenshot,pixelformat,shadowalpha,shadowcolor,skiptoset,useSave;
static int viewportx,viewporty,viewportw,viewporth,max_attack_types,max_animations,sample_play_id;
static float lasthita,lasthitx,lasthitz,advancex,advancey,blockade,scrollminz,scrollmaxz,scrollminx,scrollmaxx;
static int light[2];static char *currentScene,*branch_name;static void *background,*vscreen;
static @SLOWTYPE@ slowmotion[2];
#define TYPE_ENEMY 1
#define TYPE_PLAYER 2
#define TYPE_NPC 3
#define GAME_SPEED 200
#define PLAYER_MAX_Z 240
#define PLAYER_MIN_Z 160
#define KBYTES 1
#define MAX_STR_VAR_LEN 255
static int count_ents(int kind) {return kind+10;}
static int getSystemRam(int unit) {return unit+20;}
static int getFreeRam(int unit) {return unit+30;}
static int getUsedRam(int unit) {return unit+40;}
static int timer_gettick(void) {return 991;}
static void getPakName(char *out,int size,int index) {(void)index;snprintf(out,size,"test");}
@CALLBACKS@
@METHODS@
static double field(int index) {switch(index){@READ_FIELDS@default:abort();}}
static ScriptVariant integer(int number) {ScriptVariant v={0};v.vt=VT_INTEGER;v.lVal=number;return v;}
static ScriptVariant text(const char *name) {ScriptVariant v={0};v.vt=VT_STR;v.strVal=1;snprintf(cache[1],256,"%s",name);return v;}
static void reset(void) {
 @INITIALIZERS@
 current_set=current_level=0;levelsets[0].levelorder[0].branchname="branch";
 *diagnostic=0;collects=0;
}
static int physical(const char *name) {
 for(int i=0;i<_sv_the_end;++i)if(!strcmp(svlist[i],name))return i;
 return _sv_the_end;
}
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"System property revision=%u case=%u line=%d\n",obor_profile_build,cases,__LINE__);abort();}}while(0)
static void domains(const char **names,int count) {
 assert(sizeof(svlist)/sizeof(*svlist)==_sv_the_end);
 for(int i=0;i<_sv_the_end;++i) {
  ++cases;reset();int logical=-1;
  for(int j=0;j<count;++j)if(!strcmp(names[j],svlist[i]))logical=j;
  assert(obor_systemvariant_available(i)==(logical>=0));
  ScriptVariant a=text(svlist[i]),*v[]={&a};mapstrings_systemvariant(v,1);
  assert(a.vt==(logical<0?VT_STR:VT_INTEGER));
  assert(collects==(logical>=0));
  if(logical>=0){assert(a.lVal==logical && obor_systemvariant_native(logical)==i && !*diagnostic);}
  else {char wanted[256];snprintf(wanted,sizeof(wanted),"openborvariant: System variable name not found: '%s'\n",svlist[i]);assert(!strcmp(wanted,diagnostic));}
 }
 assert(obor_systemvariant_native(-1)==_sv_the_end && obor_systemvariant_native(count)==_sv_the_end);
 assert(obor_systemvariant_native(INT_MAX)==_sv_the_end);
}
static void effect(const char *name,int readable,int field_id,int decimal,int target,int narrow) {
 for(int numeric=0;numeric<2;++numeric) {
  ++cases;reset();double before[18];for(int i=0;i<18;++i)before[i]=field(i);
  ScriptVariant a=text(name),result=integer(911),*out=&result,*args[]={&a};
  if(numeric)mapstrings_systemvariant(args,1);
  assert(a.vt==VT_STR || obor_systemvariant_native(a.lVal)==physical(name));
  assert(openbor_systemvariant(args,&out,1)==(readable?S_OK:E_FAIL));
  assert(out==(readable?&result:NULL));
  assert(a.vt==VT_INTEGER && collects==1);
  if(readable) {
   if(!strcmp(name,"current_branch")){assert(result.vt==VT_STR && !strcmp(StrCache_Get(result.strVal),"branch"));}
   else {double expected=field_id>=0?before[field_id]:991;assert(result.vt==(decimal?VT_DECIMAL:VT_INTEGER));assert((decimal?result.dblVal:result.lVal)==expected);}
   assert(!*diagnostic);
  } else assert(result.vt==VT_EMPTY && !strcmp(diagnostic,"Unknown system property name.\n"));
  for(int i=0;i<18;++i)assert(field(i)==before[i]);
  for(int value_type=0;value_type<3;++value_type) {
   ++cases;reset();for(int i=0;i<18;++i)before[i]=field(i);
   a=text(name);ScriptVariant value=integer(300);result=integer(911);out=&result;
   if(value_type==1){value.vt=VT_DECIMAL;value.dblVal=300.75;}
   if(value_type==2){value.vt=VT_STR;value.strVal=2;strcpy(cache[2],"unconverted");}
   ScriptVariant *put[]={&a,&value};if(numeric)mapstrings_systemvariant(put,2);
   assert(openbor_changesystemvariant(put,&out,2)==(target>=0?S_OK:E_FAIL));
   assert(out==(target>=0?&result:NULL) && result.vt==VT_INTEGER && result.lVal==911);
   assert(a.vt==VT_INTEGER && collects==1 && !*diagnostic);
   for(int i=0;i<18;++i)assert(field(i)==(i==target && value_type<2?(narrow?44:300):before[i]));
  }
 }
}
@DEFINITIONS@
int main(void) {@CONTEXTS@return 0;}
'''
                replacements = {'RECORDS': '\n'.join(records), 'CONVERTERS': converters,
                    'ENUM': enum, 'NAMES': names, 'MACRO': macro,
                    'SEARCH': function((root / 'source/utils.c').read_text(), 'searchList'),
                    'CALLBACKS': callbacks, 'METHODS': methods, 'READ_FIELDS': read_fields,
                    'INITIALIZERS': initializers, 'DEFINITIONS': '\n'.join(definitions),
                    'CONTEXTS': '\n'.join(contexts), 'SLOWTYPE': 'unsigned char' if engine == '3741' else 'unsigned'}
                for key, value in replacements.items():
                    program = program.replace('@' + key + '@', value)
                program = re.sub(r'^[ \t]+', lambda m: m.group(0).expandtabs(4), program, flags=re.MULTILINE)
                native(program, extra_flags=('-Wno-unused-variable', '-Wno-unused-function',
                    '-Wno-unused-parameter', '-Wno-implicit-fallthrough'))

    def test_system_property_numeric_and_text_domains(self):
        source = (ENGINE / 'openborscript.c').read_text()
        header = (ENGINE / 'openborscript.h').read_text()
        start = header.index('enum systemvariant_enum')
        enum = header[start:header.index('};', start)+2]
        start = source.index('static const char* svlist[]')
        names = source[start:source.index('};', start)+2]
        methods = '\n'.join(function(source, name) for name in (
            'obor_systemvariant_available', 'obor_systemvariant_native',
            'mapstrings_systemvariant', 'openbor_systemvariant', 'openbor_changesystemvariant'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>
typedef long LONG;
typedef int HRESULT;
#define S_OK 0
#define E_FAIL (-1)
enum { VT_EMPTY,VT_INTEGER,VT_STR };
typedef struct { int vt; LONG lVal; const char *strVal; } ScriptVariant;
static uint32_t obor_profile_build;
static int read_index,write_index;
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) { memset(v,0,sizeof(*v));v->vt=type; }
static void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
#define MAPSTRINGS(VAR,LIST,COUNT,MESSAGE) do { \
 if((VAR)->vt==VT_STR) {for(prop=0;prop<(COUNT);prop++) \
 if(!strcmp((VAR)->strVal,(LIST)[prop])) break; \
 if(prop<(COUNT)) {ScriptVariant_ChangeType(VAR,VT_INTEGER);(VAR)->lVal=prop;} } \
 (void)propname; } while(0)
ENUM
NAMES
static int getsyspropertybyindex(ScriptVariant *v,int index) { read_index=index;v->vt=VT_INTEGER;v->lVal=index;return index>=0 && index<_sv_the_end; }
static int changesyspropertybyindex(int index,ScriptVariant *v) { assert(v->lVal==123);write_index=index;return index>=0 && index<_sv_the_end; }
METHODS
int main(void) {
    assert(sizeof(svlist)/sizeof(*svlist)==_sv_the_end);
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;int logical=0;
        for(int physical=0;physical<_sv_the_end;++physical) {
            int absent=(profile<3783 && (!strcmp(svlist[physical],"scrollmaxx") || !strcmp(svlist[physical],"scrollminx"))) ||
                       (profile<3838 && !strcmp(svlist[physical],"sample_play_id"));
            ScriptVariant arg={VT_STR,0,svlist[physical]},value={VT_INTEGER,123,0},result={0},*out=&result,*args[]={&arg,&value};
            assert(openbor_systemvariant(args,&out,1)==(absent?E_FAIL:S_OK));
            if(absent) { assert(!out);continue; }
            assert(arg.vt==VT_INTEGER && arg.lVal==logical && out==&result && read_index==physical);
            arg=(ScriptVariant){VT_INTEGER,logical,0};out=&result;
            assert(openbor_systemvariant(args,&out,1)==S_OK && read_index==physical);
            arg=(ScriptVariant){VT_STR,0,svlist[physical]};out=&result;
            assert(openbor_changesystemvariant(args,&out,2)==S_OK && write_index==physical && arg.lVal==logical);
            arg=(ScriptVariant){VT_INTEGER,logical,0};out=&result;
            assert(openbor_changesystemvariant(args,&out,2)==S_OK && write_index==physical);
            ++logical;
        }
        for(int index=logical;index<=_sv_the_end;++index) {
            ScriptVariant arg={VT_INTEGER,index,0},result={0},*out=&result,*args[]={&arg};
            assert(openbor_systemvariant(args,&out,1)==E_FAIL && !out);
        }
        assert(obor_systemvariant_native(-1)==_sv_the_end && obor_systemvariant_native(INT_MAX)==_sv_the_end);
    }
}
'''.replace('ENUM', enum).replace('NAMES', names).replace('METHODS', methods))

    def test_entity_weapon_block_orbit_and_sleep_boundaries(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-entity-state-boundaries.json')
        extra = []
        for row in fixture['sources']:
            self.assertEqual(row['engine'], '3842')
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']), {'ent_default_init', 'ent_set_anim',
                'update_animation', 'set_idle', 'set_weapon', 'common_idle_anim'})
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            extra.append(row['revision'])
        boundary = fixture.get('_contract_boundaries')
        required = ({revision for engine, revision in boundary['profiles'] if engine == '3842'}
                    if boundary is not None else {3761, 3769, 3773})
        self.assertEqual(set(extra), required)
        profiles = sorted(set(extra) | set(range(3780, 3843)))
        source = (ENGINE / 'openbor.c').read_text()
        methods = '\n'.join(function(source, name) for name in (
            'obor_apply_weapon_model', 'set_weapon', 'set_idle', 'common_block'))
        idle = function(source, 'common_idle_anim')
        start = idle.index('if(obor_profile_build >= 3819 && self->idling)')
        idle_bit = idle[start:idle.index(';', start)+1]
        start = idle.index('else if(validanim(ent,ANI_SLEEP)')
        sleep_check = idle[start:idle.index('{', start)].replace('else if', 'if', 1)
        animate = function(source, 'ent_set_anim')
        start = animate.index('if(obor_profile_build < 3819 && aninum != ANI_SLEEP)')
        animation_time = animate[start:animate.index(';', start)+1]
        update = function(source, 'update_animation')
        start = update.index('if((obor_profile_build >= 3819')
        frame_time = update[start:update.index(';', start)+1]
        wander = function(source, 'common_try_wander')
        start = wander.index('mod = ')
        orbit = wander[start:wander.index('if(dox)', start)]
        initialize = function(source, 'ent_default_init')
        start = initialize.index('if( validanim(e,ANI_SPAWN))')
        spawn_animation = initialize[start:initialize.index('//else set_idle(e);', start)]
        start = initialize.index('if(validanim(e,ANI_SPAWN)', initialize.index('SUBTYPE_NOTGRAB'))
        spawn_action = initialize[start:initialize.index('else', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t obor_profile_build;
enum { TYPE_PLAYER=1,ANI_SLEEP=2,ANI_BLOCK=3,FLAG_SPECIAL=4,ANI_SPAWN=4,ANI_RESPAWN=5,MAX_PLAYERS=1 };
typedef struct entity { struct { int type,weaploss[2],numweapons,*weapon,sleepwait,aggression,holdblock; float speed; } modeldata;
    struct entity *defaultmodel; int playerindex,idling,attacking,inpain,jumping,blocking,animating,
    sleeptime,animnum,sortid,health,pathblocked; void (*takeaction)(void);
} entity;
static entity object,*self=&object;
static struct { int weapnum,keys; } player[1];
static struct { int setweap; } room={2},*level=&room;
static struct { int hRes; } videomodes={320};
static int time=100,model_calls,idle_calls,animation_calls,seen_idle,last_animation,has_spawn,has_respawn;
static int validanim(entity *e,int anim) { assert(e==self);return anim==ANI_SPAWN?has_spawn:(anim==ANI_RESPAWN?has_respawn:1); }
static int common_idle_anim(entity *ent) { assert(ent==self);seen_idle=ent->idling;++idle_calls; IDLE_BIT return 1; }
static void ent_set_anim(entity *ent,int anim,int reset) { assert(ent==self && reset==0);last_animation=anim;++animation_calls; }
static void set_model_ex(entity *ent,char *name,int index,entity *model,int flag) {
    (void)name;(void)index;(void)model;(void)flag;assert(ent==self);++model_calls;ent->modeldata.weaploss[0]=0;
}
METHODS
static void animation_time(entity *ent,int aninum) { ANIMATION_TIME }
static void frame_time(void) { FRAME_TIME }
static int can_sleep(entity *ent) { SLEEP_CHECK { return 1; } return 0; }
static int orbit(void) { int mod; ORBIT return mod; }
static void common_spawn(void) { }
static void initial_spawn(entity *e) { SPAWN_ANIMATION }
static void initial_spawn_action(entity *e) { SPAWN_ACTION }
int main(void) {
    const unsigned profiles[]={PROFILES};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        unsigned profile=profiles[p];
        obor_profile_build=profile;memset(&object,0,sizeof(object));
        object.modeldata.type=TYPE_PLAYER;object.modeldata.weaploss[0]=3;
        player[0].weapnum=99;model_calls=0;
        set_weapon(&object,7,0);assert(model_calls==1 && player[0].weapnum==(profile<3793?2:7));
        object.idling=0;idle_calls=0;set_idle(&object);
        assert(idle_calls==1 && seen_idle==(profile<3819?0:1));
        assert(object.idling==(profile<3819?1:3));
        object.modeldata.sleepwait=5;object.sleeptime=7;animation_time(&object,ANI_BLOCK);
        assert(object.sleeptime==(profile<3819?105:7));
        object.sleeptime=7;animation_time(&object,ANI_SLEEP);assert(object.sleeptime==7);
        for(int idling=0;idling<=3;++idling)for(int sleep=0;sleep<=1;++sleep) {
            object.idling=idling;object.animnum=sleep?ANI_SLEEP:ANI_BLOCK;object.animating=0;object.sleeptime=7;
            frame_time();
            int changed=profile<3819?0:(profile<3824?(!sleep&&(idling&2)):(!(idling&2)||sleep));
            assert(object.sleeptime==(changed?105:7));
        }
        object.sleeptime=time;object.animating=0;
        assert(can_sleep(&object)==(profile==3824));
        object.animating=1;assert(can_sleep(&object)==(profile<3825));
        object.sleeptime=time-1;object.animating=0;assert(can_sleep(&object)==(profile>=3824));
        object.modeldata.speed=2;
        for(int id=-200;id<=200;id+=100)for(int health=-9;health<=9;++health) {
            object.sortid=id;object.health=health;
            int expected=((int)(time/(320/2.0f))+id/100+health/3)%4;
            if(profile>=3801) { if(expected<0)expected=-expected;if((id/100)%2)expected=3-expected; }
            assert(orbit()==expected);
        }
        object.inpain=1;object.animating=0;object.blocking=1;object.modeldata.type=TYPE_PLAYER;
        object.modeldata.holdblock=2;
        player[0].keys=FLAG_SPECIAL;idle_calls=animation_calls=0;common_block();
        if(profile>=3834)assert(animation_calls==1 && object.inpain==0);
        else if(profile==3798 || profile>=3801)assert(animation_calls==0 && idle_calls==0 && object.inpain==1);
        else assert(animation_calls==0 && idle_calls==1);
        for(has_spawn=0;has_spawn<=1;++has_spawn)for(has_respawn=0;has_respawn<=1;++has_respawn) {
            animation_calls=0;initial_spawn(&object);
            int available=has_spawn || (profile>=3787 && has_respawn);
            assert(animation_calls==available);
            if(available)assert(last_animation==(has_spawn?ANI_SPAWN:ANI_RESPAWN));
            object.takeaction=NULL;initial_spawn_action(&object);
            assert(object.takeaction==(available?common_spawn:NULL));
        }
    }
}
'''.replace('METHODS', methods).replace('IDLE_BIT', idle_bit)
           .replace('ANIMATION_TIME', animation_time).replace('FRAME_TIME', frame_time)
           .replace('SLEEP_CHECK', sleep_check).replace('ORBIT', orbit)
           .replace('SPAWN_ANIMATION', spawn_animation).replace('SPAWN_ACTION', spawn_action)
           .replace('PROFILES', ','.join(map(str, profiles))))

    def test_level_shadow_color_and_saved_model_loading_boundaries(self):
        from test_historical_save_bonus import saved_bonus_model_rows
        profiles = [row['revision'] for row in saved_bonus_model_rows()]
        source = (ENGINE / 'openbor.c').read_text()
        start = source.index('case CMD_LEVEL_SHADOWCOLOR:')
        color = source[start:source.index('case CMD_LEVEL_SHADOWALPHA:', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t obor_profile_build;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"saved model profile=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
enum { VT_EMPTY,VT_PTR };
typedef struct { int vt; } ScriptVariant;
static struct { void *owner; const char *key; ScriptVariant value; } *global_var_list[1];
static ScriptVariant indexed_var_list[1];
static int max_global_var_index=-1,max_indexed_vars,current_set,models_cached=3;
typedef struct { int unload; } model;
static struct { const char *name; int selectable; model *model; } model_cache[3];
static char probe_prefix[256],probe_file[256]="state.s00";
static void getBasePath(char *out,const char *kind,int n) { assert(!strcmp(kind,"Saves") && n==0);strcpy(out,probe_prefix); }
static void getPakName(char *out,size_t capacity,int n) { assert(n==2 && capacity>10);strcpy(out,"state.s00"); }
static int obor_pak_path_append(char *out,size_t capacity,const char *name) { assert(strlen(out)+strlen(name)<capacity);strcat(out,name);return 1; }
static void borExit(int code) { (void)code;assert(0); }
static void vardump(ScriptVariant *v,char *out) { (void)v;(void)out;assert(0); }
METHOD
static int parsed;
static const char *argument;
static int parsecolor(const char *text) { ++parsed;return strchr(text,'_')?0x123456:atoi(text)+1000; }
#define GET_ARG(n) (argument)
#define GET_INT_ARG(n) (atoi(argument))
enum { CMD_LEVEL_SHADOWCOLOR };
static int color(void) {
    struct { int shadowcolor; } next;
    switch(CMD_LEVEL_SHADOWCOLOR) { COLOR_BODY }
    return next.shadowcolor;
}
int main(void) {
    if(getenv("ANYBOR_NATIVE_ARTIFACTS")) {
        const char *scratch=getenv("TMPDIR");assert(scratch);
        int n=snprintf(probe_prefix,sizeof(probe_prefix),"%s/",scratch);
        assert(n>0 && (size_t)n<sizeof(probe_prefix));
        n=snprintf(probe_file,sizeof(probe_file),"%sstate.s00",probe_prefix);
        assert(n>0 && (size_t)n<sizeof(probe_file));
    }
    unsigned cases=0;
    model loaded={3};
    model_cache[0].name="first";model_cache[0].selectable=1;model_cache[0].model=&loaded;
    model_cache[1].name="cached";model_cache[1].model=NULL;
    model_cache[2].name="third";model_cache[2].model=&loaded;
    const unsigned profiles[]={@PROFILES@};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        unsigned profile=profiles[p];
        obor_profile_build=profile;
        parsed=0;argument="17";assert(color()==(profile<3819?17:1017));
        argument="12_34_56";assert(color()==(profile<3819?12:0x123456));
        assert(parsed==(profile<3819?0:2));
        assert(saveScriptFile()==1);
        FILE *file=fopen(probe_file,"rb");assert(file);char text[1024]={0};
        assert(fread(text,1,sizeof(text)-1,file)>0);fclose(file);
        assert((strstr(text,"changemodelproperty(\"first\",4,1);")!=NULL)==(profile>=3822));
        assert((strstr(text,"loadmodel(\"first\",3,1);")!=NULL)==(profile>=3822 && profile<3835));
        assert((strstr(text,"loadmodel(\"third\",3,0);")!=NULL)==(profile>=3822 && profile<3835));
        assert(strstr(text,"loadmodel(\"cached\"")==NULL);
        ++cases;
    }
    assert(remove(probe_file)==0);
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);
}
'''.replace('METHOD', function(source, 'saveScriptFile')).replace('COLOR_BODY', color)
           .replace('@PROFILES@', ','.join(map(str, profiles))))

    def test_dynamic_animation_ids_and_initial_attack_slots(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        constants = header[header.index('#define\t\tATK_NORMAL\t'):header.index('#define     MAX_DOTS')]
        helpers = '\n'.join(function(source, n) for n in ('obor_attack_base', 'obor_attack_special'))
        build = function(source, 'obor_build_model_constants')
        start = build.index('memcpy(animpains,')
        initialization = build[start:build.rindex('}')]
        script = (ENGINE / 'openborscript.c').read_text()
        start = script.index('#define ICMPSCONSTB(')
        macro = script[start:script.index('void mapstrings_transconst(', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
static uint32_t obor_profile_build;
CONSTANTS
HELPERS
#define strnicmp strncasecmp
typedef long LONG;
MACRO
static int pains[20],falls[20],rises[20],riseattacks[20],blkpains[20],deaths[20];
static int *animpains,*animfalls,*animrises,*animriseattacks,*animblkpains,*animdies;
static int max_attack_types,maxanim;
static void initialize(void) { int i; INITIALIZATION }
static int lookup(const char *constname) {
    struct { LONG lVal; } v={0};
    if(0) { }
    ICMPSCONSTB(ANI_PAIN,animpains)
    return (int)v.lVal;
}
int main(void) {
    for(int i=0;i<20;++i) pains[i]=falls[i]=rises[i]=riseattacks[i]=blkpains[i]=deaths[i]=100+i;
    const unsigned profiles[]={PROFILES};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        unsigned profile=profiles[p];
        obor_profile_build=profile;max_attack_types=OBOR_ATTACK_BASE+2;maxanim=500;
        int **tables[]={&animpains,&animfalls,&animrises,&animriseattacks,&animblkpains,&animdies};
        for(unsigned i=0;i<6;++i) { *tables[i]=calloc(max_attack_types+1,sizeof(int));assert(*tables[i]);(*tables[i])[max_attack_types]=12345; }
        initialize();assert(maxanim==512);
        for(unsigned i=0;i<6;++i) {
            assert((*tables[i])[14]==114);
            for(int slot=15;slot<OBOR_ATTACK_BASE;++slot)
                assert((*tables[i])[slot]==(profile<3831?0:100+slot));
            assert((*tables[i])[OBOR_ATTACK_BASE]==500+(int)i*2);
            assert((*tables[i])[max_attack_types]==12345);
        }
        assert(lookup("ANI_PAIN11")==((profile<3826 || profile==3830)?0:500));
        assert(lookup("ANI_PAIN12")==((profile<3826 || profile==3830)?0:501));
        for(unsigned i=0;i<6;++i)free(*tables[i]);
    }
}
'''.replace('CONSTANTS', constants).replace('HELPERS', helpers)
           .replace('MACRO', macro).replace('INITIALIZATION', initialization).replace('PROFILES', ','.join(map(str, attack_domain_revisions()))))

    def test_environment_damage_keeps_the_selected_type_and_health_contract(self):
        source = (ENGINE / 'openbor.c').read_text()
        start = source.index('if(self->damage_on_landing > 0 && !self->dead)')
        landing = source[start:source.index('// in case landing, set hithead', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum { ATK_LAND=16,ATK_PIT,ATK_LIFESPAN,ATK_TIMEOVER, TYPE_PLAYER=1,
    SCROLL_UP=2,SCROLL_DOWN=4,DEFAULT_OFFSCREEN_KILL=1000,COUNTER_SPEED=400,GAME_SPEED=200 };
#define PIT_DEPTH (-10)
typedef struct { int attack_type,attack_force; float dropv[3]; } s_attack;
typedef struct entity { float x,z,a,lifespancountdown; int health,damage_on_landing,damagetype,dead;
    struct { int offscreenkill,type; } modeldata;
    struct { float factor; } defense[20];
    void (*takedamage)(struct entity *,s_attack *);
} entity;
static uint32_t obor_profile_build;
static entity object,*self=&object;
static struct { int scrolldir,type,settime; } storage,*level=&storage;
static struct { int hRes,vRes; } videomodes={320,240};
static struct { entity *ent; } player[4];
static struct { int effectvol; } savedata;
static int max_attack_types,level_completed,endgame,SAMPLE_TIMEOVER=-1,timeleft,showtimeover;
static int damage_calls,kind,force,previous_health,killed;
static float advancex,advancey,default_model_dropv[3];
static s_attack emptyattack;
static int is_frozen(entity *e) { assert(e==self);return 0; }
static void kill(entity *e) { assert(e==self);++killed; }
static void player_die(void) { ++killed; }
static void damage(entity *e,s_attack *a) { assert(e==self);++damage_calls;kind=a->attack_type;force=a->attack_force;previous_health=e->health; }
static void sound_play_sample(int id,int priority,int left,int right,int speed) { (void)id;(void)priority;(void)left;(void)right;(void)speed;assert(0); }
LOST
TIMEOVER
static void land(void) { s_attack attack; LANDING }
static void reset(void) {
    memset(&object,0,sizeof(object));object.health=40;object.takedamage=damage;
    object.damagetype=3;object.lifespancountdown=100;
    object.defense[ATK_LAND].factor=0.25f;damage_calls=killed=0;
}
int main(void) {
    const unsigned profiles[]={PROFILES};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        unsigned profile=profiles[p];
        obor_profile_build=profile;max_attack_types=profile<3830?16:20;
        reset();object.damage_on_landing=8;land();
        assert(damage_calls==1 && kind==(profile<3830?3:ATK_LAND) && force==8);
        reset();object.takedamage=0;object.damage_on_landing=8;land();
        assert(object.health==(profile<3830?32:38) && object.damage_on_landing==0);
        for(int expired=0;expired<2;++expired) {
            reset();if(expired)object.lifespancountdown=-1;else object.a=-11;
            check_lost();assert(damage_calls==1 && force==40);
            assert(kind==(profile<3830?max_attack_types:(expired?ATK_LIFESPAN:ATK_PIT)));
            assert(previous_health==(profile<3830?0:40));
            reset();object.takedamage=0;if(expired)object.lifespancountdown=-1;else object.a=-11;
            check_lost();assert(killed==1 && damage_calls==0);
        }
        reset();player[0].ent=&object;level_completed=0;level->type=0;
        time_over();assert(damage_calls==1 && kind==(profile<3830?max_attack_types:ATK_TIMEOVER));
    }
}
'''.replace('LOST', function(source, 'check_lost'))
           .replace('TIMEOVER\n', function(source, 'time_over') + '\n')
           .replace('LANDING', landing).replace('PROFILES', ','.join(map(str, attack_domain_revisions()))))

    def test_camera_mean_extremes_span_and_integer_truncation(self):
        source = (ENGINE / 'openbor.c').read_text()
        start = source.index('case CMD_LEVEL_SCROLLZ:')
        scroll_parser = source[start:source.index('case CMD_LEVEL_BLOCKADE:', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum { TYPE_ENEMY=1,TYPE_ENDLEVEL=2,TYPE_ITEM=4,TYPE_OBSTACLE=8,
       SCROLL_RIGHT=2,SCROLL_DOWN=4,SCROLL_LEFT=8,SCROLL_UP=16,
       SCROLL_OUTWARD=32,SCROLL_INWARD=64,SCROLL_BACK=128,
       COUNTER_SPEED=400,GAME_SPEED=200 };
typedef struct { float x,z,a; int dead; } entity;
static uint32_t obor_profile_build;
static struct { entity *ent; } player[4];
typedef struct { int at,musicfade,musicoffset,wait,groupmin,groupmax,nojoin,scrollminz,scrollmaxz,
    scrollminx,scrollmaxx,blockade,palette,light[2],shadowcolor,shadowalpha; char music[128]; } spawn;
static struct { int advancetime,numspawns,type,pos,waiting,noreset,settime,scrolldir,width,
    cameraxoffset,camerazoffset,rocking; float scrollspeed; spawn *spawnpoints; } room,*level=&room;
static struct { int maxplayers; } levelsets[1];
static struct { int hRes,vRes; } videomodes={320,240};
static struct { int musicvol; } savedata;
static int current_set,current_spawn,groupmin,groupmax,level_completed,freezeall,time,
    timeleft,go_time,musicoffset,musicloop,nojoin,light[2],shadowcolor,shadowalpha,panel_height=5000,cameratype;
static char musicname[128];
static float advancex,advancey,scrolldx,scrolldy,scrollminx,scrollmaxx,scrollminz,scrollmaxz,blockade,musicfade[2];
static int entity_count=9999;
static int findent(int type) { (void)type;return 1; }
static int count_ents(int type) { (void)type;return entity_count; }
static void change_system_palette(int n) { (void)n;assert(0); }
static void smartspawn(spawn *s) { (void)s;assert(0); }
METHOD
enum { CMD_LEVEL_SCROLLZ,CMD_LEVEL_SCROLLX };
static spawn next;
#define GET_INT_ARG(n) ((n)==1?low:high)
static void parse_scroll(int code,int low,int high) { switch(code) { SCROLL_PARSER } }
static int close_enough(float a,float b) { return a-b<0.001f && b-a<0.001f; }
int main(void) {
    entity ent[3]={{1000.5f,600.5f,10,0},{1001.5f,601.5f,20,0},{1200.5f,720.5f,40,0}};
    for(int i=0;i<3;++i)player[i].ent=ent+i;
    levelsets[0].maxplayers=3;room.width=5000;room.scrollspeed=10000;
    room.cameraxoffset=7;room.camerazoffset=13;scrollmaxx=scrollmaxz=5000;
    const int directions[]={SCROLL_RIGHT,SCROLL_LEFT,SCROLL_OUTWARD,SCROLL_INWARD};
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(unsigned d=0;d<4;++d)for(cameratype=0;cameratype<=1;++cameratype) {
            room.scrolldir=directions[d]|SCROLL_BACK;room.advancetime=0;room.waiting=0;time=1;
            advancex=advancey=500;level_completed=0;update_scroller();
            const float x=profile<3837?(1000+1001+1200)/3.0f-160+7:1100.5f-160+7;
            float z;
            if(profile<3837) {
                if(d<2)z=cameratype?(590+581+680)/3.0f-120+13:(600+601+720)/3.0f-120+13;
                else z=(600+601+720)/3.0f-120+(d==2?7:13);
            } else z=cameratype&&d<2?(581.5f+720.5f)/2-120+13:660.5f-120+13;
            assert(close_enough(advancex,x) && close_enough(advancey,z));
            assert(close_enough(scrolldx,x-500) && close_enough(scrolldy,z-500));
        }
        /* The later contract holds the camera when players exceed the viewport. */
        ent[2].x=2000.5f;room.scrolldir=SCROLL_RIGHT;advancex=500;advancey=500;
        update_scroller();assert(close_enough(advancex,profile<3837?(1000+1001+2000)/3.0f-160+7:500));
        ent[2].x=1200.5f;
        parse_scroll(CMD_LEVEL_SCROLLX,1000,1300);
        assert(profile<3783 ? next.scrollminz==1000 && next.scrollminx==0 :
               (next.scrollminx&0x7fffffff)==1000 && next.scrollminz==0);
        room.spawnpoints=&next;room.numspawns=1;current_spawn=0;groupmin=groupmax=1;entity_count=0;
        room.scrolldir=SCROLL_RIGHT;advancex=advancey=500;scrollminx=scrollminz=0;scrollmaxx=scrollmaxz=5000;cameratype=0;
        update_scroller();assert(current_spawn==1);
        assert(profile<3783 ? scrollminz==1000 && scrollminx==0 && advancey==1000 :
               scrollminx==1000 && scrollminz==0 && advancex==1000);
        room.numspawns=0;entity_count=9999;groupmin=0;scrollminx=scrollminz=0;scrollmaxx=scrollmaxz=5000;
        parse_scroll(CMD_LEVEL_SCROLLZ,-3,0);
        assert(profile<3783 ? next.scrollminz==0 && next.scrollmaxz==0 : (next.scrollminz&0x80000000)!=0);
        for(int i=0;i<3;++i)player[i].ent=NULL;
        advancex=500;advancey=500;update_scroller();
        assert(advancex==500 && advancey==500);
        for(int i=0;i<3;++i)player[i].ent=ent+i;
    }
}
'''.replace('METHOD', function(source, 'update_scroller')).replace('SCROLL_PARSER', scroll_parser))

    def test_attack_tables_suffixes_and_defense_all_boundaries(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        constants = header[header.index('#define\t\tATK_NORMAL\t'):header.index('#define     MAX_DOTS')]
        helpers = '\n'.join(function(source, name) for name in (
            'obor_attack_base', 'obor_attack_special', 'obor_attack_name_available'))
        start = source.index('case CMD_MODEL_DEFENSE:')
        cases = source[start:source.index('case CMD_MODEL_HEIGHT:', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
static uint32_t obor_profile_build;
CONSTANTS
HELPERS
#define stricmp strcasecmp
#define starts_with(a,b) (!strncasecmp(a,b,sizeof(b)-1))
#define get_tail_number(n,a,b) n=atoi((a)+sizeof(b)-1); if(n<1)n=1
#define GET_ARG(n) (args[n])
#define GET_FLOAT_ARG(n) ((float)atof(args[n]))
enum { CMD_MODEL_DEFENSE, CMD_MODEL_OFFENSE, SUBTYPE_BIKER };
typedef struct { float factor,pain,knockdown,blockpower,blockthreshold,blockratio,blocktype; } s_defense;
static const s_defense default_defense={1,0,0,0,0,0,0};
typedef struct { int subtype; s_defense *defense; float *offense_factors; } model;
static model data,*newchar=&data;
static int max_attack_types, warnings;
static void writeToLogFile(const char *format,...) { (void)format; ++warnings; }
static void parse(int code,const char *name) {
    const char *args[]={"command",name,"0.25","0","0","0","0","0","0"};
    struct { int count; } arglist={9};
    const char *value,*filename="synthetic",*command="command";
    s_defense defense; int i,tempInt; float tempFloat;
    switch(code) { CASES default: assert(0); }
}
int main(void) {
    const unsigned profiles[]={PROFILES};
    const char *names[]={"normal","normal1","normal2","normal10","normal11",
        "normal12","normal2147483647","item","land","pit","lifespan","timeover","ALL"};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        assert(OBOR_ATTACK_BASE==(profiles[p]<3830?16:20));
        assert(OBOR_ATTACK_SPECIAL==(profiles[p]<3831?6:10));
        for(int extension=0;extension<2;++extension) {
            max_attack_types=OBOR_ATTACK_BASE+(extension?2:0);
            data.defense=calloc(max_attack_types+1,sizeof(*data.defense));
            data.offense_factors=calloc(max_attack_types+1,sizeof(*data.offense_factors));
            assert(data.defense && data.offense_factors);
            for(unsigned n=0;n<sizeof(names)/sizeof(*names);++n) {
                memset(data.defense,0,(max_attack_types+1)*sizeof(*data.defense));
                memset(data.offense_factors,0,(max_attack_types+1)*sizeof(*data.offense_factors));
                data.defense[max_attack_types].factor=123;
                data.offense_factors[max_attack_types]=123;
                warnings=0; parse(CMD_MODEL_DEFENSE,names[n]); parse(CMD_MODEL_OFFENSE,names[n]);
                int suffix=n==1 && profiles[p]<3831 ? 11 : n==4 ? 11 : n==5 ? 12 : 0;
                int suffix_index=suffix+(profiles[p]<3831?6:10)-1;
                float spare=suffix && suffix_index==max_attack_types ? 0.25f : 123;
                assert(data.defense[max_attack_types].factor==spare && data.offense_factors[max_attack_types]==spare);
                if(n==0) assert(data.defense[ATK_NORMAL].factor==0.25f);
                if(n==1) {
                    if(profiles[p]>=3831) assert(data.defense[ATK_NORMAL].factor==0.25f);
                    else { assert(data.defense[ATK_NORMAL].factor==0); assert(data.defense[16].factor==0.25f); }
                }
                if(n==2) assert(data.defense[ATK_NORMAL2].factor==0.25f);
                if(n==4 || n==5) {
                    int index=(n==4?11:12)+(profiles[p]<3831?6:10)-1;
                    assert(warnings==(index>max_attack_types?2:0));
                    if(index<=max_attack_types) assert(data.defense[index].factor==0.25f && data.offense_factors[index]==0.25f);
                }
                if(n==6) assert(warnings==2);
                if(n==7) assert(data.defense[ATK_ITEM].factor==(profiles[p]>=3831?0.25f:0));
                if(n>=8 && n<=11 && profiles[p]<3831) assert(data.defense[0].factor==0);
                if(n==12) {
                    for(int i=0;i<max_attack_types;++i) {
                        int environmental=i==ATK_PIT || i==ATK_LIFESPAN || i==ATK_TIMEOVER;
                        assert(data.defense[i].factor==((profiles[p]>=3830 && environmental)?0:0.25f));
                        assert(data.offense_factors[i]==((profiles[p]>=3831 && environmental)?0:0.25f));
                    }
                }
            }
            free(data.defense);free(data.offense_factors);
        }
    }
}
'''.replace('CONSTANTS', constants).replace('HELPERS', helpers).replace('CASES', cases).replace('PROFILES', ','.join(map(str, attack_domain_revisions()))))

    def test_model_frame_argument_readers_keep_native_types_and_source_values(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-model-frame-argument-contracts.json')
        rows, commands = fixture['sources'], fixture['commands']
        by_revision = {row['revision']: row for row in rows}
        self.assertEqual(len(rows), len(by_revision))
        self.assertIn(3680, by_revision)
        self.assertIn(3681, by_revision)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), by_revision)
        root = ROOT / 'src/engines/3741'
        text = (root / 'openbor.c').read_text()
        loader = function(text, 'load_cached_model')
        actual, fields = [], []
        for index, command in enumerate(commands):
            label = 'case ' + command['command'] + ':'
            self.assertEqual(loader.count(label), 1)
            tail = loader.split(label, 1)[1]
            end = re.search(r'\n[ \t]*(?:case CMD_MODEL_\w+:|default:)', tail)
            self.assertIsNotNone(end)
            body = tail[:end.start()]
            statements = []
            for field in command['fields']:
                matches = re.findall(r'newanim->' + re.escape(field) + r'\s*=\s*[^;]+;', body)
                self.assertEqual(len(matches), 1, (command['command'], field))
                statements.append(matches[0])
                if field not in fields:
                    fields.append(field)
            actual.append('case %d: %s break;' % (index, '\n'.join(statements)))
        expected = []
        for key, readers in fixture['contracts'].items():
            cases = []
            for index, command in enumerate(commands):
                statements = []
                for item in readers[command['command']]:
                    if item['kind'] == 'copy':
                        value = 'want.' + item['from']
                    else:
                        arg = item['argument'] - 1
                        value = 'input->%s[%d]' % (
                            'floating' if item['kind'] == 'float' else 'integer', arg)
                        if item['kind'] == 'frame':
                            value = '(input->this_token[%d]?frame:%s)' % (arg, value)
                        skip = 'input->this_token[%d]' % arg if item['kind'] == 'frame' else '0'
                        statements.append('expected_warnings += *input->arguments[%d] && '
                            '!input->numeric[%d] && !(%s);' % (arg, arg, skip))
                    statements.append('want.' + item['field'] + '=' + value + ';')
                cases.append('case %d: %s break;' % (index, '\n'.join(statements)))
            expected.append('case %d:switch(command_index){%s}break;' %
                (list(fixture['contracts']).index(key), '\n'.join(cases)))
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['loader_sha256'], r'^[0-9a-f]{64}$')
            for digest in row['parser_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d);' % (
                row['revision'], list(fixture['contracts']).index(row['contract'])))
        inputs = []
        for item in fixture['inputs']:
            inputs.append('{{%s},{%s},{%s},{%s},{%s}}' % (
                ','.join(json.dumps(s) for s in item['arguments']),
                ','.join(map(str, item['integer'])),
                ','.join(str(float(v))+'f' for v in item['floating']),
                ','.join(str(int(v)) for v in item['numeric']),
                ','.join(str(int(s.lower() == 'this')) for s in item['arguments'])))
        macros = '\n'.join(re.search(r'(?m)^#define '+name+r'\(z\)[^\r\n]*', text)[0]
            for name in ('GET_ARG', 'GET_INT_ARG', 'GET_FLOAT_ARG', 'GET_FRAME_ARG'))
        parsers = '\n'.join(function(text, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat'))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Frame argument mismatch: revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int warnings;
static int warning(const char *format,...) {(void)format;++warnings;return 0;}
#define printf warning
@PARSERS@
#undef printf
static struct {int count;char *args[3];} arglist;
static char *filename="fixture",*command="frame";
static s_anim *newanim;
@MACROS@
static void apply(int command_index) {switch(command_index){@ACTUAL@}}
struct input {const char *arguments[2];int integer[2];float floating[2];int numeric[2],this_token[2];};
static const struct input inputs[]={@INPUTS@};
static const int frames[]={@FRAMES@};
static void check(int contract) {
 for(unsigned t=0;t<sizeof(inputs)/sizeof(*inputs);++t)
 for(unsigned f=0;f<sizeof(frames)/sizeof(*frames);++f)
 for(int command_index=0;command_index<@COMMANDS@;++command_index) {
  const struct input *input=inputs+t;
  int frame=frames[f],expected_warnings=0;
  s_anim actual={0},want={0};
  __typeof__(*actual.weaponframe) actual_weapon[2]={0},want_weapon[2]={0};
  __typeof__(*actual.spawnframe) actual_spawn[5]={0},want_spawn[5]={0};
  __typeof__(*actual.summonframe) actual_summon[5]={0},want_summon[5]={0};
  actual.weaponframe=actual_weapon;want.weaponframe=want_weapon;
  actual.spawnframe=actual_spawn;want.spawnframe=want_spawn;
  actual.summonframe=actual_summon;want.summonframe=want_summon;
  actual.numframes=want.numframes=frame;
  arglist.count=3;arglist.args[1]=(char*)input->arguments[0];arglist.args[2]=(char*)input->arguments[1];
  newanim=&actual;warnings=0;apply(command_index);
  switch(contract){@EXPECTED@}
  assert(warnings==expected_warnings);
  @COMPARE@
 }
}
int main(void) {@CHECKS@ return 0;}
'''.replace('@PARSERS@', parsers).replace('@MACROS@', macros)
           .replace('@ACTUAL@', '\n'.join(actual)).replace('@EXPECTED@', '\n'.join(expected))
           .replace('@INPUTS@', ','.join(inputs)).replace('@FRAMES@', ','.join(map(str, fixture['frame_positions'])))
           .replace('@COMMANDS@', str(len(commands)))
           .replace('@COMPARE@', '\n'.join('assert(actual.%s==want.%s);' % (s, s) for s in fields))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_projectile_terminal_health_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-projectile-health-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['star_move_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(row['sites'], 2)
            checks.append('obor_profile_build=%d;check(%d);' % (
                row['revision'], int(row['subtract_terminal_health'])))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static unsigned test_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Projectile health mismatch: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
static s_level level_storage,*level=&level_storage;
static s_videomodes videomodes={.hRes=320};
static float advancex;
static int PLAYER_MAX_Z=232,wall_index,kills,falls,seen_health,mutate;
#undef time
#define time projectile_clock
static int projectile_clock=37;
void common_fall(void) {abort();}
void common_lie(void) {abort();}
static void flying(void) {abort();}
void kill(entity *e) {assert(e==self && ++kills==1);}
int checkwall(float x,float z) {assert(x==self->x && z==self->z);return wall_index;}
float randf(float max) {assert(max==1);return 0.25f;}
int set_fall(entity *e,int type,int reset,entity *other,int force,int drop,int noblock,int guardcost,int jugglecost,int pauseadd) {
 assert(e==self && other==self && type==ATK_NORMAL && !reset && force==100000 && !drop && !noblock && !guardcost && !jugglecost && !pauseadd && ++falls==1);
 seen_health=self->health;if(mutate)self->health=250000;return 1;
}
@TOSS@
@STAR_MOVE@
static int terminal_health(int value,int legacy) {
 if(!legacy)return 0;
 int64_t result=(int64_t)value-100000;return result<INT_MIN?INT_MIN:(int)result;
}
static void check(int legacy) {
 const int healths[]={1,99999,100000,100001,200000,INT_MAX,INT_MIN+100000,INT_MIN+99999,INT_MIN};
 s_anim fall={0};fall.numframes=1;
 s_anim *animations[MAX_ANIS]={0};
 float walls[1][8];memset(walls,0,sizeof(walls));walls[0][7]=20;
 for(int route=0;route<10;++route)for(unsigned h=0;h<sizeof(healths)/sizeof(*healths);++h)
 for(mutate=0;mutate<2;++mutate)for(int direction=0;direction<2;++direction)for(int blink=0;blink<2;++blink) {
  ++test_case;entity actor={0},platform={0};self=&actor;memset(level,0,sizeof(*level));
  self->health=healths[h];self->modeldata.animation=animations;self->modeldata.animation_capacity=MAX_ANIS;
  animations[ANI_FALL]=route==6?NULL:&fall;
  self->x=route==1 || route==6?300:route==7?-100:route==9?500:100;self->z=220;
  self->base=route==3?1:route==8?0:10;self->a=self->base;
  self->landed_on_platform=route==4 || route==5?&platform:NULL;
  self->modeldata.falldie=route==8?0:1;self->modeldata.nodieblink=blink?2:0;
  self->direction=direction;self->animating=1;self->attacking=1;self->projectile=1;
  self->xdir=2;self->takeaction=flying;self->damage_on_landing=9;
  level->width=320;level->walls=walls;level->exit_blocked=route==1 || route==6;
  wall_index=route==2 || route==5?0:-1;level->numwalls=wall_index>=0?1:0;
  kills=falls=0;seen_health=INT_MAX;
  int expired=route==7 || route==8 || route==9;
  int bounce=route==1 || route==2 || route==5;
  int landed=route==3 || route==4 || route==5;
  int expected=healths[h],first=expected;
  if(bounce){first=expected=terminal_health(expected,legacy);if(mutate)expected=250000;}
  if(landed)expected=terminal_health(expected,legacy);
  assert(star_move()==!expired && kills==expired && falls==bounce);
  assert(self->health==expected);
  if(bounce)assert(seen_health==first && self->tossv==2.75f && self->toss_time==(u32)(time+1));
  assert(self->nextthink==(u32)(expired?0:time+THINK_SPEED/2));
  assert(self->takeaction==(expired?flying:landed?common_lie:bounce?common_fall:flying));
  assert(!!self->animating==!(landed && blink));
  assert(!!self->attacking==!bounce && !!self->projectile==!bounce);
  assert(self->damage_on_landing==(bounce?0:9));
  assert(self->xdir==(bounce?(direction?-1.2f:1.2f):2));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@TOSS@', function(source, 'toss')).replace('@STAR_MOVE@', function(source, 'star_move'))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_pickup_script_order_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-pickup-order-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        thinker = function(source, 'player_think')
        match = re.search(r'if\([^\n]*find_ent_here[^\n]*player_test_pickable[^\n]*\)\s*\{', thinker)
        self.assertIsNotNone(match)
        brace = thinker.index('{', match.start())
        wrapper = function('void selected(void) ' + thinker[brace:], 'selected')
        block = thinker[match.start():brace] + wrapper[wrapper.index('{'):]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key in ('common_sha256', 'player_pickup_block_sha256', 'didfind_sha256'):
                self.assertRegex(row[key], r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d,%d);' % (
                row['revision'], int(row['common_hide_before_script']),
                int(row['player_effect_before_animation_and_script'])))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static unsigned test_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Pickup order mismatch: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
s_player player[4];
s_savedata savedata;
static s_level level_storage,*level=&level_storage;
#undef time
#define time pickup_clock
static int pickup_clock=11;
int timeleft,noshare,credits;
int SAMPLE_GET=10,SAMPLE_GET2=11,SAMPLE_1UP=12;
static entity *item;
static int mutate,available,anim_calls,script_calls,drops,weapons,score_total;
static int trace_count;
static char trace[4];
static struct {float item_z,x,z;int health,item_health;} animation_seen,script_seen;
static void event(char e) {assert(trace_count<3);trace[trace_count++]=e;trace[trace_count]=0;}
void common_get(void) {abort();}
void suicide(void) {abort();}
void dropweapon(int flag) {assert(!flag);++drops;}
void set_weapon(entity *e,int number,int flag) {assert(e==self && e->weapent==item && number==7 && !flag);++weapons;}
void addscore(int index,int amount) {assert(index==0 && amount==25);score_total+=amount;}
void smart_bomb(entity *e,s_attack *a) {(void)e;(void)a;abort();}
int sound_play_sample(int sample,unsigned priority,int left,int right,unsigned speed) {
 assert(sample>=10 && sample<=12 && !priority && left==savedata.effectvol && right==savedata.effectvol && speed==100);return 0;
}
int test_item(entity *e,entity *other) {assert(e==self && other==item);return 1;}
@HELPERS@
void set_opponent(entity *e,entity *other) {event('D');native_set_opponent(e,other);}
entity *find_ent_here(entity *exclude,float x,float z,int types,int (*test)(entity*,entity*)) {
 assert(exclude==self && x==self->x && z==self->z && types==TYPE_ITEM && test==player_test_pickable);
 return available && test(self,item)?item:NULL;
}
void ent_set_anim(entity *e,int animation,int reset) {
 assert(e==self && animation==ANI_GET && !reset && ++anim_calls==1);event('A');
 animation_seen.item_z=item->z;animation_seen.health=e->health;animation_seen.item_health=item->health;
 animation_seen.x=e->x;animation_seen.z=e->z;e->animnum=animation;
}
void execute_didhit_script(entity *e,entity *other,int force,int drop,int type,int noblock,int guardcost,int jugglecost,int pauseadd,int blocked) {
 assert(e==item && other==self && !force && !drop && type==item->modeldata.subtype && !noblock && !guardcost && !jugglecost && !pauseadd && !blocked && ++script_calls==1);
 event('H');script_seen.item_z=item->z;script_seen.health=self->health;script_seen.item_health=item->health;
 script_seen.x=self->x;script_seen.z=self->z;
 if(mutate){item->z=77;item->health=30;}
}
@DIDFIND@
@COMMON@
static int player_pickup(void) {entity *other=NULL;@PLAYER_BLOCK@return 0;endthinkcheck:return 1;}
static void check(int common_before,int player_before) {
 s_anim anim={0};anim.numframes=1;
 s_anim *animations[MAX_ANIS]={0};
 savedata.effectvol=50;
 for(int path=0;path<2;++path)for(int kind=0;kind<5;++kind)for(int valid=0;valid<2;++valid)
 for(mutate=0;mutate<2;++mutate)for(int holding=0;holding<2;++holding)for(int animal=0;animal<3;++animal)
 for(available=0;available<2;++available) {
  if((!path && !available) || (path && holding))continue;
  ++test_case;entity actor={0},object={0},held={0};self=&actor;item=&object;
  memset(player,0,sizeof(player));memset(&animation_seen,0,sizeof(animation_seen));memset(&script_seen,0,sizeof(script_seen));
  anim_calls=script_calls=drops=weapons=score_total=trace_count=0;trace[0]=0;
  self->health=50;self->modeldata.health=100;self->x=10;self->z=20;
  self->xdir=2;self->zdir=3;self->idling=1;self->modeldata.animal=animal;
  self->modeldata.animation=animations;self->modeldata.animation_capacity=MAX_ANIS;animations[ANI_GET]=valid?&anim:NULL;
  self->weapent=holding?&held:NULL;
  item->x=30;item->z=40;item->modeldata.name="fixture";item->modeldata.weapnum=7;
  item->modeldata.subtype=kind==1?SUBTYPE_WEAPON:kind==2?SUBTYPE_PROJECTILE:kind==3?SUBTYPE_TOUCH:SUBTYPE_NONE;
  item->health=(kind==0 || kind==3)?20:0;item->modeldata.score=kind==4?25:0;
  int accepted=path?(valid && available && kind!=3 && !(kind==1 && animal==2)):
                      ((kind!=1 && kind!=2) || (!holding && valid));
  int animated=accepted && (path || (valid && kind!=3));
  if(path)assert(player_pickup()==accepted);else common_pickupitem(item);
  assert(anim_calls==animated && script_calls==accepted);
  const char *expected_trace=!accepted?"":path?(player_before?"DAH":"AHD"):animated?"AH":"H";
  assert(!strcmp(trace,expected_trace));
  int equipped=accepted && (kind==1 || kind==2) && (!path || player_before || !mutate);
  assert(self->weapent==(equipped?item:holding?&held:NULL));
  assert(drops==equipped && weapons==(equipped && kind==1));
  assert(score_total==(path && accepted && kind==4?25:0));
  int expected_health=50;
  if(accepted && (kind==0 || (!path && kind==3)))expected_health=70;
  if(path && accepted && !player_before && mutate && kind!=4)expected_health=80;
  assert(self->health==expected_health);
  int remaining=(kind==0 || kind==3)?20:0;
  if(accepted)remaining=mutate && (!path || player_before || kind==4)?30:0;
  assert(item->health==remaining);
  float final_z=!accepted?40:mutate && (path?player_before:common_before)?77:100000;
  assert(item->z==final_z);
  int copied=equipped && kind==1 && animal;
  assert(self->x==(copied?30:10) && self->z==(copied?40:20));
  assert(self->xdir==(animated?0:2) && self->zdir==(animated?0:3));
  if(animated) {
   assert(animation_seen.item_z==(path && player_before?100000:40));
   assert(animation_seen.health==(path && player_before && kind==0?70:50));
   int seen_copy=copied && (!path || player_before);
   assert(animation_seen.x==(seen_copy?30:10) && animation_seen.z==(seen_copy?40:20));
  }
  if(accepted) {
   assert(script_seen.item_z==((path?player_before:common_before)?100000:40));
   assert(script_seen.health==((!path && (kind==0 || kind==3)) || (path && player_before && kind==0)?70:50));
   assert(script_seen.item_health==(path && !player_before && kind==0?20:0));
  }
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@HELPERS@', '\n'.join(function(source, name) for name in (
                'diff','isSubtypeWeapon','isSubtypeProjectile','isSubtypeTouch','player_test_pickable')) + '\n' +
                function(source, 'set_opponent').replace('set_opponent(', 'native_set_opponent(', 1))
           .replace('@DIDFIND@', function(source, 'didfind_item'))
           .replace('@COMMON@', function(source, 'common_pickupitem'))
           .replace('@PLAYER_BLOCK@', block).replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_jump_combo_action_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-jump-combo-action-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['costmove_sha256'], r'^[0-9a-f]{64}$')
            self.assertRegex(row['combo_sha256'], r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d);' % (row['revision'], int(row['jump_keeps_action'])))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static unsigned test_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Jump combo action mismatch: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
s_player player[4];
static s_level level_storage,*level=&level_storage;
static int nocost,healthcheat,energy_mode,matched,anim_calls,unlink_calls;
static void (*seen_action)(void);
static void airborne_action(void) {abort();}
void common_attack_proc(void) {abort();}
int check_energy(int which,int animation) {
 assert(animation==ANI_ATTACK1 || animation==ANI_ATTACK2);
 return !!(energy_mode&(which?2:1));
}
static int match_combo(int *input,s_player *p,int steps) {
 assert(p==player && (steps==1 || steps==2) && input[0]==steps);return matched;
}
void ent_unlink(entity *e) {assert(e==self && ++unlink_calls==1);}
void ent_set_anim(entity *e,int animation,int reset) {
 assert(e==self && animation==ANI_ATTACK2 && !reset && unlink_calls==1 && ++anim_calls==1);
 seen_action=e->takeaction;
}
@FUNCTIONS@
static void check(int keeps_action) {
 s_anim anim={0},pose={0};anim.numframes=1;anim.energycost.cost=7;
 s_anim *animations[MAX_ANIS]={0};animations[ANI_ATTACK1]=animations[ANI_ATTACK2]=&anim;
 s_com commands[2];memset(commands,0,sizeof(commands));
 commands[0].steps=1;commands[0].input[0]=1;commands[0].anim=ANI_ATTACK1;
 commands[1].steps=2;commands[1].input[0]=2;commands[1].anim=ANI_ATTACK2;
 for(int caller=0;caller<2;++caller)for(int jump=0;jump<2;++jump)
 for(int setting=0;setting<4;++setting)for(energy_mode=0;energy_mode<4;++energy_mode)
 for(nocost=0;nocost<2;++nocost)for(healthcheat=0;healthcheat<2;++healthcheat)
 for(int route=0;route<2;++route) {
  ++test_case;entity actor={0};self=&actor;memset(player,0,sizeof(player));
  self->modeldata.animation=animations;self->modeldata.animation_capacity=MAX_ANIS;
  self->modeldata.special=commands;self->modeldata.specials_loaded=2;
  self->animation=&pose;self->animnum=ANI_IDLE;self->idling=1;
  self->jumping=jump;self->takeaction=airborne_action;
  self->mp=self->health=100;self->xdir=2;self->zdir=3;self->inpain=1;
  memset(self->combostep,0x5a,sizeof(self->combostep));
  level->nospecial=setting;anim_calls=unlink_calls=0;seen_action=NULL;
  matched=route;int fs=caller?1:route;
  int allowed=energy_mode && ((fs && setting<2) || (!fs && (setting==0 || setting==3)));
  if(caller && !matched)allowed=0;
  int result=caller?check_combo():check_costmove(ANI_ATTACK2,fs,jump);
  assert(result==!!allowed && anim_calls==!!allowed && unlink_calls==!!allowed);
  void (*expected_action)(void)=allowed && (!keeps_action || !jump)?common_attack_proc:airborne_action;
  assert(self->takeaction==expected_action);
  if(allowed)assert(seen_action==expected_action);
  int spent=allowed && !nocost && !healthcheat;
  assert(self->mp==100-(spent && (energy_mode&2)?7:0));
  assert(self->health==100-(spent && !(energy_mode&2)?7:0));
  assert(self->xdir==(allowed?0:2) && self->zdir==(allowed?0:3));
  assert(!!self->attacking==!!allowed && !!self->idling==!allowed && !!self->inpain==!allowed);
  for(unsigned i=0;i<sizeof(self->combostep);++i)
   assert(self->combostep[i]==(allowed && i<sizeof(int)*5?0:0x5a));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@FUNCTIONS@', '\n'.join(function(source, name) for name in ('diff', 'check_costmove', 'check_combo')))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_player_running_policy_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-player-running-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        thinker = function(source, 'player_think')
        tail = thinker.split('//dang long run checking logic', 1)[1].lstrip()
        brace = tail.index('{')
        wrapper = function('void selected(void) ' + tail[brace:], 'selected')
        policy = tail[:brace] + wrapper[wrapper.index('{'):]
        entries = re.findall(r'if\([^\n]*runupdown&2[^\n]*validanim\(self,ANI_RUN\)\)\s*\{[^{}]*\}', thinker)
        self.assertEqual(len(entries), 2)
        stops = re.findall(r'(?m)^[ \t]*[^\n]*self->running = 0;[^\n]*// '
                           r'(?:Quits running if player (?:presses (?:up|down)|changes direction)|'
                           r'Player let go)[^\n]*', thinker)
        self.assertEqual(len(stops), 5)
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['special_input_steps'], 27)
            checks.append('obor_profile_build=%d;check(%d);' % (row['revision'], int(row['modern_run_policy'])))
        methods = '\n'.join('static void tap_%d(void){%s else ++fallbacks;}' % (i, body)
            for i, body in enumerate(entries))
        methods += '\n' + '\n'.join('static void stop_%d(void){\n%s\n}' % (i, statement)
            for i, statement in enumerate(stops))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static unsigned test_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Running policy mismatch: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
static s_player input,*pl=&input;
static int oldrunning,t,fallbacks;
@DIFF@
static void update_running(void) {int runx,runz,movex,movez;@POLICY@}
@METHODS@
static const int decision_cases[][7]={@CASES@};
static void check(int modern) {
 entity actor={0};self=&actor;
 for(test_case=0;test_case<sizeof(decision_cases)/sizeof(*decision_cases);++test_case) {
  const int *c=decision_cases[test_case];
  self->modeldata.runupdown=c[0];oldrunning=c[4];self->running=c[5];self->xdir=c[2];self->zdir=c[3];
  pl->keys=(c[1]&1?FLAG_MOVEUP:0)|(c[1]&2?FLAG_MOVEDOWN:0)|
           (c[1]&4?FLAG_MOVELEFT:0)|(c[1]&8?FLAG_MOVERIGHT:0);
  u32 keys=pl->keys;update_running();
  assert(!!self->running==(modern?c[6]:c[5]));
  assert(self->xdir==c[2] && self->zdir==c[3] && pl->keys==keys);
 }
 s_anim anim={0};anim.numframes=1;
 s_anim *animations[MAX_ANIS]={0};self->modeldata.animation=animations;
 self->modeldata.animation_capacity=MAX_ANIS;
 void (*tap[])(void)={tap_0,tap_1};
 const int combo[]={0,1,MAX_SPECIAL_INPUTS-1};
 for(int direction=0;direction<2;++direction)for(int policy=0;policy<8;++policy)
 for(t=0;t<2;++t)for(int valid=0;valid<2;++valid)for(int active=0;active<2;++active)
 for(int c=0;c<3;++c) {
  ++test_case;self->modeldata.runupdown=policy;self->running=active;
  animations[ANI_RUN]=valid?&anim:NULL;
  pl->playkeys=FLAG_MOVEUP|FLAG_MOVEDOWN|FLAG_ATTACK;pl->combostep=combo[c];fallbacks=0;
  u32 initial=pl->playkeys,flag=direction?FLAG_MOVEDOWN:FLAG_MOVEUP;
  int enter=modern && t && (policy&2) && valid;tap[direction]();
  assert(fallbacks==!enter && !!self->running==(enter?1:active));
  assert(pl->playkeys==(enter?initial&~flag:initial));
  assert(pl->combostep==(enter?(combo[c]+MAX_SPECIAL_INPUTS-1)%MAX_SPECIAL_INPUTS:combo[c]));
 }
 void (*stops[])(void)={stop_0,stop_1,stop_2,stop_3,stop_4};
 for(int site=0;site<5;++site)for(int policy=0;policy<8;++policy)for(int active=0;active<2;++active) {
  ++test_case;self->modeldata.runupdown=policy;self->running=active;stops[site]();
  int stopped=!modern && (site>=2 || !policy);
  assert(!!self->running==(stopped?0:active));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@DIFF@', function(source, 'diff')).replace('@POLICY@', policy)
           .replace('@METHODS@', methods)
           .replace('@CASES@', ','.join('{'+','.join(map(str, row))+'}' for row in fixture['decision_cases']))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_turn_animation_velocity_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-turn-velocity-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        thinker = function(source, 'player_think')
        blocks = re.findall(r'self->takeaction\s*=\s*common_turn;[\s\S]*?goto endthinkcheck;', thinker)
        self.assertEqual(len(blocks), 4)
        wrappers = '\n'.join('static void turn_%d(void){%s\nassert(0);\nendthinkcheck:++completed;}' % (i, block)
            for i, block in enumerate(blocks))
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['branch_sha256']), 4)
            for digest in row['branch_sha256']:
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d);' % (row['revision'], int(row['clear_velocity'])))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static int branch,mutate,calls,completed;
#define assert(c) do {if(!(c)){fprintf(stderr,"Turn velocity mismatch: revision=%u branch=%d line=%d\n",obor_profile_build,branch,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
static float seen_x,seen_z;
void common_turn(void) {abort();}
void ent_set_anim(entity *e,int animation,int reset) {
 assert(e==self && animation==ANI_TURN && !reset && ++calls==1);
 assert(e->takeaction==common_turn && e->turning && !e->idling);
 seen_x=e->xdir;seen_z=e->zdir;
 if(mutate){e->xdir=-7;e->zdir=11;}
}
@BRANCHES@
static void check(int clear_velocity) {
 static const float velocities[]={-2,0,3};
 void (*turns[])(void)={turn_0,turn_1,turn_2,turn_3};
 for(branch=0;branch<4;++branch)for(unsigned x=0;x<3;++x)for(unsigned z=0;z<3;++z)
 for(mutate=0;mutate<2;++mutate) {
  entity actor={0};self=&actor;
  self->idling=1;self->xdir=velocities[x];self->zdir=velocities[z];
  calls=completed=0;turns[branch]();
  assert(calls==1 && completed==1 && self->takeaction==common_turn);
  assert(seen_x==(clear_velocity?0:velocities[x]));
  assert(seen_z==(clear_velocity?0:velocities[z]));
  assert(self->xdir==(mutate?-7:seen_x) && self->zdir==(mutate?11:seen_z));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@BRANCHES@', wrappers).replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_jump_special_callback_order_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-jump-special-order-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['jump_check_sha256'], r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d);' % (
                row['revision'], int(row['callback_after_motion_reset'])))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static int scenario,healthcheat,noaircancel,mutate,calls,called_animation;
#define assert(c) do {if(!(c)){fprintf(stderr,"Jump special order mismatch: revision=%u case=%d line=%d\n",obor_profile_build,scenario,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
entity *self;
s_player player[4];
static s_level current_level,*level=&current_level;
static struct {float x,z,toss;int attacking,special,health,mp;} seen;
int check_energy(int which,int animation) {
 assert(animation==ANI_JUMPSPECIAL);
 return scenario!=2 && (which?scenario!=1:1);
}
void ent_set_anim(entity *e,int animation,int reset) {
 assert(e==self && reset==0 && ++calls==1);called_animation=animation;
 seen.x=e->xdir;seen.z=e->zdir;seen.toss=e->tossv;seen.attacking=!!e->attacking;
 seen.special=!!(player[e->playerindex].playkeys&FLAG_SPECIAL);seen.health=e->health;seen.mp=e->mp;
 e->animnum=animation;
 if(mutate && animation==ANI_JUMPSPECIAL){e->xdir=11;e->zdir=12;e->tossv=13;e->attacking=0;}
}
@JUMP_CHECK@
static void check(int after_reset) {
 for(scenario=0;scenario<9;++scenario)for(healthcheat=0;healthcheat<2;++healthcheat)
 for(mutate=0;mutate<2;++mutate) {
  entity actor={0};self=&actor;
  memset(player,0,sizeof(player));memset(level,0,sizeof(*level));memset(&seen,0,sizeof(seen));
  calls=0;called_animation=-1;noaircancel=0;
  s_anim anim={0};anim.numframes=1;anim.energycost.cost=7;
  s_anim *animations[MAX_ANIS]={0};
  animations[ANI_JUMPSPECIAL]=animations[ANI_JUMPCANT]=animations[ANI_JUMPATTACK]=&anim;
  self->modeldata.animation=animations;self->modeldata.animation_capacity=MAX_ANIS;
  self->xdir=2;self->zdir=3;self->tossv=4;self->mp=self->health=100;
  self->jumpid=ANI_JUMP;self->animnum=ANI_IDLE;
  player[0].playkeys=FLAG_SPECIAL;
  if(scenario==3)animations[ANI_JUMPSPECIAL]=NULL;
  if(scenario==4)player[0].playkeys=FLAG_ATTACK;
  if(scenario==5 || scenario==8){noaircancel=1;self->animating=1;}
  if(scenario==6)level->nospecial=1;
  if(scenario==7)level->nospecial=3;
  if(scenario==8)self->animnum=self->jumpid;
  player_jump_check();
  int special=scenario==0 || scenario==1 || scenario==7 || scenario==8;
  int expected_animation=special?ANI_JUMPSPECIAL:scenario==2?ANI_JUMPCANT:scenario==4?ANI_JUMPATTACK:-1;
  assert(calls==(expected_animation>=0) && called_animation==expected_animation);
  assert(self->health==(special && scenario==1 && !healthcheat?93:100));
  assert(self->mp==(special && scenario!=1 && !healthcheat?93:100));
  if(special) {
   assert(!seen.special && seen.health==self->health && seen.mp==self->mp);
   assert(seen.x==(after_reset?0:2) && seen.z==(after_reset?0:3) && seen.toss==(after_reset?0:4));
   assert(seen.attacking==after_reset);
   assert(self->xdir==(after_reset && mutate?11:0));
   assert(self->zdir==(after_reset && mutate?12:0));
   assert(self->tossv==(after_reset && mutate?13:0));
   assert(!!self->attacking==!(after_reset && mutate));
   assert(!player[0].playkeys);
  } else {
   assert(self->xdir==2 && self->zdir==3 && self->tossv==(scenario==2?0:4));
   assert(!!self->attacking==(scenario==4));
   assert(player[0].playkeys==(scenario==4?0:FLAG_SPECIAL));
  }
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@JUMP_CHECK@', function(source, 'player_jump_check'))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_gif_footer_palette_and_errors_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-gif-palette-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        source = (root / 'openbor.c').read_text()
        header = (root / 'openbor.h').read_text()
        flags = '\n'.join(line for line in header.splitlines()
            if re.match(r'#define\s+(?:GAME_SPEED|FLAG_\w+)\s', line))
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['playgif_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(row['restore_after_playback'], row['restore_after_error'])
            checks.append('obor_profile_build=%d;check(%d,%s);' % (
                row['revision'], int(row['restore_after_playback']), json.dumps(row['error_format'])))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "types.h"
#include "anigif.h"
@FLAGS@
#define stricmp strcasecmp
static uint32_t obor_profile_build;
static int scenario,rgb_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"GIF footer mismatch: revision=%u mode=%d rgb=%d line=%d\n",obor_profile_build,scenario,rgb_case,__LINE__);abort();}}while(0)
int pixelformat,screenformat;
static s_videomodes videomodes={.hRes=2,.vRes=2};
static s_screen old_background,*background;
static char *packfile="fixture.pak";
static struct {int gamma,brightness;} savedata;
static u32 time,newtime,bothnewkeys;
static int allocations,releases,opens,updates,palette_calls,palette_value,decodes[3];
static int palette_restored_background[2];
static char logtext[256];
static int gif_log(const char *format,...) {
 va_list args;va_start(args,format);int result=vsnprintf(logtext,sizeof(logtext),format,args);va_end(args);return result;
}
static s_screen *allocscreen(int width,int height,int format) {
 (void)format;assert(width==2 && height==2);++allocations;
 s_screen *screen=calloc(1,sizeof(*screen));assert(screen);screen->width=width;screen->height=height;return screen;
}
static void clearscreen(s_screen *s) {assert(s && s->width==2);}
static void freescreen(s_screen **s) {assert(s && *s);++releases;free(*s);*s=NULL;}
static void standard_palette(int correction) {
 assert(correction==1 && palette_calls<2);palette_restored_background[palette_calls++]=(background==&old_background);palette_value=1;
}
static int testpackfile(char *name,char *pak) {(void)name;assert(pak==packfile);return scenario==4?-1:0;}
int anigif_open(char *name,char *pak,unsigned char *pal,anigif_info *info) {
 assert(name && pak==packfile && pal && opens<3);int index=opens++;decodes[index]=0;
 if(scenario==1 || (scenario==3 && index==1)){info->handle=-1;return 0;}
 info->handle=index+100;return 1;
}
int anigif_decode(s_screen *screen,int *delay,int x,int y,unsigned char *pal,anigif_info *info) {
 assert(screen && delay && x==3 && y==5 && pal && info->handle>=100 && info->handle<103);
 int stage=decodes[info->handle-100]++;assert(stage<3);
 *delay=1;pal[0]=77;
 return stage==0?ANIGIF_DECODE_RETRY:stage==1?ANIGIF_DECODE_FRAME:ANIGIF_DECODE_END;
}
void anigif_close(anigif_info *info) {info->handle=-1;}
static u32 sound_getinterval(void) {return UINT32_MAX;}
static void update_backbuffer(s_screen *b,s_screen **frames) {assert(b && frames[0] && frames[1] && frames[2]);}
static void spriteq_add_screen(int x,int y,int z,s_screen *s,s_drawmethod *method,int sort) {
 assert(!x && !y && !z && s && !method && !sort);
}
static void vga_vwait(void) {}
static void palette_set_corrected(unsigned char *pal,int r,int g,int b,int br,int bg,int bb) {
 assert(pal[0]==77 && !r && !g && !b && !br && !bg && !bb);palette_value=2;
}
static void update(int ingame,int wait) {assert(!ingame && (wait==0 || wait==1));assert(++updates<4);time+=10;newtime+=20;}
#define printf gif_log
@PLAYGIF@
#undef printf
static void check(int restore,const char *error_format) {
 /* Start with the RGB success path so all three static decoder contexts have
    a completed open/close before exercising later open refusals. */
 for(rgb_case=1;rgb_case>=0;--rgb_case)for(scenario=0;scenario<5;++scenario) {
  if(!rgb_case && (scenario==3 || scenario==4))continue;
  for(int noskip=0;noskip<2;++noskip) {
   allocations=releases=opens=updates=palette_calls=palette_value=0;logtext[0]=0;
   pixelformat=screenformat=rgb_case?PIXEL_x8:PIXEL_8;
   background=&old_background;time=123;newtime=456;
   bothnewkeys=scenario==2?FLAG_ESC:0;
   int failed=scenario==1 || scenario==3;
   int result=playgif("fixture.gif",3,5,noskip);
   assert(result==(failed?0:scenario==2?-1:1));
   assert(time==123 && newtime==456 && background==&old_background);
   assert(allocations==releases && allocations==(rgb_case && scenario!=4?4:1));
   assert(palette_calls==1+restore && !palette_restored_background[0]);
   if(restore)assert(palette_restored_background[1]);
   assert(palette_value==(!failed && (!rgb_case || scenario==4) && !restore?2:1));
   char expected[256]={0};if(failed && *error_format)snprintf(expected,sizeof(expected),error_format,"fixture.gif");
   assert(!strcmp(logtext,expected));
   assert(failed?updates==0:updates==1);
  }
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@FLAGS@', flags).replace('@PLAYGIF@', function(source, 'playgif'))
           .replace('@CHECKS@', '\n'.join(checks)), [root / 'source/gamelib'],
           ['-DLIBRETRO=1'])

    def test_biker_defense_extent_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-biker-defense-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        text = (root / 'openbor.c').read_text()
        macro = re.search(r'(?m)^#define GET_ARGP\(z\)[^\r\n]*', text)[0]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['subtype_sha256'], r'^[0-9a-f]{64}$')
            checks.append('obor_profile_build=%d;check(%d);' % (
                row['revision'], row['fixed_slots'] or 0))
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
#define assert(c) do {if(!(c)){fprintf(stderr,"Subtype defense mismatch: revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
void shutdown(int status,char *format,...) {(void)status;(void)format;abort();}
int max_attack_types;
@MACRO@
@HANDLER@
static void check(int fixed_slots) {
 static char *names[]={"biker","BIKER","arrow"};
 static const int counts[]={MAX_ATKS,MAX_ATKS+1,MAX_ATKS+7};
 for(unsigned n=0;n<3;++n)for(unsigned c=0;c<3;++c)for(int custom=0;custom<2;++custom) {
  max_attack_types=counts[c];
  s_model model={0};
  s_defense actual[MAX_ATKS+9],expected[MAX_ATKS+9];
  memset(actual,0,sizeof(actual));
  for(unsigned i=0;i<sizeof(actual)/sizeof(*actual);++i)actual[i].factor=0.25f+(float)i;
  memcpy(expected,actual,sizeof(actual));
  if(n<2)for(int i=0;i<(fixed_slots?fixed_slots:max_attack_types);++i)expected[i].factor=2;
  model.defense=actual;model.offscreenkill=custom?37:0;
  ArgList args={0};args.count=2;args.args[0]="subtype";args.args[1]=names[n];
  lcmHandleCommandSubtype(&args,&model,"fixture");
  assert(!memcmp(actual,expected,sizeof(actual)));
  assert(model.subtype==(n<2?SUBTYPE_BIKER:SUBTYPE_ARROW));
  assert(model.offscreenkill==(custom?37:n<2?300:200));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@MACRO@', macro)
           .replace('@HANDLER@', function(text, 'lcmHandleCommandSubtype'))
           .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_global_command_availability_and_values_follow_own_source(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-global-command-contracts.json')
        rows, commands = fixture['sources'], fixture['commands']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        text = (root / 'openbor.c').read_text()
        domain_info = {'models': ('load_models', 'getModelstxtCommand', 'createModelstxtCommandList'),
                       'order': ('load_levelorder', 'getLevelOrderCommand', 'createLevelOrderCommandList'),
                       'model': ('load_cached_model', 'getModelCommand', 'createModelCommandList'),
                       'level': ('load_level', 'getLevelCommand', 'createLevelCommandList')}
        fields = [target for command in commands for target in command['targets']]
        integer_fields = {'skiptoset'} | {target for command in commands if command.get('integer')
                                        for target in command['targets']}
        self.assertEqual(len(fields), len(set(fields)))
        dispatch, lookup = [], []
        for domain_index, (domain, (loader_name, getter, create)) in enumerate(domain_info.items()):
            loader = function(text, loader_name)
            cases = []
            for command in commands:
                if command['domain'] != domain:
                    continue
                label = 'case '+command['enum']+':'
                self.assertEqual(loader.count(label), 1)
                tail = loader.split(label, 1)[1]
                end = re.search(r'\n[ \t]*(?:case CMD_|default:)', tail)
                self.assertIsNotNone(end)
                cases.append(label + tail[:end.start()])
            defaults = list(re.finditer(r'(?m)^(\t+)default:\n', loader))
            self.assertTrue(defaults)
            command_defaults = []
            for candidate in defaults:
                end = loader.index('\n'+candidate[1][:-1]+'}', candidate.end())
                block = loader[candidate.start():end]
                if 'not understood' in block:
                    command_defaults.append(block)
            self.assertEqual(len(command_defaults), 1, loader_name)
            cases.append(command_defaults[0])
            dispatch.append('case %d:switch(code){%s}break;' % (domain_index, '\n'.join(cases)))
            lookup.append('case %d:code=%s(lists[%d],command);break;' % (domain_index, getter, domain_index))
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            checks.append('obor_profile_build=%d;check((const int[]){%s},%d);' % (
                row['revision'], ','.join(str(int(row['available'][c['name']])) for c in commands),
                int(row['constructor_uses_global_defaults'])))
        cases = []
        for command in commands:
            expected = []
            for index, target in enumerate(command['targets']):
                arg = index if len(command['targets']) > 1 else 0
                value = 'values[argument_case][%d]' % arg
                if command.get('integer'):
                    value = '(argument_case==0?0:argument_case==1?7:-3)'
                if target == 'skiptoset':
                    value = '0'  # All fixed examples have integer conversion zero.
                if target == 'newchar->attackthrottletime':
                    value += '*GAME_SPEED'
                    expected.append('if(argument_case>0) want[%d]=%s;' % (fields.index(target), value))
                else:
                    expected.append('want[%d]=%s;' % (fields.index(target), value))
            cases.append('{%d,%s,%s},' % (list(domain_info).index(command['domain']),
                json.dumps(command['name']), command['enum']))
            command['expectation'] = '\n'.join(expected)
        expect = '\n'.join('case %d:%s break;' % (i, c['expectation']) for i, c in enumerate(commands))
        init = function(text, 'init_model')
        constructor = []
        for name in fixture['constructor_fields']:
            statements = re.findall(r'newchar->'+name+r'\s*=\s*[^;]+;', init)
            self.assertEqual(len(statements), 1)
            constructor.append(statements[0])
        includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                    *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
        version = subprocess.check_output(shlex.split(os.environ.get('HOST_CC', 'cc')) +
            ['--version'], text=True, timeout=10)
        flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3741', '-fsigned-char',
                 '-ffunction-sections', '-fdata-sections', '-Wno-unused-variable',
                 '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-error=sign-compare',
                 '-Wno-error=misleading-indentation', '-Wno-error=int-to-pointer-cast']
        flags += ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static int command_index,argument_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Configuration mismatch: revision=%u command=%d arguments=%d line=%d\n",obor_profile_build,command_index,argument_case,__LINE__);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@LOWERCASE@
#include @LIST_C@
#include @COMMANDS_C@
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Configuration mismatch: revision=%u command=%d arguments=%d line=%d\n",obor_profile_build,command_index,argument_case,__LINE__);abort();}}while(0)
static int warnings;
static int warning(const char *format,...) {(void)format;++warnings;return 0;}
#define printf warning
@PARSERS@
@DECLARATIONS@
static s_model model,*newchar=&model;
static struct {int count;char *args[4];} arglist;
static char *filename="fixture",*command,*buf,fnbuf[128];
static ptrdiff_t pos;
static size_t size;
static int handle_txt_include(char *c,void *a,char **f,char *n,char **b,ptrdiff_t *p,size_t *s) {
 (void)c;(void)a;(void)f;(void)n;(void)b;(void)p;(void)s;return 0;
}
@MACROS@
static void apply(int domain,int code) {int line=1;switch(domain){@DISPATCH@}}
static const struct {int domain;const char *name;int code;} commands[]={@COMMANDS@};
static void check(const int *available,int globals) {
 List *lists[]={@CREATE_LISTS@};
 static const float values[3][3]={{0,0,0},{0.5f,0,0},{0.5f,-0.25f,1.5f}};
 for(command_index=0;command_index<@COMMAND_COUNT@;++command_index)
 for(argument_case=0;argument_case<3;++argument_case)
 for(int upper=0;upper<2;++upper) {
  memset(&model,0,sizeof(model));
  @SEED@
  float want[@FIELD_COUNT@];for(int i=0;i<@FIELD_COUNT@;++i)want[i]=17.5f;
  skiptoset=17;want[@SKIP_INDEX@]=17;
  @INT_SEED@
  if(available[command_index])switch(command_index){@EXPECT@}
  char name[64];strcpy(name,commands[command_index].name);
  if(upper)for(char *p=name;*p;++p)*p=(char)toupper((unsigned char)*p);
  command=name;arglist.count=argument_case==0?1:argument_case==1?2:4;
  arglist.args[0]=command;arglist.args[1]="0.5";arglist.args[2]="-0.25";arglist.args[3]="1.5";
  if(commands[command_index].domain==3)arglist.args[1]=argument_case==1?"7":"-3";
  int code=0;switch(commands[command_index].domain){@LOOKUP@}
  assert(code==(available[command_index]?commands[command_index].code:0));
  warnings=0;apply(commands[command_index].domain,code);
  assert(warnings==!available[command_index]);
  @COMPARE@
  @CONSTRUCTOR@
  assert(newchar->jumpspeed==(globals?default_model_jumpspeed:-1));
  assert(newchar->jumpheight==(globals?default_model_jumpheight:4));
  assert(newchar->runjumpheight==(globals?default_model_jumpheight:4));
  assert(newchar->grabdistance==(globals?default_model_grabdistance:36));
  assert(newchar->throwdist==(globals?default_model_jumpheight*0.625f:2.5f));
 }
 for(int i=0;i<@DOMAIN_COUNT@;++i)freeCommandList(lists[i]);
}
int main(void) {@CHECKS@return 0;}
'''.replace('@LOWERCASE@', function((root / 'source/utils.c').read_text(), 'lc'))
           .replace('@LIST_C@', json.dumps(str(root / 'source/scriptlib/List.c')))
           .replace('@COMMANDS_C@', json.dumps(str(root / 'source/gamelib/commands.c')))
           .replace('@PARSERS@', '\n'.join(function(text, name) for name in ('isNumeric','getValidInt','getValidFloat')))
           .replace('@DECLARATIONS@', '\n'.join(('int ' if name in integer_fields else 'float ')+name+';' for name in fields if '[' not in name and '->' not in name and name != 'skiptoset') +
                '\nfloat default_model_dropv[3];int skiptoset;')
           .replace('@MACROS@', '\n'.join(re.search(r'(?m)^#define '+name+r'\(z\)[^\r\n]*', text)[0]
                for name in ('GET_ARG','GET_INT_ARG','GET_FLOAT_ARG')))
           .replace('@DISPATCH@', '\n'.join(dispatch)).replace('@LOOKUP@', '\n'.join(lookup))
           .replace('@COMMANDS@', '\n'.join(cases)).replace('@COMMAND_COUNT@', str(len(commands)))
           .replace('@FIELD_COUNT@', str(len(fields))).replace('@SKIP_INDEX@', str(fields.index('skiptoset')))
           .replace('@SEED@', '\n'.join(field+('=17;' if field in integer_fields else '=17.5f;') for field in fields if field != 'skiptoset'))
           .replace('@INT_SEED@', '\n'.join('want[%d]=17;' % fields.index(field) for field in integer_fields))
           .replace('@CREATE_LISTS@', ','.join(item[2]+'()' for item in domain_info.values()))
           .replace('@DOMAIN_COUNT@', str(len(domain_info)))
           .replace('@EXPECT@', expect)
           .replace('@COMPARE@', '\n'.join('assert(%s==want[%d]);' % (field, i) for i, field in enumerate(fields)))
           .replace('@CONSTRUCTOR@', '\n'.join(constructor)).replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_model_drawmethod_arguments_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-model-drawmethod-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3729, 3730, 3731, 3770, 3771}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] in ('3741', '3842') and 3666 <= revision <= 3773:
                self.assertIn(revision, revisions)
        for engine in ('3741', '3842'):
            root = ROOT / 'src/engines' / engine
            text = (root / 'openbor.c').read_text()
            loader = function(text, 'load_cached_model')
            label = 'case CMD_MODEL_DRAWMETHOD:'
            self.assertEqual(loader.count(label), 1)
            tail = loader.split(label, 1)[1]
            end = re.search(r'\n[ \t]*case CMD_MODEL_\w+:', tail)
            self.assertIsNotNone(end)
            command_body = tail[:end.start()]
            fields = fixture['fields'] + fixture['extra_fields'].get(engine, [])
            initial = []
            for seed in fixture['seeds']:
                initial.append('{' + ','.join(str(seed[name]) for name in fields) + '}')
            inputs = []
            for args in fixture['inputs']:
                inputs.append('{%d,{%s}}' % (len(args) + 1,
                    ','.join(json.dumps(s) for s in ['drawmethod', *args])))
            expectations = []
            contract_ids = {}
            for key, cases in fixture['contracts'].items():
                if not any(row['engine'] == engine and row['contract'] == key for row in rows):
                    continue
                contract_ids[key] = len(contract_ids)
                entries = []
                for case in cases:
                    color = case['color_inputs']
                    self.assertIn(len(color), (0, 3))
                    entries.append('{%d,%d,{%s},%d,%d,{%s},%d}' % (
                        case['seed'], case['input'],
                        ','.join(str(case['fields'][name]) for name in fields),
                        case['warnings'], int(bool(color)),
                        ','.join(map(str, color or [0, 0, 0])),
                        -1 if case['blend_mark'] is None else case['blend_mark']))
                expectations.append('{' + ','.join(entries) + '}')
            checks = []
            for row in rows:
                if row['engine'] != engine:
                    continue
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertRegex(row['command_sha256'], r'^[0-9a-f]{64}$')
                checks.append('obor_profile_build=%d;check(%d);' % (
                    row['revision'], contract_ids[row['contract']]))
            macro_source = text + '\n' + (root / 'openbor.h').read_text()
            macros = '\n'.join(re.search(r'(?m)^#define '+name+r'\(z\)[^\r\n]*', macro_source)[0]
                for name in ('GET_ARG', 'GET_INT_ARG', 'GET_FLOAT_ARG'))
            parsers = '\n'.join(function(text, name) for name in (
                'isNumeric', 'getValidInt', 'getValidFloat', 'parsecolor'))
            includes = [root, ROOT / 'src/port/libretro', ROOT / 'src/glue', root / 'source',
                        *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            flags = ['-std=gnu11', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+engine,
                     '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                     '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                     '-Wno-error=sign-compare', '-Wno-error=misleading-indentation']
            # The original signed one-bit flag stores 1 as -1. Keep that
            # value and check it; Clang diagnoses the native assignment.
            flags += ['-Wno-error=pragma-pack',
                      '-Wno-error=single-bit-bitfield-constant-conversion'] if 'clang' in version.lower() else []
            flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
            with self.subTest(engine=engine):
                native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Drawmethod mismatch: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static unsigned test_case;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int warnings,color_calls,color_inputs[3];
static int warning(const char *format,...) {(void)format;++warnings;return 0;}
int _makecolour(int r,int g,int b) {
 ++color_calls;color_inputs[0]=r;color_inputs[1]=g;color_inputs[2]=b;return 37;
}
#define printf warning
@PARSERS@
#undef printf
static struct {int count;char *args[11];} arglist;
static char *filename="fixture",*command="drawmethod";
static char *value;
static s_drawmethod drawmethod;
static int blendfx[8],blendfx_is_set;
int obor_profile_blend_count(void) {return obor_profile_build==3730?7:6;}
@MACROS@
static void apply(void) {switch(0){case 0:@COMMAND_BODY@}}
static const long long seeds[][ @FIELD_COUNT@ ]={@INITIAL@};
static const struct {int count;char *args[11];} inputs[]={@INPUTS@};
struct expected {int seed,input;long long fields[@FIELD_COUNT@];int warnings,color_calls,color[3],blend_mark;};
static const struct expected expected[][ @CASES@ ]={@EXPECTED@};
static void check(int contract) {
 for(test_case=0;test_case<@CASES@;++test_case)
 for(blendfx_is_set=0;blendfx_is_set<=1;++blendfx_is_set) {
  const struct expected *want=&expected[contract][test_case];
  memset(&drawmethod,0,sizeof(drawmethod));
  @SEED_FIELDS@
  arglist.count=inputs[want->input].count;
  for(int i=0;i<arglist.count;++i)arglist.args[i]=inputs[want->input].args[i];
  memset(blendfx,0,sizeof(blendfx));
  warnings=color_calls=0;memset(color_inputs,0,sizeof(color_inputs));apply();
  @COMPARE@
  assert(warnings==want->warnings && color_calls==want->color_calls);
  assert(!memcmp(color_inputs,want->color,sizeof(color_inputs)));
  for(int i=0;i<8;++i)assert(blendfx[i]==(!blendfx_is_set && i==want->blend_mark));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@PARSERS@', parsers).replace('@MACROS@', macros)
               .replace('@COMMAND_BODY@', command_body)
               .replace('@FIELD_COUNT@', str(len(fields)))
               .replace('@INITIAL@', ','.join(initial)).replace('@INPUTS@', ','.join(inputs))
               .replace('@CASES@', str(len(fixture['inputs']) * len(fixture['seeds'])))
               .replace('@EXPECTED@', ','.join(expectations))
               .replace('@SEED_FIELDS@', '\n'.join('drawmethod.%s=seeds[want->seed][%d];' % (name, i)
                    for i, name in enumerate(fields)))
               .replace('@COMPARE@', '\n'.join('assert((long long)drawmethod.%s==want->fields[%d]);' % (name, i)
                    for i, name in enumerate(fields)))
               .replace('@CHECKS@', '\n'.join(checks)), includes, flags)

    def test_aiattack_constants_follow_each_source_namespace_and_value(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-aiattack-constant-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision']: row for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertIsNone(revisions[3675]['constants']['AIATTACK1_ALWAYS'])
        self.assertEqual(revisions[3676]['constants']['AIATTACK1_ALWAYS'], 8)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        root = ROOT / 'src/engines/3741'
        text = (root / 'openborscript.c').read_text()
        mapper = function(text, 'mapstrings_transconst')
        entry = function(text, 'openbor_transconst')
        start = text.index('#define ICMPCONST(')
        macro = text[start:text.index('void mapstrings_transconst(', start)]
        constants = set(re.findall(r'ICMPCONST\((\w+)\)', mapper))
        assessed = tuple(rows[0]['constants'])
        definitions = []
        header = (root / 'openbor.h').read_text()
        for name in assessed:
            match = re.search(r'(?m)^#define\s+' + name + r'\s+(0x[0-9A-Fa-f]+|[0-9]+)', header)
            self.assertIsNotNone(match)
            definitions.append('#define %s %s' % (name, match[1]))
        # Only the declared AI namespace is assessed; unrelated constant
        # values supply neutral definitions for the complete mapper body.
        definitions += ['#define '+name+' 0' for name in sorted(constants -
            set(assessed) - {'VT_EMPTY', 'VT_INTEGER', 'VT_STR'})]
        definitions += ['#define MAX_ATKS 16'] if 'MAX_ATKS' not in constants else []
        definitions += ['#define STA_ATKS 6'] if 'STA_ATKS' not in constants else []
        arrays = sorted(set(re.findall(r'\b(anim\w+)\[', entry)))
        definitions += ['static int '+name+'[1];' for name in arrays]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key in ('mapper_sha256', 'entry_sha256'):
                self.assertRegex(row[key], r'^[0-9a-f]{64}$')
            values = [row['constants'][name] for name in assessed]
            values += [row['constants']['AIATTACK1_ALWAYS'], None]
            checks.append('obor_profile_build=%d;check((const int[]){%s});' %
                (row['revision'], ','.join(str(value if value is not None else -1) for value in values)))
        names = list(assessed) + ['aiattack1_always', 'SYNTHETIC_UNKNOWN_AI']
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef long LONG;
typedef int HRESULT;
enum {VT_EMPTY,VT_INTEGER,VT_STR};
typedef struct {int vt;LONG lVal;int strVal;} ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define stricmp strcasecmp
#define strnicmp strncasecmp
static uint32_t obor_profile_build;
static const char *names[]={NAMES};
static char *StrCache_Get(int index) {
 assert(index>=0 && (unsigned)index<sizeof(names)/sizeof(*names));return (char*)names[index];
}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;v->lVal=0;}
static void ScriptVariant_Clear(ScriptVariant *v) {memset(v,0,sizeof(*v));}
DEFINITIONS
MACRO
MAPPER
ENTRY
static void check(const int *values) {
 for(unsigned i=0;i<sizeof(names)/sizeof(*names);++i) {
  ScriptVariant arg={VT_STR,0,(int)i},result={VT_EMPTY,77,0},*out=&result,*args[]={&arg};
  assert(openbor_transconst(args,&out,1)==S_OK && out==&result);
  if(values[i]>=0)assert(arg.vt==VT_INTEGER && result.vt==VT_INTEGER && result.lVal==values[i]);
  else assert(arg.vt==VT_STR && arg.strVal==(int)i && result.vt==VT_EMPTY);
 }
 ScriptVariant arg={VT_INTEGER,99,0},result={0},*out=&result,*args[]={&arg};
 assert(openbor_transconst(args,&out,1)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==99);
}
int main(void) {CHECKS return 0;}
'''.replace('NAMES', ','.join(json.dumps(name) for name in names))
           .replace('DEFINITIONS', '\n'.join(definitions)).replace('MACRO', macro)
           .replace('MAPPER', mapper).replace('ENTRY', entry).replace('CHECKS', '\n'.join(checks)),
           extra_flags=('-Wno-unused-variable',))

    def test_sample_arguments_defaults_payload_and_result_per_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-sample-call-contracts.json')
        rows = fixture['sources']
        by_revision = {row['revision']: row for row in rows}
        self.assertEqual(len(rows), len(by_revision))
        self.assertTrue(by_revision[3705]['exact_six_arguments'])
        self.assertFalse(by_revision[3706]['exact_six_arguments'])
        self.assertFalse(by_revision[3837]['returns_channel'])
        self.assertTrue(by_revision[3838]['returns_channel'])
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] in ('3741', '3842'):
                revision = int(profile.get('revision', profile['build']))
                self.assertEqual(by_revision[revision]['engine'], profile['engine'])
        for engine in ('3741', '3842'):
            root = ENGINE if engine == ENGINE.name else ROOT / 'src/engines' / engine
            method = function((root / 'openborscript.c').read_text(), 'openbor_playsample')
            checks = []
            for row in rows:
                if row['engine'] != engine:
                    continue
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
                checks.append('obor_profile_build=%d;check(%d,%d);' % (
                    row['revision'], row['exact_six_arguments'], row['returns_channel']))
            native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef long LONG;
typedef int HRESULT;
enum {VT_EMPTY,VT_INTEGER,VT_STR};
typedef struct {int vt;LONG lVal;} ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
static uint32_t obor_profile_build;
static struct {int effectvol;} savedata={41};
static int calls,looped,conversions;
static LONG observed[5];
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
 ++conversions;if(v->vt!=VT_INTEGER)return E_FAIL;*out=v->lVal;return S_OK;
}
void ScriptVariant_ChangeType(ScriptVariant *v,int type) {
 memset(v,0,sizeof(*v));v->vt=type;
}
static int sound_play_sample(int id,unsigned priority,int left,int right,unsigned speed) {
 ++calls;observed[0]=id;observed[1]=priority;observed[2]=left;observed[3]=right;observed[4]=speed;
 return id<0?-1:7;
}
static int sound_loop_sample(int id,unsigned priority,int left,int right,unsigned speed) {
 ++looped;return sound_play_sample(id,priority,left,right,speed);
}
METHOD
static void check(int strict,int returns_channel) {
 for(int count=0;count<=8;++count)for(int id=-1;id<=1;++id)for(int loop=0;loop<=1;++loop) {
  ScriptVariant values[8]={{VT_INTEGER,id},{VT_INTEGER,13},{VT_INTEGER,23},{VT_INTEGER,29},
      {VT_INTEGER,125},{VT_INTEGER,loop},{VT_STR,77},{VT_STR,88}};
  ScriptVariant result={VT_EMPTY,1234},*out=&result,*args[8];
  for(int i=0;i<8;++i)args[i]=values+i;
  calls=looped=conversions=0;memset(observed,0,sizeof(observed));
  int status=openbor_playsample(args,&out,count);
  if(strict && count!=6) {
   assert(status==E_FAIL && out==&result && result.vt==VT_EMPTY && result.lVal==1234);
   assert(!calls && !conversions);continue;
  }
  assert(conversions==(count<6?count:6));
  int effective_id=count?id:-1;
  if(!returns_channel && effective_id<0) {
   assert(status==E_FAIL && !out && !calls);continue;
  }
  assert(status==S_OK && calls==1);
  assert(looped==(count>=6?loop:0));
  assert(observed[0]==effective_id && observed[1]==(count>=2?13:0));
  assert(observed[2]==(count>=3?23:41) && observed[3]==(count>=4?29:41));
  assert(observed[4]==(count>=5?125:100));
  if(returns_channel)
   assert(out==&result && result.vt==VT_INTEGER && result.lVal==(effective_id<0?-1:7));
  else assert(!out && result.vt==VT_EMPTY && result.lVal==1234);
 }
 for(int bad=0;bad<6;++bad) {
  ScriptVariant values[6],result={VT_EMPTY,1234},*out=&result,*args[6];
  for(int i=0;i<6;++i) {values[i]=(ScriptVariant){i==bad?VT_STR:VT_INTEGER,1};args[i]=values+i;}
  calls=looped=conversions=0;
  assert(openbor_playsample(args,&out,6)==E_FAIL && !out && !calls && conversions==bad+1);
 }
}
int main(void) {CHECKS return 0;}
'''.replace('METHOD', method).replace('CHECKS', '\n'.join(checks)))

    def test_playsample_void_integer_results_invalid_ids_and_conversion(self):
        source = (ENGINE / 'openborscript.c').read_text()
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef long LONG;
typedef int HRESULT;
enum { VT_EMPTY, VT_INTEGER, VT_STR };
typedef struct { int vt; LONG lVal; } ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
static uint32_t obor_profile_build;
static struct { int effectvol; } savedata={64};
static int calls,looped;
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) { if(v->vt!=VT_INTEGER)return E_FAIL;*out=v->lVal;return S_OK; }
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) { memset(v,0,sizeof(*v));v->vt=type; }
static int sound_play_sample(int id,unsigned priority,int l,int r,unsigned speed) { (void)priority;(void)l;(void)r;(void)speed;++calls;return id<0?-1:7; }
static int sound_loop_sample(int id,unsigned priority,int l,int r,unsigned speed) { ++looped;return sound_play_sample(id,priority,l,r,speed); }
METHOD
int main(void) {
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(int id=-1;id<=1;++id) for(int loop=0;loop<=1;++loop) {
            ScriptVariant values[6]={{VT_INTEGER,id},{VT_INTEGER,0},{VT_INTEGER,64},
                {VT_INTEGER,64},{VT_INTEGER,100},{VT_INTEGER,loop}};
            ScriptVariant result={0},*out=&result,*args[6];
            for(int i=0;i<6;++i)args[i]=values+i;
            calls=looped=0;int status=openbor_playsample(args,&out,6);
            if(profile<3838) {
                assert(!out);
                assert(status==(id<0?E_FAIL:S_OK));
                assert(calls==(id<0?0:1));
            } else {
                assert(status==S_OK && out==&result && result.vt==VT_INTEGER);
                assert(result.lVal==(id<0?-1:7) && calls==1);
            }
            assert(looped==(calls&&loop?1:0));
            out=&result;values[2].vt=VT_STR;calls=0;
            assert(openbor_playsample(args,&out,6)==E_FAIL && !out && !calls);
        }
    }
}
'''.replace('METHOD', function(source, 'openbor_playsample')))

    def test_native_script_function_namespace_and_valid_results(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-script-function-contracts.json')
        rows = [dict(row, **fixture['contracts'][row['contract']])
                for row in fixture['sources']]
        by_revision = {row['revision']: row for row in rows}
        self.assertEqual(len(rows), len(by_revision))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] in ('3741', '3842'):
                revision = int(profile.get('revision', profile['build']))
                self.assertEqual(by_revision[revision]['engine'], profile['engine'])
        for before, after, name in ((3677, 3678, 'strwidth'),
                (3699, 3700, 'shutdown'), (3703, 3704, 'options'),
                (3833, 3834, 'exit'), (3837, 3838, 'querychannel'),
                (3837, 3838, 'stopchannel')):
            self.assertNotIn(name, by_revision[before]['registered'])
            self.assertIn(name, by_revision[after]['registered'])
        for engine in ('3741', '3842'):
            root = ENGINE if engine == ENGINE.name else ROOT / 'src/engines' / engine
            text = (root / 'openborscript.c').read_text()
            parts = {name: function(text, name) for name in (
                'obor_script_function_available', 'Script_GetFunctionName',
                'Script_LoadSystemFunctions')}
            callbacks = {}
            for name in ('strwidth', 'shutdown', 'options', 'querychannel', 'stopchannel'):
                if re.search(r'(?m)^HRESULT openbor_' + name + r'\(', text):
                    callbacks['openbor_' + name] = function(text, 'openbor_' + name)
            declarations = '\n'.join('static void %s(void) { }' % name
                for name in fixture['names'] if name not in callbacks)
            checks = []
            for row in rows:
                if row['engine'] != engine:
                    continue
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                for key in ('registry_sha256', 'lookup_sha256'):
                    self.assertRegex(row[key], r'^[0-9a-f]{64}$')
                for digest in row['callback_sha256'].values():
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
                entries = ','.join('{%s,(void*)%s}' % (json.dumps(name), symbol)
                    for name, symbol in row['registered'].items())
                queries = ','.join('{%s,(void*)%s}' % (
                    json.dumps(row['lookup'].get(symbol, '<unknown function>')), symbol)
                    for symbol in fixture['names'])
                present = ','.join(str(int(name in row['registered'])) for name in
                    ('strwidth', 'shutdown', 'options', 'querychannel', 'stopchannel'))
                checks.append('''{
 obor_profile_build=%d;Script_LoadSystemFunctions();
 const struct entry expected[]={%s},queries[]={%s};
 assert(used==sizeof(expected)/sizeof(*expected));
 for(unsigned i=0;i<used;++i)
  assert(!strcmp(observed[i].name,expected[i].name) && observed[i].function==expected[i].function);
 for(unsigned i=0;i<sizeof(queries)/sizeof(*queries);++i)
  assert(!strcmp(Script_GetFunctionName(queries[i].function),queries[i].name));
 valid_calls(%s);
}''' % (row['revision'], entries, queries, present))
            native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int HRESULT;
typedef long LONG;
typedef struct {int vt;union {LONG lVal;int strVal;};} ScriptVariant;
enum {VT_EMPTY,VT_INTEGER,VT_STR};
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
#define DEFAULT_SHUTDOWN_MESSAGE "default"
#define HAS_CHANNELS CHANNEL_FLAG
static uint32_t obor_profile_build;
static const char *strings[]={"zero","sample","status"};
static int options_calls,shutdown_status,query_value,stopped,last_cache;
static const char *shutdown_text;
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
 if(v->vt!=VT_INTEGER)return E_FAIL;*out=v->lVal;return S_OK;
}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;}
static char *StrCache_Get(int index) {
 assert(index>=0 && index<3);last_cache=index;return (char*)strings[index];
}
static int font_string_width(int font,char *text) {
 assert(font>=0 && font<2);return font*100+(int)strlen(text);
}
static void options(void) {++options_calls;}
static void shutdown(int status,const char *text) {shutdown_status=status;shutdown_text=text;}
static int sound_query_channel(int channel) {query_value=channel;return channel+17;}
static void sound_stop_sample(int channel) {stopped=channel;}
struct entry {const char *name;void *function;};
static struct entry observed[512];
static unsigned used;
static int theFunctionList;
static void List_Reset(int *list) {assert(list==&theFunctionList);used=0;}
static void List_InsertAfter(int *list,void *function,const char *name) {
 assert(list==&theFunctionList && used<512);
 observed[used++]=(struct entry){name,function};
}
DECLARATIONS
CALLBACKS
METHODS
static void valid_calls(int width,int shutdown_available,int menu,int query,int stop) {
 ScriptVariant first={VT_STR,{.strVal=1}},second={VT_INTEGER,{.lVal=0}};
 ScriptVariant result={0},*out=&result,*arguments[]={&first,&second};
 if(width)for(int font=0;font<2;++font) {
  second.lVal=font;out=&result;last_cache=-1;
  assert(openbor_strwidth(arguments,&out,2)==S_OK && out==&result);
  assert(result.vt==VT_INTEGER && result.lVal==font*100+6 && last_cache==1);
 }
 if(menu) {
  options_calls=0;out=&result;
  assert(openbor_options(arguments,&out,0)==S_OK && !out && options_calls==1);
 }
 if(shutdown_available)for(int count=0;count<=2;++count) {
  first=(ScriptVariant){VT_INTEGER,{.lVal=2}};
  second=(ScriptVariant){VT_STR,{.strVal=1}};
  out=&result;shutdown_status=-1;shutdown_text=NULL;
  assert(openbor_shutdown(arguments,&out,count)==S_OK && !out);
  assert(shutdown_status==(count?2:0));
  /* Compare the source-defined cache selection, separately from core exit. */
  assert(!strcmp(shutdown_text,count>1?strings[2]:DEFAULT_SHUTDOWN_MESSAGE));
 }
#if HAS_CHANNELS
 first=(ScriptVariant){VT_INTEGER,{.lVal=2}};
 if(query) {
  out=&result;result=(ScriptVariant){0};query_value=-1;
  assert(openbor_querychannel(arguments,&out,1)==E_FAIL && !out);
  assert(query_value==2 && result.vt==VT_INTEGER && result.lVal==19);
 }
 if(stop) {
  out=&result;stopped=-1;
  assert(openbor_stopchannel(arguments,&out,1)==E_FAIL && !out && stopped==2);
 }
#else
 (void)query;(void)stop;
#endif
}
int main(void) { CHECKS return 0; }
'''.replace('CHANNEL_FLAG', str(int('openbor_querychannel' in callbacks)))
               .replace('DECLARATIONS', declarations)
               .replace('CALLBACKS', '\n'.join(callbacks.values()))
               .replace('METHODS', '\n'.join(parts.values()))
               .replace('CHECKS', '\n'.join(checks)),
               extra_flags=('-Wno-unused-function', '-Wno-unused-parameter',
                            '-Wno-misleading-indentation'))

    def test_animation_cmd_text_matches_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-animation-cmd-contracts.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({(r['revision'], r['flag']) for r in rows}))
        covered = {r['revision'] for r in rows}
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, 3812, 3813, 3820, 3821, 3822, 3823}) <= covered)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), covered)
        source = (ENGINE / 'openbor.c').read_text()
        method = function(source, 'load_cached_model')
        self.assertEqual(method.count('case CMD_MODEL_AT_CMD:'), 1)
        case = method.split('case CMD_MODEL_AT_CMD:', 1)[1].split('default:', 1)[0]
        first = re.search(r'static const char(?:\*\s*|\s+)pre_text', method)
        self.assertIsNotNone(first)
        constants = method[first.start():method.index('modelCommands cmd;', first.start())]
        helpers = '\n'.join(function(source, name) for name in (
            'obor_animation_cmd_grouped', 'obor_animation_cmd_returns'))
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['cmd_body_sha256'], r'^[0-9a-f]{64}$')
            calls = ''.join('curframe=%d;arguments[1]=%s;generate();\n' %
                (cmd['frame'], json.dumps(cmd['name'])) for cmd in fixture['commands'])
            checks.append('reset(%d,%d);%scheck(%s);' % (
                row['revision'], row['flag'], calls, json.dumps(row['expected'])))
        native(r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint32_t obor_profile_build;
static int no_cmd_compatible,ani_id,script_id,frm_id,curframe,j;
static char storage[8192],*scriptbuf=storage,*value,*shutdownmessage;
static size_t scriptlen,sbsize;
static char namebuf[256],*arguments[]={"@cmd","alpha",""};
static struct {int index;} animation={7},*newanim=&animation;
#define GET_ARG(i) arguments[(i)]
#define strclen(s) strlen(s)
CONSTANTS
HELPERS
static void buffer_append(char **out,const char *text,int limit,size_t *capacity,size_t *length) {
    size_t n=strlen(text);assert(limit>0 && *out==storage && *length+n<*capacity);
    memcpy(*out+*length,text,n+1);*length+=n;
}
static void generate(void) {
    switch(0) {case 0: CASE}
lCleanup:
    assert(!shutdownmessage);
}
static void reset(uint32_t revision,int flag) {
    obor_profile_build=revision;no_cmd_compatible=flag;
    script_id=frm_id=-1;ani_id=0;scriptlen=0;sbsize=sizeof(storage);
    *storage=0;shutdownmessage=NULL;
}
static void check(const char *expected) {
    size_t j=0;
    for(size_t i=0;storage[i];++i)
        if(!isspace((unsigned char)storage[i])) {
            assert(expected[j] && storage[i]==expected[j]);++j;
        }
    assert(!expected[j]);
}
int main(void) { CHECKS return 0; }
'''.replace('CONSTANTS', constants).replace('HELPERS', helpers)
           .replace('CASE', case).replace('CHECKS', '\n'.join(checks)),
           extra_flags=('-Wno-unused-const-variable',))

    def test_nested_interpreter_and_exit_registration_boundaries(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-nested-execution-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, 3805, 3806, 3812, 3813,
                         3833, 3834, 3835, 3836}) <= revisions)
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-nested-execution-contracts.json', json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            for key, boundary in (('nested_suppression', 3806), ('nested_snapshot', 3813),
                                  ('snapshot_option', 3836), ('exit_registered', 3834)):
                self.assertEqual(row[key], row['revision'] >= boundary)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        source = (ENGINE / 'openborscript.c').read_text()
        model_source = (ENGINE / 'openbor.c').read_text()
        cmd_helpers = '\n'.join(function(model_source, name) for name in (
            'obor_animation_cmd_grouped', 'obor_animation_cmd_returns'))
        registration = function(source, 'Script_LoadSystemFunctions')
        match = re.search(r'if\(obor_profile_build >= 3834\)\s*List_InsertAfter\([^;]*system_exit[^;]*;', registration)
        self.assertIsNotNone(match)
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#define FALSE 0
#define SUCCEEDED(x) ((x)>=0)
static uint32_t obor_profile_build;
typedef struct { int bReset,cursor; struct { const char *name; } theSymbolTable; } Interpreter;
typedef struct { Interpreter *pinterpreter; const char *comment; } Script;
static Script *pcurrentscript;
static int no_cmd_compatible,no_nested_script,executions;
CMD_HELPERS
static void Interpreter_Reset(Interpreter *v) { v->cursor=0;v->bReset=1; }
static int Interpreter_EvaluateImmediate(Interpreter *v) { assert(v->cursor==0);v->cursor=9;v->bReset=1;++executions;return 0; }
static void shutdown(int code,const char *format,...) { (void)code;(void)format;assert(0); }
static void system_exit(void) { }
static int theFunctionList,registrations;
static void List_InsertAfter(int *list,void *func,const char *name) { assert(list==&theFunctionList && func==(void*)system_exit && !strcmp(name,"exit"));++registrations; }
METHOD
static void register_exit(void) { REGISTRATION }
int main(void) {
    Script outer={0},script={0}; Interpreter interpreter;
    script.pinterpreter=&interpreter;
    const unsigned profiles[]={PROFILES};
    for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);++i) {
        unsigned profile=profiles[i];
        obor_profile_build=profile;registrations=0;register_exit();
        assert(registrations==(profile>=3834));
        for(int nested=0;nested<=1;++nested) for(int compatible=0;compatible<=1;++compatible)
        for(int blocked=0;blocked<=1;++blocked) {
            interpreter=(Interpreter){nested,41,{"synthetic"}};
            no_cmd_compatible=compatible;no_nested_script=blocked;executions=0;
            pcurrentscript=&outer;
            assert(Script_Execute(&script)==1 && pcurrentscript==&outer);
            if(profile>=3806 && nested && blocked) assert(executions==0 && interpreter.cursor==41);
            else if(nested && ((profile>=3813 && profile<3836) || (profile>=3836 && compatible)))
                assert(executions==1 && interpreter.cursor==41 && interpreter.bReset==1);
            else assert(executions==1 && interpreter.cursor==9 && interpreter.bReset==!(profile>=3836 && nested));
            assert(obor_animation_cmd_grouped()==(profile>=3813 && (profile<3823 || compatible)));
            assert(obor_animation_cmd_returns()==(profile>=3821 && (profile<3823 || compatible)));
        }
    }
}
'''.replace('METHOD', function(source, 'Script_Execute')).replace('REGISTRATION', match.group())
           .replace('CMD_HELPERS', cmd_helpers)
           .replace('PROFILES', ','.join(str(row['revision']) for row in rows)))


if __name__ == '__main__':
    unittest.main()
