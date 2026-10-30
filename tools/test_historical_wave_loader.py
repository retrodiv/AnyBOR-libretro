"""Check each source-defined WAV read/length/padding contract safely.

Actual prepared loader bodies run against bounded authored packfile fixtures.
These checks do not execute the mixer or establish audible/gameplay acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from historical_wave_loader import render_wave
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
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
        cls.rows = load_contract_fixture(CONTRACT_PATH)['sources']
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
        for profile in contract_profiles(CONTRACT_PATH, pin['profiles']):
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
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-sound-cache-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((SOURCE / 'src/pin.json').read_text())['profiles']):
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


    def test_early_sample_capacity_per_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
                                        'fixtures/profile-early-sample-limit.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((SOURCE / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', SOURCE / 'src/engines' / fixture['engine']))
        code = (engine / 'source/gamelib/soundmix.c').read_text()
        declarations = []
        for name in ['s_soundcache', 'samplestruct', 'channelstruct']:
            found = re.findall(r'typedef\s+struct\s*\{[^{}]*}\s*' + name + r'\s*;', code)
            self.assertEqual(len(found), 1)
            declarations += found
        constants = []
        for name in ['MAX_SAMPLES', 'OBOR_PROFILE_SAMPLE_LIMIT', 'MAX_CHANNELS', 'MAXVOLUME',
                     'MAX_SOUND_LEN', 'INT_TO_FIX', 'CHANNEL_PLAYING']:
            constants.append(one(code, r'^#define[ \t]+' + name + r'\b[^\n]*'))
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['sample_limit'], (512, 1024))
            checks.append('check(%d,%d);' % (row['revision'], row['sample_limit']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
@CONSTANTS@
@TYPES@
static uint32_t obor_profile_build;
static samplestruct sampledata[MAX_SAMPLES];
static s_soundcache soundcache[MAX_SAMPLES];
static channelstruct vchannel[MAX_CHANNELS];
static int mixing_inited=1,max_channels=4,playfrequency=11025,loads,logs;
static int loadwave(char *name,char *pack,samplestruct *sample,unsigned maxsize) {
 assert(!strcmp(name,"sample") || !strcmp(name,"replacement"));
 assert(!strcmp(pack,"fixture") && maxsize==MAX_SOUND_LEN);
 loads++;sample->sampleptr=malloc(4);assert(sample->sampleptr);
 sample->soundlen=2;sample->bits=16;sample->frequency=11025;sample->channels=1;return 2;
}
static int logged(const char *format,...) {(void)format;logs++;return 0;}
#define writeToLogFile logged
@FUNCTIONS@
static void check(unsigned revision,int limit) {
 obor_profile_build=revision;assert(OBOR_PROFILE_SAMPLE_LIMIT==limit);
 memset(sampledata,0,sizeof(sampledata));memset(soundcache,0,sizeof(soundcache));
 memset(vchannel,0,sizeof(vchannel));loads=logs=0;
 mixing_inited=0;assert(sound_alloc_sample("sample","fixture")==-1 && !loads);
 mixing_inited=1;
 for(int i=0;i<limit;i++)assert(sound_alloc_sample("sample","fixture")==i);
 assert(loads==limit && sound_alloc_sample("sample","fixture")==-1 && loads==limit);
 for(int i=0;i<limit;i++){
  soundcache[i].filename=strdup("present");assert(soundcache[i].filename);soundcache[i].index=i;
 }
 assert(sound_load_sample("present","fixture",1)==0 && loads==limit);
 assert(sound_load_sample("extra","fixture",1)==-1 && loads==limit);
 assert(sound_play_sample(limit-1,7,64,64,100)==3);
 assert(vchannel[3].samplenum==limit-1 && vchannel[3].fp_period==4096 &&
        vchannel[3].active==CHANNEL_PLAYING && vchannel[3].channels==1);
 assert(sound_play_sample(-1,0,64,64,100)==-1 &&
        sound_play_sample(limit,0,64,64,100)==-1);
 /* Rejected indices preserve both native tables. */
 if(limit<MAX_SAMPLES) {
  void *sample=malloc(4);char *name=strdup("reserved");assert(sample && name);
  sampledata[limit].sampleptr=sample;soundcache[limit].filename=name;
  sound_free_sample(limit);sound_unload_sample(limit);
  assert(sampledata[limit].sampleptr==sample && soundcache[limit].filename==name);
  assert(sound_play_sample(limit,0,64,64,100)==-1);
  free(sample);free(name);sampledata[limit].sampleptr=NULL;soundcache[limit].filename=NULL;
 }
 void *last=sampledata[limit-1].sampleptr;mixing_inited=0;sound_free_sample(limit-1);
 assert(sampledata[limit-1].sampleptr==last);mixing_inited=1;
 sound_unload_sample(limit-1);
 assert(!sampledata[limit-1].sampleptr && !soundcache[limit-1].filename);
 assert(sound_load_sample("replacement","fixture",1)==limit-1 && loads==limit+1);
 sound_free_sample(-1);sound_unload_sample(-1);sound_unload_all_samples();
 for(int i=0;i<MAX_SAMPLES;i++)assert(!sampledata[i].sampleptr && !soundcache[i].filename);
 assert(!logs);
}
int main(void){@CHECKS@ puts("early_sample_limit=1");return 0;}
'''
        names = ['sound_free_sample', 'sound_alloc_sample', 'sound_load_sample',
                 'sound_unload_sample', 'sound_unload_all_samples', 'sound_play_sample']
        for key, value in dict(CONSTANTS='\n'.join(constants), TYPES='\n'.join(declarations),
                               FUNCTIONS='\n'.join(function(code, name) for name in names),
                               CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-sample-limit-') as folder:
            unit, binary = Path(folder) / 'probe.c', Path(folder) / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(unit),
                *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_sample_limit=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
