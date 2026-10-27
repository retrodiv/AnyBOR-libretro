"""Render the native animation command and name resolver against source facts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from test_historical_player import function


def render_animation_names(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    start = source.index('case CMD_MODEL_ANIM:')
    command = source[start:source.index('case CMD_MODEL_LOOP:', start)]
    first = header.index('#define strclen(')
    macros = header[first:header.index('\n/*', first)]
    definitions = []
    for name, value in re.findall(r'^#define\s+(ANI_\w+)\s+(\d+)\b', header, re.M):
        definitions.append('#define ' + name + ' ' + value)
    for name in ['MAX_ATKS', 'STA_ATKS']:
        definitions.append(re.search(r'^#define\s+' + name + r'\s+[^\n]+', header, re.M)[0])
    definitions += [function(source, name) for name in ('obor_attack_base', 'obor_attack_special')]
    definitions += ['#define OBOR_ATTACK_BASE (obor_attack_base())',
                    '#define OBOR_ATTACK_SPECIAL (obor_attack_special())']
    arrays = fixture['vector_order']
    definitions += ['static int ' + name + '[24];' for name in arrays]
    vectors = {}
    for key, values in fixture['vector_sets'].items():
        name = 'vectors_' + str(len(vectors))
        vectors[key] = name
        initial = ','.join('{' + ','.join(map(str, values[array] +
            [0] * (24-len(values[array])))) + '}' for array in arrays)
        definitions.append('static const int ' + name + '[14][24]={' + initial + '};')
    case_names = {}
    tables = []
    for key, cases in fixture['case_sets'].items():
        name = 'source_cases_' + str(len(case_names))
        case_names[key] = name
        initial = []
        for row in cases:
            values = [row['sync'], row['bounce'], row['attackone'],
                      row['energycost'], row['counterattack']]
            initial.append('{%s,%s,%s,%d,{%s},%s}' % (
                json.dumps(row['query']), row['jumpheight'], row['grabdistance'], row['id'],
                ','.join(map(str, row['range'])), ','.join(map(str, values))))
        tables.append('static const Case ' + name + '[]={' + ','.join(initial) + '};')
    checks = []
    for row in fixture['sources']:
        setup = ''.join('memcpy(' + array + ',' + vectors[row['vector_set']] + '[' +
                        str(i) + '],sizeof(' + array + '));' for i, array in enumerate(arrays))
        checks.append('obor_profile_build=%d;animation_limit=%d;%scheck(%s,%d);' % (
            row['revision'], row['animation_limit'], setup, case_names[row['case_set']],
            len(fixture['case_sets'][row['case_set']])) )
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
static uint32_t obor_profile_build;
#define stricmp strcasecmp
#define strnicmp strncasecmp
typedef struct {int xmin,xmax,zmin,zmax,amin,amax,bmin,bmax;} Range;
typedef struct {int f;float v;} Jump;
typedef struct {int mponly,disable,cost;} Energy;
typedef struct {int framestart,frameend,condition,damaged;} Counter;
typedef struct {int frame;} Land;
typedef struct {int framestart;} Quake;
typedef struct {
 int model_index;Range range;Jump jumpframe;Energy energycost;Counter counterrange;
 Land landframe;Quake quakeframe;
 int chargetime,shootframe,throwframe,tossframe,flipframe,attackone,dive,followanim,followcond;
 int unsummonframe,dropframe,cancel,animhits,subentity,custbomb,custknife,custstar,custpshotno;
 int sync,bounce;
} s_anim;
typedef struct {int index;float jumpheight,grabdistance;s_anim **animation;} s_model;
typedef struct {int hitsound,hitflash,blockflash,blocksound,counterattack;} s_attack;
typedef struct {int tag;} s_drawmethod;
static s_attack emptyattack;
static s_drawmethod plainmethod={71};
static s_anim current_animation,*animation_table[512];
static const char *query_text;
static s_attack command_attack;
static int animation_limit,reserved_id;
static unsigned cases;
static int SAMPLE_BEAT=123;
#define E_OUT_OF_MEMORY "fixture allocation refusal"
static s_anim *alloc_anim(void){memset(&current_animation,0,sizeof(current_animation));return &current_animation;}
static int model_animation_reserve(s_model *model,int id){
 assert(model && model->animation==animation_table && id>=0 && id<animation_limit && id<512);
 assert(reserved_id==-1);reserved_id=id;return 1;
}
static void shutdown(int status,char *message){(void)status;(void)message;abort();}
@DEFINITIONS@
@MACROS@
@TRANSLATOR@
#define GET_ARG(i) ((char*)((i)==1?query_text:""))
static int command(s_model *model){
 s_model *newchar=model;s_anim *newanim=NULL;s_attack attack;
 s_drawmethod drawmethod={-1};char *value=NULL,*shutdownmessage=NULL;
 int frameset=7,framecount=7,curframe=7,shadow_set=7,idle=7;
 int frameshadow=7,soundtoplay=7,ani_id=-1;
 float move=7,movez=7,movea=7,seta=7;
 int bbox[8],abox[8],offset[2],shadow_coords[2],shadow_xz[2],platform[8];
 memset(bbox,1,sizeof(bbox));memset(abox,1,sizeof(abox));memset(offset,1,sizeof(offset));
 memset(shadow_coords,1,sizeof(shadow_coords));memset(shadow_xz,1,sizeof(shadow_xz));memset(platform,1,sizeof(platform));
 enum {CMD_MODEL_ANIM=1};int accepted;
 switch(CMD_MODEL_ANIM){@COMMAND@}
 accepted=1;goto done;
lCleanup:
 assert(shutdownmessage && !strcmp(shutdownmessage,"Invalid animation name!"));accepted=0;
done:
 assert(newanim==&current_animation && newanim->model_index==model->index);
 assert(!frameset && !framecount && !curframe && !shadow_set && !idle);
 assert(!move && !movez && !movea && seta==-1 && frameshadow==-1 && soundtoplay==-1);
 assert(drawmethod.tag==71);
 assert(attack.hitsound==123 && attack.hitflash==-1 && attack.blockflash==-1 && attack.blocksound==-1);
 for(unsigned i=0;i<8;++i)assert(!bbox[i] && !abox[i] && !platform[i]);
 for(unsigned i=0;i<2;++i)assert(!offset[i] && !shadow_coords[i] && !shadow_xz[i]);
 command_attack=attack;return accepted;
}
typedef struct {const char *name;float height,grab;int id,range[8],sync,bounce,one,cost,counter;} Case;
@TABLES@
static void check(const Case *rows,unsigned count){
 for(unsigned i=0;i<count;++i){
  ++cases;const Case *expected=&rows[i];query_text=expected->name;reserved_id=-1;
  memset(animation_table,0,sizeof(animation_table));
  s_model model={9,expected->height,expected->grab,animation_table};
  int accepted=command(&model);s_anim *actual=&current_animation;
  int okay=accepted==(expected->id>=0);
  if(accepted){
   const int ranges[]={actual->range.xmin,actual->range.xmax,actual->range.zmin,actual->range.zmax,
    actual->range.amin,actual->range.amax,actual->range.bmin,actual->range.bmax};
   okay=okay && reserved_id==expected->id && animation_table[expected->id]==actual &&
    !memcmp(ranges,expected->range,sizeof(ranges)) && actual->sync==expected->sync &&
    actual->bounce==expected->bounce && actual->attackone==expected->one &&
    actual->energycost.cost==expected->cost && command_attack.counterattack==expected->counter;
  }else okay=okay && reserved_id==-1;
  for(unsigned n=0;n<512;++n)okay=okay && (animation_table[n]!=(s_anim*)0)==(accepted && n==(unsigned)expected->id);
  if(!okay){fprintf(stderr,"animation name profile=%u query=%s height=%g id=%d expected=%d sync=%d expected=%d bounce=%d expected=%d\n",
   obor_profile_build,query_text,(double)model.jumpheight,reserved_id,expected->id,
   actual->sync,expected->sync,actual->bounce,expected->bounce);abort();}
 }
}
int main(void){@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;}
'''.replace('@DEFINITIONS@', '\n'.join(definitions)).replace('@MACROS@', macros).replace(
        '@TRANSLATOR@', function(source, 'translate_ani_id')).replace('@COMMAND@', command).replace(
        '@TABLES@', '\n'.join(tables)).replace('@CHECKS@', '\n'.join(checks))


def render_model_sync(engine, animation_fixture, sync_fixture):
    """Reuse the translator with actual lookup, sync and default-clause bodies."""
    program = render_animation_names(engine, animation_fixture).replace(
        'int main(void){', 'int animation_names_control(void){', 1)
    program = program.replace('#include <assert.h>',
                              '#include <assert.h>\n#include <stdarg.h>', 1)
    source = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    header = (engine / 'source/gamelib/commands.h').read_text()
    enum = re.search(r'typedef enum modelCommand\s*\{.*?\}\s*modelCommands;', header, re.S)[0]
    constructor = function(commands, 'createModelCommandList')
    registrations = dict((name, value) for value, name in re.findall(
        r'LIST_ADD\((\w+),\s*"([^"]+)"\)', constructor))
    entries = ','.join('{"%s",(void*)(intptr_t)%s}' % (name, registrations[name])
                       for name in ['sync', 'anim', 'loop'])
    loader = function(source, 'load_cached_model')
    first = loader.index('cmd = getModelCommand(modelcmdlist, command);')
    lookup = loader[first:loader.index('switch(cmd)', first)]
    first = loader.index('case CMD_MODEL_SYNC:')
    sync_case = loader[first:loader.index('case CMD_MODEL_DELAY:', first)]
    first = loader.rindex('\n\t\t\t\tdefault:')
    default = loader[first:loader.index('\n\t\t\t}', first)]
    getters = '\n'.join(function(commands, name) for name in (
        'getCommandlistCommand', 'getModelCommand'))
    contexts = {row['revision']: row for row in animation_fixture['sources']}
    checks = []
    for row in sync_fixture['sources']:
        animation = contexts[row['revision']]
        values = animation_fixture['vector_sets'][animation['vector_set']]
        setup = ''.join('memcpy(%s,(const int[]){%s},%d*sizeof(int));' % (
            name, ','.join(map(str, table)), len(table)) for name, table in values.items())
        facts = {case['query']: case['id'] for case in
                 animation_fixture['case_sets'][animation['case_set']]}
        checks.append('obor_profile_build=%d;%s' % (row['revision'], setup))
        for value in sync_fixture['arguments']:
            expected = facts.get(value, -1)
            for command in sync_fixture['commands']:
                checks.append('sync_check(%s,%s,%d,%d);' % (
                    json.dumps(command), json.dumps(value), int(row['explicit_sync']), expected))
        checks.append('neighbors();')
    return program + r'''
@ENUM@
typedef struct {int unused;} List;
typedef struct {const char *name;void *value;} Node;
typedef struct {int unused;} ArgList;
static List model_commands,*modelcmdlist=&model_commands;
static Node registry[]={@ENTRIES@};
static void lc(char *text,size_t size){for(size_t i=0;i<size;++i)if(text[i]>='A' && text[i]<='Z')text[i]+='a'-'A';}
static Node *List_GetNodeByName(List *list,char *name){
 assert(list==modelcmdlist);for(unsigned i=0;i<3;++i)if(!strcmp(name,registry[i].name))return &registry[i];return NULL;
}
@GETTERS@
static modelCommands selected_command(char *command){modelCommands cmd;@LOOKUP@return cmd;}
static char sync_log[512];static unsigned include_calls,argument_reads,sync_cases;
static int sync_printf(const char *format,...){
 va_list args;va_start(args,format);int size=vsnprintf(sync_log,sizeof(sync_log),format,args);va_end(args);return size;
}
static int handle_txt_include(char *command,ArgList *args,char **filename,char *name,char **buffer,int *pos,int *size){
 (void)args;(void)name;(void)buffer;(void)pos;(void)size;
 assert(!strcmp(*filename,"fixture") && command && *command);++include_calls;return 0;
}
static char *sync_argument(int index){assert(index==1);++argument_reads;return (char*)query_text;}
#undef GET_ARG
#define GET_ARG(i) sync_argument(i)
#define printf sync_printf
static void dispatch(char *command,s_anim *newanim){
 ArgList arglist={0};char *filename="fixture",fnbuf[16]={0},*buf=NULL;int pos=0,size=0;
 modelCommands cmd=selected_command(command);
 switch(cmd){@SYNC@@DEFAULT@}
}
#undef printf
static void sync_check(const char *word,const char *value,int available,int id){
 ++sync_cases;char command[64];assert(strlen(word)<sizeof(command));strcpy(command,word);
 s_anim animation,expected;memset(&animation,0,sizeof(animation));
 animation.sync=77;animation.bounce=23;animation.range.xmin=31;animation.energycost.cost=11;
 memcpy(&expected,&animation,sizeof(expected));
 int recognized=available && (!strcmp(word,"sync") || !strcmp(word,"SyNc"));
 if(recognized)expected.sync=id;
 sync_log[0]=0;include_calls=argument_reads=0;query_text=value;dispatch(command,&animation);
 int correct=!memcmp(&animation,&expected,sizeof(animation)) && argument_reads==(unsigned)recognized;
 if(recognized || !*word)correct=correct && !include_calls && !sync_log[0];
 else {
  char message[128];snprintf(message,sizeof(message),"Command '%s' not understood in file 'fixture'!\n",command);
  correct=correct && include_calls==1 && !strcmp(sync_log,message);
 }
 if(!correct){fprintf(stderr,"model sync profile=%u command=%s value=%s sync=%d expected=%d\n",obor_profile_build,word,value,animation.sync,expected.sync);abort();}
}
static void neighbors(void){
 char anim[]="ANIM",loop[]="loop";assert(selected_command(anim)==CMD_MODEL_ANIM && !strcmp(anim,"anim"));
 assert(selected_command(loop)==CMD_MODEL_LOOP);
}
int main(void){(void)&animation_names_control;@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",sync_cases);return 0;}
'''.replace('@ENUM@', enum).replace('@ENTRIES@', entries).replace('@GETTERS@', getters).replace(
        '@LOOKUP@', lookup).replace('@SYNC@', sync_case).replace('@DEFAULT@', default).replace(
        '@CHECKS@', '\n'.join(checks))
