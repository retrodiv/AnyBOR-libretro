"""Render a native level cleanup ownership ledger for dynamic text/layer records.

The complete native function runs unchanged. Script clearing is an observation,
and tracked releases are checked before the fixture retires its allocations.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_level_cleanup(source, *, revision, release_fields, script_fields,
                         spawn_scripts, revisions=None, stream_clear='',
                         stream_release_before=None, stream_slots=None,
                         profile_helpers='', release_extents=None):
    if not isinstance(source, str) or not source.strip() or len(source) > 65536:
        raise ValueError('Bounded complete native cleanup function required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit bounded profile revision required')
    if type(spawn_scripts) is not bool:
        raise ValueError('Explicit native spawn script layout required')
    revisions = [revision] if revisions is None else revisions
    if (not isinstance(revisions, list) or not 0 < len(revisions) <= 1024 or
            any(type(value) is not int or not 0 < value <= 0xffffffff for value in revisions) or
            revisions != sorted(set(revisions)) or revision not in revisions):
        raise ValueError('Explicit unique sorted profile revisions required')
    for fields in (release_fields, script_fields):
        if (not isinstance(fields, list) or not 0 < len(fields) <= 32 or
                any(not isinstance(f, str) or not re.fullmatch(r'[A-Za-z_]\w*', f)
                    for f in fields) or len(fields) != len(set(fields))):
            raise ValueError('Distinct explicit native field names required')
    if (set(release_fields) & {'layers', 'textobjs'} or
            set(release_fields) & set(script_fields)):
        raise ValueError('Traversed records and script fields have separate ownership')
    release_extents = {} if release_extents is None else release_extents
    if (not isinstance(release_extents, dict) or
            not set(release_extents) <= set(release_fields) or
            any(not isinstance(counts, list) or len(counts) != len(revisions) or
                any(type(count) is not int or not 1 <= count <= 4096 for count in counts)
                for counts in release_extents.values())):
        raise ValueError('Explicit bounded allocation extents for each profile required')
    streams=bool(stream_clear)
    if not isinstance(profile_helpers,str)or len(profile_helpers)>8192 or '\0'in profile_helpers:
        raise ValueError('Bounded complete native profile providers required')
    if (not isinstance(stream_clear,str) or len(stream_clear)>8192 or
        streams and (not re.match(r'\s*void\s+obor_filestream_level_clear\s*\(',stream_clear) or
                     type(stream_release_before)is not int or not 0<stream_release_before<=0xffffffff or
                     type(stream_slots)is not int or not 4<=stream_slots<=1024) or
        not streams and (stream_release_before is not None or stream_slots is not None)):
        raise ValueError('Complete native stream cleanup and explicit extent/boundary required')
    declarations = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef malloc
#undef calloc
#undef free
#undef printf
#ifdef NDEBUG
#error Ownership assertions must remain enabled
#endif
#define assert(condition) do {if(!(condition)) { \
 fputs("Unexpected level cleanup ownership\n",stderr);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
static unsigned fixture_profile_index;
@RELEASE_EXTENTS@
@PROFILE_HELPERS@
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
static void *owned[128];
static unsigned releases[128],expected_releases[128],owned_count,clear_count;
static void *script_addresses[64];
static unsigned script_count,script_cleared[64];
static s_screen shared_background;
static s_screen *background=&shared_background;
static void *allocate_owned(size_t size) {
 assert(size>0 && size<=1024*1024 && owned_count<128);
 void *p=calloc(1,size);assert(p);owned[owned_count]=p;
 releases[owned_count]=0;expected_releases[owned_count++]=1;return p;
}
static void release_owned(void *p) {
 if(!p)return;
 unsigned matched=0;
 for(unsigned i=0;i<owned_count;++i)if(owned[i]==p) {
  assert(releases[i]==0);++releases[i];++matched;
 }
 assert(matched==1);
}
static void observe_clear(void *script,int mode) {
 assert(mode==2);unsigned matched=0;
 for(unsigned i=0;i<script_count;++i)if(script_addresses[i]==script) {
  assert(script_cleared[i]==0);++script_cleared[i];++matched;
 }
 assert(matched==1);++clear_count;
}
static void expect_script(void *script) {
 assert(script_count<64);script_addresses[script_count]=script;
 script_cleared[script_count++]=0;
}
#define free release_owned
@STREAM_DECLARATIONS@
#define Script_Clear observe_clear
#define free_level cleanup_under_test
@SOURCE@
#undef free_level
#undef Script_Clear
#undef free
'''
    main = r'''
static unsigned cases;
static void cleanup_case(int texts,int resources) {
 owned_count=clear_count=script_count=0;
 s_level *lv=allocate_owned(sizeof(*lv));
 @SCRIPTS@
 lv->numtextobjs=texts;
 lv->textobjs=allocate_owned((texts+1)*sizeof(*lv->textobjs));
 for(int i=0;i<texts;++i) {
  lv->textobjs[i].text=allocate_owned(4);
  memcpy(lv->textobjs[i].text,"abc",4);
 }
 if(resources) {
  @RELEASE_FIELDS@
  lv->numlayers=3;lv->layers=allocate_owned(3*sizeof(*lv->layers));
  lv->layers[1].gfx.handle=background;
  lv->layers[2].gfx.handle=allocate_owned(sizeof(s_screen));
  @SPAWN_SCRIPTS@
  @BLEND_SEED@
 }
 @STREAM_SEED@
 cleanup_under_test(NULL);
 assert(clear_count==0);
 for(unsigned i=0;i<owned_count;++i)assert(releases[i]==0);
 cleanup_under_test(lv);
 @STREAM_VERIFY@
 assert(clear_count==script_count);
 for(unsigned i=0;i<script_count;++i)assert(script_cleared[i]==1);
 for(unsigned i=0;i<owned_count;++i) {
  assert(releases[i]==expected_releases[i]);free(owned[i]);owned[i]=NULL;
 }
 @STREAM_RESET@
 ++cases;
}
int main(void) {
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned profile=0;profile<sizeof(revisions)/sizeof(*revisions);++profile) {
  fixture_profile_index=profile;
  obor_profile_build=revisions[profile];owned_count=clear_count=script_count=0;
  cleanup_under_test(NULL);assert(owned_count==0 && clear_count==0);
  for(int resources=0;resources<2;++resources) {
   cleanup_case(0,resources);cleanup_case(1,resources);cleanup_case(3,resources);
  }
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''
    spawn = ''
    if spawn_scripts:
        if 'spawnpoints' not in release_fields:
            raise ValueError('Spawn script layout needs owned spawnpoints')
        spawn = r'''
  lv->numspawns=1;
  s_spawn_script_list_node *head=NULL;
  s_spawn_script_cache_node *cache=NULL;
  for(int i=0;i<2;++i) {
   s_spawn_script_list_node *node=allocate_owned(sizeof(*node));
   s_spawn_script_cache_node *entry=allocate_owned(sizeof(*entry));
   entry->cached_spawn_script=allocate_owned(sizeof(*entry->cached_spawn_script));
   entry->filename=allocate_owned(4);memcpy(entry->filename,"abc",4);
   expect_script(entry->cached_spawn_script);
   node->spawn_script=entry->cached_spawn_script;
   node->next=head;head=node;entry->next=cache;cache=entry;
  }
  lv->spawnpoints[0].spawn_script_list_head=head;
  lv->spawn_script_cache_head=cache;
'''
    stream_declarations=stream_seed=stream_verify=stream_reset=''
    if streams:
        stream_declarations='static s_filestream *filestreams;\nstatic int numfilestreams;\n'+stream_clear
        stream_seed=r'''
 unsigned stream_table_slot=owned_count;
 filestreams=allocate_owned(@SLOTS@*sizeof(*filestreams));numfilestreams=@SLOTS@;
 expected_releases[stream_table_slot]=0;
 unsigned stream_owned[3],stream_index[3]={0,1,@SLOTS@-1};
 for(unsigned j=0;j<3;++j) {
  unsigned i=stream_index[j];stream_owned[j]=owned_count;
  filestreams[i].buf=allocate_owned(4);memcpy(filestreams[i].buf,"abc",4);
  filestreams[i].pos=(int)j+7;filestreams[i].size=j+61;filestreams[i].obor_capacity=4;
  expected_releases[stream_owned[j]]=obor_profile_build<@BOUNDARY@;
 }
'''.replace('@SLOTS@',str(stream_slots)).replace('@BOUNDARY@',str(stream_release_before))
        stream_verify=r'''
 assert(numfilestreams==@SLOTS@ && filestreams==owned[stream_table_slot]);
 for(unsigned j=0;j<3;++j) {
  unsigned i=stream_index[j];int released=obor_profile_build<@BOUNDARY@;
  assert(filestreams[i].pos==(int)j+7 && filestreams[i].size==j+61);
  assert(filestreams[i].obor_capacity==(released?0u:4u));
  assert(filestreams[i].buf==(released?NULL:owned[stream_owned[j]]));
 }
'''.replace('@SLOTS@',str(stream_slots)).replace('@BOUNDARY@',str(stream_release_before))
        stream_reset='filestreams=NULL;numfilestreams=0;'
    blend_seed=''
    if profile_helpers and 'blendings'in release_fields:
        blend_seed=r'''
  lv->numpalettes=1;
  for(int j=0;j<OBOR_BLEND_COUNT;++j)lv->blendings[0][j]=allocate_owned(4);
  for(int j=OBOR_BLEND_COUNT;j<MAX_BLENDINGS;++j)
   lv->blendings[0][j]=(unsigned char *)&shared_background;
'''
    extents = '\n'.join('static const unsigned fixture_' + field + '_extents[]={' +
                         ','.join(map(str, counts)) + '};'
                         for field, counts in release_extents.items())
    declarations = declarations.replace('@RELEASE_EXTENTS@', extents).replace(
        '@REVISION@', str(revision)).replace('@SOURCE@', source).replace(
        '@STREAM_DECLARATIONS@',stream_declarations).replace('@PROFILE_HELPERS@',profile_helpers)
    return declarations + main.replace('@SCRIPTS@', '\n'.join(
        'expect_script(&lv->%s);' % field for field in script_fields)).replace(
        '@RELEASE_FIELDS@', '\n'.join(
            'lv->%s=allocate_owned(%s*sizeof(*lv->%s));' % (
                field, 'fixture_' + field + '_extents[fixture_profile_index]'
                if field in release_extents else '1', field)
            for field in release_fields)).replace('@SPAWN_SCRIPTS@', spawn).replace(
                '@REVISIONS@', ','.join(map(str, revisions))).replace(
                    '@STREAM_SEED@',stream_seed).replace('@STREAM_VERIFY@',stream_verify).replace(
                        '@STREAM_RESET@',stream_reset).replace('@BLEND_SEED@',blend_seed)
