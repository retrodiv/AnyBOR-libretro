"""Render exact WAV loader bodies against bounded authored packfile input.

The sample declaration, constants, integer typedefs and loader remain unchanged.
Packfile I/O, allocation observation and resident-byte registration are fixtures;
this does not execute the mixer or establish audible/gameplay acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def render_wave(parts, *, legacy16, registration, revision, labels, bounded_sizes=False):
    if (not isinstance(parts, dict) or set(parts) !=
            {'loadwave', 'sample', 'constants', 'types'} or
            any(not isinstance(s, str) or not s.strip() or len(s) > 65536
                for s in parts.values())):
        raise ValueError('Bounded exact loader, sample, constants and type sources required')
    if any(type(value) is not bool for value in (legacy16, registration, bounded_sizes)):
        raise ValueError('Explicit byte/sample and registration expectations required')
    if type(revision) is not int or not 0 <= revision <= 0x7fffffff:
        raise ValueError('Bounded native profile context required')
    if (not isinstance(labels, list) or not 0 < len(labels) <= 256 or
            any(not isinstance(label, str) or not re.fullmatch(
                r'[A-Za-z0-9_-]{1,127}', label) for label in labels) or
            len(set(labels)) != len(labels)):
        raise ValueError('Unique bounded source identifiers required')
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@TYPES@
@CONSTANTS@
@SAMPLE@
static uint32_t obor_profile_build=@REVISION@;
static const int legacy16=@LEGACY@,registration=@REGISTRATION@;
static const int bounded_sizes=@BOUNDED@;
static unsigned char input[512];
static size_t input_size,position,payload_offset,allocation_size;
static void *allocation;
static unsigned allocations,frees,opens,closes,payload_reads,registrations;
static size_t payload_request,registered_bytes;
static int open_error,allocation_error;
static u16 SwapLSB16(u16 value) {return value;}
static u32 SwapLSB32(u32 value) {return value;}
static void *tracked_malloc(size_t size) {
 assert(!allocation && size<=sizeof(input)+8);++allocations;allocation_size=size;
 if(allocation_error)return NULL;
 return allocation=malloc(size);
}
static void tracked_free(void *pointer) {
 assert(pointer && pointer==allocation);++frees;free(pointer);allocation=NULL;
}
static int openpackfile(const char *name,const char *packname) {
 assert(!strcmp(name,"fixture.wav") && !strcmp(packname,"fixture.pak"));
 ++opens;position=0;return open_error?-1:1;
}
static int closepackfile(int handle) {assert(handle==1);++closes;return 0;}
static int readpackfile(int handle,void *output,int bytes) {
 assert(handle==1 && bytes>=0 && position<=input_size);
 if(output==allocation) {
  ++payload_reads;payload_request=(size_t)bytes;
  assert(position==payload_offset && (size_t)bytes<=allocation_size);
 }
 size_t count=(size_t)bytes;
 if(count>input_size-position)count=input_size-position;
 memcpy(output,input+position,count);position+=count;return (int)count;
}
static int seekpackfile(int handle,int offset,int origin) {
 assert(handle==1 && (origin==SEEK_SET || origin==SEEK_CUR));
 long next=(origin==SEEK_SET?0:(long)position)+offset;
 assert(next>=0 && (size_t)next<=input_size);position=(size_t)next;return (int)position;
}
static void obor_resources_member_bytes_loaded(const char *name,uint32_t offset,
                                               void *base,void *resident,size_t bytes) {
 assert(!strcmp(name,"fixture.wav") && offset==payload_offset);
 assert(base==allocation && resident==allocation);++registrations;registered_bytes=bytes;
}
#define malloc tracked_malloc
#define free tracked_free
@LOADER@
#undef malloc
#undef free

static void put16(size_t at,unsigned value) {
 assert(at+2<=sizeof(input));input[at]=(unsigned char)value;input[at+1]=(unsigned char)(value>>8);
}
static void put32(size_t at,unsigned value) {
 assert(at+4<=sizeof(input));for(unsigned n=0;n<4;++n)input[at+n]=(unsigned char)(value>>(8*n));
}
static void tag(const char *name,unsigned bytes) {
 assert(input_size+8<=sizeof(input));memcpy(input+input_size,name,4);
 put32(input_size+4,bytes);input_size+=8;
}
static void make_wave(unsigned bits,unsigned channels,unsigned data,
                      unsigned trailing,int junk,int extended) {
 assert(!allocation);memset(input,0,sizeof(input));input_size=0;
 tag("RIFF",0);memcpy(input+input_size,"WAVE",4);input_size+=4;
 if(junk) {tag("JUNK",4);input_size+=4;}
 tag("fmt ",16+(extended?2:0));
 put16(input_size,1);put16(input_size+2,channels);put32(input_size+4,22050);
 put32(input_size+8,22050*channels*(bits/8));put16(input_size+12,channels*(bits/8));
 put16(input_size+14,bits);input_size+=16+(extended?2:0);
 tag("data",data);payload_offset=input_size;
 for(unsigned n=0;n<data;++n)input[input_size++]=(unsigned char)(n*37+19);
 if(trailing) {assert(trailing==64);tag("JUNK",56);
  for(unsigned n=0;n<56;++n)input[input_size++]=(unsigned char)(n*13+7);}
 put32(4,(unsigned)(input_size-8));
 position=allocation_size=payload_request=registered_bytes=0;
 allocations=frees=opens=closes=payload_reads=registrations=0;
 open_error=allocation_error=0;
}
static samplestruct sentinel(void) {
 samplestruct value={0};value.soundlen=13;value.bits=17;value.frequency=23;value.channels=29;
 return value;
}
static void unchanged(samplestruct *value) {
 assert(!value->sampleptr && value->soundlen==13 && value->bits==17);
 assert(value->frequency==23 && value->channels==29);
}
static unsigned wave_checks(void) {
 const unsigned sizes[]={0,1,7,16,64},limits[]={0,1,5,16,80,MAX_SOUND_LEN};
 unsigned cases=0;
 assert(sizeof(u16)==2 && sizeof(u32)==4);
 const u16 native_one=1;assert(*(const unsigned char *)&native_one==1);
 for(unsigned bits=8;bits<=16;bits+=8)for(unsigned channels=1;channels<=2;++channels)
 for(unsigned a=0;a<sizeof(sizes)/sizeof(*sizes);++a)
 for(unsigned b=0;b<sizeof(limits)/sizeof(*limits);++b)
 for(unsigned trailing=0;trailing<=64;trailing+=64)
 for(int junk=0;junk<=1;++junk)for(int extended=0;extended<=1;++extended) {
  make_wave(bits,channels,sizes[a],trailing,junk,extended);
  samplestruct sample=sentinel();
  unsigned trimmed=sizes[a]<limits[b]?sizes[a]:limits[b];
  unsigned bytes=trimmed*(legacy16 && bits==16?2:1);
  int loaded=bytes<=sizes[a]+trailing;
  int result=loadwave("fixture.wav","fixture.pak",&sample,limits[b]);
  assert(opens==1 && closes==1 && allocations==1 && allocation_size==bytes+8);
  assert(payload_reads==1 && payload_request==bytes);
  if(loaded) {
   assert(result==(int)trimmed && sample.sampleptr==allocation);
   assert(sample.soundlen==(int)(legacy16?trimmed:trimmed/(bits==16?2:1)));
   assert(sample.bits==(int)bits && sample.channels==(int)channels && sample.frequency==22050);
   assert(!memcmp(sample.sampleptr,input+payload_offset,bytes));
   unsigned char fill=legacy16 && bits==16?0:0x80;
   for(size_t n=bytes;n<allocation_size;++n)
    assert(((unsigned char *)sample.sampleptr)[n]==fill);
   assert(registrations==(unsigned)registration);
   if(registration)assert(registered_bytes==bytes);
   tracked_free(sample.sampleptr);
  } else {assert(result==0);unchanged(&sample);assert(!registrations);}
  assert(!allocation && frees==1);++cases;
 }
 assert(cases==960);return cases;
}
static unsigned error_checks(void) {
 unsigned cases=0;
 make_wave(8,1,16,0,0,0);
 assert(loadwave("fixture.wav","fixture.pak",NULL,MAX_SOUND_LEN)==0);
 assert(!opens && !allocations);++cases;
 make_wave(8,1,16,0,0,0);open_error=1;samplestruct sample=sentinel();
 assert(loadwave("fixture.wav","fixture.pak",&sample,MAX_SOUND_LEN)==0);
 unchanged(&sample);assert(opens==1 && !closes && !allocations);++cases;
 make_wave(8,1,16,0,0,0);allocation_error=1;sample=sentinel();
 assert(loadwave("fixture.wav","fixture.pak",&sample,MAX_SOUND_LEN)==0);
 unchanged(&sample);assert(opens==1 && closes==1 && allocations==1 && !allocation);
 assert(!payload_reads && !registrations);++cases;
 for(unsigned length=0;length<12;++length) {
  make_wave(8,1,16,0,0,0);input_size=length;sample=sentinel();
  assert(loadwave("fixture.wav","fixture.pak",&sample,MAX_SOUND_LEN)==0);
  unchanged(&sample);assert(opens==1 && closes==1 && !allocations);++cases;
 }
 if(bounded_sizes) {
  /* A large caller limit still accepts small complete input after trimming. */
  make_wave(16,1,16,64,0,0);sample=sentinel();
  assert(loadwave("fixture.wav","fixture.pak",&sample,UINT_MAX)==16);
  size_t bytes=legacy16?32:16;
  assert(allocation_size==bytes+8 && payload_request==bytes);
  assert(sample.soundlen==(legacy16?16:8) && sample.sampleptr==allocation);
  assert(!memcmp(sample.sampleptr,input+payload_offset,bytes));
  assert(registrations==(unsigned)registration);
  if(registration)assert(registered_bytes==bytes);
  tracked_free(sample.sampleptr);++cases;
  for(unsigned bits=8;bits<=16;bits+=8) {
   make_wave(bits,1,16,0,0,0);put32(payload_offset-4,UINT_MAX);sample=sentinel();
   assert(loadwave("fixture.wav","fixture.pak",&sample,UINT_MAX)==0);
   unchanged(&sample);assert(opens==1 && closes==1 && !allocations);
   assert(!payload_reads && !registrations);++cases;
  }
 }
 assert(cases==(bounded_sizes?18u:15u));return cases;
}
int main(void) {
 @CHECKS@
 puts(@OBSERVATION@);return 0;
}
'''
    values = {'TYPES': parts['types'], 'CONSTANTS': parts['constants'],
              'SAMPLE': parts['sample'], 'LOADER': parts['loadwave'],
              'REVISION': str(revision), 'LEGACY': str(int(legacy16)),
              'REGISTRATION': str(int(registration)),
              'BOUNDED': str(int(bounded_sizes)),
              'CHECKS': '\n'.join('wave_checks();error_checks();' for _ in labels),
              'OBSERVATION': json.dumps(json.dumps({'status': 'PASS',
                  'sources': len(labels), 'wave_cases_each': 960,
                  'error_cases_each': 18 if bounded_sizes else 15}))}
    return re.sub(r'@(' + '|'.join(values) + r')@', lambda match: values[match[1]], code)
