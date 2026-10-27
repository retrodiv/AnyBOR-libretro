"""Observe queue handling of an unavailable image without invoking drawing.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json


def render_sprite_queue_loading(*,queue_source,revision,node_cache):
    if (not isinstance(queue_source,str) or not queue_source.startswith('/') or
            not queue_source.endswith('.c') or len(queue_source)>4096 or
            any(c in queue_source for c in ('\0','\r','\n')) or
            type(revision) is not int or not 0<revision<=0xffffffff or type(node_cache) is not bool):
        raise ValueError('Complete native queue source, revision and cache layout required')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include @QUEUE@
#undef printf
#undef assert
#ifdef NDEBUG
#error Native enqueue observations require assertions
#endif
#define assert(c) do{if(!(c)){fprintf(stderr,"Native enqueue observation mismatch: line=%d\n",__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
static s_sprite_map entries[1];
s_sprite_map *sprite_map=entries;
@NODES@
static s_sprite ready;
static s_sprite *provided_image;
static unsigned requests;
static char image_name[]="owned-image";
s_sprite *loadsprite2(char *filename,int *width,int *height){
 assert(filename==image_name && !width && !height);++requests;return provided_image;
}
static void prepare(s_sprite *cached,s_sprite *provided){
 memset(entries,0,sizeof(entries));provided_image=provided;requests=0;
 @PREPARE@
 entries[0].centerx=1;entries[0].centery=2;
 spriteq_unlock();spriteq_clear();assert(!spritequeue_len);
}
int main(void){
 memset(&ready,0,sizeof(ready));
 prepare(NULL,NULL);
 spriteq_add_sprite(3,4,5,0,NULL,6);
 unsigned unavailable_queued=(unsigned)spritequeue_len,missing_requests=requests;
 /* Observe and clear this record; never draw an unavailable image. */
 assert(unavailable_queued<=1);
 prepare(&ready,NULL);
 spriteq_add_sprite(3,4,5,0,NULL,6);
 assert(spritequeue_len==1 && queue[0].frame==&ready && queue[0].params[1]==1 && queue[0].params[2]==2);
 assert(!requests);
 prepare(NULL,&ready);
 spriteq_add_sprite(3,4,5,0,NULL,6);
 unsigned cold_ready=(unsigned)spritequeue_len,cold_requests=requests;
 assert(cold_ready==@COLD_READY@);
 prepare(NULL,NULL);
 for(int n=0;n<MAXQSPRITES;++n)spriteq_add_frame(0,0,0,&ready,NULL,0);
 assert(spritequeue_len==MAXQSPRITES);qstruct last=queue[MAXQSPRITES-1];
 spriteq_add_sprite(3,4,5,0,NULL,6);
 assert(spritequeue_len==MAXQSPRITES && !memcmp(&last,queue+MAXQSPRITES-1,sizeof(last)));
 unsigned full_missing_requests=requests;
 spriteq_unlock();spriteq_clear();
 printf("{\"status\":\"PASS\",\"unavailable_queued\":%u,\"missing_requests\":%u,\"cold_ready\":%u,\"cold_requests\":%u,\"full_missing_requests\":%u}\n",
  unavailable_queued,missing_requests,cold_ready,cold_requests,full_missing_requests);
 return 0;
}
'''.replace('@QUEUE@',json.dumps(queue_source)).replace('@REVISION@',str(revision)+'u').replace(
        '@NODES@','static s_sprite_list node;'if node_cache else '').replace('@PREPARE@',
        'memset(&node,0,sizeof(node));node.sprite=cached;node.filename=image_name;entries[0].node=&node;'
        if node_cache else 'entries[0].sprite=cached;').replace('@COLD_READY@','1'if node_cache else'0')
