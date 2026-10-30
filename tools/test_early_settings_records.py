"""Check source-defined configuration records on native and Windows layouts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
from platform import machine
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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-settings-records.json'


class EarlySettingsRecordTests(unittest.TestCase):
    def test_profile_file_bytes_and_partial_reads(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_SETTINGS_RECORD_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        current = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', header)
        self.assertIsNotNone(current)
        helper = re.search(r'/\* Preserve the source-defined settings record[^\n]*\*/[\s\S]*?(?=void savesettings\()', source)
        self.assertIsNotNone(helper)
        for name, call in [('savesettings', 'obor_profile_write_settings'),
                           ('saveasdefault', 'obor_profile_write_settings'),
                           ('loadsettings', 'obor_profile_read_settings'),
                           ('loadfromdefault', 'obor_profile_read_settings')]:
            self.assertIn(call + '(handle)', function(source, name))
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['record_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['record'], fixture['records'])
            checks.append('check(%d,%d);' % (row['revision'], row['record'] == 'early'))
        oracles = []
        for name in ['early', 'later']:
            text = fixture['records'][name]
            self.assertRegex(text, r'\bs_savedata\s*;\s*$')
            oracles.append(re.sub(r'\bs_savedata\b', 'oracle_' + name, text))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_PLAYERS 4
#define SDL 0
#define PSP 0
#pragma pack(push,4)
@CURRENT@
@ORACLES@
#pragma pack(pop)
uint32_t obor_profile_build;
static s_savedata savedata;
@HELPER@
#define INITIALIZE(record,fullscreen_value) do { \
 memset(&(record),0,sizeof(record)); \
 (record).compatibleversion=0x11223344;(record).gamma=-3;(record).brightness=257; \
 (record).usesound=1;(record).soundrate=44100;(record).soundvol=100; \
 (record).usemusic=1;(record).musicvol=99;(record).effectvol=123; \
 (record).soundbits=16;(record).usejoy=1;(record).mode=1;(record).windowpos=2; \
 (record).showtitles=1;(record).videoNTSC=0;(record).logo=1;(record).uselog=1; \
 (record).debuginfo=1;(record).fullscreen=(fullscreen_value);(record).stretch=1; \
 for(int i=0;i<MAX_PLAYERS;i++) for(int j=0;j<12;j++) (record).keys[i][j]=100*i+j; \
 for(int i=0;i<7;i++) for(int j=0;j<2;j++) (record).screen[i][j]=(char)(i+j); \
} while(0)
static void compare_bytes(const void *expected,size_t length) {
 unsigned char actual[1024];assert(length<=sizeof(actual));
 FILE *stream=tmpfile();assert(stream);
 assert(obor_profile_write_settings(stream)==length && (size_t)ftell(stream)==length);
 rewind(stream);assert(fread(actual,1,sizeof(actual),stream)==length);
 assert(!memcmp(actual,expected,length));assert(fclose(stream)==0);
}
static void check(unsigned revision,int early) {
 obor_profile_build=revision;
 for(int mode=0;mode<2;mode++) {
  oracle_early old;oracle_later newer;
  INITIALIZE(old,mode);INITIALIZE(newer,mode);INITIALIZE(savedata,mode);
  const void *expected=early?(const void *)&old:(const void *)&newer;
  size_t length=early?sizeof(old):sizeof(newer);
  compare_bytes(expected,length);
  // Full input, ignored trailing bytes and every prefix preserve original fread semantics.
  for(size_t prefix=0;prefix<=length;prefix++) {
   oracle_early old_result;oracle_later new_result;
   INITIALIZE(old_result,1-mode);INITIALIZE(new_result,1-mode);
   void *output=early?(void *)&old_result:(void *)&new_result;
   memcpy(output,expected,prefix);
   FILE *stream=tmpfile();assert(stream);
   assert(fwrite(expected,1,prefix,stream)==prefix);rewind(stream);
   INITIALIZE(savedata,1-mode);
   assert(obor_profile_read_settings(stream)==prefix && (size_t)ftell(stream)==prefix);
   assert(fclose(stream)==0);compare_bytes(output,length);
  }
  FILE *stream=tmpfile();assert(stream);
  assert(fwrite(expected,1,length,stream)==length && fputc(17,stream)!=EOF);rewind(stream);
  INITIALIZE(savedata,1-mode);assert(obor_profile_read_settings(stream)==length);
  assert(fgetc(stream)==17 && fclose(stream)==0);compare_bytes(expected,length);
 }
}
int main(void) {@CHECKS@ puts("early_settings_records=1");return 0;}
'''.replace('@CURRENT@', current[0]).replace('@ORACLES@', '\n'.join(oracles)).replace(
            '@HELPER@', helper[0]).replace('@CHECKS@', '\n'.join(checks))
        observations = []
        with tempfile.TemporaryDirectory(prefix='early-settings-records-') as name:
            work = Path(name)
            unit = work / 'probe.c'
            unit.write_text(program)
            layouts = [('native', [])]
            if machine().lower() in ('x86_64', 'amd64', 'i386', 'i686'):
                layouts.append(('windows', ['-mms-bitfields']))
            for label, layout_flags in layouts:
                binary = work / label
                command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                    '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-fno-omit-frame-pointer', *layout_flags, str(unit),
                    *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)]
                build = subprocess.run(command, capture_output=True, text=True, timeout=45)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                run = subprocess.run([str(binary)], capture_output=True, text=True,
                                     timeout=20, env=sanitizer_environment())
                observations.append({'layout': label, 'command': command,
                                     'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                                     'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr})
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn('early_settings_records=1', run.stdout)
        if os.environ.get('OBOR_SETTINGS_OBSERVATIONS'):
            Path(os.environ['OBOR_SETTINGS_OBSERVATIONS']).write_text(json.dumps({
                'contexts': len(rows), 'observations': observations,
                'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                'retirement': 'TemporaryDirectory removes source and both binaries',
            }, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
