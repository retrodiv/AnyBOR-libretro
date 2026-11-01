/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "openborscript.h"
#include "ImportCache.h"
#undef printf
#undef assert
#define assert(value) do {if(!(value)){fprintf(stderr,"clear contract revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#value);abort();}}while(0)
uint32_t obor_profile_build;
Script *pcurrentscript;
s_variantnode **global_var_list;
int max_script_vars=2,max_global_vars=32,max_global_var_index=-1,no_cmd_compatible;
List theFunctionList;
char packfile[4096]="authored";
void Script_Local_Clear(void);
static int expected_mode,callbacks,kill_context,trace_at;
static Script *expected_script;
static entity pool[3];
static entity *entries[3];
entity **ent_list=entries,*textbox,*smartbomber;
int ent_max,ent_count;
unsigned int time;
static char trace[32];
static void mark(char event){assert(trace_at+1<(int)sizeof(trace));trace[trace_at++]=event;trace[trace_at]=0;}
void writeToLogFile(const char *format,...){va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);}
void borShutdown(int status,char *format,...){(void)status;(void)format;abort();}
void exitIfFalse(int value,const char *condition,const char *function_name,const char *file,int line){
 if(!value){fprintf(stderr,"native assertion %s %s %s:%d\n",condition,function_name,file,line);abort();}
}
void abortIfFalse(int value,const char *condition,const char *function_name,const char *file,int line){exitIfFalse(value,condition,function_name,file,line);}
int openpackfile(const char *name,const char *pak){(void)name;(void)pak;abort();}
int readpackfile(int handle,void *buffer,int bytes){(void)handle;(void)buffer;(void)bytes;abort();}
int seekpackfile(int handle,int offset,int whence){(void)handle;(void)offset;(void)whence;abort();}
int closepackfile(int handle){(void)handle;abort();}
ImportNode *ImportCache_Retrieve(const char *path){(void)path;abort();}
void ImportCache_Release(ImportNode *node){(void)node;abort();}
Instruction *ImportList_GetFunctionPointer(List *list,const char *name){(void)name;assert(list && !list->size);return NULL;}
void execute_onkill_script(entity *e){
 assert(e->exists && kill_context);expected_script=e->scripts.think_script;mark('O');
}
@BODIES@
/* Scope the error contract to its actual entry reset and pointer resolution.
 * Complete rejected-compiler allocation cleanup is a separate investigation. */
