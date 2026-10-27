"""Observe native ownership-list cleanup with bounded logical alias counts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_sprite_cleanup(*, cleanup, revision, node_cache, counts, timeout_seconds=2):
    if (not isinstance(cleanup,str) or not 0<len(cleanup)<=8192 or '\0' in cleanup or
            not re.match(r'\s*void\s+freesprites\s*\(',cleanup) or
            type(revision)is not int or not 0<revision<=0xffffffff or
            type(node_cache)is not bool or type(timeout_seconds)is not int or
            not 1<=timeout_seconds<=5 or not isinstance(counts,list) or
            not 0<len(counts)<=16 or any(type(n)is not int or not 0<=n<=131072 for n in counts)):
        raise ValueError('Bounded native cleanup definition, layout, alias counts and timeout required')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include "types.h"
#undef printf
#undef assert
#ifdef NDEBUG
#error Ownership observations require assertions
#endif
#define assert(c) do{if(!(c)){fprintf(stderr,"Native sprite cleanup mismatch: line=%d\n",__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
s_sprite_list *sprite_list;
s_sprite_map *sprite_map;
unsigned int sprites_loaded;
int sprite_map_max_items;
static void *expected[8];
static unsigned expected_count,released,total_released;
static void tracked_free(void *pointer){
 if(!pointer)return;
 assert(released<expected_count && pointer==expected[released]);
 ++released;++total_released;free(pointer);
}
#define free tracked_free
@CLEANUP@
#undef free
static void deadline(int signum){
 (void)signum;
 const char message[]="Native sprite cleanup exceeded bounded time\n";
 (void)write(STDERR_FILENO,message,sizeof(message)-1);_exit(42);
}
static const unsigned counts[]={@COUNTS@};
int main(void){
 assert(signal(SIGALRM,deadline)!=SIG_ERR);
 for(unsigned c=0;c<sizeof(counts)/sizeof(counts[0]);++c){
  unsigned count=counts[c],owners=count<2?count:2;
  s_sprite_list *nodes[2]={NULL,NULL};
  expected_count=released=0;sprite_list=NULL;sprite_map=NULL;
  sprite_map_max_items=1234;sprites_loaded=count;
  for(unsigned n=0;n<owners;++n){
   nodes[n]=calloc(1,sizeof(*nodes[n]));assert(nodes[n]);
   nodes[n]->filename=malloc(16);nodes[n]->sprite=calloc(1,sizeof(s_sprite));
   assert(nodes[n]->filename && nodes[n]->sprite);
   strcpy(nodes[n]->filename,n?"owned-b":"owned-a");
   nodes[n]->next=sprite_list;sprite_list=nodes[n];
  }
  if(count){
   sprite_map=calloc(count,sizeof(*sprite_map));assert(sprite_map);
   for(unsigned n=0;n<count;++n){
    s_sprite_list *owner=nodes[n%owners];
    @MAP_ENTRY@
    sprite_map[n].centerx=(int)(n%13);sprite_map[n].centery=-(int)(n%11);
   }
  }
  for(unsigned n=owners;n>0;--n){
   expected[expected_count++]=nodes[n-1]->sprite;
   expected[expected_count++]=nodes[n-1]->filename;
   expected[expected_count++]=nodes[n-1];
  }
  if(sprite_map)expected[expected_count++]=sprite_map;
  alarm(@TIMEOUT@);freesprites();alarm(0);
  assert(released==expected_count && !sprite_list && !sprite_map && !sprites_loaded);
  assert(sprite_map_max_items==1234);
  expected_count=released=0;
  alarm(@TIMEOUT@);freesprites();alarm(0);
  assert(!released && !sprite_list && !sprite_map && !sprites_loaded && sprite_map_max_items==1234);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u,\"released\":%u}\n",
   (unsigned)(sizeof(counts)/sizeof(counts[0])),total_released);
 return 0;
}
'''.replace('@REVISION@',str(revision)+'u').replace('@CLEANUP@',cleanup).replace(
        '@COUNTS@',','.join(map(str,counts))).replace('@TIMEOUT@',str(timeout_seconds)).replace(
        '@MAP_ENTRY@','sprite_map[n].node=owner;'if node_cache else
        'sprite_map[n].filename=owner->filename;sprite_map[n].sprite=owner->sprite;')
