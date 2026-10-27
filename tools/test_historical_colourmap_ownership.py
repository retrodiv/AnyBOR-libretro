"""Check inherited map slots and borrowed entry lifetime per source contract.

Actual model-copy, subclass and palette-disposal bodies run with reduced
models and script callbacks. Full parsing, real scripts and rendering are
separate contracts.
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

from native_sanitizers import sanitizer_environment
from test_historical_palette_loading import CONTRACTS, SOURCE
from test_historical_player import function, switch_cases


def ownership_program():
    game = (SOURCE / 'src/engines/3741/openbor.c').read_text()
    method = function(game, 'load_cached_model')
    method = method.replace('switch(cmd)', 'switch(fixture_model_command)', 1)
    _, cases = switch_cases(method, 'load_cached_model', 'fixture_model_command')
    subclass = 'case CMD_MODEL_SUBCLASS:'+cases['CMD_MODEL_SUBCLASS']['body']
    cleanup = re.search(r'(?ms)^[\t ]*if\(obor_colourmap_owner_find\(model\)\)\n.*?'
                        r'(?=\n\tprintf\("\."\);)', function(game, 'free_model'))
    if cleanup is None:
        raise ValueError('One managed palette cleanup region required')
    header = SOURCE / 'src/port/libretro/obor_colourmap_storage.h'
    if not header.is_file():
        raise ValueError('The tested source must contain its actual ownership header')
    text = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int refuse=-1;
static void *fixture_allocate(size_t bytes) {
 if(refuse==0) {refuse=-1;return NULL;}
 if(refuse>0) --refuse;
 return realloc(NULL,bytes);
}
#define OBOR_COLOURMAP_ALLOC(n) fixture_allocate(n)
#include @HEADER@
#define MAX_COLOUR_MAPS 30
typedef enum {MF_COLOURMAP=2,MF_SCRIPTS=1024} ModelFreetype;
typedef struct {int value;} s_scripts;
typedef struct {
 unsigned char **colourmap;unsigned colourmap_capacity;int maps_loaded:8;
 unsigned char *palette;
 char name[32];unsigned health;int isSubclassed;ModelFreetype freetypes;
 s_scripts *scripts;
} s_model;
static unsigned obor_profile_build;
#define MAX_PAL_SIZE 1024
#define PAL_BYTES 1024
static const unsigned pixelbytes[5]={1,1,2,3,4};
static int screenformat=4;
static void fixture_shutdown(int code,const char *format,...) {
 (void)code;(void)format;assert(!"unexpected fatal conversion");abort();
}
#define shutdown fixture_shutdown
@COPY@
@CONVERTER@
@HASFREE@
static void release(s_model *model) {
 int i;
 @CLEANUP@
}
static s_model *parent_lookup;
static s_model *findmodel(const char *name) {
 assert(!strcmp(name,"parent"));return parent_lookup;
}
static unsigned copy_calls;
static s_scripts *copy_from,*copy_to;
static void copy_all_scripts(s_scripts *from,s_scripts *to,int mode) {
 assert(mode==1);copy_from=from;copy_to=to;++copy_calls;*to=*from;
}
#define GET_ARG(n) ((void)(n),"parent")
enum {CMD_MODEL_SUBCLASS=1};
static const char *shutdownmessage;
static int inherit(s_model *newchar) {
 s_model *tempmodel;s_scripts *tempscripts;
 shutdownmessage=NULL;switch(CMD_MODEL_SUBCLASS) {@SUBCLASS@}
lCleanup:
 return shutdownmessage==NULL;
}
static void initialize(s_model *model,s_scripts *scripts,unsigned extent) {
 *model=(s_model){0};model->scripts=scripts;model->freetypes=(ModelFreetype)(MF_COLOURMAP|MF_SCRIPTS);
 strcpy(model->name,"parent");model->health=77;
 assert(obor_colourmap_reserve(model,extent));
 for(unsigned i=0;i<extent;i+=extent-1) {
  unsigned char *p=malloc(256);assert(p);memset(p,i?23:17,256);
  assert(obor_colourmap_replace(model->colourmap,i,p));
 }
 model->maps_loaded=extent==30?2:4;
}
static void check(unsigned revision,int fixed) {
 obor_profile_build=revision;unsigned extent=fixed?30:4;
 for(int parent_first=0;parent_first<2;++parent_first) {
  s_model parent,child;s_scripts ps={37},cs={101};
  initialize(&parent,&ps,extent);initialize(&child,&cs,extent);
  unsigned char **child_before=child.colourmap;copy_calls=0;parent_lookup=NULL;
  assert(!inherit(&child) && !copy_calls && child.colourmap==child_before && child.scripts==&cs);
  parent_lookup=&parent;
  assert(inherit(&child));
  assert(copy_calls==1 && copy_from==&ps && copy_to==&cs && cs.value==37);
  assert(child.scripts==&cs && child.freetypes==MF_SCRIPTS && child.isSubclassed==1);
  assert(child.health==77 && !strcmp(child.name,"parent") && child.maps_loaded==parent.maps_loaded);
  assert((child.colourmap!=parent.colourmap)==fixed);
  for(unsigned i=0;i<extent;++i) assert(child.colourmap[i]==parent.colourmap[i]);
  unsigned char *old=child.colourmap[0],*replacement=malloc(256);assert(replacement);
  memset(replacement,41,256);assert(obor_colourmap_replace(child.colourmap,0,replacement));
  assert(child.colourmap[0][0]==41 && parent.colourmap[0][0]==(fixed?17:41));
  assert(old[0]==17); /* a selected entry may still be borrowed */
  if(parent_first) {
   release(&parent);assert(!parent.colourmap && !parent.colourmap_capacity && !parent.maps_loaded);
   assert(child.colourmap[0][0]==41 && child.colourmap[extent-1][0]==23);release(&child);
  } else {
   release(&child);assert(!child.colourmap && !child.colourmap_capacity && !child.maps_loaded);
   assert(parent.colourmap[0][0]==(fixed?17:41) && parent.colourmap[extent-1][0]==23);release(&parent);
  }
  assert(!obor_colourmap_tables);
 }
 if(fixed) for(int failure=0;failure<3;++failure) {
  s_model parent,child,before;s_scripts ps={37},cs={101};
  initialize(&parent,&ps,extent);initialize(&child,&cs,extent);before=child;
  parent_lookup=&parent;copy_calls=0;refuse=failure;
  assert(!inherit(&child) && copy_calls==0 && refuse==-1);
  assert(child.colourmap==before.colourmap && child.scripts==before.scripts && cs.value==101);
  assert(child.health==before.health && child.colourmap[0][0]==17);
  release(&parent);release(&child);assert(!obor_colourmap_tables);
 }
}
static void managed_conversion(unsigned revision,int fixed) {
 obor_profile_build=revision;unsigned extent=fixed?30:4;
 for(int parent_first=0;parent_first<2;++parent_first) {
  s_model parent,child;s_scripts ps={37},cs={101};
  initialize(&parent,&ps,extent);initialize(&child,&cs,extent);
  unsigned char *palette=malloc(PAL_BYTES);assert(palette);
  for(unsigned i=0;i<PAL_BYTES;++i) palette[i]=(unsigned char)(i*29u+11u);
  parent.palette=palette;parent_lookup=&parent;assert(inherit(&child));
  unsigned char flags[30]={1};unsigned char *old=child.colourmap[0],*untouched=child.colourmap[extent-1];
  for(int failure=0;failure<(fixed?1:2);++failure) {
   refuse=failure;assert(!convert_map_to_palette(&child,flags) && refuse==-1);
   assert(child.colourmap[0]==old && old[0]==17 && child.colourmap[extent-1]==untouched);
  }
  assert(convert_map_to_palette(&child,flags));
  for(unsigned i=0;i<PAL_BYTES;++i) assert(child.colourmap[0][i]==palette[17*4+i%4]);
  assert(child.colourmap[extent-1]==untouched && untouched[0]==23 && old[0]==17);
  if(parent_first) {
   release(&parent);assert(child.colourmap[0][0]==palette[17*4]);
   if(!fixed) assert(old[0]==17);
   release(&child);
  } else {
   release(&child);assert(parent.colourmap[0][0]==(fixed?17:palette[17*4]));
   if(!fixed) assert(old[0]==17);
   release(&parent);
  }
  free(palette);assert(!obor_colourmap_tables && !obor_colourmap_owners);
 }
}
int main(int argc,char **argv) {
 assert(argc==3);unsigned revision=(unsigned)strtoul(argv[1],NULL,10);int fixed=atoi(argv[2]);
 check(revision,fixed);managed_conversion(revision,fixed);return 0;
}
'''
    values = {'HEADER': json.dumps(str(header.resolve())),
              'COPY': function(game, 'obor_colourmap_reserve')+'\n'+function(game, 'obor_model_copy'),
              'CONVERTER': function(game, 'convert_map_to_palette'),
              'HASFREE': function(game, 'hasFreetype'),
              'CLEANUP': cleanup[0], 'SUBCLASS': subclass}
    return re.sub(r'@('+'|'.join(values)+r')@', lambda m: values[m[1]], text)


class HistoricalColourmapOwnershipTests(unittest.TestCase):
    def test_subclass_slots_and_borrowed_maps_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-map-ownership-') as temporary:
            work = Path(temporary)
            source, executable = work / 'probe.c', work / 'probe'
            source.write_text(ownership_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc'))+[
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-function', '-Wno-sign-compare', '-g', '-fsanitize=address,undefined',
                str(source), '-o', str(executable)], check=True, timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(executable), str(row['revision']), str(int(bool(row['fixed_slots'])))],
                                   check=True, timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
