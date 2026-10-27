"""Render bounded original create/close stream contracts for native_contract.

Only integer callback values, slot selection and owned buffer lifetime are
observed. File I/O, string conversions, other operations and level/global
cleanup are separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def extract_storage_helpers(source, extract):
    """Select complete declared storage helpers without assuming an engine era."""
    if (not isinstance(source,str)or len(source)>8<<20 or '\0'in source or
        not callable(extract)):
        raise ValueError('Bounded native source and a complete function extractor required')
    names=('obor_filestream_reserve','obor_filestream_prepare',
           'obor_filestream_next_slot','obor_filestream_index',
           'obor_filestream_buffer','obor_filestream_level_clear')
    return '\n'.join(extract(source,name)for name in names if re.search(
        r'(?m)^(?:static\s+)?(?:int|void)\s+'+name+r'\s*\([^;{}]*\)\s*\{',source))


def render_create_close(*, revisions, record, create, close, physical_fixed,
                        fixed_capacity, logical_capacity, attempts, helpers='',
                        checked_storage=False, buffer_bytes=None):
    if (not isinstance(revisions,list) or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions) or
        len(set(revisions))!=len(revisions) or type(physical_fixed)is not bool or
        type(fixed_capacity)is not int or not 1<=fixed_capacity<=256 or
        type(attempts)is not int or not 4<=attempts<=260 or
        logical_capacity is not None and
        (type(logical_capacity)is not int or not 4<=logical_capacity<=256) or
        physical_fixed and logical_capacity!=fixed_capacity):
        raise ValueError('Explicit bounded revisions, storage and independent capacity required')
    for text,name,maximum in [(record,'s_filestream',4096),
                              (create,'openbor_createfilestream',16384),
                              (close,'openbor_closefilestream',8192)]:
        if not isinstance(text,str)or not 0<len(text)<=maximum or '\0'in text or name not in text:
            raise ValueError('Complete named original record/callback required: '+name)
    if not re.fullmatch(r'\s*typedef\s+struct\s*\{[^{}]*\}\s*s_filestream\s*;\s*',record):
        raise ValueError('One complete flat native stream record required')
    if any(not re.match(r'\s*HRESULT\s+'+name+r'\s*\(',body)for body,name in
           [(create,'openbor_createfilestream'),(close,'openbor_closefilestream')]):
        raise ValueError('Complete native callback signatures required')
    if logical_capacity is not None and attempts<=logical_capacity:
        raise ValueError('Fixed-capacity controls must include its rejected next slot')
    if not isinstance(helpers,str) or len(helpers)>32768 or '\0'in helpers:
        raise ValueError('Bounded complete prepared storage helpers required')
    if (type(checked_storage)is not bool or checked_storage and
        (physical_fixed or not helpers or 'obor_capacity'not in record or
         type(buffer_bytes)is not int or not 4<=buffer_bytes<=1048576) or
        not checked_storage and buffer_bytes is not None):
        raise ValueError('Checked storage requires dynamic native helpers and an explicit initial extent')
    code=r'''
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(c,m) do {if(!(c)){fprintf(stderr,"Stream contract mismatch: %s\n",m);abort();}} while(0)
#ifdef NDEBUG
#error Stream contracts require active assertions
#endif
typedef int HRESULT;
typedef int32_t LONG;
enum {S_OK=0,E_FAIL=-1,VT_EMPTY=0,VT_INTEGER=1};
typedef struct {int vt;LONG lVal;} ScriptVariant;
#define FAILED(x) ((x)<0)
#define LEVEL_MAX_FILESTREAMS @CAPACITY@
@RECORD@
@STORAGE@
static unsigned observations,diagnostics;
static uint32_t obor_profile_build;
static void ScriptVariant_Clear(ScriptVariant *v){*v=(ScriptVariant){0};}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){v->vt=type;}
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *v,LONG *value){
 if(v->vt!=VT_INTEGER)return E_FAIL;
 *value=v->lVal;return S_OK;
}
static int stream_message(const char *message,...){
 CHECK(!strcmp(message,"Maximum file streams exceeded.\n"),"native capacity diagnostic");
 ++diagnostics;return 0;
}
#define printf stream_message
#define __realloc(p,n) do {void *grown=realloc((p),sizeof(*(p))*((size_t)(n)+1)); \
 CHECK(grown,"bounded oracle allocation");(p)=grown;memset((p)+(n),0,sizeof(*(p)));}while(0)
@HOOKS@
@HELPERS@
@CREATE@
@CLOSE@
#undef printf
static void close_slot(unsigned index){
 ScriptVariant arg={VT_INTEGER,(LONG)index},*argv[]={&arg};
 ScriptVariant result={VT_INTEGER,999},*out=&result;
 CHECK(openbor_closefilestream(argv,&out,1)==S_OK && !out,"close result");
 CHECK(!filestreams[index].buf,"closed slot");++observations;
}
static void exercise(void){
 diagnostics=0;
 unsigned live=0;
 for(unsigned i=0;i<@ATTEMPTS@;++i){
  ScriptVariant result={VT_INTEGER,999},*out=&result;
  HRESULT hr=openbor_createfilestream(NULL,&out,(int)(i%2?3:0));
  int accepted=@ACCEPTED@;
  if(!accepted){CHECK(hr==E_FAIL && !out,"capacity rejection result");}
  else {
   CHECK(hr==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==(LONG)i,"lowest free slot");
   CHECK(filestreams[i].buf && !filestreams[i].buf[0] && !filestreams[i].pos,"new empty buffer");
   ++live;
  }
  ++observations;
 }
 CHECK(diagnostics==@REJECTS@,"capacity diagnostic count");++observations;
 CHECK(live>=4,"bounded populated control");
 filestreams[3].pos=7;filestreams[3].size=61;close_slot(3);close_slot(3);
 {
  ScriptVariant result={0},*out=&result;
  CHECK(openbor_createfilestream(NULL,&out,0)==S_OK && out && out->lVal==3,"reuse released slot");
  CHECK(!filestreams[3].pos && filestreams[3].size==61 && !filestreams[3].buf[0],"native reused fields");
  ++observations;
 }
 close_slot(0);close_slot(live-1);
 {
  ScriptVariant result={0},*out=&result;
  CHECK(openbor_createfilestream(NULL,&out,0)==S_OK && out && !out->lVal,"reuse first free slot");++observations;
 }
 for(unsigned i=0;i<live;++i)free(filestreams[i].buf);
 @RESET@
}
@STORAGE_CONTROLS@
int main(void){
 (void)stream_message;
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){
  obor_profile_build=revisions[i];CHECK(obor_profile_build>0,"source revision");exercise();@CHECK_STORAGE@
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"cases\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations);return 0;
}
'''
    storage=('static s_filestream filestreams[LEVEL_MAX_FILESTREAMS];'if physical_fixed
             else'static s_filestream *filestreams;static int numfilestreams;')
    hooks=controls=''
    if checked_storage:
        hooks=r'''
static int refuse_table,refuse_buffer;
static void *controlled_realloc(void *p,size_t n){
 if(refuse_table){refuse_table=0;return NULL;}return realloc(p,n);
}
static void *controlled_calloc(size_t n,size_t bytes){
 if(refuse_buffer){refuse_buffer=0;return NULL;}return calloc(n,bytes);
}
#define realloc controlled_realloc
#define calloc controlled_calloc
'''
        controls=r'''
static void reset_storage(void){
 for(int i=0;i<numfilestreams;++i)free(filestreams[i].buf);
 free(filestreams);filestreams=NULL;numfilestreams=0;
}
static void storage_controls(void){
 ScriptVariant value={VT_INTEGER,0},*argv[]={&value},result={VT_INTEGER,999},*out;
 refuse_table=1;out=&result;
 CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL && !out,"table allocation refusal");
 CHECK(!filestreams && !numfilestreams,"table refusal preserves storage");++observations;
 refuse_buffer=1;out=&result;
 CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL && !out,"buffer allocation refusal");
 CHECK(filestreams && numfilestreams>0 && !filestreams[0].buf,"buffer refusal preserves empty slot");++observations;
 out=&result;CHECK(openbor_createfilestream(NULL,&out,0)==S_OK && out->lVal==0,"refused slot recovers");
 CHECK(filestreams[0].obor_capacity==@INITIAL@,"initial owned extent");
 for(size_t i=0;i<@INITIAL@;++i){CHECK(!filestreams[0].buf[i],"initialized owned bytes");}
 ++observations;
 char *retained=filestreams[0].buf;
 out=&result;CHECK(openbor_closefilestream(NULL,&out,1)==E_FAIL && !out && filestreams[0].buf==retained,"missing argument storage");++observations;
 out=&result;CHECK(openbor_closefilestream(argv,&out,0)==E_FAIL && !out && filestreams[0].buf==retained,"missing argument count");++observations;
 value.lVal=INT32_MIN;out=&result;CHECK(openbor_closefilestream(argv,&out,1)==E_FAIL && !out && filestreams[0].buf==retained,"negative slot");++observations;
 value.lVal=INT32_MAX;out=&result;CHECK(openbor_closefilestream(argv,&out,1)==E_FAIL && !out && filestreams[0].buf==retained,"outside slot");++observations;
 value.lVal=0;filestreams[0].pos=7;filestreams[0].size=61;out=NULL;
 CHECK(openbor_closefilestream(argv,&out,1)==S_OK && !out && !filestreams[0].buf,"void close output");
 CHECK(filestreams[0].pos==7 && filestreams[0].size==61 && !filestreams[0].obor_capacity,"close preserves native fields");++observations;
 CHECK(openbor_closefilestream(argv,&out,1)==S_OK && !out,"repeated void close");++observations;
 CHECK(!obor_filestream_buffer(0,0),"absent buffer result");++observations;
 out=&result;CHECK(openbor_createfilestream(NULL,&out,0)==S_OK && out->lVal==0,"new bounded buffer");
 filestreams[0].buf[0]='a';filestreams[0].buf[1]=0;filestreams[0].buf[2]='b';filestreams[0].buf[3]=0;
 filestreams[0].pos=2;CHECK(obor_filestream_buffer(0,1),"initialized suffix after embedded zero");++observations;
 filestreams[0].pos=-1;CHECK(!obor_filestream_buffer(0,1),"negative position");++observations;
 filestreams[0].pos=@INITIAL@;CHECK(!obor_filestream_buffer(0,1),"outside position");++observations;
 filestreams[0].pos=@INITIAL@-1;CHECK(obor_filestream_buffer(0,1),"last initialized byte");++observations;
 CHECK(!obor_filestream_index(-1) && !obor_filestream_index(INT32_MAX),"bounded helper indices");++observations;
 reset_storage();value.lVal=@VIRGIN@;out=NULL;
 CHECK(openbor_closefilestream(argv,&out,1)==@EMPTY_RESULT@ && !out,"empty native slot domain");++observations;
 reset_storage();
}
'''.replace('@INITIAL@',str(buffer_bytes)).replace('@VIRGIN@',str(logical_capacity-1 if logical_capacity else 0)).replace(
            '@EMPTY_RESULT@','S_OK'if logical_capacity else'E_FAIL')
    values=dict(RECORD=record,CREATE=create,CLOSE=close,STORAGE=storage,HELPERS=helpers,
                HOOKS=hooks,STORAGE_CONTROLS=controls,
                CHECK_STORAGE='storage_controls();'if checked_storage else'',
                CAPACITY=str(fixed_capacity),ATTEMPTS=str(attempts),
                ACCEPTED='i<'+str(logical_capacity)+'u'if logical_capacity else'1',
                REJECTS=str(max(0,attempts-logical_capacity)if logical_capacity else 0),
                RESET='memset(filestreams,0,sizeof(filestreams));'if physical_fixed else
                      'free(filestreams);filestreams=NULL;numfilestreams=0;',
                REVISIONS=','.join(str(n)+'u'for n in revisions))
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
