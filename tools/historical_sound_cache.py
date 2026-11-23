"""Render native sample-cache lifecycle checks with deterministic PCM input.

The engine's complete cache, playback and mixer functions are retained. This
fixture replaces file decoding and the audio device, and reduces model fields.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function, switch_cases


def render_sound_callers(engine, rows):
    model = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    _, commands = switch_cases(model, 'load_cached_model', 'cmd', outermost=True)
    names = ('DIESOUND', 'SOUND', 'HITFX', 'BLOCKFX')
    parts = {
        'COMMANDS': '\n'.join('case '+name+':'+commands['CMD_MODEL_'+name]['body'] for name in names),
        'PLAYBACK': function(script, 'openbor_playsample'),
        'PROFILES': '\n'.join('check(%du,%d);' % (row['revision'],row['fixed_slots']) for row in rows),
    }
    source = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
#define GET_ARG(index) (filename)
typedef int32_t LONG;
typedef int HRESULT;
enum { S_OK=0, E_FAIL=-1, VT_EMPTY=0, VT_INTEGER=1 };
#define FAILED(hr) ((hr)<0)
typedef struct { int vt; LONG lVal; } ScriptVariant;
static uint32_t obor_profile_build;
static struct { int effectvol; } savedata={43};
static struct { int diesound; } actor,*newchar=&actor;
static struct { int hitsound,blocksound; } attack;
static int soundtoplay, loads, load_option, played, looped;

static int ScriptVariant_IntegerValue(ScriptVariant *value,LONG *output) {
    if(value->vt!=VT_INTEGER) return E_FAIL;
    *output=value->lVal;
    return S_OK;
}
static void ScriptVariant_ChangeType(ScriptVariant *value,int type) { value->vt=type; }
static int sound_load_sample(const char *file,const char *pack,int option) {
    assert(!strcmp(file,"sample") && !strcmp(pack,"fixture"));
    ++loads;load_option=option;
    return 17;
}
static int sound_play_sample(int id,unsigned priority,int left,int right,unsigned speed) {
    ++played;
    if(id<0) return -1;
    assert(id==17 && priority==0 && left==43 && right==43 && speed==100);
    return 29;
}
static int sound_loop_sample(int id,unsigned priority,int left,int right,unsigned speed) {
    ++looped;
    assert(id==17 && priority==3 && left==32 && right==37 && speed==105);
    return 31;
}
enum { DIESOUND,SOUND,HITFX,BLOCKFX };
static void command(int mode,const char *filename) {
    const char *packfile="fixture";
    switch(mode) { @COMMANDS@ }
}
@PLAYBACK@
static void check(uint32_t revision,int fixed_slots) {
    obor_profile_build=revision;
    loads=0;load_option=-1;
    for(int mode=DIESOUND;mode<=BLOCKFX;++mode) {
        command(mode,"sample");
        assert(loads==mode+1 && load_option==!fixed_slots);
    }
    assert(actor.diesound==17 && soundtoplay==17 && attack.hitsound==17 && attack.blocksound==17);
    command(HITFX,"NoNe");
    assert(loads==4 && attack.hitsound==-1);
    ScriptVariant values[]={{VT_INTEGER,17},{VT_INTEGER,3},{VT_INTEGER,32},
                            {VT_INTEGER,37},{VT_INTEGER,105},{VT_INTEGER,1}};
    ScriptVariant *args[]={values,values+1,values+2,values+3,values+4,values+5};
    ScriptVariant result={VT_EMPTY,0},*output=&result;
    played=looped=0;
    assert(openbor_playsample(args,&output,1)==S_OK && played==1 && looped==0);
    assert(fixed_slots?!output:output==&result && result.vt==VT_INTEGER && result.lVal==29);
    output=&result;
    assert(openbor_playsample(args,&output,6)==S_OK && played==1 && looped==1);
    assert(fixed_slots?!output:output==&result && result.vt==VT_INTEGER && result.lVal==31);
    output=&result;
    assert(openbor_playsample(args,&output,0)==(fixed_slots?E_FAIL:S_OK));
    assert(played==(fixed_slots?1:2) && looped==1);
    assert(fixed_slots?!output:output==&result && result.lVal==-1);
    values[0].vt=VT_EMPTY;output=&result;
    assert(openbor_playsample(args,&output,1)==E_FAIL && !output);
}
int main(void) { @PROFILES@ return 0; }
'''
    return re.sub(r'@([A-Z_]+)@',lambda match:parts[match[1]],source)


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
