"""Render a bounded native HUD icon-selection probe with controlled providers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function
from test_early_jump_walkoff import braced_statement, continued_macro


def render_model_icon_domains(engine, fixture):
    """Use native model records, stores and the icon-dependent HUD windows."""
    source = (engine / 'openbor.c').read_text()
    predraw = function(source, 'predrawstatus')
    enemy = function(source, 'drawenemystatus')

    def state_window(body, who):
        chain = re.search(r'if\(' + re.escape(who) + r'->health\s*<=\s*0\).*?else\s+icon\s*=\s*' +
                          re.escape(who) + r'->modeldata\.icon\.def;', body, re.S)[0]
        rest = body[body.index(chain) + len(chain):]
        anchor = 'if(icon>=0)'
        first = rest.index(anchor)
        following = rest.find(anchor, first + len(anchor))
        window = rest[:following] if following >= 0 else rest
        return chain + '\n' + braced_statement(window, anchor)

    player = state_window(predraw, 'player[i].ent')
    opponent = state_window(predraw, 'player[i].ent->opponent')
    enemy_window = state_window(enemy, 'ent')
    weapon = braced_statement(predraw, 'if(player[i].ent->weapent->modeldata.icon.weapon >= 0)')
    magic = braced_statement(predraw, 'if(player[i].ent->modeldata.mp)')
    join = predraw[predraw.index('icon = model->icon.def;'):]
    last = braced_statement(join, 'else if(icon>=0)')
    join = join[:join.index(last) + len(last)]
    inherit = re.search(r'if\(newmodel->icon\.def[^\r\n]+\r?\n(?:[^\r\n]+\r?\n){3}',
                        function(source, 'set_model_ex'))[0]
    commands = ('ICON', 'ICONPAIN', 'ICONDIE', 'ICONGET', 'ICONW', 'ICONMPHIGH', 'ICONMPHALF', 'ICONMPLOW')
    cases = []
    for name in commands:
        label = 'case CMD_MODEL_' + name + ':'
        if source.count(label) != 1:
            raise ValueError('Exactly one icon model command required: ' + name)
        rest = source[source.index(label):]
        cases.append(rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest[len(label):]).start() + len(label)])
    numbers = ','.join('{%d,%d}' % (row['input'], row['signed16']) for row in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (row['revision'], row['icon_bits']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#include "commands.h"
#undef printf
#undef exit
#undef time
#undef pause
#undef shutdown
#undef kill
uint32_t obor_profile_build;
@MODEL_ERROR@
int PLAYER_MAX_Z=232;
static entity actor,rival,held;
static struct {entity *ent;int colourmap;} player[1];
static struct {int shiftpos[1];} videomodes;
static int picon[1][2]={{10,20}},piconw[1][2]={{30,40}},mpicon[1][2]={{50,60}},eicon[1][2]={{70,80}};
static s_drawmethod plainmethod;
static unsigned char palettes[3][16];
static char image_name[]="image";
static int next_image,image_reads,calls,queued_id,queued_x,queued_y,queued_z;
static void *queued_table;
#define GET_ARG(i) (assert((i)==1),image_name)
int loadsprite(char *name,int x,int y,int format){assert(name==image_name && !x && !y && format==4);++image_reads;return next_image;}
static int load(s_model *newchar,int command,int value_index){
 char *value,*shutdownmessage=NULL;int pixelformat=4;next_image=value_index;image_reads=0;
 char *filename=(char *)"data/model.txt";
 @MODEL_ERROR_STORAGE@
 switch(command){@CASES@ default:assert(0);}
 assert(image_reads==1);return 1;
lCleanup:assert(shutdownmessage);return 0;
}
void spriteq_add_sprite(int x,int y,int z,int id,s_drawmethod *method,int sort){
 assert(!sort && !calls);++calls;queued_id=id;queued_x=x;queued_y=y;queued_z=z;queued_table=method?method->table:NULL;
}
static void submit(int path){
 int i=0,icon=-1;entity *ent=&actor;s_model *model=&actor.modeldata;s_drawmethod drawmethod=plainmethod;
 switch(path){case 0:{@PLAYER@}break;case 1:{@OPPONENT@}break;case 2:{@ENEMY@}break;
 case 3:{@WEAPON@}break;case 4:{@MAGIC@}break;case 5:{@JOIN@}break;default:assert(0);}
}
static void inherit(s_model *newmodel,s_model *model){@INHERIT@}
static const int commands[]={CMD_MODEL_ICON,CMD_MODEL_ICONPAIN,CMD_MODEL_ICONDIE,CMD_MODEL_ICONGET,
 CMD_MODEL_ICONW,CMD_MODEL_ICONMPHIGH,CMD_MODEL_ICONMPHALF,CMD_MODEL_ICONMPLOW};
static const struct {int input,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){assert(bits==16 || bits==32);return bits==16?numbers[i].v16:numbers[i].input;}
static void check_slots(s_model *model,const int want[8]){
 int actual[]={model->icon.def,model->icon.pain,model->icon.die,model->icon.get,model->icon.weapon,
  model->icon.mphigh,model->icon.mpmed,model->icon.mplow};
 for(int i=0;i<8;++i)assert(actual[i]==want[i]);
}
static void construct(s_model *model,const unsigned indices[8],int want[8],int bits){
 memset(model,0,sizeof(*model));model->icon.def=-1;
 for(int i=0;i<8;++i){assert(numbers[indices[i]].input>=-1);assert(load(model,commands[i],numbers[indices[i]].input));want[i]=expected(indices[i],bits);}
 check_slots(model,want);
}
static void observe(int path,int wanted,int x,int y,int z,void *table){
 calls=0;queued_id=-99;queued_table=NULL;submit(path);
 assert(calls==(wanted>=0));if(wanted>=0)assert(queued_id==wanted && queued_x==x && queued_y==y && queued_z==z && queued_table==table);
}
int main(void){
 assert(sizeof(int)==4 && sizeof(short)==2);const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 unsigned accepted[64],accepted_count=0;
 for(unsigned n=0;n<count;++n)if(numbers[n].input>=-1){assert(accepted_count<64);accepted[accepted_count++]=n;}
 player[0].ent=&actor;actor.opponent=&rival;actor.weapent=&held;
 videomodes.shiftpos[0]=33;savedata.windowpos=7;
 actor.colourmap=palettes[0];rival.colourmap=palettes[1];held.colourmap=palettes[2];
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  for(unsigned n=0;n<accepted_count;++n){
   unsigned indices[8];int want[8];
   for(int i=0;i<8;++i)indices[i]=accepted[(n+3*i)%accepted_count];
   construct(&actor.modeldata,indices,want,contexts[p].bits);
   s_model duplicate=actor.modeldata;
   int accepted_again=load(&duplicate,CMD_MODEL_ICON,1);
   assert(accepted_again==(want[0]<0));
   if(accepted_again)assert(duplicate.icon.def==1 && duplicate.icon.pain==1 && duplicate.icon.die==1 && duplicate.icon.get==1);
   else assert(!image_reads && duplicate.icon.def==want[0]);
   rival.modeldata=held.modeldata=actor.modeldata;
   actor.modeldata.icon.x=101;actor.modeldata.icon.y=202;actor.modeldata.colourmap[0]=palettes[1];
   for(int state=0;state<4;++state){
    actor.health=rival.health=state==0?0:100;actor.inpain=rival.inpain=state==1;actor.getting=rival.getting=state==2;
    int wanted=want[state==0?2:state==1?1:state==2?3:0];
    observe(0,wanted,43,27,10000,palettes[0]);observe(1,wanted,103,87,10000,palettes[1]);
    observe(2,wanted,101,202,HUD_Z,palettes[0]);
   }
   observe(3,want[4],63,47,10000,palettes[2]);
   const int magic[]={-1,0,32,33,65,66,100};actor.modeldata.mp=100;
   for(unsigned m=0;m<sizeof(magic)/sizeof(magic[0]);++m){
    actor.oldmp=magic[m];int wanted=-1;
    if(want[5]>0 && magic[m]>=66)wanted=want[5];
    else if(want[6]>0 && magic[m]>=33 && magic[m]<66)wanted=want[6];
    else if(want[7]>0 && magic[m]>=0 && magic[m]<33)wanted=want[7];
    else if(want[5]>0 && want[6]==-1 && want[7]==-1)wanted=want[5];
    observe(4,wanted,83,67,10000,palettes[0]);
   }
   actor.modeldata.icon.mpmed=actor.modeldata.icon.mplow=-1;actor.oldmp=-1;
   observe(4,want[5]>0?want[5]:-1,83,67,10000,palettes[0]);
   for(int map=0;map<2;++map){player[0].colourmap=map;observe(5,want[0],43,20,10000,map?palettes[1]:NULL);}
   // Four fallback fields retain the value already converted by the loader.
   for(unsigned mask=0;mask<16;++mask){
    s_model child,base;unsigned children[8],parents[8];int child_values[8],base_values[8];
    for(int i=0;i<8;++i){children[i]=accepted[(n+i)%accepted_count];parents[i]=accepted[(n+i+5)%accepted_count];}
    construct(&child,children,child_values,contexts[p].bits);construct(&base,parents,base_values,contexts[p].bits);
    for(int i=0;i<4;++i)if(mask&(1u<<i)){int *field=i==0?&child.icon.def:i==1?&child.icon.pain:i==2?&child.icon.die:&child.icon.get;*field=-1;child_values[i]=-1;}
    inherit(&child,&base);
    for(int i=0;i<4;++i)if(child_values[i]<0)child_values[i]=base_values[i];
    check_slots(&child,child_values);
   }
  }
 }
 printf("model icon contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@MODEL_ERROR@', function(source, 'obor_model_error') + '\n' + continued_macro(source, 'OBOR_MODEL_ERROR')).replace(
        '@MODEL_ERROR_STORAGE@', re.search(r'char legacy_model_error\[\d+\][^;]*;', function(source, 'load_cached_model')).group()).replace(
        '@CASES@', '\n'.join(cases)).replace('@PLAYER@', player).replace('@OPPONENT@', opponent).replace(
        '@ENEMY@', enemy_window).replace('@WEAPON@', weapon).replace('@MAGIC@', magic).replace(
        '@JOIN@', join).replace('@INHERIT@', inherit).replace('@NUMBERS@', numbers).replace('@CONTEXTS@', contexts)


def render_selection_icon(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    predraw = function(source, 'predrawstatus')
    first = predraw.index('icon = model->icon.def;')
    branch = predraw[first:predraw.index('\n\t\t}\n\t\telse if(player[i].credits', first)]
    header = (engine / 'openbor.h').read_text()
    limit = re.search(r'(?m)^#define\s+MAX_COLOUR_MAPS\s+[^\n]+', header)[0]
    lookup = function(source, 'model_get_colourmap').replace(
        'model_get_colourmap(', 'native_model_get_colourmap(', 1)
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (
        row['revision'], row['zero_map_uses_sprite_palette']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
@LIMIT@
typedef struct {struct {int def;} icon;unsigned maps_loaded,colourmap_capacity;
    unsigned char *palette,**colourmap;} s_model;
typedef struct {int flag;unsigned char *table;} s_drawmethod;
static uint32_t obor_profile_build;
static unsigned cases,queued,lookups;
static int map,icon_value,palette_index,has_method;
static unsigned char palettes[6][16],*maps[]={palettes[2],palettes[3]};
static unsigned char *captured;
static s_model model_value,*model=&model_value;
static struct {int colourmap;} player[1];
static struct {int shiftpos[1];} videomodes;
static int picon[1][2]={{10,20}};
static s_drawmethod plainmethod={1,palettes[5]};
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"selection icon profile=%u map=%d icon=%d palette=%d line=%d\n",obor_profile_build,map,icon_value,palette_index,__LINE__);abort();}}while(0)
@LOOKUP@
static unsigned char *model_get_colourmap(s_model *owner,unsigned which){
    ++lookups;return native_model_get_colourmap(owner,which);
}
static void spriteq_add_sprite(int x,int y,int z,int id,s_drawmethod *method,int sort){
    assert(x==43 && y==20 && z==10000 && id==icon_value && sort==0);++queued;
    has_method=method!=NULL;if(method)assert(method->flag==1);
    captured=method?method->table:palettes[4];
}
static void submit(void){int i=0,icon;s_drawmethod drawmethod=plainmethod;@BRANCH@}
static void check(int sprite_zero){
    const int icons[]={-1,0,51};
    for(palette_index=0;palette_index<2;++palette_index)
    for(map=0;map<3;++map)for(unsigned k=0;k<sizeof(icons)/sizeof(*icons);++k){
        icon_value=icons[k];model_value=(s_model){{icon_value},2,2,palettes[palette_index],maps};
        player[0].colourmap=map;videomodes.shiftpos[0]=33;
        queued=lookups=0;captured=NULL;has_method=-1;submit();
        assert(queued==(unsigned)(icon_value>=0));
        if(icon_value>=0){
            int raw=sprite_zero && !map;
            unsigned char *expected=raw?palettes[4]:map?maps[map-1]:palettes[palette_index];
            assert(has_method==!raw && captured==expected);assert(lookups==(unsigned)!raw);
        }else assert(lookups==0 && captured==NULL && has_method==-1);
        ++cases;
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@LIMIT@', limit).replace('@LOOKUP@', lookup).replace('@BRANCH@', branch).replace('@CHECKS@', checks)


def render_hud_icons(engine, rows, *, predraw_source=None, colourmap_source=None):
    source = (engine / 'openbor.c').read_text()
    methods = '\n'.join((
        colourmap_source or function(source, 'model_get_colourmap'),
        predraw_source or function(source, 'predrawstatus')))
    start = source.index('case CMD_MODEL_ICON:')
    icon_case = source[start:source.index('case CMD_MODEL_ICONPAIN:', start)]
    profiles = ','.join('{%d,%d}' % (row['revision'], row['icon_usemap_selection'])
                        for row in rows)
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef struct { int die,pain,get,def,weapon,mphigh,mpmed,mplow,usemap; } Icon;
typedef struct {
    Icon icon; int mp,typeshot,shootnum,nolife;
    unsigned maps_loaded; unsigned char *palette,**colourmap;
} s_model;
typedef struct entity {
    const char *name; int health,inpain,getting,oldmp,rush[2]; long rushtime;
    s_model modeldata; unsigned char *colourmap;
    struct entity *weapent,*opponent;
} entity;
typedef struct { int maxplayers; } s_set_entry;
typedef struct { int flag,flipx; unsigned char *table; } s_drawmethod;
typedef struct {
    entity *ent; unsigned long score; int lives,joining,colourmap,credits,hasplayed;
    char name[16];
} Player;
static uint32_t obor_profile_build;
static Player player[4];
static s_set_entry levelsets[1];static int current_set;
static s_drawmethod plainmethod={1,0,NULL};
static struct { int hShift,vShift,dOffset,hRes,shiftpos[4]; } videomodes;
static struct { int windowpos,debuginfo; } savedata;
static struct { int notime,scrolldir; } level_storage,*level=&level_storage;
static int bgicon=-1,olicon=-1,timeicon=-1,golsprite=-1,gosprite=90;
static int bgicon_offsets[3],olicon_offsets[3],timeicon_offsets[3],timeloc[6];
static int pscore[4][7],picon[4][3],piconw[4][3],mpicon[4][3],pshoot[4][3];
static int plifeX[4][3],plifeN[4][3],prush[4][8],ename[4][3],eicon[4][3],pnameJ[4][7];
static int scoreformat,rush[6],time,nojoin,credits,noshare,timetoshow,showtimeover,showgo;
static const char *rush_names[2]={"a","b"};
static unsigned long freeram,totalram,usedram;
enum { GAME_SPEED=200,SCROLL_LEFT=1,SCROLL_RIGHT=2 };
static unsigned char palettes[8][16];
static unsigned char *joining_maps[2]={palettes[4],palettes[5]};
static s_model joining_model;
static unsigned cases;
typedef struct { int x,y,z,id,flag,flipx; unsigned char *table; } Queued;
static Queued queue[16];static unsigned queued;
static void font_printf(int x,int y,int font,int z,const char *format,...) {
    (void)x;(void)y;(void)font;(void)z;(void)format;
}
static void spriteq_add_sprite(int x,int y,int z,int id,s_drawmethod *method,int sortid) {
    assert(queued<16 && sortid==0);
    queue[queued++]=(Queued){x,y,z,id,method?method->flag:0,method?method->flipx:0,
                            method?method->table:NULL};
}
static void spriteq_add_box(int x,int y,int width,int height,int z,int colour,void *method) {
    (void)x;(void)y;(void)width;(void)height;(void)z;(void)colour;(void)method;
}
static int getFPS(void) { return 60; }
static const char *commaprint(unsigned long value) { (void)value;return "0"; }
static s_model *findmodel(const char *name) { assert(!strcmp(name,"joining"));return &joining_model; }
@METHODS@
static int icon_flag,name_reads,flag_reads,icon_loads;
static int pixelformat=4;
static char *icon_argument(int index) {
    assert(index==1);++name_reads;return "icon.png";
}
static int icon_integer(int index) { assert(index==2);++flag_reads;return icon_flag; }
static int loadsprite(char *name,int x,int y,int format) {
    assert(!strcmp(name,"icon.png") && !x && !y && format==4);++icon_loads;return 71;
}
#define GET_ARG(index) icon_argument(index)
#define GET_INT_ARG(index) icon_integer(index)
static int icon_command(s_model *newchar,int flag) {
    char *value,*shutdownmessage=NULL;icon_flag=flag;
    enum {CMD_MODEL_ICON=1};
    switch(CMD_MODEL_ICON) { @ICON_CASE@ }
    return 1;
lCleanup:
    assert(shutdownmessage && !strcmp(shutdownmessage,"model has multiple icons defined"));return 0;
}
#undef GET_ARG
#undef GET_INT_ARG
static void icon_arguments(int native_usemap) {
    const int flags[]={-1,0,1,2};
    for(unsigned f=0;f<sizeof(flags)/sizeof(*flags);++f)for(int duplicate=0;duplicate<2;++duplicate) {
        ++cases;s_model model={0};model.icon.def=duplicate?88:-1;
        name_reads=flag_reads=icon_loads=0;
        assert(icon_command(&model,flags[f])==!duplicate);
        if(name_reads!=1 || flag_reads!=(native_usemap && !duplicate) || icon_loads!=!duplicate) {
            fprintf(stderr,"HUD icon arguments profile=%u case=%u\n",obor_profile_build,cases);abort();
        }
        if(duplicate)assert(model.icon.def==88 && model.icon.usemap==0);
        else assert(model.icon.def==71 && model.icon.pain==71 && model.icon.die==71 &&
                    model.icon.get==71 && model.icon.usemap==(native_usemap?flags[f]:0));
    }
}
static unsigned char *selected(int native_usemap,int flag,unsigned char *palette) {
    return !native_usemap || flag ? palette : NULL;
}
static void expect(unsigned *index,int id,unsigned char *table,int x,int y) {
    assert(*index<queued);Queued *item=&queue[(*index)++];
    if(item->id!=id || item->table!=table || item->x!=x || item->y!=y ||
       item->z!=10000 || item->flag!=1 || item->flipx!=0) {
        fprintf(stderr,"HUD profile=%u case=%u item=%u id=%d expected=%d palette=%p expected=%p\n",
                obor_profile_build,cases,*index,item->id,id,(void*)item->table,(void*)table);
        abort();
    }
}
static void one_case(int native_usemap,int flags,int state,int mp,int weapon,int opponent,
                     int joinflag,int map,int hidden) {
    ++cases;queued=0;memset(player,0,sizeof(player));
    entity parent={0},held={0},rival={0},second={0};
    parent.name="parent";held.name="weapon";rival.name="rival";second.name="second";
    parent.health=state==0?0:100;parent.inpain=state==1;parent.getting=state==2;
    parent.modeldata.icon=(Icon){11,12,13,14,0,31,32,33,flags&1};
    if(hidden)parent.modeldata.icon.die=parent.modeldata.icon.pain=
                  parent.modeldata.icon.get=parent.modeldata.icon.def=-1;
    parent.colourmap=palettes[0];
    held.modeldata.icon.weapon=hidden?-1:21;held.modeldata.icon.usemap=(flags>>1)&1;
    held.colourmap=palettes[1];if(weapon)parent.weapent=&held;
    rival.health=100;rival.modeldata.icon.def=41;rival.modeldata.icon.usemap=(flags>>2)&1;
    rival.colourmap=palettes[2];if(opponent)parent.opponent=&rival;
    parent.modeldata.mp=mp?100:0;
    parent.oldmp=mp==1?90:mp==2?50:mp==3?10:-1;
    if(mp==4)parent.modeldata.icon.mpmed=parent.modeldata.icon.mplow=-1;
    joining_model=(s_model){0};joining_model.icon.def=51;joining_model.icon.usemap=joinflag;
    joining_model.palette=palettes[3];joining_model.colourmap=joining_maps;joining_model.maps_loaded=2;
    second.health=100;second.modeldata.icon.def=61;second.modeldata.icon.usemap=flags&1;
    second.colourmap=palettes[6];
    player[0].ent=&parent;player[1].joining=1;strcpy(player[1].name,"joining");
    player[1].colourmap=map;player[2].ent=&second;
    levelsets[0].maxplayers=3;level->notime=1;savedata.windowpos=7;
    for(int i=0;i<4;++i) {
        videomodes.shiftpos[i]=100*i;
        picon[i][0]=10;picon[i][1]=20;piconw[i][0]=30;piconw[i][1]=40;
        mpicon[i][0]=50;mpicon[i][1]=60;eicon[i][0]=70;eicon[i][1]=80;
    }
    predrawstatus();unsigned index=0;
    unsigned char *parent_table=selected(native_usemap,flags&1,palettes[0]);
    if(!hidden)expect(&index,11+state,parent_table,10,27);
    if(weapon && !hidden)expect(&index,21,selected(native_usemap,(flags>>1)&1,palettes[1]),30,47);
    if(mp>=1 && mp<=4)expect(&index,mp==4?31:30+mp,parent_table,50,67);
    if(opponent)expect(&index,41,selected(native_usemap,(flags>>2)&1,palettes[2]),70,87);
    unsigned char *joining_table=map?joining_maps[map-1]:palettes[3];
    expect(&index,51,selected(native_usemap,joinflag,joining_table),110,20);
    expect(&index,61,selected(native_usemap,flags&1,palettes[6]),210,27);
    assert(index==queued);
}
int main(void) {
    const struct {unsigned revision;int native_usemap;} profiles[]={@PROFILES@};
    FILE *output=NULL;const char *path=getenv("OBOR_HUD_OBSERVATIONS");
    if(path){output=fopen(path,"w");assert(output);fputs("[",output);}
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p].revision;unsigned before=cases;
        icon_arguments(profiles[p].native_usemap);
        for(int flags=0;flags<8;++flags)for(int state=0;state<4;++state)
        for(int mp=0;mp<6;++mp)for(int weapon=0;weapon<2;++weapon)
        for(int opponent=0;opponent<2;++opponent)for(int joinflag=0;joinflag<2;++joinflag)
        for(int map=0;map<3;++map)for(int hidden=0;hidden<2;++hidden)
            one_case(profiles[p].native_usemap,flags,state,mp,weapon,opponent,joinflag,map,hidden);
        if(output)fprintf(output,"%s{\"revision\":%u,\"cases\":%u}",p?",":"",obor_profile_build,cases-before);
    }
    if(output){fputs("]\n",output);assert(!fclose(output));}
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);
    return 0;
}
'''.replace('@METHODS@', methods).replace('@ICON_CASE@', icon_case).replace('@PROFILES@', profiles)
