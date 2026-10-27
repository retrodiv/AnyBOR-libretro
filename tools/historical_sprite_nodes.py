"""Bounded observations of native sprite cache identity and node ownership.

Image decoding, encoding bytes and map growth have separate native probes.
This probe supplies typed bitmap/encoder/reload services and retains the exact
selected native cache functions. It does not model a complete engine or arena.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_sprite_nodes(*, loader, cleanup, cache, revision, node_cache,
                        clipped_metadata=False, count_type='unsigned int', mode='valid'):
    definitions=((loader,'int','loadsprite'),(cleanup,'void','freesprites'))
    if (type(node_cache)is not bool or type(clipped_metadata)is not bool or
            (clipped_metadata and not node_cache) or mode not in ('valid','all') or
            type(revision)is not int or not 0<revision<=0xffffffff or
            count_type not in ('unsigned int','uint64_t') or
            (node_cache and (not isinstance(cache,str) or not cache)) or
            (not node_cache and cache!='')):
        raise ValueError('Explicit native cache layout, revision and observation mode required')
    if node_cache:definitions+=((cache,'void','cachesprite'),)
    for body,result,name in definitions:
        if (not isinstance(body,str) or not 0<len(body)<=16384 or '\0'in body or
                not re.match(r'\s*'+result+r'\s+'+name+r'\s*\(',body)):
            raise ValueError('Bounded exact native sprite definitions required')
    code=r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <setjmp.h>
#include "types.h"
#undef printf
#ifdef NDEBUG
#error Native ownership observations require active assertions
#endif
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Native sprite node mismatch: %s\n",m);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
s_sprite_list *sprite_list;
s_sprite_map *sprite_map;
@COUNT_TYPE@ sprites_loaded;
int sprite_map_max_items;
static char *packfile="bounded-provider";
static void *owned[64];
static unsigned active[64],records,allocations,fail_allocation,bitmap_loads,bitmap_frees;
static unsigned reloads,reload_unavailable,stops,observations;
static s_bitmap *live_bitmap;
static jmp_buf stopped;
static char stop_message[512];
static void *owned_malloc(size_t bytes){
 CHECK(bytes>0 && bytes<=65536 && records<64,"bounded allocation");
 ++allocations;if(fail_allocation && allocations==fail_allocation)return NULL;
 void *pointer=calloc(1,bytes);CHECK(pointer,"test allocation available");
 owned[records]=pointer;active[records++]=1;return pointer;
}
static void owned_free(void *pointer){
 if(!pointer)return;
 for(unsigned n=records;n>0;--n)if(owned[n-1]==pointer && active[n-1]){
  active[n-1]=0;free(pointer);return;
 }
 CHECK(0,"release requires a live owned allocation");
}
static unsigned live_owners(void){
 unsigned result=0;for(unsigned n=0;n<records;++n)result+=active[n];return result;
}
static s_bitmap *loadbitmap(char *name,char *pack,int format){
 CHECK(name && pack==packfile && !live_bitmap,"typed bitmap request");
 ++bitmap_loads;live_bitmap=calloc(1,sizeof(*live_bitmap));CHECK(live_bitmap,"bitmap allocation");
 live_bitmap->width=4;live_bitmap->height=3;live_bitmap->pixelformat=format;return live_bitmap;
}
static void clipbitmap(s_bitmap *bitmap,int *left,int *right,int *top,int *bottom){
 CHECK(bitmap==live_bitmap,"clip owns bitmap");*left=*right=*top=*bottom=1;
 @CLIP@
}
static ptrdiff_t fakey_encodesprite(s_bitmap *bitmap){
 CHECK(bitmap==live_bitmap,"sizing owns bitmap");return sizeof(s_sprite);
}
static void encodesprite(int x,int y,s_bitmap *bitmap,s_sprite *sprite){
 CHECK(bitmap==live_bitmap && sprite,"typed encode destination");
 sprite->centerx=x;sprite->centery=y;sprite->width=2;sprite->height=1;
 sprite->pixelformat=bitmap->pixelformat;
}
static void freebitmap(s_bitmap *bitmap){
 CHECK(bitmap && bitmap==live_bitmap,"one bitmap release");
 ++bitmap_frees;free(bitmap);live_bitmap=NULL;
}
static void prepare_sprite_map(size_t requested){
 CHECK(sprite_map && requested<8,"bounded supplied sprite map");
}
static s_sprite *loadsprite2(char *filename,int *width,int *height){
 CHECK(filename && !width && !height,"native cache reload request");++reloads;
 if(reload_unavailable)return NULL;
 s_sprite *sprite=owned_malloc(sizeof(*sprite));CHECK(sprite,"test reload allocation");
 @RELOAD_FIELDS@
 sprite->centerx=-1;sprite->centery=-1;sprite->width=2;sprite->height=1;return sprite;
}
static void terminal(int code,const char *format,...){
 CHECK(code==1,"native load-stop status");++stops;
 va_list args;va_start(args,format);vsnprintf(stop_message,sizeof(stop_message),format,args);va_end(args);
 longjmp(stopped,1);
}
#define malloc owned_malloc
#define free owned_free
#define stricmp strcasecmp
#define shutdown terminal
#define borShutdown terminal
@LOADER@
@CACHE@
@CLEANUP@
#undef malloc
#undef free
#undef shutdown
#undef borShutdown
static s_sprite *at_sprite(unsigned index){@AT_SPRITE@}
static char *at_name(unsigned index){@AT_NAME@}
static void reset(void){
 CHECK(!sprite_list && !sprite_map && !sprites_loaded && !live_bitmap && !live_owners(),"clean prior case");
 records=allocations=fail_allocation=bitmap_loads=bitmap_frees=reloads=reload_unavailable=stops=0;
 sprite_map=owned_malloc(8*sizeof(*sprite_map));sprite_map_max_items=8;
}
static void finish(void){
 freesprites();CHECK(!sprite_list && !sprite_map && !sprites_loaded && !live_bitmap,"empty native cache");
 CHECK(!live_owners() && bitmap_loads==bitmap_frees,"all owned data released once");
}
static void valid(void){
 reset();CHECK(loadsprite("alpha",5,7,1)==0,"first index");
 s_sprite *shared=at_sprite(0);char *name=at_name(0);
 CHECK(shared && !strcmp(name,"alpha") && shared->centerx==4 && shared->centery==6,"first sprite identity");
 CHECK(sprite_map[0].centerx==4 && sprite_map[0].centery==6,"first center");
 CHECK(loadsprite("ALPHA",5,7,2)==0 && bitmap_loads==1,"same center and case reuse, native format key");
 CHECK(loadsprite("alpha",9,11,1)==1 && sprites_loaded==2,"distinct center alias");
 CHECK(at_sprite(1)==shared && at_name(1)==name,"alias borrows original data");
 CHECK(sprite_map[1].centerx==8 && sprite_map[1].centery==10,"alias center");
 CHECK(bitmap_loads==@ALIAS_LOADS@,"native alias image request count");
 CHECK(loadsprite("beta",2,3,1)==2 && sprites_loaded==3,"second owner index");
 CHECK(sprite_list && !strcmp(sprite_list->filename,"beta") && sprite_list->next &&
       !strcmp(sprite_list->next->filename,"alpha") && !sprite_list->next->next,"native owning list order");
 CHECK(at_sprite(2)!=shared && at_sprite(0)==shared,"owners distinct, aliases retained");
 CHECK(loadsprite("alpha",9,11,1)==@LATER_INDEX@ && sprites_loaded==@LATER_COUNT@,"native later alias policy");
 @VALID_CACHE@
 observations+=@VALID_COUNT@;finish();
}
static void unavailable_component(unsigned target){
 reset();CHECK(loadsprite("keep",5,7,1)==0,"existing owner setup");
 s_sprite_list *saved_node=sprite_list;s_sprite *saved_sprite=at_sprite(0);char *saved_name=at_name(0);
 unsigned baseline=live_owners();allocations=0;fail_allocation=target;
 if(!setjmp(stopped)){loadsprite("new",3,4,1);CHECK(0,"unavailable component must stop load");}
 CHECK(stops==1 && !strcmp(stop_message,"loadsprite() Out of memory!\n"),"native allocation stop message");
 CHECK(sprite_list==saved_node && !saved_node->next && sprites_loaded==1 &&
       at_sprite(0)==saved_sprite && at_name(0)==saved_name,"existing owner retained");
 CHECK(!live_bitmap && live_owners()==baseline,"partial owner released");
 fail_allocation=0;++observations;finish();
}
@UNAVAILABLE_CACHE@
int main(void){
 valid();@ALL_CASES@
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",observations);return 0;
}
'''
    valid_cache=r'''
 cachesprite(-1,0);cachesprite((int)sprites_loaded,1);
 CHECK(at_sprite(0)==shared && !reloads,"out-of-range cache requests leave valid owner intact");
 cachesprite(0,0);CHECK(!at_sprite(0) && !at_sprite(1),"unload shared owner");
 cachesprite(1,0);CHECK(!at_sprite(1),"repeated unload");
 cachesprite(1,1);CHECK(at_sprite(0) && at_sprite(0)==at_sprite(1) && reloads==1,"reload shared owner once");
 cachesprite(0,1);CHECK(reloads==1,"ready cache reuse");
 CHECK(sprite_map[0].centerx==4 && sprite_map[1].centerx==8,"reload retains centers");
 cachesprite(0,0);CHECK(loadsprite("ALPHA",5,7,2)==0 && reloads==2,"cold reuse loads metadata first");
 CHECK(at_name(0)==name && sprites_loaded==3,"cold reuse retains filename and map count");
'''
    unavailable_cache=r'''
static void unavailable_reload(void){
 reset();CHECK(loadsprite("alpha",5,7,1)==0,"existing reload owner setup");
 cachesprite(0,0);s_sprite_list *saved=sprite_list;unsigned baseline=live_owners();
 reload_unavailable=1;
 cachesprite(0,1);CHECK(!at_sprite(0) && reloads==1 && !stops,"cache retains absent reload");
 if(!setjmp(stopped)){loadsprite("alpha",5,7,1);CHECK(0,"cold reload must stop load");}
 CHECK(stops==1 && strstr(stop_message,"alpha") && reloads==2,"reload failure stop");
 CHECK(sprite_list==saved && sprites_loaded==1 && !at_sprite(0) && live_owners()==baseline,"reload owner retained");
 sprite_map[1].node=NULL;sprites_loaded=2;
 cachesprite(1,0);cachesprite(1,1);
 CHECK(reloads==2 && live_owners()==baseline,"absent node is a stable no-op");
 observations+=3;finish();
}
'''
    replacements={
        '@REVISION@':str(revision)+'u','@LOADER@':loader,'@CACHE@':cache,'@CLEANUP@':cleanup,
        '@COUNT_TYPE@':count_type,
        '@CLIP@':('bitmap->clipped_width=2;bitmap->clipped_height=1;'if clipped_metadata else
                 'bitmap->width=2;bitmap->height=1;'),
        '@RELOAD_FIELDS@':('sprite->offsetx=1;sprite->offsety=1;sprite->srcwidth=2;sprite->srcheight=1;'
                          if node_cache else ''),
        '@AT_SPRITE@':'return sprite_map[index].node->sprite;'if node_cache else 'return sprite_map[index].sprite;',
        '@AT_NAME@':'return sprite_map[index].node->filename;'if node_cache else 'return sprite_map[index].filename;',
        '@ALIAS_LOADS@':'1'if node_cache else '2','@VALID_CACHE@':valid_cache if node_cache else '',
        '@LATER_INDEX@':'1'if node_cache else '3','@LATER_COUNT@':'3'if node_cache else '4',
        '@VALID_COUNT@':'12'if node_cache else '6',
        '@UNAVAILABLE_CACHE@':unavailable_cache if node_cache else '',
        '@ALL_CASES@':('for(unsigned n=1;n<=3;++n)unavailable_component(n);'+
                      ('unavailable_reload();'if node_cache else ''))if mode=='all'else '',
    }
    for key,value in replacements.items():code=code.replace(key,value)
    return code
