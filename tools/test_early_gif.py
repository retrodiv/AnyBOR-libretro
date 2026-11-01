"""Check complete native GIF decoding against own-source pixel contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class EarlyGifTests(unittest.TestCase):
    def test_full_playback_rgb_palette_clock_keys_and_cleanup(self):
        path = Path(__file__).parent/'fixtures/profile-early-gif-playback.json'
        fixture = load_contract_fixture(path)
        rows = fixture['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT/'src/engines'/fixture['engine']))
        core = (engine/'openbor.c').read_text()
        screen = (engine/'source/gamelib/screen.c').read_text()
        color = (engine/'source/gamelib/pixelformat.c').read_text()
        buffers = {}

        def array(hexadecimal):
            raw = bytes.fromhex(hexadecimal)
            self.assertLessEqual(len(raw), 16384)
            if raw not in buffers:
                buffers[raw] = 'data_%d' % len(buffers)
            return buffers[raw]

        def integers(values):
            return '{'+','.join(map(str, values or [0]))+'}'

        media = ['{%s,%d}' % (array(m['wire']), len(bytes.fromhex(m['wire']))) for m in fixture['media']]
        cases = []
        for case in fixture['scenarios']:
            epochs = []
            self.assertEqual(len(case['results']), len(fixture['epochs']))
            for modes in case['results']:
                self.assertEqual([r['hardware'] for r in modes], [0, 2, 4])
                results = []
                for r in modes:
                    self.assertLessEqual(r['updates'], 3)
                    self.assertEqual(r['updates'], len(r['pictures']))
                    fields = [str(r[k]) for k in ['hardware', 'pixelformat', 'status', 'stop',
                              'updates', 'vwait', 'standard', 'palette_calls']]
                    fields += [array(r['palette_prefix']), str(len(bytes.fromhex(r['palette_prefix']))),
                               str(r['sound_calls']), str(r['queue_calls']), integers(r['alloc_formats']),
                               str(len(r['alloc_formats'])), str(r['allocated']), str(r['freed']),
                               integers(r['open_roles']), str(len(r['open_roles'])),
                               '{'+','.join(integers(v) for v in (r['pictures'] or [[0]*8]))+'}',
                               str(r['time']), str(r['newtime'])]
                    results.append('{'+','.join(fields)+'}')
                epochs.append('{'+','.join(results)+'}')
            fields = [json.dumps(case['name']), json.dumps(case['filename']) if case['filename'] is not None else 'NULL',
                      '{'+','.join(json.dumps(v) if v is not None else 'NULL' for v in case['names'])+'}']
            fields += [str(case[k]) for k in ['direct', 'present_channels', 'main_present', 'bad_main',
                       'bad_channel', 'alloc_fail', 'variant', 'noskip', 'key_frame', 'sticky_key', 'audio', 'x', 'y']]
            cases.append('{'+','.join(fields)+',{'+','.join(epochs)+'}}')
        allocations = function(screen, 'allocscreen')
        allocations = re.sub(r'\ballocscreen\b', 'native_allocscreen', allocations, count=1)
        allocations = 'static '+allocations+'\n'+function(screen, 'freescreen')+'\n'+function(screen, 'clearscreen')
        declarations = '\n'.join('static const unsigned char %s[]={%s};' %
                                  (name, ','.join(map(str, raw)) if raw else '0') for raw, name in buffers.items())
        program = (path.parent/'early_gif_playback.c').read_text()
        for key, value in dict(COLORS='\n'.join(function(color, name) for name in ['colour16', 'colour32']),
                               DATA=declarations, MEDIA=',\n'.join(media), CASES=',\n'.join(cases),
                               ALLOCATORS=allocations, MAKECOLOR=function(core, '_makecolour'),
                               DECODER=json.dumps(str(engine/'source/gamelib/anigif.c')),
                               CALLERS='\n'.join(function(core, name) for name in
                                   ['obor_playgif_legacy', 'update_backbuffer', 'playgif']),
                               CHECKS='\n'.join('check(%d,%d);' % (r['revision'], r['era']) for r in rows)).items():
            program = program.replace('@'+key+'@', value)
        with tempfile.TemporaryDirectory(prefix='early-gif-playback-') as directory:
            unit = Path(directory)/'probe.c'
            binary = unit.with_suffix('')
            unit.write_text(program)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-Dstricmp=strcasecmp', '-fsigned-char', '-fcommon',
                     '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations']
            includes = [engine/'source/gamelib', ROOT/'src/port/libretro', ROOT/'src/glue', engine/'source']
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            build = subprocess.run(compiler+flags+['-I'+str(p) for p in includes]+
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout+build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            self.assertIn('early_gif_playback=1', run.stdout)
            if os.environ.get('OBOR_GIF_PLAYBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_GIF_PLAYBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=compiler, contexts=len(rows), scenarios=len(fixture['scenarios']),
                    hardware_formats=3, epochs=len(fixture['epochs']), source_bytes=len(program.encode()),
                    source_sha256=hashlib.sha256(program.encode()).hexdigest(), stdout=run.stdout,
                    scope=fixture['scope']), indent=2)+'\n')

    def test_native_decoder_palettes_pixels_wire_and_context_boundaries(self):
        path = Path(__file__).parent/'fixtures/profile-early-gif-decoder.json'
        fixture = load_contract_fixture(path)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT/'src/engines'/fixture['engine']))
        colors = (engine/'source/gamelib/pixelformat.c').read_text()
        colors = '\n'.join(function(colors, name) for name in ['colour16', 'colour32'])
        buffers = {}

        def array(hexadecimal):
            value = bytes.fromhex(hexadecimal)
            self.assertLessEqual(len(value), 8192)
            if value not in buffers:
                buffers[value] = 'data_%d' % len(buffers)
            return buffers[value]

        media = []
        for item in fixture['media']:
            self.assertTrue(0 < item['width']*item['height'] <= 256)
            media.append('{%s,%d,%d,%d}' %
                         (array(item['wire']), len(bytes.fromhex(item['wire'])), item['width'], item['height']))
        cases = []
        for case in fixture['scenarios']:
            epochs = []
            self.assertEqual(len(case['results']), len(fixture['epochs']))
            for modes in case['results']:
                self.assertEqual([r['format'] for r in modes], [0, 1, 2, 4])
                expectations = []
                for r in modes:
                    fields = [str(r[k]) for k in ['format', 'open', 'code', 'delay', 'position',
                                                  'live', 'bitdepth', 'colours', 'transparent']]
                    fields += [array(r[k]) for k in ['palette', 'pixels']]
                    fields += [str(len(bytes.fromhex(r[k]))) for k in ['palette', 'pixels']]
                    expectations.append('{'+','.join(fields)+'}')
                epochs.append('{'+','.join(expectations)+'}')
            fields = [str(case[k]) for k in ['media', 'noblacken', 'palette_present', 'x', 'y']]
            cases.append('{'+','.join(fields)+',{'+','.join(epochs)+'}}')
        declarations = '\n'.join('static const unsigned char %s[]={%s};' %
                                  (name, ','.join(map(str, raw))) for raw, name in buffers.items())
        program = (path.parent/'early_gif_decoder.c').read_text()
        for key, value in dict(COLORS=colors, DATA=declarations, MEDIA=',\n'.join(media),
                               CASES=',\n'.join(cases), DECODER=json.dumps(str(engine/'source/gamelib/anigif.c')),
                               CHECKS='\n'.join('check(%d,%d);' % (r['revision'], r['era']) for r in rows)).items():
            program = program.replace('@'+key+'@', value)
        with tempfile.TemporaryDirectory(prefix='early-gif-') as directory:
            unit = Path(directory)/'probe.c'
            binary = unit.with_suffix('')
            unit.write_text(program)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            includes = [engine/'source/gamelib', ROOT/'src/port/libretro', ROOT/'src/glue', engine/'source']
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-fsigned-char', '-fcommon',
                     '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations']
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            build = subprocess.run(compiler+flags+['-I'+str(p) for p in includes]+
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout+build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            self.assertIn('early_gif_decoder=1', run.stdout)
            if os.environ.get('OBOR_GIF_DECODER_OBSERVATIONS'):
                Path(os.environ['OBOR_GIF_DECODER_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=compiler, contexts=len(rows), scenarios=len(fixture['scenarios']),
                    formats=4, epochs=len(fixture['epochs']), source_bytes=len(program.encode()),
                    source_sha256=hashlib.sha256(program.encode()).hexdigest(), stdout=run.stdout,
                    scope=fixture['scope']), indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
