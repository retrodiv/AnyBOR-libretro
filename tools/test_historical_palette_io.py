"""Check per-source RGB palette I/O, byte output and partial failure effects.

Actual palette/colour functions run with bounded deterministic packfile I/O.
The original collector verifies the complete function group for every source;
identical groups may share emitted C while executing each profile's checks.
This does not establish container decoding, model ownership or game rendering.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_palette_loading import SOURCE
from test_historical_player import function

CONTRACTS = json.loads((Path(__file__).parent /
    'fixtures/profile-palette-io-contracts.json').read_text())
FUNCTIONS = ('colour16', 'colour32', '_load_palette16', '_load_palette32', 'load_palette')


def palette_io_program(components=None, rows=None, *, original=False):
    rows = CONTRACTS['sources'] if rows is None else rows
    if components is None:
        root = SOURCE / 'src/engines/3741'
        game = (root / 'openbor.c').read_text()
        colour = (root / 'source/gamelib/pixelformat.c').read_text()
        components = {name: function(colour if name.startswith('colour') else game, name)
                      for name in FUNCTIONS}
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define WII 0
#define MAX_PAL_SIZE 1024
#define PIXEL_8 0
#define PIXEL_x8 1
#define PIXEL_16 2
#define PIXEL_32 4
static int screenformat=PIXEL_32;
static unsigned char rgb[770];
static int file_length,position,read_calls,close_calls,open_calls,fail_read_at;
static const char *packfile="fixture";
static int openpackfile(char *name,const char *pak) {
 assert(!strcmp(name,"palette") && pak==packfile);++open_calls;
 return file_length<0?-1:17;
}
static int readpackfile(int handle,void *output,int size) {
 assert(handle==17 && size>0 && size<=768);++read_calls;
 if(fail_read_at>=0 && position==fail_read_at) return -1;
 int remaining=file_length-position,count=remaining<size?remaining:size;
 assert(count>=0 && count<=770 && output);
 memcpy(output,rgb+position,(size_t)count);position+=count;return count;
}
static void closepackfile(int handle) {assert(handle==17);++close_calls;}
@FUNCTIONS@
static unsigned native_colour(int index,int format) {
 unsigned r=rgb[index*3],g=rgb[index*3+1],b=rgb[index*3+2];
 return format==PIXEL_16?((b&248u)<<8)|((g&252u)<<3)|(r>>3):
   (b<<16)|(g<<8)|r;
}
static void trial(int format,int length,int error_at) {
 unsigned char *output=malloc(MAX_PAL_SIZE);assert(output);
 unsigned char expected[MAX_PAL_SIZE];memset(output,165,MAX_PAL_SIZE);
 memset(expected,165,sizeof(expected));screenformat=format;file_length=length;
 fail_read_at=error_at;position=read_calls=close_calls=open_calls=0;
 int success=length>=768 && error_at<0;
 int bytes=length<0?0:length<768?length:768;
 if(error_at>=0) bytes=error_at;
 if(length>=0) {
  if(format==PIXEL_8) {
   int copied=error_at>=0?0:bytes;
   memcpy(expected,rgb,(size_t)copied);
   if(success) memset(expected,0,3);
  } else {
   unsigned stride=format==PIXEL_16?2:4;
   memset(expected,0,stride*256);
   for(int i=0;i<bytes/3;++i) {
    unsigned colour=native_colour(i,format);
    if(success && i==0) colour=0;
    if(format==PIXEL_16) {
     uint16_t value=(uint16_t)colour;memcpy(expected+i*2,&value,2);
    } else {uint32_t value=colour;memcpy(expected+i*4,&value,4);}
   }
  }
 }
 assert(load_palette(output,"palette")==success);
 assert(!memcmp(output,expected,sizeof(expected)));
 assert(open_calls==1 && close_calls==(length>=0));
 if(length<0) assert(position==0 && read_calls==0);
 else if(format==PIXEL_8) assert(position==(error_at>=0?0:bytes) && read_calls==1);
 else {
  assert(position==bytes);
  assert(read_calls==(success?256:bytes/3+1));
 }
 free(output);
}
static void check(void) {
 for(unsigned i=0;i<sizeof(rgb);++i) rgb[i]=(unsigned char)(i*37u+13u);
 const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
 for(unsigned f=0;f<sizeof(formats)/sizeof(*formats);++f) {
  int format=formats[f];
  trial(format,-1,-1);
  for(int length=0;length<=770;++length) trial(format,length,-1);
  if(format==PIXEL_8) trial(format,768,0);
  else for(int offset=0;offset<768;offset+=3) trial(format,768,offset);
 }
}
int main(int argc,char **argv) {
 @MAIN@
 return 0;
}
'''
    if original:
        main = ('(void)argc;(void)argv;\n'+
                ''.join('check(); /* source %d */\n' % row['revision'] for row in rows)+
                'puts('+json.dumps(json.dumps({'status': 'PASS', 'sources': len(rows),
                                               'formats': 3, 'lengths_each': 772}))+');')
    else:
        main = ('assert(argc==2);int revision=atoi(argv[1]),found=0;\n'+
                ''.join('if(revision==%d) {check();++found;}\n' % row['revision'] for row in rows)+
                'assert(found==1);')
    return program.replace('@FUNCTIONS@', '\n'.join(components[name] for name in FUNCTIONS)).replace('@MAIN@', main)


class HistoricalPaletteIOTests(unittest.TestCase):
    def test_rgb_registry_covers_each_registered_profile(self):
        rows = CONTRACTS['sources']
        self.assertEqual(len({x['revision'] for x in rows}), len(rows))
        for row in rows:
            self.assertEqual(set(row['function_hashes']), set(FUNCTIONS))
            for value in row['function_hashes'].values():
                self.assertRegex(value, r'^[0-9a-f]{64}$')
        for name in FUNCTIONS:
            self.assertEqual(len({x['function_hashes'][name] for x in rows}), 1)
        revisions = {x['revision'] for x in rows}
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)

    def test_exact_rgb_bytes_eof_and_read_errors_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-palette-rgb-') as temporary:
            work = Path(temporary)
            source, exe = work / 'probe.c', work / 'probe'
            source.write_text(palette_io_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-g', '-fsanitize=address,undefined', str(source), '-o', str(exe)], check=True, timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe), str(row['revision'])], check=True,
                                   timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
