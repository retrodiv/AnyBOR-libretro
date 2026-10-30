"""Check own select-screen music call order and fallback policy.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-select-music.json'


class EarlySelectMusicTests(unittest.TestCase):
    def test_menu_attempt_and_fallback(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        selection = function(source, 'selectplayer')
        statement = re.search(
            r'if\(!music\("data/music/menu",\s*1,\s*0\).*?\)\s*'
            r'music\("data/music/remix",\s*1,\s*0\);', selection, re.S)
        self.assertIsNotNone(statement)
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d);' % (row['revision'], row['fallback']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
uint32_t obor_profile_build;
static int menu_result,calls;
static int music(const char *track,int loop,int offset){
 assert(loop==1 && offset==0);
 assert(!strcmp(track,calls?"data/music/remix":"data/music/menu"));
 calls++;assert(calls<=2);return calls==1?menu_result:1;
}
static void select_music(void){@STATEMENT@}
static void check(unsigned revision,int fallback){
 obor_profile_build=revision;
 for(int result=-1;result<=1;result++){
  menu_result=result;calls=0;select_music();
  assert(calls==(result==0 && fallback?2:1));
 }
}
int main(void){@CHECKS@ puts("early_select_music=1");return 0;}
'''
        program = program.replace('@STATEMENT@', statement[0]).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-select-music-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-Wall', '-Wextra', '-Werror',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                  '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_SELECT_MUSIC_OBSERVATIONS'):
                Path(os.environ['OBOR_SELECT_MUSIC_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_select_music=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
