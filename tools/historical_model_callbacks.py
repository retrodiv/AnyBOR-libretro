"""Render model callback loading, unknown-command handling and dispatch.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_modelcopy_callback(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    header = (engine / 'source/gamelib/commands.h').read_text()
    enum = re.search(r'typedef enum modelCommand\s*\{.*?\}\s*modelCommands;', header, re.S)[0]
    registry = function(commands, 'createModelCommandList')
    command_id = re.search(r'LIST_ADD\((\w+),\s*"onmodelcopyscript"\)', registry)[1]
    loader = function(source, 'load_cached_model')
    first = loader.index('cmd = getModelCommand(modelcmdlist, command);')
    lookup = loader[first:loader.index('switch(cmd)', first)]
    first = loader.index('case CMD_MODEL_ONMODELCOPYSCRIPT:')
    case = loader[first:loader.index('case CMD_MODEL_ANIMATIONSCRIPT:', first)]
    first = loader.rindex('\n\t\t\t\tdefault:')
    default = loader[first:loader.index('\n\t\t\t}', first)]
    switch = function(source, 'set_model_ex')
    condition = re.search(r'if\(([^\n]+Script_IsInitialized\(ent->scripts->onmodelcopy_script\))\)', switch)[1]
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (
        row['revision'], row['modelcopy_available']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#define stricmp strcasecmp
@ENUM@
_Static_assert(CMD_MODEL_ONMODELCOPYSCRIPT!=0 && CMD_MODEL_ONMODELCOPYSCRIPT!=CMD_MODEL_SYNC,"separate consumer gates");
static uint32_t obor_profile_build;
static unsigned cases,loads,compiles,inits,includes,warnings,executions,writes;
static int word,initial,ready,error_status;
static char message[256];
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"model callback profile=%u word=%d initial=%d ready=%d line=%d\n",obor_profile_build,word,initial,ready,__LINE__);abort();}}while(0)
typedef struct {int unused;} List;
typedef struct {const char *name;void *value;} Node;
typedef struct {char *args[2];} ArgList;
static List model_commands,*modelcmdlist=&model_commands;
static Node registration={"onmodelcopyscript",(void*)(intptr_t)@COMMAND_ID@};
static void lc(char *text,size_t size){for(size_t i=0;i<size;++i)
    if(text[i]>='A' && text[i]<='Z')text[i]+='a'-'A';}
static Node *List_GetNodeByName(List *list,char *name){
    assert(list==modelcmdlist);return !strcmp(name,registration.name)?&registration:NULL;
}
@GETTERS@
static modelCommands selected_command(char *command){modelCommands cmd;@LOOKUP@return cmd;}
typedef struct Entity Entity;
typedef struct {int initialized;Entity *self,*old;} Script;
typedef struct {Script *onmodelcopy_script;} Scripts;
typedef struct {Scripts *scripts;} Model;
struct Entity {Scripts *scripts;int marker;};
typedef Entity entity;
typedef void VOID;
enum {VT_EMPTY,VT_PTR=5};
typedef struct {int vt;void *ptrVal;} ScriptVariant;
static Script callback;
static Scripts scripts={&callback};
static Model model={&scripts};
static Entity live={&scripts,222},prior={&scripts,111};
static int Script_IsInitialized(Script *s){assert(s==&callback);return s->initialized;}
static void Script_Init(Script *s,char *name,char *filename,int first){
    assert(s==&callback && !strcmp(name,"onmodelcopyscript") && !strcmp(filename,"model.test") && !first);
    ++inits;s->initialized=1;
}
static int load_script(Script *s,char *path){assert(s==&callback && !strcmp(path,"body.c"));++loads;return 1;}
static int Script_AppendText(Script *s,char *text,char *filename){
    (void)s;(void)text;(void)filename;abort();
}
static int Script_Compile(Script *s){assert(s==&callback && s->initialized);++compiles;return 1;}
static void ScriptVariant_Init(ScriptVariant *v){*v=(ScriptVariant){0};}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){v->vt=type;}
static void ScriptVariant_Clear(ScriptVariant *v){*v=(ScriptVariant){0};}
static void Script_Set_Local_Variant(Script *s,char *name,ScriptVariant *v){
    assert(s==&callback);++writes;
    if(!strcmp(name,"self"))s->self=v->vt==VT_PTR?v->ptrVal:NULL;
    else {assert(!strcmp(name,"old"));s->old=v->vt==VT_PTR?v->ptrVal:NULL;}
}
static void Script_Execute(Script *s){
    assert(s==&callback && s->self==&live && s->old==&prior);
    assert(s->self->marker==222 && s->old->marker==111);++executions;
}
static void shutdown(int status,char *format,...){(void)format;error_status=status;assert(0);}
static int buffer_pakfile(char *path,char **out,size_t *size){
    (void)path;(void)out;(void)size;assert(0);return 0;
}
#define GET_ARGP(i) (arglist->args[(i)])
#define GET_INT_ARGP(i) atoi(GET_ARGP(i))
@SCRIPT_LOADER@
@INCLUDE_BODY@
static int handle_txt_include(char *command,ArgList *args,char **filename,char *name,char **buffer,ptrdiff_t *pos,size_t *size){
    ++includes;return native_handle_txt_include(command,args,filename,name,buffer,pos,size);
}
static int tracked_printf(const char *format,...){
    ++warnings;va_list args;va_start(args,format);int n=vsnprintf(message,sizeof(message),format,args);va_end(args);return n;
}
#define printf tracked_printf
static void parse(char *command){
    Model *newchar=&model;ArgList arglist={{command,"body.c"}};
    char *filename="model.test",namebuf[32]={0},line[]="onmodelcopyscript body.c";
    char *buf=line;ptrdiff_t pos=0;size_t size=sizeof(line)-1;
    char *fnbuf=namebuf;modelCommands cmd=selected_command(command);
    switch(cmd){@CASE@@DEFAULT@}
}
#undef printf
@CALLBACK@
static void dispatch(Entity *ent,Entity *before){if(@CONDITION@)execute_onmodelcopy_script(ent,before);}
static void check(int available){
    const char *words[]={"onmodelcopyscript","ONMODELCOPYSCRIPT","OnModelCopyScript","unknown",""};
    for(word=0;word<5;++word)for(initial=0;initial<2;++initial)for(ready=0;ready<2;++ready){
        char command[64];strcpy(command,words[word]);callback=(Script){.initialized=initial};
        loads=compiles=inits=includes=warnings=executions=writes=0;error_status=0;message[0]=0;
        parse(command);unsigned loaded=available && word<3;
        assert(inits==loaded && loads==loaded && compiles==loaded && !error_status);
        assert(callback.initialized==(loaded?1:initial));
        assert(includes==(unsigned)(!loaded && word<4));assert(warnings==includes);
        if(warnings){char expected[256];
            snprintf(expected,sizeof(expected),"Command '%s' not understood in file '%s'!\n",command,"model.test");
            assert(!strcmp(message,expected));}
        callback.initialized=ready;dispatch(&live,&prior);
        unsigned invoked=available && ready;
        assert(executions==invoked && writes==4*invoked && !callback.self && !callback.old);++cases;
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@ENUM@', enum).replace('@COMMAND_ID@', command_id).replace('@GETTERS@', '\n'.join(
        function(commands, name) for name in ('getCommandlistCommand', 'getModelCommand'))).replace(
        '@LOOKUP@', lookup).replace('@SCRIPT_LOADER@', '\n'.join(function(source, name) for name in
            ('obor_extract_inline_script', 'lcmHandleCommandScripts'))).replace(
        '@INCLUDE_BODY@', function(source, 'handle_txt_include').replace(
            'handle_txt_include(', 'native_handle_txt_include(', 1)).replace('@CASE@', case).replace(
        '@DEFAULT@', default).replace('@CALLBACK@', function(source, 'execute_onmodelcopy_script')).replace(
        '@CONDITION@', condition).replace('@CHECKS@', checks)


def render_inline_script_loading(engine):
    source = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    level = function(source, 'load_level')
    start = level.index('case CMD_LEVEL_AT_SCRIPT:')
    spawn = level[start:level.index('case CMD_LEVEL_AT:', start)]
    loader = '\n'.join(function(source, name) for name in
                       ('obor_extract_inline_script', 'lcmHandleCommandScripts', 'lcmHandleLevelCommandScripts'))
    variables = '\n'.join(function(script, name) for name in
                          ('Script_ResetVariables', 'openbor_getscriptvar', 'openbor_setscriptvar'))
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define stricmp strcasecmp
#define GET_ARGP(index) (arglist->value)
#define FAILED(result) ((result) < 0)
#define script_magic 0x73636f
static uint32_t obor_profile_build;
static int max_script_vars = 2;
typedef struct { char *value; } ArgList;
typedef int HRESULT;
typedef long LONG;
enum { S_OK = 0, E_FAIL = -1, VT_EMPTY = 0, VT_INTEGER = 1 };
typedef struct { int vt; LONG lVal; } ScriptVariant;
typedef struct {
    int magic;
    ScriptVariant *vars;
    unsigned initialized, appended, loaded, compiled;
} Script;
static Script *pcurrentscript;
enum { CMD_LEVEL_AT_SCRIPT = 1 };

static void ScriptVariant_Clear(ScriptVariant *var) { *var = (ScriptVariant){0}; }
static void ScriptVariant_Init(ScriptVariant *var) { ScriptVariant_Clear(var); }
static void ScriptVariant_ChangeType(ScriptVariant *var, int type) { var->vt = type; }
static void ScriptVariant_Copy(ScriptVariant *to, ScriptVariant *from) { *to = *from; }
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *var, LONG *value)
{
    assert(var->vt == VT_INTEGER);
    *value = var->lVal;
    return S_OK;
}

static int Script_IsInitialized(Script *script) { return script->initialized != 0; }
static void Script_Init(Script *script, char *name, char *file, int first)
{
    assert(name && file && first == 0);
    ++script->initialized;
}
static int Script_AppendText(Script *script, char *body, char *file)
{
    assert(script->initialized && file && !strcmp(body, "\nvoid main() {}\n"));
    ++script->appended;
    return 1;
}
static int load_script(Script *script, char *path)
{
    assert(script->initialized && (!strcmp(path, "entry.c") || !strcmp(path, "@script")));
    ++script->loaded;
    return 1;
}
static void Script_Compile(Script *script) { ++script->compiled; }
static void shutdown(int code, const char *message, ...)
{
    (void)code;
    (void)message;
    abort();
}

@VARIABLES@
@LOADER@

static size_t read_spawn(char *buf, size_t size, Script *output)
{
    size_t pos = 0;
    char *scriptbuf = NULL, *filename = "level.txt";
    const char *errormessage = NULL;
    struct { Script spawnscript; } next = {*output};
    switch(CMD_LEVEL_AT_SCRIPT)
    {
        @SPAWN@
    }
    *output = next.spawnscript;
    return pos;
lCleanup:
    assert(errormessage);
    free(scriptbuf);
    abort();
}

static void check_script_variables(Script *script, int available)
{
    ScriptVariant index = {VT_INTEGER, 1}, value = {VT_INTEGER, 37}, output = {0};
    ScriptVariant *args[] = {&index, &value}, *result = &output;
    pcurrentscript = script;
    assert(openbor_getscriptvar(args, &result, 1) == (available ? S_OK : E_FAIL));
    if(available)
    {
        assert(result == &output && output.vt == VT_EMPTY && script->magic == script_magic);
        assert(openbor_setscriptvar(args, &result, 2) == S_OK && output.lVal == 1);
        assert(openbor_getscriptvar(args, &result, 1) == S_OK && output.lVal == 37);
    }
    else
    {
        assert(!result && !script->vars);
        result = &output;
        assert(openbor_setscriptvar(args, &result, 2) == E_FAIL && !result);
    }
}

int main(void)
{
    char text[] = "entity @script\nvoid main() {}\n@end_script\n0123456789 next";
    const size_t end = sizeof("entity @script\nvoid main() {}\n@end_script") - 1;
    const unsigned builds[] = {3879, 3880, 3887, 3888, 3893, 3894, 3896};
    const unsigned inline_model[] = {0, 1, 1, 1, 1, 1, 1};
    const size_t spawn_gap[] = {0, 11, 11, 0, 0, 0, 0};
    const int level_variables[] = {0, 0, 0, 0, 0, 1, 1};
    char *body = NULL;
    size_t consumed = 0;
    assert(!obor_extract_inline_script("@script\n", 8, &body, &consumed));
    assert(!body && !consumed);
    for(size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        Script model = {0}, spawn = {0};
        ArgList file = {"entry.c"}, inline_source = {"@script"};
        assert(lcmHandleCommandScripts(&file, text, sizeof(text)-1, &model, "model", "model.txt", 1) == 0);
        assert(model.initialized == 1 && model.loaded == 1 && model.compiled == 1 && !model.appended);
        assert(lcmHandleCommandScripts(&inline_source, text, sizeof(text)-1, &model, "model", "model.txt", 0)
               == inline_model[i] * end);
        assert(model.initialized == 2 && model.loaded == 2 - inline_model[i] && model.compiled == 1);
        assert(model.appended == inline_model[i]);
        assert(read_spawn(text, sizeof(text)-1, &spawn) == end + spawn_gap[i]);
        assert(read_spawn(text, end+2, &spawn) == end + (spawn_gap[i] ? 2 : 0));
        assert(spawn.initialized == 1 && spawn.appended == 2 && !spawn.compiled);
        check_script_variables(&model, 0);
        check_script_variables(&spawn, 0);
        if(inline_model[i])
        {
            Script level = {0}, named_spawn = {0};
            assert(lcmHandleLevelCommandScripts(&file, text, sizeof(text)-1, &level,
                                               "level", "level.txt", 1) == 0);
            assert(level.compiled == 1 && level.loaded == 1);
            check_script_variables(&level, level_variables[i]);
            assert(lcmHandleLevelCommandScripts(&inline_source, text, sizeof(text)-1, &level,
                                               "level", "level.txt", 1) == end);
            assert(level.compiled == 2 && level.appended == 1);
            check_script_variables(&level, level_variables[i]);
            assert(lcmHandleLevelCommandScripts(&file, text, sizeof(text)-1, &named_spawn,
                                               "spawn", "level.txt", 0) == 0);
            assert(named_spawn.loaded == 1 && !named_spawn.compiled);
            check_script_variables(&named_spawn, level_variables[i]);
            free(level.vars);
            free(named_spawn.vars);
        }
    }
    return 0;
}
'''.replace('@VARIABLES@', variables).replace('@LOADER@', loader).replace('@SPAWN@', spawn)
