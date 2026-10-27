"""Render native script-container slot, callback and ownership contracts.

Script services are observed; entity allocation and real VM cleanup have
separate linked-unit checks. Member names are independent source declarations.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


NAMES=('alloc_all_scripts','clear_all_scripts','free_all_scripts','copy_all_scripts')


def render_script_containers(parts, *, revision, pointer_container, members,
                             offsets, null_arguments, member_count_definition='',
                             member_orders=None, support=''):
    if (not isinstance(parts,dict) or set(parts)!=set(NAMES) or
            any(not isinstance(v,str) or not v.strip() or len(v)>32768 for v in parts.values()) or
            type(revision) is not int or not 0<revision<=0xffffffff or
            type(pointer_container) is not bool or type(null_arguments) is not bool):
        raise ValueError('Complete native container source and explicit context required')
    if (not isinstance(members,list) or not 1<=len(members)<=128 or
            any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z_]\w{0,63}',n) for n in members) or
            len(set(members))!=len(members)):
        raise ValueError('Ordered independent native script members required')
    if (not isinstance(offsets,list) or not offsets or
            any(type(v) is not int or v not in (0,1) for v in offsets) or
            offsets!=sorted(set(offsets))):
        raise ValueError('Unique explicit aligned/byte-offset storage cases required')
    pointer_signature=bool(re.search(r'alloc_all_scripts\s*\(\s*(?:s_scripts\s*\*\s*\*|void\s*\*)',
                                     parts['alloc_all_scripts']))
    if pointer_signature!=pointer_container:
        raise ValueError('Declared script container representation differs')
    if (not isinstance(member_count_definition,str) or len(member_count_definition)>256 or
            '\n' in member_count_definition or
            (pointer_container and not re.fullmatch(r'#define\s+scripts_membercount\s+[^\n]+',member_count_definition)) or
            (not pointer_container and member_count_definition)):
        raise ValueError('Exact source member-count context required')
    if not isinstance(support,str) or len(support)>32768:
        raise ValueError('Bounded source dependency required')
    if member_orders is None:
        member_orders=[]
    if not isinstance(member_orders,list) or len(member_orders)>128:
        raise ValueError('Explicit bounded source traversal orders required')
    seen=set();order_clauses=[]
    for row in member_orders:
        if (not isinstance(row,dict) or set(row)!={'revision','members'} or
                type(row['revision']) is not int or not 0<row['revision']<=0xffffffff or
                row['revision'] in seen or not isinstance(row['members'],list) or
                len(row['members'])!=len(members) or
                any(not isinstance(v,str) for v in row['members']) or
                set(row['members'])!=set(members)):
            raise ValueError('Unique source revisions and complete member order required')
        seen.add(row['revision'])
        declared=','.join('offsetof(s_scripts,%s)'%v for v in row['members'])
        order_clauses.append('    if(obor_profile_build==%du){static const size_t native_offsets[]={%s};return native_offsets[i];}\n'%(row['revision'],declared))
    expected_order='static size_t expected_member_offset(unsigned i){\n'+''.join(order_clauses)+'    return member_offsets[i];\n}\n'
    code=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef free
#undef assert
#ifdef NDEBUG
#error Script container assertions must remain enabled
#endif
static const char *phase="setup";
#define assert(c) do {if(!(c)){fprintf(stderr,"Script container mismatch: %s\n",phase);abort();}}while(0)
void exitIfFalse(int value,const char *condition,const char *name,const char *file,int line){
 (void)condition;(void)name;(void)file;(void)line;assert(value);
}
void abortIfFalse(int value,const char *condition,const char *name,const char *file,int line){
 exitIfFalse(value,condition,name,file,line);
}
void *checkAlloc(void *p,size_t n,const char *name,const char *file,int line){
 (void)name;(void)file;(void)line;assert(n==0 || p);return p;
}
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
static const size_t member_offsets[]={@MEMBERS@};
@EXPECTED_ORDER@
static const size_t scripts_membercount=sizeof(member_offsets)/sizeof(*member_offsets);
@NATIVE_COUNT@
_Static_assert(sizeof(s_scripts)==@COUNT@*sizeof(Script*),"native pointer-only container");
struct item {uintptr_t address;unsigned live;int value;};
static struct item items[256];
static uintptr_t tables[2];
static unsigned table_live[2],allocated,released,table_frees,callbacks;
static Script *expected_source[128],*expected_destination[128];
static Script **expected_clear;
static int expected_method;
static struct item *item(Script *p){
 for(unsigned i=0;i<allocated;++i)if(items[i].address==(uintptr_t)p){assert(items[i].live);return items+i;}
 assert(!"unknown script");return NULL;
}
static Script *observed_alloc(void){
 assert(allocated<256);Script *p=calloc(1,sizeof(*p));assert(p);
 items[allocated]=(struct item){(uintptr_t)p,1,(int)allocated+41};++allocated;return p;
}
static void observed_clear(Script *p,int method){
 assert(callbacks<scripts_membercount && p==expected_clear[callbacks] && method==expected_method);
 (void)item(p);++callbacks;
}
static void observed_copy(Script *to,Script *from,int method){
 assert(callbacks<scripts_membercount && to==expected_destination[callbacks] &&
        from==expected_source[callbacks] && method==expected_method);
 item(to)->value=item(from)->value;++callbacks;
}
static void observed_free(void *p){
 if(!p)return;
 for(unsigned i=0;i<allocated;++i)if(items[i].address==(uintptr_t)p){
  assert(items[i].live);items[i].live=0;++released;free(p);return;
 }
 for(unsigned i=0;i<2;++i)if(tables[i]==(uintptr_t)p){
  assert(table_live[i]);table_live[i]=0;++table_frees;free(p);return;
 }
 assert(!"unexpected release");
}
@SUPPORT@
#define alloc_script observed_alloc
#define Script_Clear observed_clear
#define Script_Copy observed_copy
#define free observed_free
@ALLOC@
@CLEAR@
@FREE@
@COPY@
#undef alloc_script
#undef Script_Clear
#undef Script_Copy
#undef free
static Script *member(const void *storage,unsigned i){
 Script *p=NULL;memcpy(&p,(const unsigned char*)storage+expected_member_offset(i),sizeof(p));return p;
}
static void verify_empty(const void *storage){
 @EMPTY@
}
int main(void){
 const unsigned offsets[]={@OFFSETS@};unsigned cases=0;
 for(unsigned offset=0;offset<sizeof(offsets)/sizeof(*offsets);++offset)
 for(int method=0;method<=2;++method){
  union {void *alignment;unsigned char bytes[sizeof(s_scripts)+1];} first,second;
  union {void *alignment;s_scripts table;} aligned_first={.table={0}},aligned_second={.table={0}};
  s_scripts *first_slot=NULL,*second_slot=NULL;
  memset(&first,0,sizeof(first));memset(&second,0,sizeof(second));
  void *a=offsets[offset]?first.bytes+1:@ALIGNED_FIRST@;
  void *b=offsets[offset]?second.bytes+1:@ALIGNED_SECOND@;
  allocated=released=table_frees=callbacks=0;memset(items,0,sizeof(items));
  memset(tables,0,sizeof(tables));memset(table_live,0,sizeof(table_live));
  phase="allocation";@ALLOCATE@
  assert(allocated==2*scripts_membercount);
  void *parent=@PARENT@,*child=@CHILD@;assert(parent&&child&&parent!=child);
  @REGISTER_TABLES@
  for(unsigned i=0;i<scripts_membercount;++i){
   expected_source[i]=member(parent,i);expected_destination[i]=member(child,i);
   assert((uintptr_t)expected_source[i]==items[i].address);
   assert((uintptr_t)expected_destination[i]==items[i+scripts_membercount].address);
  }
  expected_method=method;phase="copy callback order";callbacks=0;
  copy_all_scripts(parent,child,method);assert(callbacks==scripts_membercount);
  for(unsigned i=0;i<scripts_membercount;++i)
   assert(item(expected_destination[i])->value==(int)i+41);
  phase="parent clear order";expected_clear=expected_source;callbacks=0;
  clear_all_scripts(parent,method);assert(callbacks==scripts_membercount);
  phase="parent release";@FREE_PARENT@ verify_empty(a);
  assert(released==scripts_membercount);
  phase="child still owned";
  for(unsigned i=0;i<scripts_membercount;++i)
   assert(item(expected_destination[i])->value==(int)i+41);
  expected_clear=expected_destination;callbacks=0;
  clear_all_scripts(child,method);assert(callbacks==scripts_membercount);
  @FREE_CHILD@ verify_empty(b);
  assert(released==allocated && table_frees==@TABLE_FREES@);++cases;
 }
 @NULL_ARGUMENTS@
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''
    code=code.replace('scripts_membercount','expected_member_count')
    if pointer_container:
        allocate=('alloc_all_scripts(a);alloc_all_scripts(b);'
                  'unsigned before=allocated;alloc_all_scripts(a);assert(allocated==before);')
        parent='NULL';child='NULL'
        # Explicit reference loads use character copies rather than the native
        # table walk; declaration offsets independently check every member.
        code=code.replace('void *parent=@PARENT@,*child=@CHILD@;',
                          'void *parent=NULL,*child=NULL;memcpy(&parent,a,sizeof(parent));memcpy(&child,b,sizeof(child));')
        tables='tables[0]=(uintptr_t)parent;tables[1]=(uintptr_t)child;table_live[0]=table_live[1]=1;'
        empty='void *p=(void*)1;memcpy(&p,storage,sizeof(p));assert(!p);'
        free_a='free_all_scripts(a);';free_b='free_all_scripts(b);'
    else:
        allocate='alloc_all_scripts((s_scripts*)a);alloc_all_scripts((s_scripts*)b);'
        parent='a';child='b';tables=''
        empty='for(unsigned i=0;i<expected_member_count;++i)assert(!member(storage,i));'
        free_a='free_all_scripts((s_scripts*)a);';free_b='free_all_scripts((s_scripts*)b);'
    nulls=('phase="missing container";unsigned before=allocated;'
           'alloc_all_scripts(NULL);free_all_scripts(NULL);clear_all_scripts(NULL,2);'
           'copy_all_scripts(NULL,NULL,2);assert(allocated==before);') if null_arguments else ''
    values=dict(REVISION=str(revision)+'u',MEMBERS=','.join('offsetof(s_scripts,%s)'%n for n in members),
        COUNT=str(len(members)),OFFSETS=','.join(str(v) for v in offsets),
        NATIVE_COUNT=member_count_definition,EXPECTED_ORDER=expected_order,SUPPORT=support,
        ALIGNED_FIRST='(void*)&first_slot' if pointer_container else '(void*)&aligned_first.table',
        ALIGNED_SECOND='(void*)&second_slot' if pointer_container else '(void*)&aligned_second.table',
        ALLOC=parts['alloc_all_scripts'],CLEAR=parts['clear_all_scripts'],FREE=parts['free_all_scripts'],
        COPY=parts['copy_all_scripts'],ALLOCATE=allocate,PARENT=parent,CHILD=child,
        REGISTER_TABLES=tables,EMPTY=empty,FREE_PARENT=free_a,FREE_CHILD=free_b,
        TABLE_FREES='2' if pointer_container else '0',NULL_ARGUMENTS=nulls)
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
