"""Check source-owned menu calls, frame drawing and the locked sprite queue.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def render_menu_queue(engine, fixture):
    menus, rows = fixture['menus'], fixture['sources']
    if (not 1 <= len(menus) <= 32 or len(set(menus)) != len(menus) or
            any(not re.fullmatch(r'[A-Za-z_]\w{0,63}', n) for n in menus) or
            not 1 <= len(rows) <= 128 or len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique menu names and source contexts required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                len(row['level_call']) != len(menus) or
                any(type(x) is not bool for x in row['level_call']) or
                any(type(row[k]) is not bool for k in ('only_new', 'always_available', 'post_on_always'))):
            raise ValueError('Explicit source-derived menu and frame flags required')
    core = (engine / 'openbor.c').read_text()
    queue = (engine / 'source/gamelib/spriteq.c').read_text()
    update = function(core, 'update')
    start = update.index('// gfx section')
    ending = re.search(r'spriteq_draw\(vscreen,[^\n]*// notice, always draw sprites[^\n]*\n\s*}',
                       update[start:])
    if ending is None:
        raise ValueError('Complete current frame graphics window required')
    window = update[start:start + ending.end()]
    wrappers = []
    for i, name in enumerate(menus):
        body = function(core, name)
        calls = re.findall(r'\bupdate\([^;\n]+;', body)
        if not calls:
            raise ValueError('An actual menu frame call is required')
        wrappers.append('static void menu_' + str(i) + '(void){' + calls[0] + '}')
    begin = re.search(r'(?m)^#define\s+MAXQSPRITES\b', queue)
    if begin is None:
        raise ValueError('Native sprite queue storage required')
    globals_ = queue[begin.start():queue.index('void spriteq_add_frame(')]
    draw = function(queue, 'spriteq_draw')
    prefix = draw[:draw.index('switch(order[i]->type)')]
    selected = draw[draw.index('case SQT_SCREEN:'):draw.index('case SQT_DOT:')]
    draw = (prefix + 'switch(order[i]->type){' + selected + 'default:abort();}}}').replace(
        'void spriteq_draw(', 'static void native_spriteq_draw(', 1)
    pieces = [globals_, function(queue, 'spriteq_sort'), function(queue, 'spriteq_add_screen'),
              function(queue, 'spriteq_clear'), draw]
    checks = '\n'.join('check(%d,(const int[]){%s},%d,%d,%d);' % (
        r['revision'], ','.join(str(int(v)) for v in r['level_call']),
        r['only_new'], r['always_available'], r['post_on_always']) for r in rows)
    code = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef printf
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"menu contract revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#c);abort();}}while(0)
@DEFINES@
uint32_t obor_profile_build;
static s_level instance,*level;
static s_screen *vscreen,*background,*zoombuffer,*old_image,*new_image;
static int alwaysupdate,selectScreen,zoom_scale_x,zoom_scale_y,zoom_z,zoom_center_x,zoom_center_y;
static int observed_ingame,observed_wait,observed_filter,queue_calls,draw_count,draw_mask;
static char trace[96];static unsigned at;
static void event(char c){assert(at+1<sizeof(trace));trace[at++]=c;trace[at]=0;}
static unsigned char *screen_pixels(s_screen *s){return (unsigned char*)s+offsetof(s_screen,data);}
void draw_scrolled_bg(void){event('B');}
void predrawstatus(void){event('P');}
void drawstatus(void){event('S');}
void execute_updatedscripts(void){event('U');}
void draw_textobjs(void){event('T');}
void display_ents(void){event('E');}
void clearscreen(s_screen *s){assert(s==vscreen);memset(screen_pixels(s),0,4);event('C');}
void putscreen(s_screen *dest,s_screen *src,int x,int y,s_drawmethod *method){
 assert(dest==vscreen && !x && !y);
 if(src==background){assert(!method);screen_pixels(dest)[0]=4;event('b');}
 else {assert(method && (src==old_image || src==new_image));++draw_count;
  if(src==old_image){draw_mask|=1;screen_pixels(dest)[1]=11;event('O');}
  else {draw_mask|=2;screen_pixels(dest)[2]=22;event('N');}}
}
s_screen *allocscreen(int w,int h,int format){(void)w;(void)h;(void)format;abort();}
void freescreen(s_screen **s){(void)s;abort();}
void copyscreen(s_screen *dest,s_screen *src){(void)dest;(void)src;abort();}
void zoomscreen(s_screen *dest,s_screen *src,int x,int y,int sx,int sy){
 (void)dest;(void)src;(void)x;(void)y;(void)sx;(void)sy;abort();
}
@PIECES@
void spriteq_draw(s_screen *s,int only_new,int low,int high){
 observed_filter=only_new;++queue_calls;native_spriteq_draw(s,only_new,low,high);
}
static void menu_frame(int ingame,int usevwait){
 observed_ingame=ingame;observed_wait=usevwait;
 @WINDOW@
}
#define update menu_frame
@WRAPPERS@
#undef update
static void (*const menu_calls[])(void)={@CALLS@};
static s_screen *new_screen(void){
 s_screen *s=calloc(1,sizeof(*s)+4);assert(s);s->width=4;s->height=1;s->pixelformat=PIXEL_8;return s;
}
static void check(unsigned revision,const int *level_call,int only_new,int always_available,int post_on_always){
 obor_profile_build=revision;vscreen=new_screen();s_screen *bg=new_screen();old_image=new_screen();new_image=new_screen();
 spritequeue_len=spriteq_old_len=spriteq_locked=0;
 spriteq_add_screen(0,0,0,old_image,NULL,0);spriteq_add_screen(0,0,1,new_image,NULL,0);
 spriteq_old_len=1;
 for(unsigned menu=0;menu<sizeof(menu_calls)/sizeof(*menu_calls);++menu)
 for(int has_level=0;has_level<2;++has_level)for(int locked=0;locked<2;++locked)
 for(int selection=0;selection<2;++selection)for(int always=0;always<=always_available;++always)
 for(int has_bg=0;has_bg<2;++has_bg){
  level=has_level?&instance:NULL;spriteq_locked=locked;selectScreen=selection;alwaysupdate=always;background=has_bg?bg:NULL;
  memset(screen_pixels(vscreen),0,4);at=0;trace[0]=0;observed_ingame=observed_wait=observed_filter=-1;queue_calls=draw_count=draw_mask=0;
  menu_calls[menu]();int ingame=has_level && level_call[menu];
  assert(observed_ingame==ingame && observed_wait==0 && queue_calls==1);
  int filter=only_new && !ingame,skip=filter && locked;
  assert(observed_filter==filter && draw_count==(skip?1:2) && draw_mask==(skip?2:3));
  char expected[96]="";
  if(ingame)strcat(expected,"BPS");
  if(ingame || (post_on_always && always))strcat(expected,"UT");
  if(!ingame){strcat(expected,"C");if(has_bg)strcat(expected,"b");}
  if(ingame || selection)strcat(expected,"E");
  if(!skip)strcat(expected,"O");strcat(expected,"N");
  assert(!strcmp(trace,expected));assert(screen_pixels(vscreen)[1]==(skip?0:11) && screen_pixels(vscreen)[2]==22);
 }
 spriteq_locked=0;spriteq_clear();free(vscreen);free(bg);free(old_image);free(new_image);
}
int main(void){@CHECKS@ puts("menu_queue=1");return 0;}
'''
    defines = '\n'.join(line for line in core.splitlines()
                        if line.startswith(('#define MIN_INT', '#define MAX_INT')))
    if len(defines.splitlines()) != 2:
        raise ValueError('Actual depth bounds required')
    for key, value in dict(DEFINES=defines, PIECES='\n'.join(pieces), WINDOW=window,
                           WRAPPERS='\n'.join(wrappers), CALLS=','.join('menu_' + str(i) for i in range(len(menus))),
                           CHECKS=checks).items():
        code = code.replace('@' + key + '@', value)
    return code
