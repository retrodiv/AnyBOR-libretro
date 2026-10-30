"""Render complete native level-owned stream creation and release controls.

The matching variant C unit is linked separately. Other level resources are
empty; script cleanup observes release order without executing unrelated VM code.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_level_storage(*, revisions, creating, releasing, helpers, slots,
                         buffer_bytes, owned_extent, header_includes):
    if (not isinstance(revisions,list)or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions)or
        revisions!=sorted(set(revisions))or type(slots)is not int or not 4<=slots<=256 or
        type(buffer_bytes)is not int or not 1<=buffer_bytes<=1048576 or
        type(owned_extent)is not bool):
        raise ValueError('Explicit bounded level storage and native revisions required')
    for text,name,result in [(creating,'openbor_createfilestream','HRESULT'),
                             (releasing,'free_level','void')]:
        if (not isinstance(text,str)or not 0<len(text)<=32768 or '\0'in text or
            not re.match(r'\s*'+result+r'\s+'+name+r'\s*\(',text)):
            raise ValueError('Complete native creation and release callbacks required')
    if not isinstance(helpers,str)or len(helpers)>32768 or '\0'in helpers:
        raise ValueError('Bounded complete native storage helpers required')
    if (not isinstance(header_includes,list)or not 0<len(header_includes)<=16 or
        any(not isinstance(n,str)or len(n)>256 or
            not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',n)or n.startswith('/')or
            '..'in n.split('/')for n in header_includes)or
        len(set(header_includes))!=len(header_includes)):
        raise ValueError('Explicit ordered native headers required')
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
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Level stream contract: %s\n",m);abort();}}while(0)
#ifdef NDEBUG
#error Level stream contracts need active assertions
#endif
_Static_assert(LEVEL_MAX_FILESTREAMS==@SLOTS@,"declared native slot capacity");
uint32_t obor_profile_build;
s_level *level;
static s_level *retiring;
static void *owners[@SLOTS@+8];
static s_level *owner_levels[@SLOTS@+8];
static unsigned live[@SLOTS@+8],used,script_clears,level_frees,diagnostics,observations;
static int refuse_buffer;
static void ledger_reset(void){
 for(unsigned i=0;i<used;++i)CHECK(!live[i],"no retained stream owner");
 used=script_clears=level_frees=diagnostics=0;
}
static void *allocate_buffer(size_t bytes,int zero){
 CHECK(bytes==@BYTES@&&used<@SLOTS@+8,"native buffer allocation size");
 if(refuse_buffer){refuse_buffer=0;return NULL;}
 void *p=zero?calloc(bytes,1):malloc(bytes);CHECK(p,"fixture buffer allocation");
 owners[used]=p;owner_levels[used]=level;live[used++]=1;return p;
}
static void *create_malloc(size_t bytes){return allocate_buffer(bytes,0);}
static void *create_calloc(size_t n,size_t bytes){
 CHECK(!n||bytes<=SIZE_MAX/n,"bounded multiplication");return allocate_buffer(n*bytes,1);
}
static void release_owned(void *p){
 if(!p)return;
 for(unsigned i=0;i<used;++i)if(live[i]&&owners[i]==p){
  CHECK(owner_levels[i]==retiring,"stream release belongs to argument level");
  live[i]=0;free(p);return;
 }
 CHECK(p==retiring,"level release belongs to argument level");
 for(unsigned i=0;i<used;++i)CHECK(owner_levels[i]!=retiring||!live[i],"stream bytes precede level release");
 CHECK(script_clears==5,"all empty scripts precede level release");
 ++level_frees;free(p);
}
static void observe_script_clear(Script *script,int mode){
 CHECK(retiring&&mode==2,"native script cleanup request");
 CHECK(script==&retiring->update_script||script==&retiring->updated_script||
       script==&retiring->key_script||script==&retiring->level_script||
       script==&retiring->endlevel_script,"only empty argument-level scripts");
 for(unsigned i=0;i<used;++i)CHECK(owner_levels[i]!=retiring||!live[i],"stream bytes precede scripts");
 for(unsigned i=0;i<@SLOTS@;++i){
  CHECK(!retiring->filestreams[i].buf,"released native buffer field");
  @RELEASE_EXTENT@
 }
 ++script_clears;
}
static int stream_message(const char *format,...){
 CHECK(!strcmp(format,"Maximum file streams exceeded.\n"),"native capacity diagnostic");
 ++diagnostics;return 0;
}
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(value,"native assertion");
}
void abortIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(value,condition,function,file,line);
}
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){
 exitIfFalse(!bytes||p,"native variant allocation",function,file,line);return p;
}
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@HELPERS@
#define malloc create_malloc
#define calloc create_calloc
#define printf stream_message
#define obor_profile_malloc_named(name, bytes) create_malloc(bytes)
#define obor_profile_calloc_named(name, bytes) create_calloc(1, bytes)
@CREATING@
#undef obor_profile_malloc_named
#undef obor_profile_calloc_named
#undef malloc
#undef calloc
#undef printf
#define free release_owned
#define Script_Clear observe_script_clear
@RELEASING@
#undef free
#undef Script_Clear
static void create_expected(int slot){
 ScriptVariant result={0},*out=&result;
 CHECK(openbor_createfilestream(NULL,&out,0)==S_OK&&out==&result&&
       result.vt==VT_INTEGER&&result.lVal==slot,"native creation result and slot");
 CHECK(level->numfilestreams==slot+1&&!level->filestreams[slot].pos&&
       level->filestreams[slot].size==(size_t)(71+slot)&&
       level->filestreams[slot].buf&&!level->filestreams[slot].buf[0],"native retained fields");
 @CREATE_EXTENT@
 ScriptVariant_Clear(&result);
}
static s_level *new_level(void){
 s_level *p=calloc(1,sizeof(*p));CHECK(p,"fixture level allocation");
 for(unsigned i=0;i<@SLOTS@;++i){p->filestreams[i].pos=9;p->filestreams[i].size=71+i;}
 return p;
}
static void release_level(s_level *p){
 retiring=p;script_clears=0;unsigned before=level_frees;
 free_level(p);CHECK(level_frees==before+1,"one level owner released");retiring=NULL;
}
static void capacity_case(void){
 ledger_reset();level=new_level();
 for(unsigned i=0;i<@SLOTS@;++i)create_expected((int)i);
 ScriptVariant result={0},*out=&result;
 CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL&&!out&&diagnostics==1,"native full-capacity result");
 retiring=level;release_owned(level->filestreams[0].buf);retiring=NULL;
 level->filestreams[0].buf=NULL;@CLEAR_EXTENT@
 out=&result;CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL&&!out&&diagnostics==2,
                  "monotonic native count does not reuse a vacant slot");
 ScriptVariant_Clear(&result);release_level(level);level=NULL;++observations;
}
static void argument_owner_case(void){
 ledger_reset();s_level *primary=new_level(),*other=new_level();
 level=primary;create_expected(0);char *primary_buffer=primary->filestreams[0].buf;
 level=other;create_expected(0);level=primary;
 release_level(other);
 CHECK(primary->filestreams[0].buf==primary_buffer&&!primary_buffer[0]&&
       primary->numfilestreams==1&&primary->filestreams[0].size==71,"unrelated active level preserved");
 @PRESERVED_EXTENT@
 release_level(primary);level=NULL;++observations;
}
@REFUSAL_CASE@
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];capacity_case();argument_owner_case();@RUN_REFUSAL@
  free_level(NULL);++observations;ledger_reset();StrCache_Clear();
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"cases\":%u}\n",
        (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations);return 0;
}
'''
    refusal=r'''
static void refusal_case(void){
 ledger_reset();level=new_level();ScriptVariant result={0},*out=&result;
 refuse_buffer=1;
 CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL&&!out&&!refuse_buffer&&
       !level->numfilestreams&&!level->filestreams[0].buf&&!level->filestreams[0].obor_capacity,
       "allocation refusal retains the unused native slot");
 create_expected(0);release_level(level);level=NULL;
 out=&result;CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL&&!out,"unavailable active level");
 level=new_level();level->numfilestreams=-1;out=&result;
 CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL&&!out&&!used,"negative native count");
 level->numfilestreams=@SLOTS@+1;out=&result;
 CHECK(openbor_createfilestream(NULL,&out,0)==E_FAIL&&!out,"outside native count");
 level->numfilestreams=0;release_level(level);level=NULL;
 ScriptVariant_Clear(&result);++observations;
}
'''.replace('@SLOTS@',str(slots))if owned_extent else''
    # Refusal follows two live-owner phases; reset the owner ledger after
    # releasing its recovered level before testing an unused new level.
    refusal=refusal.replace('level=new_level();level->numfilestreams=-1;',
                            'ledger_reset();level=new_level();level->numfilestreams=-1;')
    values=dict(HEADERS='\n'.join('#include "'+n+'"'for n in header_includes),
        SLOTS=str(slots),BYTES=str(buffer_bytes),HELPERS=helpers,CREATING=creating,
        RELEASING=releasing,REVISIONS=','.join(str(n)+'u'for n in revisions),
        RELEASE_EXTENT='CHECK(!retiring->filestreams[i].obor_capacity,"released extent metadata");'if owned_extent else'',
        CLEAR_EXTENT='level->filestreams[0].obor_capacity=0;'if owned_extent else'',
        CREATE_EXTENT=('CHECK(level->filestreams[slot].obor_capacity=='+str(buffer_bytes)+',"initialized extent");'
                       'for(size_t i=0;i<'+str(buffer_bytes)+';++i)CHECK(!level->filestreams[slot].buf[i],"initialized owned bytes");')if owned_extent else'',
        PRESERVED_EXTENT='CHECK(primary->filestreams[0].obor_capacity=='+str(buffer_bytes)+',"unrelated extent preserved");'if owned_extent else'',
        REFUSAL_CASE=refusal,RUN_REFUSAL='refusal_case();'if owned_extent else'')
    return re.sub(r'@('+'|'.join(values)+r')@',lambda match:values[match[1]],code)
