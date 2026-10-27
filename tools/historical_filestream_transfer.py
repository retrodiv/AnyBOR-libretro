"""Render a native-header stream opening contract with a bounded PAK provider.

The provider supplies owned bytes; filesystem paths and unrelated VM calls
are refused. This measures callback transfer/layout, not archive parsing or
the complete filesystem backend.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_pak_open(*, revisions, opening, helpers='', payload, owned_extent=False,
                    level_streams=False, header_includes=None, provider_const_name=False):
    if (not isinstance(revisions,list) or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions) or
        len(set(revisions))!=len(revisions) or not isinstance(opening,str) or
        not 0<len(opening)<=32768 or not re.match(r'\s*HRESULT\s+openbor_openfilestream\s*\(',opening) or
        not isinstance(helpers,str) or len(helpers)>32768 or type(owned_extent)is not bool or
        type(level_streams)is not bool or
        type(provider_const_name)is not bool or
        not isinstance(payload,list) or not 0<len(payload)<=4096 or
        any(type(n)is not int or not 0<=n<=255 for n in payload)):
        raise ValueError('Explicit bounded callback, revisions, owned bytes and native helper context required')
    if '\0'in opening+helpers:
        raise ValueError('Native sources must retain valid text bytes')
    header_includes=['openborscript.h','openbor.h']if header_includes is None else header_includes
    if (not isinstance(header_includes,list)or not 0<len(header_includes)<=16 or
        any(not isinstance(name,str)or len(name)>256 or not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',name)or
            name.startswith('/')or '..'in name.split('/')for name in header_includes)or
        len(set(header_includes))!=len(header_includes)):
        raise ValueError('Explicit ordered native header includes required')
    code=r'''
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
@HEADERS@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#undef fopen
#undef fseek
#undef ftell
#undef fread
#undef fclose
#undef StrCache_Get
#undef ScriptVariant_Clear
#undef ScriptVariant_ChangeType
#undef ScriptVariant_IntegerValue
#define StrCache_Get fixture_stream_string
#define ScriptVariant_Clear fixture_stream_clear
#define ScriptVariant_ChangeType fixture_stream_type
#define ScriptVariant_IntegerValue fixture_stream_integer
#define CHECK(c,m) do {if(!(c)){fprintf(stderr,"Stream transfer mismatch: %s\n",m);abort();}}while(0)
#ifdef NDEBUG
#error Stream transfer checks require active assertions
#endif
uint32_t obor_profile_build;
s_filestream *filestreams;
int numfilestreams;
@LEVEL_DECLARATION@
static const unsigned char bytes[]={@PAYLOAD@};
static unsigned provider_calls,observations;
static char filename[]="stream-fixture.txt";
CHAR *StrCache_Get(int index){CHECK(index==0,"string index");return filename;}
void ScriptVariant_Clear(ScriptVariant *value){memset(value,0,sizeof(*value));}
void ScriptVariant_ChangeType(ScriptVariant *value,VARTYPE type){value->vt=type;}
HRESULT ScriptVariant_IntegerValue(ScriptVariant *value,LONG *out){
 if(value->vt!=VT_INTEGER)return E_FAIL;
 *out=value->lVal;return S_OK;
}
HRESULT Interpreter_Call(Interpreter *interpreter){(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter){(void)interpreter;abort();}
static void forbidden_base(char *path,char *kind,int create){
 (void)path;(void)kind;(void)create;abort();
}
static void forbidden_name(char *path,size_t capacity,int which){
 (void)path;(void)capacity;(void)which;abort();
}
static int forbidden_path(char *path,size_t capacity,const char *part){
 (void)path;(void)capacity;(void)part;abort();
}
static int forbidden_exists(const char *path){(void)path;abort();}
static int forbidden_external_path(char *path,size_t capacity,const char *name,const char *suffix){
 (void)path;(void)capacity;(void)name;(void)suffix;abort();
}
#undef getBasePath
#undef getPakName
#undef obor_pak_path_append
#undef fileExists
#define getBasePath forbidden_base
#define getPakName forbidden_name
#define obor_pak_path_append forbidden_path
#define fileExists forbidden_exists
#undef filestream_get_external_path
#define filestream_get_external_path forbidden_external_path
int buffer_pakfile(@NAME_TYPE@name,char **buffer,size_t *length){
 CHECK(!strcmp(name,filename),"provider name");++provider_calls;
 *length=sizeof(bytes);*buffer=malloc(sizeof(bytes)+1);CHECK(*buffer,"bounded provider allocation");
 memcpy(*buffer,bytes,sizeof(bytes));(*buffer)[sizeof(bytes)]=0;return 1;
}
@HELPERS@
@OPENING@
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];provider_calls=0;
  @LEVEL_SETUP@
  for(int i=0;i<3;++i){
   ScriptVariant name={0},result={0},*out=&result,*argv[]={&name};
   name.vt=VT_STR;name.strVal=0;
   CHECK(openbor_openfilestream(argv,&out,1)==S_OK && out==&result,"opening result");
   CHECK(result.vt==VT_INTEGER && result.lVal==i,"returned slot");
   CHECK(@SLOT@.size==sizeof(bytes) && !@SLOT@.pos,"native buffer fields");
   CHECK(!memcmp(@SLOT@.buf,bytes,sizeof(bytes)) && !@SLOT@.buf[sizeof(bytes)],"owned transferred bytes");
   @EXTENT@
   ++observations;
  }
  CHECK(provider_calls==3,"provider route");
  for(int i=0;i<@COUNT@;++i)free(@SLOT@.buf);
  @RESET@
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"cases\":%u,\"record_bytes\":%zu,\"buffer_offset\":%zu,\"size_offset\":%zu}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations,sizeof(s_filestream),
  offsetof(s_filestream,buf),offsetof(s_filestream,size));return 0;
}
'''
    values=dict(PAYLOAD=','.join(map(str,payload)),REVISIONS=','.join(str(n)+'u'for n in revisions),
                NAME_TYPE='const char *'if provider_const_name else'char *',
                HEADERS='\n'.join('#include "'+name+'"'for name in header_includes),
                HELPERS=helpers,OPENING=opening,
                LEVEL_DECLARATION='s_level *level;'if level_streams else'',
                LEVEL_SETUP='level=calloc(1,sizeof(*level));CHECK(level,"bounded level storage");'if level_streams else'',
                SLOT='level->filestreams[i]'if level_streams else'filestreams[i]',
                COUNT='level->numfilestreams'if level_streams else'numfilestreams',
                RESET='free(level);level=NULL;'if level_streams else'free(filestreams);filestreams=NULL;numfilestreams=0;',
                EXTENT='CHECK('+('level->filestreams[i]'if level_streams else'filestreams[i]')+
                       '.obor_capacity==sizeof(bytes)+1,"owned extent");'if owned_extent else'')
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
