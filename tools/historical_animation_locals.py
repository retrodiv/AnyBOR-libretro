"""Render scalar local-store and complete animation-callback contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_animation_locals(engine, fixture):
    model = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    gc = function(script, '_gc_var').replace('void _gc_var()', 'void native_gc_var()', 1)
    save = function(script, 'Script_Save_Local_Variant').replace(
        'Script_Save_Local_Variant(', 'native_save(', 1)
    load = function(script, 'Script_Load_Local_Variant').replace(
        'Script_Load_Local_Variant(', 'native_load(', 1)
    bodies = '\n'.join(function(script, name) for name in (
        '_set_var', 'Script_Set_Global_Variant', 'Script_Get_Local_Variant',
        'Script_Set_Local_Variant', 'Script_IsInitialized'))
    checks = []
    for row in fixture['sources']:
        checks.append('revision=%d;obor_profile_build=revision;requires_init=%d;'
                      'has_snapshot=%d;has_rebind=%d;auto_gc=%d;'
                      'nested_option=%d;cmd_option=%d;run();' % (
                          row['revision'], row['setter_requires_initialized_owner'],
                          row['animation_saves_local_context'], row['animation_rebinds_current_model'],
                          row['setter_collects_at_capacity'], row['nested_option_registered'],
                          row['cmd_option_registered']))
    settings = function(model, 'load_script_setting')
    branches = []
    for name in ('nonestedscript', 'nocmdcompatible'):
        match = re.search(r'else if\(stricmp\(command,\s*"' + name + r'"\)==0\)', settings)
        if match is None:
            raise ValueError('Missing script-setting branch: ' + name)
        first = settings.index('{', match.end())
        end, depth = first + 1, 1
        while depth:
            depth += (settings[end] == '{') - (settings[end] == '}')
            end += 1
        branches.append(settings[match.start():end])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#ifndef PROBE_FOCUS
#define PROBE_FOCUS 0
#endif
typedef void VOID;
typedef long LONG;
enum {VT_EMPTY,VT_INTEGER,VT_PTR};
typedef struct {int vt;union {LONG lVal;VOID *ptrVal;};} ScriptVariant;
typedef struct {int bReset,code;} Interpreter;
typedef struct Script {int initialized;Interpreter *pinterpreter;} Script;
typedef struct {char *key;Script *owner;ScriptVariant value;} s_variantnode;
typedef struct {Script *animation_script;} s_scripts;
typedef struct {s_scripts *scripts;} s_model;
typedef struct {int index;} Animation;
typedef struct entity {s_scripts *scripts;s_model *model,*defaultmodel;Animation *animation;int animnum,animpos;} entity;
static unsigned revision,cases;
static uint32_t obor_profile_build;
static int requires_init,has_snapshot,has_rebind,auto_gc;
static int nested_option,cmd_option,no_nested_script,no_cmd_compatible,setting_value,setting_reads;
static const char *stage="setup";
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"animation locals profile=%u stage=%s line=%d\n",revision,stage,__LINE__);abort();}}while(0)
static s_variantnode nodes[64],*node_pointers[64],**global_var_list=node_pointers;
static int max_global_var_index,max_global_vars;
static unsigned gc_calls,save_calls,load_calls;
static int gc_entry_index,events[16],event_count;
static ScriptVariant seen[2][4];
static int seen_code[2],executions;
static const char *names[]={"self","animnum","frame","animhandle"};
static int get_setting_argument(int index){assert(index==1);++setting_reads;return setting_value;}
#define GET_INT_ARG(i) get_setting_argument(i)
#define stricmp strcasecmp
static void configure(char *command){if(0){}@SETTINGS@}
#undef stricmp
static void ScriptVariant_Init(ScriptVariant *v){memset(v,0,sizeof(*v));}
static void ScriptVariant_Clear(ScriptVariant *v){memset(v,0,sizeof(*v));}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){memset(v,0,sizeof(*v));v->vt=type;}
static void ScriptVariant_Copy(ScriptVariant *to,ScriptVariant *from){*to=*from;}
static void event(int code){assert(event_count<16);events[event_count++]=code;}
@GC@
static void _gc_var(void){++gc_calls;gc_entry_index=max_global_var_index;native_gc_var();}
@BODIES@
@SAVE@
@LOAD@
static int Script_Save_Local_Variant(Script *owner,char *list[]){
    ++save_calls;event(20);
    for(int i=0;i<4;++i)assert(!strcmp(list[i],names[i]));
    assert(!list[4][0]);return native_save(owner,list);
}
static void Script_Load_Local_Variant(Script *owner,int handle){++load_calls;event(21);native_load(owner,handle);}
static void Script_Copy(Script *to,Script *from,int clear){
    assert(to && from && from->initialized && from->pinterpreter && !clear);
    event(from->pinterpreter->code);to->initialized=from->initialized;to->pinterpreter=from->pinterpreter;
}
static void Script_Execute(Script *owner){
    assert(owner->initialized && owner->pinterpreter && executions<2);
    int code=owner->pinterpreter->code;event(10+code);seen_code[executions]=code;
    for(int i=0;i<4;++i){
        ScriptVariant *v=Script_Get_Local_Variant(owner,(char*)names[i]);
        if(v)seen[executions][i]=*v;else ScriptVariant_Init(&seen[executions][i]);
        ScriptVariant changed={.vt=VT_INTEGER,.lVal=200+10*code+i};
        assert(Script_Set_Local_Variant(owner,(char*)names[i],&changed));
    }
    ++executions;
}
@EXECUTE@
static void reset_table(int capacity){
    for(int i=0;i<64;++i){
        free(nodes[i].key);memset(&nodes[i],0,sizeof(nodes[i]));
        nodes[i].key=calloc(1,1);assert(nodes[i].key);node_pointers[i]=nodes+i;
    }
    max_global_var_index=-1;max_global_vars=capacity;
    gc_calls=save_calls=load_calls=0;gc_entry_index=-1;event_count=executions=0;
    memset(seen,0,sizeof(seen));memset(seen_code,0,sizeof(seen_code));
}
static ScriptVariant *raw_local(Script *owner,const char *name){
    for(int i=0;i<=max_global_var_index;++i)
        if(global_var_list[i]->owner==owner && !strcmp(global_var_list[i]->key,name))return &global_var_list[i]->value;
    return NULL;
}
static void integer_is(ScriptVariant *v,int value){assert(v && v->vt==VT_INTEGER && v->lVal==value);}
static void check_owner(void){
    stage="owner";reset_table(64);Script owner={.initialized=1};
    ScriptVariant value={.vt=VT_INTEGER,.lVal=10},empty={0};
    assert(Script_Set_Local_Variant(&owner,"owned",&value));
    owner.initialized=0;value.lVal=20;
    assert(Script_Set_Local_Variant(&owner,"owned",&value)==!requires_init);
    integer_is(raw_local(&owner,"owned"),requires_init?10:20);
    assert(!Script_Get_Local_Variant(&owner,"owned"));
    assert(Script_Set_Local_Variant(&owner,"new",&value)==!requires_init);
    assert(!!raw_local(&owner,"new")==!requires_init);
    assert(Script_Set_Local_Variant(&owner,"owned",&empty)==!requires_init);
    assert(!!raw_local(&owner,"owned")==requires_init);
    assert(Script_Set_Global_Variant("global",&value));integer_is(raw_local(NULL,"global"),20);
    assert(!Script_Set_Local_Variant(NULL,"x",&value));
    assert(!_set_var(NULL,&value,NULL) && !_set_var("",&value,NULL));
    /* Internal context labels have no real Script metadata to validate. */
    assert(_set_var("context",&value,(Script*)(intptr_t)1));
    integer_is(raw_local((Script*)(intptr_t)1,"context"),20);++cases;
}
static void check_capacity(void){
    stage="capacity";reset_table(4);ScriptVariant value={.vt=VT_INTEGER,.lVal=1};
    assert(_set_var("a",&value,NULL) && _set_var("b",&value,NULL) && _set_var("c",&value,NULL));
    ScriptVariant_Clear(raw_local(NULL,"b"));
    assert(_set_var("d",&value,NULL));
    assert(gc_calls==(unsigned)auto_gc && gc_entry_index==(auto_gc?3:-1));
    assert(max_global_var_index==(auto_gc?2:3));
    integer_is(raw_local(NULL,"a"),1);integer_is(raw_local(NULL,"c"),1);integer_is(raw_local(NULL,"d"),1);
    assert(_set_var("e",&value,NULL)==auto_gc);
    assert(gc_calls==(auto_gc?2u:0u) && max_global_var_index==3);
    unsigned collected=gc_calls;assert(!_set_var("refused",&value,NULL));assert(gc_calls==collected);
    ScriptVariant_Clear(raw_local(NULL,"a"));
    assert(!_set_var("still-refused",&value,NULL));assert(gc_calls==collected && max_global_var_index==3);
    value.lVal=7;assert(_set_var("c",&value,NULL));assert(gc_calls==collected);
    integer_is(raw_local(NULL,"c"),7);
    ScriptVariant empty={0};assert(_set_var("d",&empty,NULL));assert(max_global_var_index==2);
    assert(gc_calls==collected && !raw_local(NULL,"d"));++cases;
}
static void check_settings(void){
    stage="settings";
    char *queries[]={"nonestedscript","nocmdcompatible","unknown-setting"};
    for(int query=0;query<3;++query)for(int value=0;value<3;++value){
        no_nested_script=no_cmd_compatible=setting_reads=0;setting_value=value;
        configure(queries[query]);
        assert(no_nested_script==(query==0 && nested_option?value:0));
        assert(no_cmd_compatible==(query==1 && cmd_option?value:0));
        assert(setting_reads==(query==0?nested_option:query==1?cmd_option:0));++cases;
    }
}
static void check_animation(int same,int current_on,int default_on,int initialized,int interpreter_state,int initial_locals){
    stage="animation";reset_table(64);
    Interpreter current_code={.code=1},default_code={.code=2},local_code={.code=9,.bReset=interpreter_state==2};
    Script current={.initialized=current_on,.pinterpreter=&current_code};
    Script fallback={.initialized=default_on,.pinterpreter=&default_code};
    Script local={.initialized=1,.pinterpreter=interpreter_state?&local_code:NULL};
    s_scripts current_scripts={&current},fallback_scripts={&fallback},local_scripts={&local};
    s_model current_model={&current_scripts},fallback_model={&fallback_scripts};
    Animation animation={19};
    entity ent={.scripts=&local_scripts,.model=&current_model,
        .defaultmodel=same?&current_model:&fallback_model,.animation=&animation,.animnum=7,.animpos=3};
    if(initial_locals)for(int i=0;i<4;++i){
        ScriptVariant value={.vt=VT_INTEGER,.lVal=100+i};
        assert(Script_Set_Local_Variant(&local,(char*)names[i],&value));
    }
    local.initialized=initialized;
    int active=current_on || default_on;
    int snapshot=active && has_snapshot && interpreter_state==2;
    execute_animation_script(&ent);
    int expected_trace[16],count=0;
    if(snapshot)expected_trace[count++]=20;
    if(current_on){expected_trace[count++]=1;expected_trace[count++]=11;}
    if(!same && default_on){expected_trace[count++]=2;expected_trace[count++]=12;}
    if(active && has_rebind && current_on)expected_trace[count++]=1;
    if(snapshot)expected_trace[count++]=21;
    assert(count==event_count && !memcmp(expected_trace,events,(size_t)count*sizeof(int)));
    assert(executions==current_on+(!same && default_on));
    assert(save_calls==(unsigned)snapshot && load_calls==save_calls && !gc_calls);
    for(int call=0;call<executions;++call){
        int code=call==0?(current_on?1:2):2;assert(seen_code[call]==code);
        for(int i=0;i<4;++i){ScriptVariant *v=&seen[call][i];
            if(call){integer_is(v,210+i);}
            else if(initialized || !requires_init){
                if(i==0)assert(v->vt==VT_PTR && v->ptrVal==&ent);
                else integer_is(v,i==1?7:i==2?3:19);
            }else if(initial_locals){integer_is(v,100+i);}
            else assert(v->vt==VT_EMPTY);
        }
    }
    for(int i=0;i<4;++i){
        ScriptVariant *v=raw_local(&local,names[i]);
        int retained=initial_locals && (!active || (snapshot && initialized));
        if(retained)integer_is(v,100+i);else assert(!v);
    }
    if(active){
        assert(local.initialized);
        int final_code=current_on && (has_rebind || same || !default_on)?1:2;
        assert(local.pinterpreter->code==final_code);
    }else assert(local.initialized==initialized && local.pinterpreter==(interpreter_state?&local_code:NULL));
    ++cases;
}
static void run(void){
    if(PROBE_FOCUS==0 || PROBE_FOCUS==4)check_settings();
    if(PROBE_FOCUS==0 || PROBE_FOCUS==1)check_owner();
    if(PROBE_FOCUS==0 || PROBE_FOCUS==2)check_capacity();
    if(PROBE_FOCUS==0 || PROBE_FOCUS==3)
        for(int same=0;same<2;++same)for(int a=0;a<2;++a)for(int b=0;b<2;++b){
            if(same && a!=b)continue;
            for(int init=0;init<2;++init)for(int interp=0;interp<3;++interp)
                for(int locals=0;locals<2;++locals)check_animation(same,a,b,init,interp,locals);
        }
}
int main(void){
    @CHECKS@
    for(int i=0;i<64;++i)free(nodes[i].key);
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@GC@', gc).replace('@BODIES@', bodies).replace('@SAVE@', save).replace(
        '@LOAD@', load).replace('@EXECUTE@', function(model, 'execute_animation_script')).replace(
        '@CHECKS@', '\n'.join(checks)).replace('@SETTINGS@', '\n'.join(branches))
