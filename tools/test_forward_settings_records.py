"""Compare forward-profile settings with their own source-defined records.

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

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-forward-settings-contracts.json'


class ForwardSettingsRecordTests(unittest.TestCase):
    def sources(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(fixture, pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(hashlib.sha256(row['record'].encode()).hexdigest(), row['record_sha256'])
        engine = Path(os.environ.get('OBOR_FORWARD_SETTINGS_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        return rows, engine

    def run_native(self, program, *, marker='forward_settings=1'):
        with tempfile.TemporaryDirectory(prefix='forward-settings-') as directory:
            work = Path(directory)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(program)
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', str(source),
                *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=30, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn(marker, run.stdout.splitlines())

    def test_4432_native_settings_layouts_and_partial_reads(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-4432-settings-record-contracts.json'))
        rows = fixture['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(fixture, fixture['expected_revisions']))
        self.assertTrue(set(fixture['boundary_controls']) <= set(revisions))
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(fixture, pin['profiles'], source_range=fixture['range']):
            if profile['engine'] == fixture['engine']:
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        if '_contract_boundaries' not in fixture:
            for row in rows:
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')

        engine = ROOT / 'src/engines' / fixture['engine']
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'source/savedata.h').read_text()
        definitions = [re.search(r'^#define\s+' + field + r'\s+\d+', header, re.M)[0]
                       for field in ('MAX_PLAYERS', 'MAX_BTN_NUM')]
        definitions.append(re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', header)[0])
        start = source.index('#define OBOR_SETTINGS_4432_SIZE')
        helper = source[start:source.index('void savesettings()', start)]
        for name, call in [('savesettings', 'obor_write_settings'),
                           ('saveasdefault', 'obor_write_settings'),
                           ('loadsettings', 'obor_read_settings'),
                           ('loadfromdefault', 'obor_read_settings')]:
            self.assertIn(call + '(handle)', function(source, name))

        debug_fields = ('debug_collision_attack', 'debug_collision_body', 'debug_collision_range',
                        'debug_position', 'debug_features')
        checks = []
        for index, record in enumerate(fixture['records']):
            declaration = record['record']
            self.assertEqual(hashlib.sha256(declaration.encode()).hexdigest(), record['record_sha256'])
            declaration = re.sub(r'\bMAX_BTN_NUM\b', str(record['keys']), declaration)
            definitions.append(re.sub(r'\bs_savedata\b', f'native_{index}', declaration))
            assignments, retained = [], []
            for offset, field in enumerate(debug_fields, 20):
                if re.search(r'\bint\s+' + field + r'\s*;', declaration):
                    assignments.append(f'    value.{field} = seed + {offset};')
                else:
                    retained.append(f'    assert(savedata.{field} == DEFAULT_SEED + {offset});')
            original_fields = '\n'.join(assignments)
            initial_fields = original_fields.replace('value.', 'initial.')
            retained_fields = '\n'.join(retained)
            checks.append(f'''static void check_{index}(unsigned revision)
{{
    native_{index} value, initial;
    int seed = ORIGINAL_SEED;
    FILL(value);
{original_fields}
    seed = DEFAULT_SEED;
    FILL(initial);
{initial_fields}
    check_record(revision, &value, &initial, sizeof(value), {record['keys']});
{retained_fields}
}}''')

        calls = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertIn(row['record'], range(len(checks)))
            calls.append(f"    check_{row['record']}({row['revision']}u);")
        marker = f'settings_4432={len(rows)}'
        program = Path(__file__).with_name('settings_record_4432_contract.c.in').read_text()
        values = dict(DEFINITIONS='\n'.join(definitions), HELPER=helper, CHECKS='\n\n'.join(checks),
                      CALLS='\n'.join(calls), MARKER=marker)
        for key, value in values.items():
            program = program.replace('@' + key + '@', value)
        self.run_native(program, marker=marker)

    def test_native_record_bytes_and_every_partial_prefix(self):
        rows, engine = self.sources()
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        record = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', header)
        self.assertIsNotNone(record)
        start = source.index('/* Keep native settings bytes independent')
        helper = source[start:source.index('void savesettings()', start)]
        for name, call in [('savesettings', 'obor_profile_write_settings'),
                           ('saveasdefault', 'obor_profile_write_settings'),
                           ('loadsettings', 'obor_profile_read_settings'),
                           ('loadfromdefault', 'obor_profile_read_settings')]:
            self.assertIn(call + '(handle)', function(source, name))
        definitions, checks = [], []
        for row in rows:
            name = 'oracle_%d' % row['revision']
            definitions.append(re.sub(r'\bs_savedata\b', name, row['record']))
            extras = ''
            if row['software_filter']:
                extras += 'value.swfilter=seed+67;'
            extras += ''.join('value.screen[%d][%d]=seed+%d;' % (i, j, 80 + 2*i + j)
                              for i in range(row['screen_rows']) for j in range(2))
            checks.append('''static void check_%(revision)d(void) {
 %(name)s value; unsigned char expected[sizeof(value)], partial[sizeof(value)];
 obor_profile_build=%(revision)du;
 int seed=100; FILL(value); %(extras)s memcpy(expected,&value,sizeof(value));
 seed=300; FILL(value); %(extras)s
 assert(sizeof(value)<=sizeof(savedata));
 initialize(100); compare(expected,sizeof(value));
 for(size_t prefix=0;prefix<=sizeof(value);prefix++) {
  memcpy(partial,&value,sizeof(value));memcpy(partial,expected,prefix);
  FILE *stream=tmpfile();assert(stream);
  assert(fwrite(expected,1,prefix,stream)==prefix);rewind(stream);
  initialize(300);assert(obor_profile_read_settings(stream)==prefix);
  assert((size_t)ftell(stream)==prefix && fclose(stream)==0);
  compare(partial,sizeof(value));
 }
 FILE *stream=tmpfile();assert(stream);
 assert(fwrite(expected,1,sizeof(value),stream)==sizeof(value));
 assert(fputc(73,stream)!=EOF);rewind(stream);initialize(300);
 assert(obor_profile_read_settings(stream)==sizeof(value));
 assert(fgetc(stream)==73 && fclose(stream)==0);compare(expected,sizeof(value));
}''' % dict(revision=row['revision'], name=name, extras=extras))
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define MAX_PLAYERS 4
#define SDL 0
#define PSP 0
@RECORD@
@ORACLES@
static s_savedata savedata;
static uint32_t obor_profile_build;
@HELPER@
#define FILL(record) do { \
 memset(&(record),0,sizeof(record)); \
 (record).compatibleversion=0x11223344u; \
 (record).gamma=-seed;(record).brightness=seed+1;(record).usesound=seed+2; \
 (record).soundrate=44100u;(record).soundvol=seed+3;(record).usemusic=seed+4; \
 (record).musicvol=seed+5;(record).effectvol=seed+6;(record).soundbits=16; \
 (record).usejoy=seed+7;(record).mode=seed+8;(record).windowpos=seed+9; \
 (record).showtitles=seed+10;(record).videoNTSC=seed+11;(record).logo=seed+12; \
 (record).uselog=seed+13;(record).debuginfo=seed+14; \
 (record).fullscreen=seed+15;(record).stretch=seed+16; \
 for(int i=0;i<MAX_PLAYERS;i++) for(int j=0;j<12;j++) \
  (record).keys[i][j]=seed+100*i+j; \
} while(0)
static void initialize(int seed) {
 FILL(savedata);savedata.swfilter=seed+67;
 for(int i=0;i<7;i++) for(int j=0;j<2;j++) savedata.screen[i][j]=seed+80+2*i+j;
}
static void compare(const unsigned char *expected,size_t bytes) {
 unsigned char actual[sizeof(savedata)];FILE *stream=tmpfile();assert(stream);
 assert(obor_profile_write_settings(stream)==bytes && (size_t)ftell(stream)==bytes);
 rewind(stream);assert(fread(actual,1,sizeof(actual),stream)==bytes);
 assert(!memcmp(actual,expected,bytes) && fclose(stream)==0);
}
@CHECKS@
int main(void) {@CALLS@ puts("forward_settings=1");return 0;}
'''
        values = dict(RECORD=record[0], ORACLES='\n'.join(definitions), HELPER=helper,
                      CHECKS='\n'.join(checks),
                      CALLS=''.join('check_%d();' % row['revision'] for row in rows))
        for key, value in values.items():
            program = program.replace('@' + key + '@', value)
        self.run_native(program)

    def test_native_video_modes_and_custom_mode(self):
        rows, engine = self.sources()
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        record = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', header)
        types = (engine / 'source/gamelib/types.h').read_text()
        video = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_videomodes;', types)
        self.assertIsNotNone(record)
        self.assertIsNotNone(video)
        initializer = function(source, 'init_videomodes')
        start = initializer.index('VIDEOMODES:') + len('VIDEOMODES:')
        finish = initializer.index('#if SDL || WII', start)
        block = initializer[start:finish]
        contexts = []
        for row in rows:
            self.assertIn(row['video_policy'], ('per-mode', 'shared-filter'))
            self.assertRegex(row['video_source_sha256'], r'^[0-9a-f]{64}$')
            self.assertRegex(row['video_fragment_sha256'], r'^[0-9a-f]{64}$')
            contexts.append('{%du,%d}' % (row['revision'], row['video_policy'] == 'shared-filter'))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define MAX_PLAYERS 4
#define SDL 0
#define PSP 0
@RECORD@
@VIDEO@
static s_savedata savedata;
static s_videomodes videomodes;
static uint32_t obor_profile_build;
static int videoMode, PLAYER_MIN_Z, PLAYER_MAX_Z, BGHEIGHT, failure;
static const char *failure_format;
static void shutdown(int status,const char *format,...) {
 failure=status;failure_format=format;
}
static void initialize_video(void) {@BLOCK@}
static const struct {unsigned revision;int shared;} contexts[] = {@CONTEXTS@};
static const struct {int width,height,x,y,debug,minimum,maximum,background;} modes[] = {
 {320,240,0,0,231,160,232,160}, {480,272,80,20,263,182,264,182},
 {640,480,160,35,464,321,465,321}, {720,480,200,35,464,321,465,321},
 {800,480,240,35,464,321,465,321}, {800,600,240,44,580,401,582,401},
 {960,540,320,40,522,362,524,362}
};
int main(void) {
 for(size_t i=0;i<sizeof(contexts)/sizeof(*contexts);i++) {
  obor_profile_build=contexts[i].revision;
  for(int j=0;j<7;j++) {savedata.screen[j][0]=20+j;savedata.screen[j][1]=40+j;}
  savedata.swfilter=73;
  for(videoMode=0;videoMode<7;videoMode++) {
   memset(&videomodes,0,sizeof(videomodes));initialize_video();assert(!failure);
   assert(videomodes.mode==(contexts[i].shared?videoMode:20+videoMode));
   assert(videomodes.filter==(contexts[i].shared?73:40+videoMode));
   assert(videomodes.hRes==modes[videoMode].width && videomodes.vRes==modes[videoMode].height);
   assert(videomodes.hShift==modes[videoMode].x && videomodes.vShift==modes[videoMode].y);
   assert(videomodes.dOffset==modes[videoMode].debug && PLAYER_MIN_Z==modes[videoMode].minimum);
   assert(PLAYER_MAX_Z==modes[videoMode].maximum && BGHEIGHT==modes[videoMode].background);
  }
  videoMode=255;videomodes.mode=17;videomodes.filter=19;
  videomodes.hRes=123;videomodes.vRes=456;initialize_video();
  assert(videomodes.mode==(contexts[i].shared?(char)255:17));
  assert(videomodes.filter==(contexts[i].shared?73:19));
  assert(videomodes.hRes==123 && videomodes.vRes==456 && videomodes.dOffset==438);
  videoMode=7;initialize_video();assert(failure==1);
  assert(!strncmp(failure_format,"Invalid video mode:",19));failure=0;
 }
 puts("forward_settings=1");return 0;
}
'''
        for key, value in dict(RECORD=record[0], VIDEO=video[0], BLOCK=block,
                               CONTEXTS=','.join(contexts)).items():
            program = program.replace('@' + key + '@', value)
        self.run_native(program)

    def test_defaults_preserve_the_native_auxiliary_pair(self):
        rows, engine = self.sources()
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        record = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', header)
        self.assertIsNotNone(record)
        defaults = function(source, 'clearsettings')
        # Execute the complete defaults prefix. Key assignments have their own controls.
        prefix = defaults[defaults.index('{') + 1:defaults.index('savedata.keys[0]')]
        contexts = []
        for row in rows:
            self.assertRegex(row['defaults_fragment_sha256'], r'^[0-9a-f]{64}$')
            self.assertIs(type(row['clears_screen']), bool)
            contexts.append('{%du,%d,%d,%d}' % (row['revision'], row['screen_rows'],
                                               row['clears_screen'], row['software_filter']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define MAX_PLAYERS 4
#define COMPATIBLEVERSION 123456u
@RECORD@
static s_savedata savedata;
static uint32_t obor_profile_build;
static void defaults(void) {@PREFIX@}
static const struct {unsigned revision;int screens,clears_screen,software_filter;} contexts[]={@CONTEXTS@};
int main(void) {
 for(size_t i=0;i<sizeof(contexts)/sizeof(*contexts);i++) {
  obor_profile_build=contexts[i].revision;memset(&savedata,0,sizeof(savedata));
  savedata.swfilter=97;
  for(int j=0;j<7;j++) for(int k=0;k<2;k++) savedata.screen[j][k]=20+2*j+k;
  defaults();
  assert(savedata.compatibleversion==COMPATIBLEVERSION);
  assert(savedata.gamma==0 && savedata.brightness==0 && savedata.usesound==1);
  assert(savedata.soundrate==44100 && savedata.soundbits==16 && savedata.soundvol==15);
  assert(savedata.usemusic==1 && savedata.musicvol==100 && savedata.effectvol==120);
  assert(savedata.usejoy==1 && savedata.mode==0 && savedata.showtitles==0);
  assert(savedata.windowpos==0 && savedata.logo==0 && savedata.uselog==1);
  assert(savedata.debuginfo==0 && savedata.fullscreen==0 && savedata.stretch==0);
  if(contexts[i].software_filter) assert(savedata.swfilter==0);
  for(int j=0;j<contexts[i].screens;j++) for(int k=0;k<2;k++)
   assert(savedata.screen[j][k]==(contexts[i].clears_screen?0:20+2*j+k));
 }
 puts("forward_settings=1");return 0;
}
'''
        for key, value in dict(RECORD=record[0], PREFIX=prefix,
                               CONTEXTS=','.join(contexts)).items():
            program = program.replace('@' + key + '@', value)
        self.run_native(program)


if __name__ == '__main__':
    unittest.main()
