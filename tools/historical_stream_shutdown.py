"""Render stream ownership checks around a complete global script cleanup.

Unrelated VM lists and variable stores are empty and their services refuse
unexpected work. This checks stream release, not complete VM shutdown.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_shutdown(*, revisions, shutdown, slots, physical_fixed,
                    release_streams, record=None, record_pack=None):
    if (not isinstance(revisions, list) or not 0 < len(revisions) <= 128 or
        any(type(n) is not int or not 0 < n <= 0xffffffff for n in revisions) or
        revisions != sorted(set(revisions)) or type(slots) is not int or
        not 4 <= slots <= 1024 or type(physical_fixed) is not bool or
        type(release_streams) is not bool or physical_fixed and release_streams or
        not isinstance(shutdown, str) or not 0 < len(shutdown) <= 32768 or
        '\0' in shutdown or not re.match(r'\s*void\s+Script_Global_Clear\s*\(', shutdown)):
        raise ValueError('Complete cleanup and explicit bounded ownership context required')
    if record is None:
        if record_pack is not None:
            raise ValueError('Packing belongs to an explicit original record')
    elif (not isinstance(record, str) or not 0 < len(record) <= 8192 or
          '\0' in record or not re.fullmatch(r'\s*typedef\s+struct\s*\{[^{}]*\}\s*s_filestream\s*;\s*', record) or
          type(record_pack) is not int or record_pack not in (1, 2, 4, 8, 16)):
        raise ValueError('Complete original stream record and native packing required')
    code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
@RENAME_RECORD@
#include "openborscript.h"
#include "openbor.h"
@OWN_RECORD@
#undef malloc
#undef calloc
#undef free
#undef printf
#ifdef NDEBUG
#error Stream shutdown checks require active assertions
#endif
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Stream shutdown ownership: %s\n",m);abort();}}while(0)
uint32_t obor_profile_build;
List theFunctionList,scriptheap;
s_variantnode **global_var_list;
ScriptVariant *indexed_var_list;
int max_global_vars,max_indexed_vars,max_global_var_index;
s_spawn_entry spawnentry;
@STREAM_DECLARATION@
static void *owners[128];
static void *table_owner;
static unsigned expected[128],released[128],owner_count;
static unsigned list_clears,list_sizes,list_resets,string_clears,import_clears;
static char borrowed[]="retained borrowed storage";
static void *owned(size_t bytes,int must_release){
 CHECK(bytes>0 && bytes<1048576 && owner_count<128,"bounded owned allocation");
 void *p=calloc(1,bytes);CHECK(p,"owned allocation");
 owners[owner_count]=p;expected[owner_count]=must_release;released[owner_count++]=0;return p;
}
static void release_owned(void *p){
 if(!p)return;
 if(p==table_owner)for(unsigned i=1;i<owner_count;++i)
  CHECK(released[i]==expected[i],"buffers must precede table release");
 unsigned matches=0;
 for(unsigned i=0;i<owner_count;++i)if(owners[i]==p){
  CHECK(expected[i] && !released[i],"unexpected or repeated release");
  ++released[i];++matches;
 }
 CHECK(matches==1,"release must have one owner");
}
static void empty_clear(List *p){
 CHECK(p==&theFunctionList || p==&scriptheap,"declared empty list");++list_clears;
}
static int empty_size(const List *p){CHECK(p==&scriptheap,"empty heap list");++list_sizes;return 0;}
static void empty_reset(List *p){CHECK(p==&scriptheap,"empty heap reset");++list_resets;}
static int refuse_next(List *p){(void)p;abort();}
static char *refuse_name(const List *p){(void)p;abort();}
static void *refuse_retrieve(const List *p){(void)p;abort();}
static void refuse_node(void *p){(void)p;abort();}
static void refuse_variant(ScriptVariant *p){(void)p;abort();}
static void refuse_names(void){abort();}
static void observe_strings(void){++string_clears;}
static void observe_imports(void){++import_clears;}
static int ignore_printf(const char *format,...){(void)format;return 0;}
HRESULT Interpreter_Call(Interpreter *interpreter){(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter){(void)interpreter;abort();}
#undef List_Clear
#undef List_GetSize
#undef List_Reset
#undef List_GotoNext
#undef List_GetName
#undef List_Retrieve
#undef ScriptVariant_Clear
#undef StrCache_Clear
#undef ImportCache_Clear
#define List_Clear empty_clear
#define List_GetSize empty_size
#define List_Reset empty_reset
#define List_GotoNext refuse_next
#define List_GetName refuse_name
#define List_Retrieve refuse_retrieve
#define _freeheapnode refuse_node
#define ScriptVariant_Clear refuse_variant
#define obor_script_variable_names_clear refuse_names
#define StrCache_Clear observe_strings
#define ImportCache_Clear observe_imports
#define free release_owned
#define printf ignore_printf
@SHUTDOWN@
#undef free
#undef printf
static unsigned cases;
static void check_case(unsigned mode){
 owner_count=list_clears=list_sizes=list_resets=string_clears=import_clears=0;
 global_var_list=NULL;indexed_var_list=NULL;max_global_vars=max_indexed_vars=0;
 max_global_var_index=17;memset(&spawnentry,0xa5,sizeof(spawnentry));
 table_owner=NULL;
 @SETUP@
 if(mode>=2){
  const unsigned indices[]={0,2,@SLOTS@-1};
  for(unsigned n=0;n<3;++n){
   unsigned i=indices[n];filestreams[i].buf=owned(9,@RELEASE@);
   memcpy(filestreams[i].buf,"a\0b\r\nc\n",8);
   filestreams[i].pos=(int)n;filestreams[i].size=8;
  }
 }
 @BORROWED_TAIL@
 Script_Global_Clear();
 CHECK(list_clears==2 && list_sizes==1 && list_resets==1,"empty native list sequence");
 CHECK(string_clears==1 && import_clears==1,"cache cleanup callbacks");
 CHECK(max_global_var_index==-1 && !global_var_list && !indexed_var_list,"native variable reset");
 for(size_t i=0;i<sizeof(spawnentry);++i)CHECK(!((unsigned char*)&spawnentry)[i],"spawn reset");
 @VERIFY_TABLE@
 CHECK(!memcmp(borrowed,"retained borrowed storage",sizeof(borrowed)),"borrowed bytes preserved");
 for(unsigned i=0;i<owner_count;++i){
  CHECK(released[i]==expected[i],"required owner release");free(owners[i]);owners[i]=NULL;
 }
 @RESET@
 ++cases;
}
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];
  for(unsigned mode=0;mode<4;++mode)check_case(mode);
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"cases\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),cases);return 0;
}
'''
    values = dict(
        RENAME_RECORD='#define s_filestream anchor_filestream' if record is not None else '',
        OWN_RECORD=('#undef s_filestream\n#pragma pack(push,'+str(record_pack)+')\n'+record+
                    '\n#pragma pack(pop)') if record is not None else '',
        STREAM_DECLARATION=('s_filestream filestreams['+str(slots)+'];' if physical_fixed else
                            's_filestream *filestreams;int numfilestreams;'),
        SHUTDOWN=shutdown, SLOTS=str(slots), RELEASE='1' if release_streams else '0',
        REVISIONS=','.join(str(n)+'u' for n in revisions),
        SETUP=('memset(filestreams,0,sizeof(filestreams));' if physical_fixed else
               'numfilestreams=mode ? '+str(slots)+':0;filestreams=mode ? '
               'owned((numfilestreams+(mode==3))*sizeof(*filestreams),'+
               ('1' if release_streams else '0')+'):NULL;table_owner=filestreams;'),
        BORROWED_TAIL='' if physical_fixed else
                      'if(mode==3)filestreams[numfilestreams].buf=borrowed;',
        VERIFY_TABLE=('' if physical_fixed else
                      'CHECK(!filestreams && !numfilestreams,"dynamic table retired");'
                      if release_streams else
                      'CHECK(numfilestreams==(mode ? '+str(slots)+':0),"retained native count");'),
        RESET='memset(filestreams,0,sizeof(filestreams));' if physical_fixed else
              'filestreams=NULL;numfilestreams=0;')
    return re.sub(r'@('+'|'.join(values)+r')@', lambda m:values[m[1]], code)
