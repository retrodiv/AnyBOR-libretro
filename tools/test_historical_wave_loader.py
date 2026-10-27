"""Check each source-defined WAV read/length/padding contract safely.

Actual prepared loader bodies run against bounded authored packfile fixtures.
These checks do not execute the mixer or establish audible/gameplay acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from historical_wave_loader import render_wave
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-wave-loader-contracts.json'


def one(source, pattern):
    matches = list(re.finditer(pattern, source, re.M))
    if len(matches) != 1:
        raise ValueError('One exact native WAV source component required')
    return matches[0][0]


def source_parts(engine):
    root = SOURCE / 'src/engines' / engine / 'source/gamelib'
    code = (root / 'soundmix.c').read_text()
    types = (root / 'types.h').read_text()
    return dict(loadwave=function(code, 'loadwave'),
                sample=one(code, r'^[ \t]*typedef\s+struct[ \t]*\{[^{}]*\}\s*samplestruct\s*;'),
                constants='\n'.join(one(code, r'^#[ \t]*define[ \t]+'+name+r'\b[^\r\n]*')
                    for name in ('HEX_RIFF','HEX_WAVE','HEX_fmt','HEX_data','FMT_PCM','MAX_SOUND_LEN')),
                types='\n'.join(one(types, r'^typedef '+name+' '+alias+r';[ \t]*$')
                    for name, alias in (('uint16_t','u16'),('uint32_t','u32'))))


def program(parts, rows):
    first = rows[0]
    text = render_wave(parts, legacy16=first['legacy16'], registration=True,
                       bounded_sizes=first['prepared_size_checks'],
                       revision=first['revision'], labels=['prepared_source'])
    marker = 'int main(void) {'
    if text.count(marker) != 1:
        raise ValueError('Exactly one authored WAV fixture main required')
    revisions = ','.join(str(row['revision']) for row in rows)
    # Profile context is selected outside every extracted body. Grouping never
    # merges different source-defined expectations.
    return text[:text.index(marker)] + '''
int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);int matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build) {++matched;wave_checks();error_checks();}
 assert(matched==1);return 0;
}
'''.replace('@REVISIONS@', revisions)


class WaveLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(CONTRACT_PATH.read_text())['sources']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-wave-loader-')
        cls.addClassCleanup(temporary.cleanup)
        cls.work = Path(temporary.name)
        cls.groups = {}
        for row in cls.rows:
            key = (row['engine'], row['legacy16'], row['prepared_size_checks'])
            cls.groups.setdefault(key, []).append(row)
        cls.executables = {}
        for index, (key, rows) in enumerate(cls.groups.items()):
            code = cls.work / ('contract-%d.c' % index)
            executable = code.with_suffix('')
            code.write_text(program(source_parts(key[0]), rows))
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc')) + [
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-sign-compare','-Wno-unused-function','-Wno-unused-variable','-g',
                '-fsanitize=address,undefined,float-cast-overflow',
                str(code),'-o',str(executable)], check=True, timeout=60)
            cls.executables[key] = executable

    def test_registered_profiles_and_both_boundary_sides_have_own_sources(self):
        revisions = [row['revision'] for row in self.rows]
        self.assertEqual(len(revisions),len(set(revisions)))
        self.assertTrue({3791,3792} <= set(revisions))
        by_revision = {row['revision']:row for row in self.rows}
        self.assertIs(by_revision[3791]['legacy16'],True)
        self.assertIs(by_revision[3792]['legacy16'],False)
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        engines = {row['engine'] for row in self.rows}
        for profile in pin['profiles']:
            if profile['engine'] in engines:
                row = by_revision[int(profile.get('revision',profile['build']))]
                self.assertEqual(row['engine'],profile['engine'])
        for row in self.rows:
            with self.subTest(revision=row['revision']):
                self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
                self.assertIs(type(row['legacy16']),bool)
                self.assertIs(type(row['prepared_size_checks']),bool)
                self.assertEqual(set(row['source_sha256']),
                                 {'loadwave','sample','constants','types'})
                for digest in row['source_sha256'].values():
                    self.assertRegex(digest,r'^[0-9a-f]{64}$')
                self.assertRegex(row['load_caller_sha256'],r'^[0-9a-f]{64}$')

    def test_native_bytes_lengths_padding_and_size_checks_per_source(self):
        for key, rows in self.groups.items():
            for row in rows:
                with self.subTest(revision=row['revision']):
                    subprocess.run([str(self.executables[key]),str(row['revision'])],
                                   check=True, timeout=20, env=sanitizer_environment())


class SoundCacheTests(unittest.TestCase):
    def test_sample_slots_lifetime_playback_and_model_cache_per_profile(self):
        from historical_sound_cache import render_sound_cache
        from test_historical_behavior import native
        fixture = json.loads((Path(__file__).parent /
            'fixtures/profile-sound-cache-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertTrue({3761, 3769, 3773} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['fixed_slots'], row['revision'] < 3838)
            self.assertEqual(row['capacity'], 1024 if row['fixed_slots'] else None)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        engine = SOURCE / 'src/engines/3842'
        scriptlib = engine / 'source/scriptlib'
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_sound_cache(engine, rows), include_dirs=[scriptlib], extra_flags=[
                '-DUNIT_TEST=1', '-Wno-sign-compare', '-Wno-unused-variable',
                str(scriptlib / 'List.c')])


if __name__ == '__main__':
    unittest.main()
