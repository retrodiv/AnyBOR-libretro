"""Render bounded model-cache queries against own-source selector facts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_model_selectors(engine, fixture):
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    header = (engine / 'source/scriptlib/ScriptVariant.h').read_text()
    types = re.search(r'typedef enum VariantType[\s\S]+?\}ScriptVariant;', header)[0]
    bodies = '\n'.join(function(variant, name) for name in (
        'ScriptVariant_Init', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue'))
    bodies += function((engine / 'openbor.c').read_text(), 'get_cached_model_index')
    bodies += '\n#define printf probe_printf\n'
    bodies += '\n'.join(function(source, name) for name in (
        'openbor_getmodelproperty', 'openbor_changemodelproperty'))
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (
        row['revision'], row['name_lookup_selector']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
typedef int32_t LONG,HRESULT;
typedef void VOID;
typedef double DOUBLE;
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define stricmp strcasecmp
@TYPES@
_Static_assert(sizeof(LONG)==sizeof(int),"legacy selector members share signed32 width");
static uint32_t obor_profile_build;
static unsigned cases,diagnostics;
static int selector_mode,property,operation;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"model selector profile=%u selector=%d property=%d operation=%d line=%d\n",obor_profile_build,selector_mode,property,operation,__LINE__);abort();}}while(0)
static char strings[64][128];
static char *StrCache_Get(int i){assert(i>=0 && i<64);return strings[i];}
static int StrCache_Pop(void){return 63;}
static void StrCache_Collect(int i){assert(i>=0 && i<64);}
static int probe_printf(const char *format,...){(void)format;++diagnostics;return 0;}
static struct {int loadflag;void *model;char name[16],path[32];int selectable;} model_cache[3];
static int models_cached=3;
@BODIES@
#undef printf
static void setup(void){
    const char *names[]={"alpha","beta","gamma"};
    const char *paths[]={"data/a.txt","data/b.txt","data/c.txt"};
    for(int i=0;i<3;++i){model_cache[i].loadflag=10+i;model_cache[i].model=&model_cache[i];
        strcpy(model_cache[i].name,names[i]);strcpy(model_cache[i].path,paths[i]);
        model_cache[i].selectable=20+i;}
    strcpy(strings[0],"gamma");strcpy(strings[1],"alpha");strcpy(strings[2],"BETA");
    strcpy(strings[3],"missing");diagnostics=0;
}
static void check(int names){
    const int named_index[]={2,0,1};
    for(selector_mode=0;selector_mode<6;++selector_mode){
        int slot=selector_mode%3,index=selector_mode<3 || !names?slot:named_index[slot];
        for(property=0;property<6;++property){
            for(operation=0;operation<3;++operation){
                setup();ScriptVariant selector,prop,value,result;
                ScriptVariant_Init(&selector);ScriptVariant_Init(&prop);
                ScriptVariant_Init(&value);ScriptVariant_Init(&result);
                selector.vt=selector_mode<3?VT_INTEGER:VT_STR;selector.lVal=slot;
                prop.vt=VT_INTEGER;prop.lVal=property;
                value.vt=operation==2?VT_STR:VT_INTEGER;value.lVal=operation==2?0:71;
                result.vt=VT_INTEGER;result.lVal=777;
                ScriptVariant *args[]={&selector,&prop,&value},*out=&result;
                HRESULT status=operation?openbor_changemodelproperty(args,&out,3):
                                         openbor_getmodelproperty(args,&out,2);
                assert(status==S_OK && out==&result);
                assert(diagnostics==(unsigned)(selector_mode>=3 && !names));
                if(!operation){
                    if(property==0)assert(result.vt==VT_INTEGER && result.lVal==10+index);
                    else if(property==1 || property==2)assert(result.vt==VT_STR &&
                        !strcmp(StrCache_Get(result.strVal),model_cache[index].name));
                    else if(property==3)assert(result.vt==VT_STR &&
                        !strcmp(StrCache_Get(result.strVal),model_cache[index].path));
                    else assert(result.vt==VT_INTEGER && result.lVal==(property==4?20+index:777));
                }else{
                    assert(result.vt==VT_INTEGER && result.lVal==
                        (operation==2 && property<5?0:777));
                    for(int i=0;i<3;++i)assert(model_cache[i].selectable==
                        (operation==1 && property<5 && i==index?71:20+i));
                }
                ++cases;
            }
        }
    }
    /* Defined candidate refusal for indices absent from the original table. */
    for(operation=0;operation<2;++operation){
        for(int i=0;i<3;++i){
            setup();ScriptVariant sel={.lVal=i==0?-1:3,.vt=i==2?VT_STR:VT_INTEGER};
            ScriptVariant prop={.lVal=4,.vt=VT_INTEGER},value={.lVal=71,.vt=VT_INTEGER};
            ScriptVariant result={.lVal=777,.vt=VT_INTEGER},*out=&result;
            ScriptVariant *args[]={&sel,&prop,&value};
            assert((operation?openbor_changemodelproperty(args,&out,3):
                              openbor_getmodelproperty(args,&out,2))==E_FAIL);
            assert(result.vt==VT_INTEGER && result.lVal==777);
            for(int j=0;j<3;++j)assert(model_cache[j].selectable==20+j);
            ++cases;
        }
        for(int count=0;count<2;++count){
            ScriptVariant result={.lVal=777,.vt=VT_INTEGER},*out=&result;
            assert((operation?openbor_changemodelproperty(NULL,&out,count):
                              openbor_getmodelproperty(NULL,&out,count))==E_FAIL);
            assert(out==NULL);++cases;
        }
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@TYPES@', types).replace('@BODIES@', bodies).replace('@CHECKS@', checks)


def render_playable_reset(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    game = function(source, 'playgame')
    prefix = game[game.index('memset(player,'):game.index('if((useSavedGame')]
    calls = [line for line in prefix.splitlines() if 'reset_playable_list(1);' in line]
    if len(calls) != 1:
        raise ValueError('Exactly one saved-game playable reset call required')
    player_type = re.search(r'(?m)^#define\s+TYPE_PLAYER\s+[^\n]+', header)[0]
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (
        row['revision'], row['saved_game_resets_playable']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
@PLAYER_TYPE@
static uint32_t obor_profile_build;
static unsigned cases;
static int restored,flag,seed;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"playable reset profile=%u restored=%d flag=%d seed=%d line=%d\n",obor_profile_build,restored,flag,seed,__LINE__);abort();}}while(0)
typedef struct {unsigned type;} Model;
static Model models[2]={{TYPE_PLAYER},{0}};
static struct {Model *model;int selectable;} model_cache[3];
static int models_cached=3;
@RESET@
static void saved_prefix(void){if(restored && flag){if(flag==2){@CALL@}}}
static void setup(int value){
    for(int i=0;i<3;++i){model_cache[i].model=i<2?&models[i]:NULL;
        model_cache[i].selectable=value+i;}
}
static void check(int resets){
    const int seeds[]={-1,0,7};
    for(restored=0;restored<2;++restored)for(flag=0;flag<3;++flag)
    for(seed=0;seed<3;++seed){
        setup(seeds[seed]);saved_prefix();
        assert(model_cache[0].selectable==(resets && restored && flag==2?1:seeds[seed]));
        assert(model_cache[1].selectable==seeds[seed]+1);
        assert(model_cache[2].selectable==seeds[seed]+2);++cases;
    }
    for(int which=0;which<2;++which){
        setup(7);reset_playable_list((char)which);
        assert(model_cache[0].selectable==which);
        assert(model_cache[1].selectable==(which?8:0));
        assert(model_cache[2].selectable==(which?9:0));++cases;
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@PLAYER_TYPE@', player_type).replace('@RESET@', function(source, 'reset_playable_list')).replace(
        '@CALL@', calls[0]).replace('@CHECKS@', checks)
