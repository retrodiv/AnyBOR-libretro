"""Render selected native model-loading phases against own-source facts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from test_historical_player import function


def render_model_load_phase(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    standalone = function(source, 'load_model_constants')
    if 'static void obor_reset_model_constants(' in source:
        reset = function(source, 'obor_reset_model_constants')
        build = function(source, 'obor_build_model_constants')
    else:
        # Before-change controls need the same isolated setup/teardown. These
        # helpers are not inserted into the selected production call paths.
        first = standalone.index('\t// reload default values')
        last = standalone.index('\t// Read file', first)
        reset = 'static void obor_reset_model_constants(void) {\n' + standalone[first:last] + '}\n'
        build = ''
    loader = function(source, 'load_models')
    loader = loader[:loader.index('\t// Defer load_cached_model')]
    loader += '\n(void)i;(void)modelLoadCount;free(buf);return 1;}\n'
    startup = function(source, 'startup')
    first = startup.index('\tprintf("Loading level order')
    startup = startup[first:startup.index('\tprintf("Object engine init', first)]
    command_header = (engine / 'source/gamelib/commands.h').read_text()
    enum = re.search(r'typedef enum\s*\{[^}]+\}\s*modelstxtCommands;', command_header)[0]
    definitions = [line for line in header.splitlines()
                   if re.match(r'^#define\s+(?:ANI_\w+|MAX_(?:ANIS|ATKS|ARG_LEN|DOWNS|UPS|BACKWALKS|WALKS|IDLES|SPECIALS|ATTACKS|FOLLOWS)|STA_ATKS)\s', line)]
    definitions += [function(source, name) for name in ('obor_attack_base', 'obor_attack_special')]
    definitions += ['#define OBOR_ATTACK_BASE (obor_attack_base())',
                    '#define OBOR_ATTACK_SPECIAL (obor_attack_special())']
    pointers = fixture['vector_order']
    for pointer in pointers:
        name = fixture['array_names'][pointer]
        definitions.append(re.search(r'(?m)^int\s+' + name + r'\[[^\]]+\]\s*=\s*\{[^}]*\}', source)[0] + ';')
        definitions.append('static int *' + pointer + ';')
    definitions.append('static int max_downs,max_ups,max_backwalks,max_walks,max_idles,'
                       'max_freespecials,max_attacks,max_follows,max_attack_types,max_animations;')
    copies = []
    fact_names = {}
    for key, facts in fixture['fact_sets'].items():
        name = 'facts_' + str(len(fact_names))
        fact_names[key] = name
        initial = facts['initial_vectors']
        copies.append('static const int ' + name + '[14][64]={' + ','.join(
            '{' + ','.join(map(str, initial[p])) + '}' for p in pointers) + '};')
    checks = []
    for row in fixture['sources']:
        facts = fixture['fact_sets'][row['facts']]
        d = facts['defaults']
        checks.append('revision=%d;expected_early=%d;expected_base=%d;expected_special=%d;'
                      'expected_initial=%s;check(0);check(1);' % (
                          row['revision'], row['early_constants'], d['MAX_ATKS'], d['STA_ATKS'],
                          fact_names[row['facts']]))
    lengths = ['max_downs', 'max_ups', 'max_backwalks', 'max_walks', 'max_idles',
               'max_freespecials', 'max_attacks', 'max_follows'] + ['max_attack_types'] * 6
    native_vectors = ''.join('actual[%d]=%s;lengths[%d]=%s;' % (i, p, i, lengths[i])
                             for i, p in enumerate(pointers))
    defaults = ['MAX_DOWNS', 'MAX_UPS', 'MAX_BACKWALKS', 'MAX_WALKS', 'MAX_IDLES',
                'MAX_SPECIALS', 'MAX_ATTACKS', 'MAX_FOLLOWS'] + ['expected_base'] * 6
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
static unsigned revision,cases;
static uint32_t obor_profile_build;
static int expected_early,expected_base,expected_special,phase,custom;
static const char *stage="setup";
static const int (*expected_initial)[64];
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"load phase profile=%u phase=%d stage=%s line=%d\n",revision,phase,stage,__LINE__);abort();}}while(0)
@DEFINITIONS@
@ENUM@
@FACTS@
typedef struct {char *args[8];} ArgList;
#define GET_ARG(i) (arglist.args[(i)])
#define GET_INT_ARG(i) atoi(GET_ARG(i))
#define GET_FLOAT_ARG(i) ((float)atof(GET_ARG(i)))
static int combodelay,colourselect,spdirection[4],autoland,nolost,ajspecial,nocost;
static int forcecheatsoff,nodropen,nodropspawn,noaircancel,nomaxrushreset[5];
static int mpblock,blockratio,nochipdeath,lifescore,credscore,versusdamage;
static float default_model_dropv[3],default_model_jumpspeed,default_model_jumpheight;
static float default_model_grabdistance,move_noatk_factor,group_noatk_factor,agg_noatk_factor;
static float min_noatk_chance,max_noatk_chance,offscreen_noatk_factor,noatk_duration;
static struct {int mode;} savedata;
static struct {int set;} loadingbg[1];
static char *custModels,*custBkgrds;
static int modelstxtcmdlist;
static unsigned file_calls,script_calls,cache_calls,music_calls,screen_calls,diagnostics;
static char files[8][128];
static int getModelCommand(int list,char *name) {
    (void)list;
    @LOOKUP@
    return CMD_MODELSTXT_THE_END;
}
static int ParseArgs(ArgList *args,const char *line,char *out) {
    size_t n=strcspn(line,"\r\n");assert(n<MAX_ARG_LEN);memcpy(out,line,n);out[n]=0;
    for(unsigned i=0;i<8;++i)args->args[i]=(char*)"";
    char *p=out;unsigned i=0;
    while(*p){while(*p==' ' || *p=='\t')++p;if(!*p)break;assert(i<8);args->args[i++]=p;
        while(*p && *p!=' ' && *p!='\t'){++p;}
        if(*p)*p++=0;}
    return i!=0;
}
static size_t getNewLineStart(const char *p) {
    size_t n=strcspn(p,"\r\n");if(p[n]=='\r')++n;if(p[n]=='\n')++n;return n;
}
static int silent_printf(const char *format,...) {
    if(strstr(format,"not understood"))++diagnostics;
    return 0;
}
static void shutdown(int status,const char *format,...) {(void)status;(void)format;abort();}
static int buffer_pakfile(const char *name,char **out,size_t *size) {
    assert(file_calls<8);strcpy(files[file_calls++],name);
    int seed=!strcmp(name,"data/models.txt")?0:3;seed+=phase;
    char text[1024];int n=snprintf(text,sizeof(text),
        "maxwalks %d\nload fixture model.txt\nmaxidles %d\nmaxbackwalks %d\nmaxups %d\n"
        "maxdowns %d\nmaxattacktypes %d\nmaxfollows %d\nmaxfreespecials %d\nmaxattacks %d\n"
        "music fixture 0\nknow fixture model.txt\n",5+seed,6+seed,4+seed,3+seed,
        2+seed,13+seed,8+seed,9+seed,7+seed);
    assert(n>0 && (size_t)n<sizeof(text));*size=(size_t)n;*out=malloc(*size+1);assert(*out);
    memcpy(*out,text,*size+1);return 1;
}
static int isLoadingScreenTypeBg(int set){return set&1;}
static int isLoadingScreenTypeBar(int set){return set&2;}
static void load_background(char *name,int unused){(void)unused;assert(strstr(name,"loading"));}
static void standard_palette(int value){assert(value==1);}
static void lifebar_colors(void){}
static void init_colourtable(void){}
static void free_modelcache(void){}
static void obor_preload_begin(void){}
static void cache_model(char *name,char *path,int load) {
    stage="metadata";++cache_calls;assert(!strcmp(name,"fixture") && !strcmp(path,"model.txt"));
    assert(load==0 || load==1);
    assert(!!animwalks==(expected_early && phase!=2));
    assert(max_walks==(expected_early?5:5+(custom?3:0)+phase));
}
static void music(char *name,int loop,long offset) {
    assert(!strcmp(name,"fixture") && loop==1 && offset==0);++music_calls;
}
static void update_loading(void *bar,int progress,int maximum) {
    stage="loading-screen";(void)bar;++screen_calls;assert(progress==-1 && maximum==1);
    assert(!!animwalks==(phase==0?expected_early:phase==1));
}
static void load_levelorder(void){}
static void load_script_setting(void){}
static void load_scripts(void) {
    stage="scripts";++script_calls;assert(phase==0);
    assert(!!animwalks==expected_early);
    assert(max_walks==(expected_early?5:MAX_WALKS));
}
typedef struct {int unused;} s_model;
static s_model *getFirstModel(void){return NULL;}
static void free_model(s_model *model){(void)model;abort();}
static void freesprites(void){}
static void load_special_sounds(void){}
static void load_special_sprites(void){}
static char *fixture_strncat(char *out,const char *in,size_t length) {
    return strncat(out,in,length);
}
#define strncat fixture_strncat
#define printf silent_printf
@RESET@
@BUILD@
@STANDALONE@
@LOADER@
@FREE_MODELS@
@CLEANUP@
static void start_selected(void){@STARTUP@}
#undef printf
static void check_vectors(int absent) {
    int *actual[14],lengths[14];@NATIVE_VECTORS@
    int base[14]={@DEFAULT_LENGTHS@};
    int seed=expected_early?0:(custom?3:0)+phase;
    int count[14]={2+seed,3+seed,4+seed,5+seed,6+seed,9+seed,7+seed,8+seed};
    for(int a=8;a<14;++a)count[a]=13+seed+expected_special>expected_base?
        13+seed+expected_special:expected_base;
    int next=MAX_ANIS;
    for(int a=0;a<14;++a){
        assert(lengths[a]==count[a]);
        if(absent){assert(!actual[a]);continue;}
        assert(actual[a]);
        for(int i=0;i<base[a];++i)assert(actual[a][i]==expected_initial[a][i]);
        for(int i=base[a];i<count[a];++i)assert(actual[a][i]==next++);
    }
    if(!absent)assert(max_animations==next);
}
static void check(int use_custom) {
    obor_profile_build=revision;phase=0;custom=use_custom;
    file_calls=script_calls=cache_calls=music_calls=screen_calls=diagnostics=0;
    obor_reset_model_constants();custModels=custom?(char*)"alternate.txt":NULL;
    custBkgrds=custom?(char*)"fixtures/":NULL;loadingbg[0].set=custom?3:0;
    start_selected();stage="cold-vectors";check_vectors(0);++cases;
    assert(file_calls==(expected_early?2u:1u) && script_calls==1 && !diagnostics);
    assert(!strcmp(files[0],expected_early || !custom?"data/models.txt":"data/alternate.txt"));
    if(expected_early)assert(!strcmp(files[1],custom?"data/alternate.txt":"data/models.txt"));
    int *saved_walks=animwalks;
    phase=1;load_models();stage="direct-reload";check_vectors(0);++cases;
    if(expected_early)assert(animwalks==saved_walks);
    phase=2;resourceCleanUp();stage="cleanup-reload";check_vectors(expected_early);++cases;
    assert(file_calls==(expected_early?4u:3u));
    assert(script_calls==1 && cache_calls==6 && music_calls==3 && screen_calls==3 && !diagnostics);
    obor_reset_model_constants();
}
int main(void){@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;}
'''.replace('@DEFINITIONS@', '\n'.join(definitions)).replace('@ENUM@', enum).replace(
        '@FACTS@', '\n'.join(copies)).replace('@LOOKUP@', '\n'.join(
            'if(!strcmp(name,%s))return %s;' % (json.dumps(name.removeprefix('CMD_MODELSTXT_').lower()), name)
            for name in re.findall(r'\bCMD_MODELSTXT_\w+', enum) if name != 'CMD_MODELSTXT_THE_END')).replace(
        '@RESET@', reset).replace('@BUILD@', build).replace('@STANDALONE@', standalone).replace(
        '@LOADER@', loader).replace('@FREE_MODELS@', function(source, 'free_models')).replace(
        '@CLEANUP@', function(source, 'resourceCleanUp')).replace('@STARTUP@', startup).replace(
        '@NATIVE_VECTORS@', native_vectors).replace('@DEFAULT_LENGTHS@', ','.join(defaults)).replace(
        '@CHECKS@', '\n'.join(checks))
