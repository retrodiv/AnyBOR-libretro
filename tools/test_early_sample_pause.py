"""Check source-defined sample pause, mixed bytes and pause-menu event order.

Native mixer/channel functions use authored constant PCM. Menu event providers
isolate dispatch order; this does not measure a frontend's audio scheduling.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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
from test_color_blends import compile_checked
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-sample-pause.json'


class EarlySamplePauseTests(unittest.TestCase):
    def test_registry_and_source_controls(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_native_mixer_channels_and_menu_order(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        mixer = (engine / 'source/gamelib/soundmix.c').read_text()
        types = []
        for name in ('channelstruct', 'samplestruct', 'musicchannelstruct'):
            rows = re.findall(r'typedef struct\s*\{[^{}]*\}\s*' + name + r';', mixer)
            self.assertEqual(len(rows), 1, name)
            types.append(rows[0])
        names = ['MAXVOLUME', 'MAX_SAMPLES', 'OBOR_PROFILE_SAMPLE_LIMIT', 'MAX_CHANNELS', 'INT_TO_FIX', 'FIX_TO_INT',
                 'CHANNEL_PLAYING', 'CHANNEL_LOOPING', 'MUSIC_NUM_BUFFERS', 'SOUND_MONO', 'SOUND_STEREO']
        constants = []
        for name in names:
            rows = re.findall(r'(?m)^#define[ \t]+' + name + r'\b[^\n]*', mixer)
            self.assertEqual(len(rows), 1, name)
            constants.append(rows[0])
        update = function(core, 'update')
        first = update.index('        if(obor_profile_build < 3434)')
        last = update.index('\t\tpausemenu();', first) + len('\t\tpausemenu();')
        enter = update[first:last]
        bodies = '\n'.join(function(mixer, name) for name in
                           ('mixaudio', 'sound_play_sample', 'sound_loop_sample', 'sound_pause_sample'))
        checks = '\n'.join('check(%d,%d);' % (r['revision'], r['sample_pause']) for r in fixture['sources'])
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
@CONSTANTS@
@TYPES@
static uint32_t obor_profile_build;
static channelstruct vchannel[MAX_CHANNELS];
static samplestruct sampledata[MAX_SAMPLES];
static musicchannelstruct musicchannel;
static int32_t mixed[32],*mixbuf=mixed;
static int max_channels=3,mixing_inited=1,playfrequency=11025;
@BODIES@
enum {FLAG_MOVEUP=1,FLAG_MOVEDOWN=2,FLAG_START=4,FLAG_ESC=8,FLAG_SCREENSHOT=16,
      SAMPLE_BEEP=0,SAMPLE_BEEP2=1};
static int pause,bothnewkeys,endgame;
static struct {int effectvol;} savedata={64};
static struct {int lives;} player[4];
static int events[4],event_at;
static char trace[64];static unsigned trace_at;
static void mark(char c){assert(trace_at+1<sizeof(trace));trace[trace_at++]=c;trace[trace_at]=0;}
static void update(int ingame,int wait){assert(ingame==1 && wait==0 && event_at<4);bothnewkeys=events[event_at++];}
static void menu_text(int selected,int row,int font,const char *text){(void)selected;(void)row;(void)font;assert(text);}
static void sound_pause_music(int toggle){mark(toggle?'M':'m');}
static void observed_sample_pause(int toggle){mark(toggle?'P':'p');sound_pause_sample(toggle);}
static int menu_beep(int sample,unsigned priority,int left,int right,unsigned speed){
 assert((sample==SAMPLE_BEEP || sample==SAMPLE_BEEP2) && !priority && left==64 && right==64 && speed==100);
 mark('B');return 0;
}
static void options(void){mark('O');}
static void spriteq_unlock(void){mark('U');}
#define _menutextm menu_text
#define sound_play_sample menu_beep
#define sound_pause_sample observed_sample_pause
@MENU@
#undef sound_pause_sample
#undef sound_play_sample
#undef _menutextm
static void spriteq_lock(void){mark('L');}
static void menu_entry(void){mark('E');}
#define sound_play_sample menu_beep
#define sound_pause_sample observed_sample_pause
#define pausemenu menu_entry
static void enter_pause(void){@ENTER@}
#undef pausemenu
#undef sound_pause_sample
#undef sound_play_sample
static void clear_trace(void){trace_at=0;trace[0]=0;}
static void check(unsigned revision,int pausing){
 obor_profile_build=revision;
 unsigned char pcm8[2][64];short pcm16[2][64];
 for(int bits=8;bits<=16;bits+=8)for(int channels=1;channels<=2;channels++){
  memset(vchannel,0,sizeof(vchannel));memset(sampledata,0,sizeof(sampledata));memset(&musicchannel,0,sizeof(musicchannel));
  for(int sound=0;sound<2;sound++){
   for(int i=0;i<64;i++){pcm8[sound][i]=(unsigned char)(129+sound);pcm16[sound][i]=(short)(1000*(sound+1));}
   sampledata[sound].sampleptr=bits==8?(void*)pcm8[sound]:(void*)pcm16[sound];
   sampledata[sound].soundlen=64;sampledata[sound].bits=bits;
   sampledata[sound].frequency=11025;sampledata[sound].channels=channels;
  }
  int old=sound_play_sample(0,1,64,64,100);assert(old==2);
  unsigned old_position=vchannel[old].fp_samplepos;
  sound_pause_sample(1);
  for(int i=0;i<3;i++)assert(vchannel[i].paused==pausing);
  memset(mixed,0,sizeof(mixed));mixaudio(8);
  int unit=bits==8?256:1000;
  for(int i=0;i<8;i++)assert(mixed[i]==(pausing?0:unit));
  assert((vchannel[old].fp_samplepos==old_position)==pausing);
  old_position=vchannel[old].fp_samplepos;
  int beep=sound_play_sample(1,1,64,64,100);assert(beep==1 && !vchannel[beep].paused);
  memset(mixed,0,sizeof(mixed));mixaudio(8);
  for(int i=0;i<8;i++)assert(mixed[i]==unit*(pausing?2:3));
  assert((vchannel[old].fp_samplepos==old_position)==pausing);
  sound_pause_sample(0);memset(mixed,0,sizeof(mixed));mixaudio(8);
  for(int i=0;i<8;i++)assert(mixed[i]==unit*3);
  memset(vchannel,0,sizeof(vchannel));sound_pause_sample(1);
  int loop=sound_loop_sample(0,1,64,64,100);
  assert(loop==2 && !vchannel[loop].paused && vchannel[loop].active==CHANNEL_LOOPING);
 }
 clear_trace();enter_pause();assert(!strcmp(trace,pausing?"MPBLE":"BMLE"));
 for(int scenario=0;scenario<4;scenario++){
  clear_trace();memset(events,0,sizeof(events));event_at=0;endgame=0;
  for(int i=0;i<4;i++)player[i].lives=5;
  if(scenario==0)events[0]=FLAG_START;
  if(scenario==1)events[0]=FLAG_ESC;
  if(scenario==2){events[0]=FLAG_SCREENSHOT;events[1]=FLAG_ESC;}
  if(scenario==3){events[0]=FLAG_MOVEUP;events[1]=FLAG_START;}
  pausemenu();assert(!pause && !bothnewkeys);
  const char *expected=scenario==2?(pausing?"MPBOmpBU":"MBOmBU"):
                       scenario==3?(pausing?"BmpBU":"BmBU"):(pausing?"mpBU":"mBU");
  assert(!strcmp(trace,expected));assert(endgame==(scenario==3));
  for(int i=0;i<4;i++)assert(player[i].lives==(scenario==3?0:5));
 }
}
int main(void){@CHECKS@puts("early_sample_pause=1");return 0;}
'''
        for key, value in dict(CONSTANTS='\n'.join(constants), TYPES='\n'.join(types), BODIES=bodies,
                               MENU=function(core, 'pausemenu'), ENTER=enter, CHECKS=checks).items():
            code = code.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-sample-pause-') as directory:
            source = Path(directory) / 'probe.c'
            binary = source.with_suffix('')
            source.write_text(code)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            compile_checked(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-O0', '-g', '-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all', str(source), *links, '-o', str(binary)])
            output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                             env=sanitizer_environment())
            self.assertIn('early_sample_pause=1', output)


if __name__ == '__main__':
    unittest.main()
