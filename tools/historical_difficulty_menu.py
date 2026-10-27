"""Render the native difficulty menu with deterministic input and draw calls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from test_historical_player import function


def render_difficulty_menu(engines, rows):
    bodies = '\n'.join(function((root / 'openbor.c').read_text(), 'choose_difficulty').replace(
        'choose_difficulty()', 'choose_difficulty_'+engine+'()', 1)
        for engine, root in engines.items())
    modes = {'two_pages': 0, 'selector_page': 1, 'back_on_previous_page': 2}
    contexts = ','.join('{%d,%d,%d,choose_difficulty_%s}' % (
        row['revision'], modes[row['paging']], row['locked_row_offset'], row['engine']) for row in rows)
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Difficulty menu revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
#define FLAG_ESC 1
#define FLAG_MOVEUP 2
#define FLAG_MOVEDOWN 4
#define FLAG_ANYBUTTON 8
#define MAX_NAME_LEN 31
#define SAMPLE_BEEP 0
#define SAMPLE_BEEP2 1
static struct {int hRes;} videomodes={320};
typedef struct {int alpha;} s_drawmethod;
static s_drawmethod plainmethod;
static int bothnewkeys,bonus,num_difficulties,saveslot,newgameMenu;
static struct {int effectvol;} savedata={64};
static struct {int times_completed;char dName[MAX_NAME_LEN+1];} savelevel[16];
static struct {int ifcomplete;char name[16];} levelsets[16];
static int color_black,color_white=1;
static int _liney(int a,int b) {(void)a;(void)b;return 10;}
static int fontheight(int a) {(void)a;return 8;}
static int loadGameFile(void) {return 0;}
static int sound_play_sample(int a,unsigned b,int c,int d,unsigned e) {
 (void)a;(void)b;(void)c;(void)d;(void)e;return 0;
}
static void spriteq_add_box(int a,int b,int c,int d,int e,int f,s_drawmethod *g) {
 (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;
}
static void spriteq_add_line(int a,int b,int c,int d,int e,int f,s_drawmethod *g) {
 (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;
}
static struct {int index,row,selected,locked;} observed[5];
static int observed_count,back_seen,back_selected,expected_selector,paging,row_offset;
static int keys[40],key_count,key_index;
static void _menutextm(int selected,int row,int unused,const char *fmt,...) {
 (void)unused;
 if(!strcmp(fmt,"Game Mode"))return;
 if(!strcmp(fmt,"Back")) {assert(row==6 && !back_seen);back_seen=1;back_selected=selected;return;}
 va_list args;va_start(args,fmt);const char *name=va_arg(args,const char*);va_end(args);
 int index=-1;for(int i=0;i<num_difficulties;++i)if(!strcmp(name,levelsets[i].name))index=i;
 assert(index>=0 && observed_count<5);
 observed[observed_count].index=index;observed[observed_count].row=row;
 observed[observed_count].selected=selected;
 observed[observed_count].locked=strcmp(fmt,"%s")!=0;++observed_count;
}
static void update(int a,int b) {
 assert(a==0 && b==0 && key_index<key_count);
 if(num_difficulties>1) {
  int first;
  if(paging==0)first=num_difficulties<=5?0:(expected_selector>=5?5:0);
  else {int cursor=expected_selector-(paging==2 && expected_selector==num_difficulties);first=cursor-cursor%5;}
  int count=num_difficulties-first;if(count>5)count=5;
  assert(count==observed_count && back_seen);
  for(int j=0;j<count;++j) {
   int i=first+j,locked=bonus<levelsets[i].ifcomplete;
   assert(observed[j].index==i && observed[j].selected==(expected_selector==i));
   assert(observed[j].locked==locked);
   assert(observed[j].row==j+(locked && levelsets[i].ifcomplete==1?row_offset:0));
  }
  assert(back_selected==(expected_selector==first+count));
 } else assert(!observed_count && !back_seen);
 observed_count=back_seen=0;
 bothnewkeys=keys[key_index++];
 if(bothnewkeys==FLAG_MOVEUP)--expected_selector;
 if(bothnewkeys==FLAG_MOVEDOWN)++expected_selector;
 if(expected_selector<0)expected_selector=num_difficulties;
 if(expected_selector>num_difficulties)expected_selector=0;
}
@BODIES@
static void check(int (*choose)(void)) {
 const int counts[]={1,2,5,6,9,10,11,15,16},values[]={0,1,3};
 for(unsigned n=0;n<sizeof(counts)/sizeof(*counts);++n)
 for(int l=0;l<3;++l)for(int b=0;b<3;++b)
 for(int path=0;path<2;++path)for(int accept=0;accept<2;++accept) {
  num_difficulties=counts[n];bonus=values[b];
  for(int target=0;target<=num_difficulties;++target) {
   ++test_case;
   for(int i=0;i<num_difficulties;++i) {
    snprintf(levelsets[i].name,sizeof(levelsets[i].name),"SET%d",i);
    levelsets[i].ifcomplete=values[l];memset(savelevel[i].dName,0,sizeof(savelevel[i].dName));
   }
   key_count=key_index=expected_selector=observed_count=back_seen=0;
   int steps=path && target?num_difficulties-target+1:target;
   for(int i=0;i<steps;++i)keys[key_count++]=path?FLAG_MOVEUP:FLAG_MOVEDOWN;
   keys[key_count++]=accept?FLAG_ANYBUTTON:FLAG_ESC;
   keys[key_count++]=FLAG_ESC;
   saveslot=-7;int result=choose();
   int unlocked=bonus>=values[l];
   int expected=num_difficulties==1 && unlocked?0:
     accept && target<num_difficulties && unlocked?target:-1;
   assert(result==expected);
   if(result>=0)assert(saveslot==result && !strcmp(savelevel[result].dName,levelsets[result].name));
   else assert(saveslot==-7);
  }
 }
}
int main(void) {
 const struct {unsigned revision;int paging,row_offset;int (*choose)(void);} rows[]={@ROWS@};
 for(unsigned i=0;i<sizeof(rows)/sizeof(*rows);++i) {
  obor_profile_build=rows[i].revision;paging=rows[i].paging;row_offset=rows[i].row_offset;check(rows[i].choose);
 }
 assert(test_case==sizeof(rows)/sizeof(*rows)*84*36);
 return 0;
}
'''.replace('@BODIES@', bodies).replace('@ROWS@', contexts)
