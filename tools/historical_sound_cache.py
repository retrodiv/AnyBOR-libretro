"""Render native sample-cache lifecycle checks with deterministic PCM input.

The engine's complete cache, playback and mixer functions are retained. This
fixture replaces file decoding and the audio device, and reduces model fields.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def render_sound_cache(engine, rows):
    code = (engine / 'source/gamelib/soundmix.c').read_text()
    model = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    types = []
    for name in ('channelstruct', 'samplestruct', 's_soundcache', 'musicchannelstruct'):
        matches = re.findall(r'typedef\s+struct\s*\{[^{}]*\}\s*'+name+r'\s*;', code)
        if len(matches) != 1:
            raise ValueError('One complete native sample type required: '+name)
        types.append(matches[0])
    constants = []
    for name in ('MAX_CHANNELS', 'MAXVOLUME', 'MAX_SOUND_LEN', 'MUSIC_NUM_BUFFERS',
                 'CHANNEL_PLAYING', 'CHANNEL_LOOPING', 'SOUND_MONO',
                 'INT_TO_FIX', 'FIX_TO_INT', 'MIXSHIFT', 'SB_BUFFER_SIZE', 'MIXBUF_SIZE'):
        constants.append(re.search(r'^#define\s+'+name+r'\b[^\n]*', code, re.M)[0])
    macro = re.search(r'^#define __realloc\([^\n]*\n(?:[^\n]*\\\n)*[^\n]*', header, re.M)[0]
    # Keep the actual legacy arrays and modern list/cache declarations together.
    start = code.find('#define OBOR_LEGACY_MAX_SAMPLES')
    if start < 0:
        start = code.index('static List samplelist;')
    stop = code.index('int sample_play_id = 0;', start)+len('int sample_play_id = 0;')
    declarations = code[start:stop]
    names = re.findall(r'^static (?:void|int|samplestruct\s*\*)\s*(obor_legacy_\w+|obor_sample_data)\s*\(', code, re.M)
    names += ['sound_reload_sample', 'sound_load_sample', 'sound_unload_sample',
              'sound_unload_all_samples', 'sound_play_sample', 'sound_loop_sample',
              'sound_query_channel', 'sound_stop_sample', 'sound_stopall_sample',
              'sound_exit', 'sound_init', 'mixaudio']
    functions = '\n'.join(function(code, name) for name in names)
    model_functions = '\n'.join(function(model, name) for name in ('cachesound', 'cache_model_sprites'))
    contexts = ','.join('{%d,%d}' % (r['revision'], r['fixed_slots']) for r in rows)
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#define UNIT_TEST 1
#include "List.h"
#define stricmp strcasecmp
@CONSTANTS@
@TYPES@
@DECLARATIONS@
@REALLOC@
static uint32_t obor_profile_build;
static channelstruct vchannel[MAX_CHANNELS];
static musicchannelstruct musicchannel;
static int *mixbuf,playbits,playfrequency=11025,max_channels,mixing_active,mixing_inited;
static char *packfile="fixture.pak";
static unsigned test_case,loads,logs;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Sample cache revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
static int logged(const char *fmt,...) {(void)fmt;++logs;return 0;}
static void lc(char *s,size_t n) {for(size_t i=0;i<n;++i)s[i]=(char)tolower((unsigned char)s[i]);}
static int loadwave(char *filename,char *packname,samplestruct *sample,unsigned maxsize) {
 (void)packname;(void)maxsize;++loads;
 if(!strcmp(filename,"missing"))return 0;
 sample->bits=!strncmp(filename,"eight",5)?8:16;sample->soundlen=16;
 sample->frequency=11025;sample->channels=1;
 sample->sampleptr=malloc(32);assert(sample->sampleptr);
 if(sample->bits==8)memset(sample->sampleptr,129,32);
 else for(int i=0;i<16;++i)((short*)sample->sampleptr)[i]=256;
 return 16;
}
static void sound_stop_playback(void) {mixing_active=0;}
#define printf logged
#define writeToLogFile logged
@FUNCTIONS@
#undef printf
#undef writeToLogFile
#define MAX_PLAYERS 4
typedef struct {int hitsound,blocksound;} s_attack;
typedef struct {int numframes,*sprite,*soundtoplay;s_attack **attacks;} s_anim;
typedef struct {
 struct {int def,die,get,mphigh,mplow,mpmed,pain,weapon;} icon;
 int diesound,parrow[MAX_PLAYERS][2],animation_capacity;s_anim **animation;
} s_model;
static unsigned sprite_calls;
static void cachesprite(int index,int load) {(void)index;(void)load;++sprite_calls;}
@MODEL_FUNCTIONS@
static void reset(void) {
 sound_exit();loads=logs=0;sample_play_id=0;assert(sound_init(4));
 memset(&musicchannel,0,sizeof(musicchannel));
}
static void check(int fixed) {
 ++test_case;assert(!mixing_inited);
 assert(sound_load_sample("first",packfile,0)==-1);assert(!sound_reload_sample(-1));
 reset();
 ++test_case;assert(sound_load_sample("first",packfile,0)==0 && loads==1);
 assert(sound_load_sample("FIRST",packfile,0)==0 && loads==1);
 assert(sound_load_sample("second",packfile,0)==1 && loads==2);
 sound_unload_sample(0);unsigned before=loads;
 assert(sound_load_sample("second",packfile,0)==(fixed?0:1));
 assert(loads==before+(fixed?1:0));
 sound_unload_sample(1);before=loads;
 assert(sound_load_sample("SECOND",packfile,0)==(fixed?0:1));
 assert(loads==before+(fixed?0:1));
 reset();
 ++test_case;assert(sound_load_sample("missing",packfile,0)==-1);
 assert(logs==(unsigned)fixed);logs=0;
 assert(sound_load_sample("missing",packfile,1)==-1);
 assert(logs==(unsigned)!fixed);
 assert(sound_load_sample("first",packfile,0)==0);
 reset();
 ++test_case;char name[32];
 for(int i=0;i<1024;++i){snprintf(name,sizeof(name),"sound%04d",i);assert(sound_load_sample(name,packfile,0)==i);}
 assert(sound_load_sample("extra",packfile,0)==(fixed?-1:1024));
 sound_unload_sample(50);assert(sound_load_sample("replacement",packfile,0)==(fixed?50:1025));
 reset();
 // Complete mixer executes both PCM depths, channel selection and looping.
 for(int bits=8;bits<=16;bits+=8) {
  ++test_case;int id=sound_load_sample(bits==8?"eight":"sixteen",packfile,0);
  assert(id==(bits==8?0:1));sound_stopall_sample();
  int ch=sound_play_sample(id,7,64,64,100);assert(ch==3);
  assert(vchannel[ch].channels==1 && vchannel[ch].fp_period==4096);
  assert(sample_play_id==(fixed?0:(bits==8?1:3)));
  for(int i=0;i<8;++i)mixbuf[i]=0;
  mixaudio(8);for(int i=0;i<8;++i)assert(mixbuf[i]==256);
  assert(vchannel[ch].fp_samplepos==0 && !vchannel[ch].active);
  ch=sound_loop_sample(id,7,64,64,0);assert(ch==3 && vchannel[ch].active==CHANNEL_LOOPING);
  mixaudio(8);assert(vchannel[ch].active==CHANNEL_LOOPING);
  if(!fixed)assert(sound_query_channel(sample_play_id)==ch);
  sound_unload_sample(id);mixaudio(8);
  assert(vchannel[ch].active==(fixed?CHANNEL_LOOPING:0));
  sound_stopall_sample();
  assert(sound_load_sample(bits==8?"eight":"sixteen",packfile,0)==id);
 }
 ++test_case;before=loads;sound_unload_sample(0);
 assert(sound_play_sample(0,0,64,64,100)==(fixed?-1:3));
 assert(loads==before+(fixed?0:1));
 assert(sound_play_sample(-1,0,64,64,100)==-1);
 assert(sound_play_sample(2000,0,64,64,100)==-1);
 sound_stopall_sample();reset();
 // Model sprite-cache operations must retain old PCM, unload/reload new PCM.
 ++test_case;for(int i=0;i<4;++i){snprintf(name,sizeof(name),"model%d",i);assert(sound_load_sample(name,packfile,0)==i);}
 int sprites[]={7},sounds[]={1};s_attack attack={2,3},*attacks[]={&attack};
 s_anim animation={1,sprites,sounds,attacks},*animations[]={&animation};
 s_model model={0};model.animation=animations;model.animation_capacity=1;
 sprite_calls=0;before=loads;cache_model_sprites(&model,0);
 assert(sprite_calls==13);cache_model_sprites(&model,1);
 assert(sprite_calls==26 && loads==before+(fixed?0:4));
 // Reinitialization releases the whole cache and starts numbering from zero.
 ++test_case;assert(sound_init(1) && max_channels==2);
 assert(sound_load_sample("new",packfile,0)==0);
 sound_exit();sound_exit();assert(!mixing_inited && !soundcache && !sound_cached);
}
int main(void) {
 const struct {unsigned revision;int fixed;} rows[]={@CONTEXTS@};
 (void)playbits;
 for(unsigned i=0;i<sizeof(rows)/sizeof(*rows);++i) {
  obor_profile_build=rows[i].revision;check(rows[i].fixed);
 }
 return 0;
}
'''.replace('@CONSTANTS@', '\n'.join(constants)).replace('@TYPES@', '\n'.join(types)).replace(
        '@DECLARATIONS@', declarations).replace('@REALLOC@', macro).replace(
        '@FUNCTIONS@', functions).replace('@MODEL_FUNCTIONS@', model_functions).replace(
        '@CONTEXTS@', contexts)