static void rejected_entries(Interpreter *pinterpreter){
 @FAILURE_ENTRIES@
 @RESOLVE_ENTRIES@
}
static HRESULT record_clear(ScriptVariant **args,ScriptVariant **result,int count){
 assert(count==1 && args[0]->vt==VT_INTEGER && args[0]->lVal==expected_mode);
 assert(pcurrentscript && pcurrentscript==expected_script && pcurrentscript->initialized && pcurrentscript->vars);
 assert(pcurrentscript->pinterpreter && pcurrentscript->obor_interpreter);
 if(kill_context){assert(expected_mode==1);mark('C');}
 callbacks++;ScriptVariant_ChangeType(*result,VT_INTEGER);(*result)->lVal=0;return S_OK;
}
static void initialize(Script *s,int with_callback){
 if(!s->vars)Script_Init(s,NULL,1);
 Script_Init(s,"clear contract",0);
 char text_with[]="int pad(int x){return x+1;} void clear(){record_clear(getlocalvar(\"localclear\"));} void main(){int x=pad(2);}";
 char text_without[]="void main(){int x=3;}";
 assert(Script_AppendText(s,with_callback?text_with:text_without,"authored.c"));
 assert(SUCCEEDED(Interpreter_CompileInstructions(s->pinterpreter,NULL)));
 assert(s->pinterpreter->pMainEntry);
 assert((s->pinterpreter->pClearEntry!=NULL)==(with_callback && obor_profile_build>=3430));
 if(s->pinterpreter->pClearEntry){
  assert(s->pinterpreter->pClearEntry>=s->pinterpreter->instructionStorage);
  assert(s->pinterpreter->pClearEntry<s->pinterpreter->instructionStorage+s->pinterpreter->theInstructionList.size);
 }
}
static void check_local_storage(int retained){
 for(int indexed=0;indexed<2;indexed++){
  Script a={0},b={0};ScriptVariant locals[2],incoming={0};
  memset(locals,0,sizeof(locals));
  a.initialized=b.initialized=1;a.vars=indexed?locals:NULL;
  Script *owners[]={&a,&b,NULL,&a,&a,&a};s_variantnode *original[6];
  int capacity=max_global_vars;max_global_vars=6;max_global_var_index=5;
  for(int i=0;i<6;i++){
   original[i]=global_var_list[i];original[i]->owner=owners[i];
   original[i]->key=malloc(16);assert(original[i]->key);
   snprintf(original[i]->key,16,"k%d",i);
   ScriptVariant_ChangeType(&original[i]->value,i&1?VT_STR:VT_INTEGER);
   if(i&1)strcpy(StrCache_Get(original[i]->value.strVal),"stored");
   else original[i]->value.lVal=10+i;
  }
  for(int i=0;i<2;i++){
   ScriptVariant_ChangeType(locals+i,i?VT_STR:VT_INTEGER);
   if(i)strcpy(StrCache_Get(locals[i].strVal),"indexed");else locals[i].lVal=7;
  }
  pcurrentscript=NULL;Script_Local_Clear();
  assert(max_global_var_index==5 && locals[0].vt==VT_INTEGER && locals[1].vt==VT_STR);
  pcurrentscript=&a;Script_Local_Clear();
  assert(max_global_var_index==(retained?5:3));
  int old_order[]={5,1,2,4,3,0};
  for(int i=0;i<6;i++){
   assert(global_var_list[i]==original[retained?i:old_order[i]]);
   assert(original[i]->owner==owners[i]);
   char key[16];snprintf(key,sizeof(key),"k%d",i);assert(!strcmp(original[i]->key,key));
   if(retained && owners[i]==&a)assert(original[i]->value.vt==VT_EMPTY);
   else if(i&1)assert(original[i]->value.vt==VT_STR && !strcmp(StrCache_Get(original[i]->value.strVal),"stored"));
   else assert(original[i]->value.vt==VT_INTEGER && original[i]->value.lVal==10+i);
  }
  for(int i=0;i<2;i++)assert(locals[i].vt==(indexed?VT_EMPTY:i?VT_STR:VT_INTEGER));
  ScriptVariant *found=Script_Get_Local_Variant("k0");
  assert(retained?(found==&original[0]->value && found->vt==VT_EMPTY):found==NULL);
  found=Script_Get_Local_Variant("k5");assert(found==&original[5]->value);
  assert(found->vt==(retained?VT_EMPTY:VT_STR));
  ScriptVariant_ChangeType(&incoming,VT_INTEGER);incoming.lVal=64;
  assert(_set_var("new",&incoming,&a)==!retained);
  assert(max_global_var_index==(retained?5:4));
  found=Script_Get_Local_Variant("new");
  assert(retained?found==NULL:(found && found->vt==VT_INTEGER && found->lVal==64));
  incoming.lVal=99;assert(_set_var("k0",&incoming,&a));
  assert(max_global_var_index==5);found=Script_Get_Local_Variant("k0");
  assert(found && found->vt==VT_INTEGER && found->lVal==99);
  assert(original[2]->owner==NULL && original[2]->value.lVal==12);
  pcurrentscript=NULL;
  for(int i=0;i<max_global_vars;i++){
   ScriptVariant_Clear(&global_var_list[i]->value);free(global_var_list[i]->key);
   global_var_list[i]->key=NULL;global_var_list[i]->owner=NULL;
  }
  for(int i=0;i<2;i++)ScriptVariant_Clear(locals+i);
  ScriptVariant_Clear(&incoming);max_global_vars=capacity;max_global_var_index=-1;
 }
}
static void check(unsigned revision,int has_clear,int kills_clear,int local_retention){
 obor_profile_build=revision;
 global_var_list=calloc((size_t)max_global_vars,sizeof(*global_var_list));assert(global_var_list);
 for(int i=0;i<max_global_vars;i++){global_var_list[i]=calloc(1,sizeof(**global_var_list));assert(global_var_list[i]);}
 check_local_storage(local_retention);
 List_Init(&theFunctionList);
 List_InsertAfter(&theFunctionList,(void*)record_clear,"record_clear");
 List_InsertAfter(&theFunctionList,(void*)system_getlocalvar,"getlocalvar");
 for(int mode=0;mode<=2;mode++)for(int present=0;present<2;present++)for(int completed=0;completed<2;completed++){
  Script s={0},sentinel={0};initialize(&s,present);
  callbacks=0;expected_mode=mode;expected_script=&s;
  s.pinterpreter->bCallCompleted=completed;
  ScriptVariant *vars=s.vars;pcurrentscript=&sentinel;
  Script_Clear(&s,mode);
  assert(pcurrentscript==&sentinel && callbacks==(has_clear && present && !completed));
  assert(!s.initialized && !s.pinterpreter && !s.obor_interpreter);
  assert(s.vars==(mode==2?NULL:vars));
  Script_Clear(&s,2);assert(!s.vars);pcurrentscript=NULL;
 }
 for(int parent_first=0;parent_first<2;parent_first++){
  Script owner={0},child={0},sentinel={0};initialize(&owner,1);Script_Init(&child,NULL,1);
  Script_Copy(&child,&owner,0);assert(child.pinterpreter==owner.pinterpreter);
  expected_mode=1;callbacks=0;pcurrentscript=&sentinel;
  Script *first=parent_first?&owner:&child,*second=parent_first?&child:&owner;
  expected_script=first;Script_Clear(first,1);
  assert(second->initialized && second->pinterpreter && callbacks==has_clear);
  /* The first call sets the shared VM completion flag. The original clear
   * caller does not reset it; the second callback is therefore skipped. */
  expected_script=second;Script_Clear(second,1);assert(callbacks==has_clear);
  assert(pcurrentscript==&sentinel);Script_Clear(&owner,2);Script_Clear(&child,2);pcurrentscript=NULL;
 }
 {Interpreter rejected={0};rejected.mainEntryIndex=3;rejected.clearEntryIndex=2;
  rejected_entries(&rejected);assert(!rejected.pMainEntry && !rejected.pClearEntry);}
 memset(pool,0,sizeof(pool));ent_max=3;ent_count=2;time=77;textbox=smartbomber=&pool[0];
 for(int i=0;i<3;i++){
  entries[i]=pool+i;pool[i].exists=i!=1;alloc_all_scripts(&pool[i].scripts);
  initialize(pool[i].scripts.think_script,1);
 }
 trace_at=callbacks=0;trace[0]=0;kill_context=1;expected_mode=1;
 Script sentinel={0};pcurrentscript=&sentinel;kill_all();kill_context=0;
 assert(!strcmp(trace,kills_clear?"OCOC":"OO"));
 assert(callbacks==(kills_clear?2:0));assert(pcurrentscript==&sentinel);
 assert(!ent_max && !ent_count && !time && !textbox && !smartbomber);
 for(int i=0;i<3;i++){
  assert(!pool[i].exists);
  assert(pool[i].scripts.think_script->initialized==!(kills_clear && i!=1));
  expected_mode=2;expected_script=pool[i].scripts.think_script;
  clear_all_scripts(&pool[i].scripts,2);free_all_scripts(&pool[i].scripts);
 }
 pcurrentscript=NULL;List_Clear(&theFunctionList);
 for(int i=0;i<max_global_vars;i++){ScriptVariant_Clear(&global_var_list[i]->value);free(global_var_list[i]->key);free(global_var_list[i]);}
 free(global_var_list);global_var_list=NULL;max_global_var_index=-1;StrCache_Clear();
}
int main(void){@CHECKS@puts("early_script_clear=1");return 0;}
