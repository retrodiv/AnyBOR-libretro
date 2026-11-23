"""Check GIF decoding, playback, and script-visible stream operations.

The native functions use a deterministic file and screen provider. Each probe
keeps the engine's decoder records, color conversion, and release paths.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, remove_horizontal_bound=False,
            template='gif_memory_bounds.c.in', inputs=None):
    decoder = (engine / 'source/gamelib/anigif.c').read_text(encoding='latin1')
    stream = 'info->info[n]' in decoder
    if remove_horizontal_bound:
        bound = 'byte < width && '
        if decoder.count(bound) != 1:
            raise ValueError('One native horizontal pixel guard required')
        decoder = decoder.replace(bound, '', 1)
    screen = (engine / 'source/gamelib/screen.c').read_text(encoding='latin1')
    colors = (engine / 'source/gamelib/pixelformat.c').read_text(encoding='latin1')
    values = dict(
        STREAM='1' if stream else '0', DECODER=decoder,
        COLORS='\n'.join(function(colors, name) for name in ('colour16', 'colour32')),
        FREE_SCREEN=function(screen, 'freescreen'),
        RAW='obor_profile_build < 3477' if engine.name == '3400' else '0',
        OPEN='anigif_open_ex' if 'int anigif_open_ex(' in decoder else 'anigif_open',
        CLOSE='anigif_close_ex' if 'void anigif_close_ex(' in decoder else 'anigif_close',
        DECODE='anigif_decode_ex' if 'int anigif_decode_ex(' in decoder else 'anigif_decode',
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    values.update(inputs or {})
    text = (HERE / 'gif_decoder_probe.c.in').read_text() + (HERE / template).read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved GIF dependency')
    return text


class GifMemoryBoundsTests(unittest.TestCase):
    def test_legacy_pixel_formats_and_byte_aligned_palettes_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            if 'info->info[n]' in (engine / 'source/gamelib/anigif.c').read_text(encoding='latin1'):
                continue
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, '#define PIXEL_FORMAT_ONLY 1\n'+program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 1000*len(profiles))

    def test_native_pixels_boundaries_names_and_owned_cleanup_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 100*len(profiles))

    def test_missing_pixel_bound_fails_a_logical_result_in_spare_backing(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3400'
        profile = next(p for p in pin['profiles'] if p['build'] == '3400')
        text = '#define PIXEL_BOUND_ONLY 1\n'+program(engine, [profile], remove_horizontal_bound=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pixels_match', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


class ForwardGifDecoderTests(unittest.TestCase):
    def test_previous_decoder_keeps_its_legacy_pixels(self):
        engine = ROOT / 'src/engines/3842'
        profiles = [dict(build='3842'), dict(build='3869')]
        result = run_native(engine, program(engine, profiles))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'PASS')
        self.assertEqual(value['profiles'], len(profiles))

    def test_stream_frames_and_playback_match_original_profiles(self):
        fixture = load_contract_fixture(HERE / 'fixtures/profile-forward-gif-stream.json')
        engine = ROOT / 'src/engines' / fixture['engine']
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        rows = {row['revision']: row for row in fixture['sources']}
        self.assertEqual(len(rows), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= rows.keys())
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        caller = function(core, 'playgif')
        player = function(core, 'obor_play_streamed_gif')
        self.assertRegex(caller, r'if\(obor_profile_build >= 3870u\)\s*return obor_play_streamed_gif\(')
        for profile in contract_profiles(fixture, pin['profiles']):
            revision = int(profile.get('revision', profile['build'].split('-')[0]))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, rows)
        for revision, row in rows.items():
            with self.subTest(revision=revision):
                profiles = [dict(build=str(revision), revision=revision)]
                native = run_native(engine, program(engine, profiles,
                    template='gif_stream_contract.c.in', inputs={'PLAYER': player}))
                self.assertEqual(native.returncode, 0, native.stderr)
                expected = fixture['snapshots'][row['sequence']] + fixture['playback_snapshots'][row['playback_sequence']]
                self.assertEqual(native.stdout.splitlines(), expected)


class ForwardGifScriptTests(unittest.TestCase):
    fixture_path = HERE / 'fixtures/profile-forward-gif-script.json'

    def test_stream_calls_return_original_results_and_release_the_stream(self):
        fixture = load_contract_fixture(self.fixture_path)
        engine = ROOT / 'src/engines' / fixture['engine']
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertIn(fixture['query_boundary'], revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(fixture, pin['profiles']):
            revision = int(profile.get('revision', profile['build'].split('-')[0]))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        scriptlib = engine / 'source/scriptlib'
        script = (engine / 'openborscript.c').read_text(encoding='latin1')
        variants = (scriptlib / 'ScriptVariant.c').read_text(encoding='latin1')
        methods = ('_freeheapnode', 'system_free', 'Script_Global_Clear', 'obor_script_gif_handle',
                   'openbor_openanigif', 'openbor_decodeanigif', 'openbor_getanigifinfo')
        inputs = dict(LIST=(scriptlib / 'List.c').read_text(encoding='latin1'),
                      VARIANTS='\n'.join(function(variants, name) for name in
                                        ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
                      CALLS='\n'.join(function(script, name) for name in methods))
        for row in fixture['sources']:
            revision = row['revision']
            with self.subTest(revision=revision):
                program_text = program(engine, [dict(build=str(revision), revision=revision)],
                    template='gif_script_contract.c.in', inputs=inputs)
                result = run_native(engine, program_text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), fixture['snapshots'][row['sequence']])

    def test_registry_and_reverse_names_match_the_boundary(self):
        fixture = load_contract_fixture(self.fixture_path)
        engine = ROOT / 'src/engines' / fixture['engine']
        script = (engine / 'openborscript.c').read_text(encoding='latin1')
        registry = '\n'.join(function(script, name) for name in
            ('obor_script_function_available', 'Script_GetFunctionName', 'Script_LoadSystemFunctions'))
        names = fixture['registry_names']
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(re.fullmatch(r'[a-z]+', name) for name in names))
        symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*\(*\s*(\w+)', registry)))
        self.assertTrue(set('openbor_' + name for name in names) <= set(symbols))
        stubs = '\n'.join(f'static void {name}(void) {{ unexpected = {i}; abort(); }}'
                          for i, name in enumerate(symbols, start=1))
        entries = ',\n'.join(f'    {{ "{name}", (void *)openbor_{name}, 0 }}' for name in names)
        contexts = fixture['registry_sources']
        revisions = {row['revision'] for row in contexts}
        self.assertEqual(len(revisions), len(contexts))
        self.assertTrue(set(fixture['registry_boundary_controls']) <= revisions)
        template = (HERE / 'gif_script_registry.c.in').read_text()
        for row in contexts:
            with self.subTest(revision=row['revision']):
                values = dict(STUBS=stubs, ENTRIES=entries, REGISTRY=registry, REVISION=f"{row['revision']}u")
                code = re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)
                result = run_native(engine, code)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), row['observations'])


if __name__ == '__main__':
    unittest.main()
