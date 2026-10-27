"""Render bounded native string-cache contracts from explicit parameters.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_string_cache(*, revisions, slots, payload, pop_with_length,
                        header_includes, query='StrCache_GetIfPresent',
                        check_termination=False):
    if (not isinstance(revisions, list) or not 0 < len(revisions) <= 128 or
        any(type(n) is not int or not 0 < n <= 0xffffffff for n in revisions) or
        revisions != sorted(set(revisions)) or type(slots) is not int or
        not 1 <= slots <= 256 or type(pop_with_length) is not bool):
        raise ValueError('Explicit bounded revisions and native cache allocation shape required')
    if (not isinstance(payload, list) or not 0 < len(payload) <= 128 or
        any(type(n) is not int or not 0 < n <= 255 for n in payload)):
        raise ValueError('Bounded nonempty native cache bytes required')
    if (not isinstance(header_includes, list) or not 0 < len(header_includes) <= 16 or
        any(not isinstance(n, str) or len(n) > 256 or
            not re.fullmatch(r'[A-Za-z0-9_./-]+\.h', n) or n.startswith('/') or
            '..' in n.split('/') for n in header_includes) or
        len(set(header_includes)) != len(header_includes)):
        raise ValueError('Explicit native cache headers required')
    if not isinstance(query, str) or len(query)>128 or not re.fullmatch(r'[A-Za-z_]\w*', query):
        raise ValueError('Explicit native cache query identifier required')
    if type(check_termination)is not bool:
        raise ValueError('Termination observations require an explicit boolean')
    source = r'''
#include <stdint.h>
#include <limits.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@HEADERS@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Native string cache: %s\n",m);abort();}}while(0)
#ifdef NDEBUG
#error Native cache assertions must remain active
#endif
uint32_t obor_profile_build;
extern int strcache_size;
static unsigned observations;
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(value,"native assertion");
}
void abortIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(value,condition,function,file,line);
}
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){
 exitIfFalse(!bytes||p,"native allocation",function,file,line);return p;
}
static const unsigned char payload[]={@PAYLOAD@};
static void cold(void){
 const int indices[]={0,-1,INT_MIN,INT_MAX};
 for(unsigned i=0;i<4;++i){CHECK(!@QUERY@(indices[i]),"unavailable cache query");++observations;}
}
static void run(void){
 int allocated[@SLOTS@];
 StrCache_Clear();cold();
 @FIXED_EXTENT@
 for(unsigned i=0;i<@SLOTS@;++i){
  allocated[i]=@POP@;
  CHECK(allocated[i]>=0&&allocated[i]<strcache_size,"native allocated cache index");
  for(unsigned j=0;j<i;++j)CHECK(allocated[i]!=allocated[j],"distinct live cache slots");
  CHAR *p=@QUERY@(allocated[i]);
  CHECK(p&&p==StrCache_Get(allocated[i]),"valid query retains native pointer");
  memcpy(p,payload,sizeof(payload));
  CHECK(!memcmp(@QUERY@(allocated[i]),payload,sizeof(payload)),"native cache bytes");++observations;
 }
 const int invalid[]={-1,strcache_size,INT_MIN,INT_MAX};
 for(unsigned i=0;i<4;++i){CHECK(!@QUERY@(invalid[i]),"bounded warm cache query");++observations;}
 const int edges[]={0,strcache_size-1};
 for(unsigned i=0;i<2;++i){CHECK(@QUERY@(edges[i])==StrCache_Get(edges[i]),"native table edge lookup");++observations;}
 for(unsigned i=0;i<@SLOTS@;++i){
  StrCache_Collect(allocated[i]);
  CHAR *p=@QUERY@(allocated[i]);
  CHECK(p==StrCache_Get(allocated[i]),"released slot retains native lookup semantics");
  if(p)CHECK(!memcmp(p,payload,sizeof(payload)),"retained native buffer bytes");
  ++observations;
 }
 StrCache_Clear();cold();
}
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){obor_profile_build=revisions[i];run();}
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations);return 0;
}
'''
    values = dict(HEADERS='\n'.join('#include "' + n + '"' for n in header_includes),
                  PAYLOAD=','.join(map(str, payload + [0])), QUERY=query,
                  SLOTS=str(slots), REVISIONS=','.join(str(n) + 'u' for n in revisions),
                  POP='StrCache_Pop((int)sizeof(payload)-1)' if pop_with_length else 'StrCache_Pop()',
                  FIXED_EXTENT='' if pop_with_length else
                  'CHECK(sizeof(payload)-1<=MAX_STR_VAR_LEN,"declared fixed cache extent");')
    if check_termination:
        checks = r'''
  {
   const size_t capacity=@CAPACITY@;
   unsigned char saved[@CAPACITY@];
   CHECK(capacity>=sizeof(payload),"declared cache allocation extent");
   memset(p,'q',capacity);p[capacity-1]=0;memcpy(saved,p,capacity);
   CHECK(@QUERY@(allocated[i])==p&&!memcmp(saved,p,capacity),"terminal byte and valid native identity");++observations;
   p[capacity-1]='q';memcpy(saved,p,capacity);
   CHECK(!@QUERY@(allocated[i])&&!memcmp(saved,p,capacity),"unterminated cache query");++observations;
   p[0]=0;memcpy(saved,p,capacity);
   CHECK(@QUERY@(allocated[i])==p&&!memcmp(saved,p,capacity),"empty string with unchanged trailing bytes");++observations;
   p[capacity-1]=0;p[0]='q';memcpy(saved,p,capacity);
   CHECK(@QUERY@(allocated[i])==p&&!memcmp(saved,p,capacity),"restored terminator and native identity");++observations;
   memcpy(p,payload,sizeof(payload));
  }
'''
        checks=checks.replace('@CAPACITY@','sizeof(payload)' if pop_with_length else 'MAX_STR_VAR_LEN+1')
        marker='"native cache bytes");++observations;\n'
        assert source.count(marker)==1
        source=source.replace(marker,marker+checks)
    return re.sub(r'@(' + '|'.join(values) + r')@', lambda m: values[m[1]], source)
