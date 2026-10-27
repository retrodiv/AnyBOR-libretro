/* Complete native import/VM fixture with authored in-memory script files.
 * Allocation tracking models the engine arena's final retirement. Individual
 * native releases remain checked; final arena retirement is a separate step.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <ctype.h>
#include <setjmp.h>
#include "Interpreter.h"
#include "ImportCache.h"
#include "packfile.h"
#include "libretroport.h"
#undef printf
#undef assert
#undef malloc
#undef calloc
#undef realloc
#undef strdup
#undef free

uint32_t obor_profile_build;
List theFunctionList;
extern List imports;
char packfile[OBOR_CONTENT_PATH_MAX]="fixture.pak";
static unsigned scenario,marker_calls,other_calls,opens;
static char messages[8192];
static jmp_buf refusal_jump;
static int expected_refusal,refusals;
#define assert(c) do {if(!(c)){fprintf(stderr,"Imports revision=%u scenario=%u line=%d: %s\n%s\n",obor_profile_build,scenario,__LINE__,#c,messages);abort();}}while(0)
static struct {void *pointer;size_t bytes;int live;} allocations[32768];
static unsigned allocation_count;
static int fail_next_owned_allocation;
static int allocation_index(void *pointer) {
 for(unsigned i=0;i<allocation_count;++i)
  if(allocations[i].pointer==pointer && allocations[i].live)return (int)i;
 return -1;
}
static void record(void *pointer,size_t bytes) {
 if(!pointer)return;
 assert(allocation_count<sizeof(allocations)/sizeof(*allocations));
 allocations[allocation_count].pointer=pointer;allocations[allocation_count].bytes=bytes;
 allocations[allocation_count++].live=1;
}
void *fixture_malloc(size_t bytes) {
 if(fail_next_owned_allocation){fail_next_owned_allocation=0;return NULL;}
 void *p=malloc(bytes);record(p,bytes);return p;
}
void *fixture_calloc(size_t count,size_t bytes) {
 assert(!count || bytes<=SIZE_MAX/count);void *p=calloc(count,bytes);record(p,count*bytes);return p;
}
void fixture_free(void *pointer) {
 if(!pointer)return;
 int index=allocation_index(pointer);assert(index>=0);allocations[index].live=0;free(pointer);
}
void *fixture_realloc(void *pointer,size_t bytes) {
 if(!pointer)return fixture_malloc(bytes);
 if(!bytes){fixture_free(pointer);return NULL;}
 int index=allocation_index(pointer);assert(index>=0);
 void *p=realloc(pointer,bytes);
 if(p){allocations[index].pointer=p;allocations[index].bytes=bytes;}
 return p;
}
char *fixture_strdup(const char *text) {
 size_t bytes=strlen(text)+1;char *p=fixture_malloc(bytes);if(p)memcpy(p,text,bytes);return p;
}
static unsigned retire_arena(void) {
 unsigned retained=0;
 for(unsigned i=0;i<allocation_count;++i)if(allocations[i].live) {
  free(allocations[i].pointer);allocations[i].live=0;++retained;
 }
 return retained;
}
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line) {
 if(!value && expected_refusal && !strcmp(function,"ImportCache_ImportFile") &&
    !strcmp(condition,"strlen(path) <= 255")) {++refusals;longjmp(refusal_jump,1);}
 if(!value){fprintf(stderr,"%s:%d %s: %s\n",file,line,function,condition);abort();}
}
void abortIfFalse(int value,const char *condition,const char *function,const char *file,int line) {
 exitIfFalse(value,condition,function,file,line);
}
void writeToLogFile(const char *format,...) {
 size_t used=strlen(messages);if(used>=sizeof(messages)-1)return;
 va_list args;va_start(args,format);vsnprintf(messages+used,sizeof(messages)-used,format,args);va_end(args);
}
void shutdown(int status,char *format,...) {(void)status;(void)format;abort();}
static HRESULT marker(ScriptVariant **args,ScriptVariant **result,int count) {
 (void)args;assert(count==0);++marker_calls;if(*result)ScriptVariant_Clear(*result);return S_OK;
}
static HRESULT other(ScriptVariant **args,ScriptVariant **result,int count) {
 (void)args;assert(count==0);++other_calls;if(*result)ScriptVariant_Clear(*result);return S_OK;
}
static int observed_count,observed_type;
static LONG observed_integer;
static DOUBLE observed_decimal;
static char observed_text[256];
static int trace_constants;
static struct {int type;LONG integer;DOUBLE decimal;char text[64];} constant_trace[8];
static HRESULT observe(ScriptVariant **args,ScriptVariant **result,int count) {
 assert(count==1 && args && args[0]);++observed_count;observed_type=args[0]->vt;
 if(observed_type==VT_INTEGER)observed_integer=args[0]->lVal;
 if(observed_type==VT_DECIMAL)observed_decimal=args[0]->dblVal;
 if(observed_type==VT_STR)snprintf(observed_text,sizeof(observed_text),"%s",StrCache_Get(args[0]->strVal));
 if(trace_constants){
  assert(observed_count<=8);unsigned i=(unsigned)observed_count-1;
  constant_trace[i].type=observed_type;constant_trace[i].integer=observed_integer;
  constant_trace[i].decimal=observed_decimal;
  if(observed_type==VT_STR){assert(strlen(observed_text)<64);strcpy(constant_trace[i].text,observed_text);}
 }
 if(*result)ScriptVariant_Clear(*result);return S_OK;
}
static Interpreter *call_context;
static Instruction *reentry_target;
static unsigned native_depth;
static HRESULT reject_call(ScriptVariant **args,ScriptVariant **result,int count) {
 (void)args;(void)result;assert(count==0);return E_FAIL;
}
static HRESULT reenter_call(ScriptVariant **args,ScriptVariant **result,int count) {
 (void)args;assert(count==0 && call_context && reentry_target);
 Instruction *outer=call_context->pCurrentInstruction;
 assert(call_context->pCurrentCall==outer);++native_depth;
 call_context->pCurrentInstruction=reentry_target;
 HRESULT status=Interpreter_Call(call_context);
 assert(call_context->pCurrentCall==outer);call_context->pCurrentInstruction=outer;
 if(*result)ScriptVariant_Clear(*result);return status;
}
typedef struct { Interpreter *pinterpreter; } ProbeScript;
void mapstrings_playerproperty(ScriptVariant **args,int count);
static int disable_mapping;
static HRESULT mapped_property(ScriptVariant **args,ScriptVariant **result,int count) {
 assert(count==2 && args && args[0] && args[1]);
 mapstrings_playerproperty(args,count);
 assert(args[1]->vt==VT_INTEGER);
 ScriptVariant_Copy(*result,args[1]);return S_OK;
}
static void *Script_GetStringMapFunction(void *function) {
 return !disable_mapping && function==(void*)mapped_property?(void*)mapstrings_playerproperty:NULL;
}
static unsigned fixture_rand32(void) { return 17; }
#define Script ProbeScript
#define rand32 fixture_rand32
#include "native_probe_mapper.h"
#undef rand32
#undef Script
static const char *leaf="void imported() { marker(); } void shared() { marker(); }";
static const char *second="void shared() { other(); }";
static const char *collision="void marker() { other(); }";
static const char *parent="#import \"leaf.c\"\nvoid unused() { marker(); }";
static struct {const char *text;size_t at;int active;} handles[16];
int openpackfile(const char *name,const char *package) {
 (void)package;char key[1024];size_t size=strlen(name);assert(size<sizeof(key));
 for(size_t i=0;i<=size;++i)key[i]=name[i]=='\\'?'/':(char)tolower((unsigned char)name[i]);
 ++opens;const char *text=NULL;
 if(strstr(key,"leaf.c") && !strcmp(key+size-6,"leaf.c"))text=leaf;
 else if(!strcmp(key,"second.c"))text=second;
 else if(!strcmp(key,"collision.c"))text=collision;
 else if(!strcmp(key,"parent.c"))text=parent;
 else if(!strcmp(key,"bad.c"))text="void unfinished(";
 if(!text)return -1;
 for(int i=0;i<16;++i)if(!handles[i].active) {
  handles[i].text=text;handles[i].at=0;handles[i].active=1;return i;
 }
 abort();
}
int closepackfile(int handle) {assert(handle>=0 && handle<16 && handles[handle].active);handles[handle].active=0;return 0;}
int seekpackfile(int handle,int offset,int whence) {
 assert(handle>=0 && handle<16 && handles[handle].active);
 size_t size=strlen(handles[handle].text);int at=offset;
 if(whence==SEEK_CUR)at+=(int)handles[handle].at;
 if(whence==SEEK_END)at+=(int)size;
 assert(at>=0 && (size_t)at<=size);handles[handle].at=(size_t)at;return at;
}
int readpackfile(int handle,void *buffer,int count) {
 assert(handle>=0 && handle<16 && handles[handle].active && count>=0);
 size_t available=strlen(handles[handle].text)-handles[handle].at;
 if((size_t)count>available)count=(int)available;
 memcpy(buffer,handles[handle].text+handles[handle].at,(size_t)count);handles[handle].at+=(size_t)count;return count;
}
static void release(ImportNode *node) {
#if PROBE_HAS_LEGACY_RELEASE
 ImportCache_Release(node);
#else
 (void)node;
#endif
}
static HRESULT compile(Interpreter *interpreter,const char *source) {
 char text[2048];assert(strlen(source)<sizeof(text));strcpy(text,source);
 Interpreter_Init(interpreter,"fixture",&theFunctionList);
 HRESULT result=Interpreter_ParseText(interpreter,text,1,"fixture");
 if(SUCCEEDED(result))result=Interpreter_CompileInstructions(interpreter,NULL);
 return result;
}
static void execute(Interpreter *interpreter) {
 Interpreter_Reset(interpreter);assert(SUCCEEDED(Interpreter_EvaluateImmediate(interpreter)));
}
static void clear_cache(void) {ImportCache_Clear();assert(List_GetSize(&imports)==0);messages[0]=0;}
static int finish(void) {
 List_Clear(&theFunctionList);StrCache_Clear();
 for(int i=0;i<16;++i)assert(!handles[i].active);
 unsigned tail=retire_arena();
 printf("{\"status\":\"PASS\",\"scenarios\":%u,\"arena_tail_allocations\":%u}\n",scenario,tail);
 return 0;
}
static void grammar_case(const char *text,int accepted,int kind,LONG integer,
                         DOUBLE decimal,const char *string,unsigned markers) {
 Interpreter interpreter;++scenario;observed_count=0;observed_type=-1;
 marker_calls=other_calls=0;messages[0]=0;observed_text[0]=0;
 HRESULT result=compile(&interpreter,text);
 assert(SUCCEEDED(result)==accepted);
 if(accepted) {
  execute(&interpreter);assert(observed_count==1 && observed_type==kind);
  if(kind==VT_INTEGER)assert(observed_integer==integer);
  if(kind==VT_DECIMAL)assert(!memcmp(&observed_decimal,&decimal,sizeof(decimal)));
  if(kind==VT_STR)assert(string && !strcmp(string,observed_text));
  assert(marker_calls==markers && !other_calls);
 }
 Interpreter_Clear(&interpreter);clear_cache();
}
static void grammar_identifier_error(const char *text) {
 Interpreter interpreter;++scenario;messages[0]=0;
 assert(FAILED(compile(&interpreter,text)));
 assert(strstr(messages,obor_profile_build<3810?"Identifier expected '7'.":"Identifier expected before '7'."));
 Interpreter_Clear(&interpreter);clear_cache();
}
static int grammar(void) {
 grammar_identifier_error("void 7;");
 grammar_identifier_error("void main(){int 7;}");
 grammar_case("void main(){observe(2+3*4);}",1,VT_INTEGER,14,0,NULL,0);
 grammar_case("int f(int x){return x+1;} void main(){observe(f(4)+f(6));}",1,VT_INTEGER,12,0,NULL,0);
 grammar_case("void main(){int a=3;observe(a=7);if(a==7)marker();}",1,VT_INTEGER,obor_profile_build<3818?3:7,0,NULL,1);
 grammar_case("void main(){int a=3;a+=4;observe(a);}",1,VT_INTEGER,7,0,NULL,0);
 grammar_case("void main(){int n=0;int i=0;for(i=0;i<4;i++){if(i==1)continue;n+=i;}observe(n);}",1,VT_INTEGER,5,0,NULL,0);
 grammar_case("void main(){int result=3;{int a=6;result+=a;}observe(result);}",1,VT_INTEGER,9,0,NULL,0);
 grammar_case("void main(){int sum=0;int i=0;int j=0;for(i=0;i<3;i++){j=0;while(j<3){j++;if(j==2)continue;if(i==1)break;sum++;}}observe(sum);}",1,VT_INTEGER,4,0,NULL,0);
 grammar_case("int f(){int i=0;do{i++;if(i==2)break;}while(i<4);return i;}void main(){observe(f());}",1,VT_INTEGER,2,0,NULL,0);
 grammar_case("void main(){int r=0;switch(2){case 1:r=1;break;case 2:r=7;break;default:r=9;}observe(r);}",obor_profile_build>=3810,VT_INTEGER,7,0,NULL,0);
 grammar_case("void main(){int r=0;switch(1){case 1:r=3;case 2:r+=4;break;default:r=9;}observe(r);}",obor_profile_build>=3810,VT_INTEGER,7,0,NULL,0);
 grammar_case("void main(){int r=0;switch(\"b\"){case \"a\":r=1;break;case \"b\":r=7;break;default:r=9;}observe(r);}",obor_profile_build>=3812,VT_INTEGER,7,0,NULL,0);
 grammar_case("void main(){int a=0;observe(1?7:(a=9));if(a==0)marker();}",obor_profile_build>=3816,VT_INTEGER,7,0,NULL,1);
 grammar_case("void main(){observe(16>>2);}",obor_profile_build>=3833,VT_INTEGER,4,0,NULL,0);
 grammar_case("void main(){observe(1+2<<2);}",obor_profile_build>=3833,VT_INTEGER,12,0,NULL,0);
 grammar_case("void main(){observe(5|2);}",obor_profile_build>=3839,VT_INTEGER,7,0,NULL,0);
 grammar_case("void main(){observe(5&3);}",obor_profile_build>=3839,VT_INTEGER,1,0,NULL,0);
 grammar_case("void main(){observe(5^3);}",obor_profile_build>=3839,VT_INTEGER,6,0,NULL,0);
 DOUBLE negative=-0.1;
 if(obor_profile_build>=3828 && obor_profile_build<3831) {
  LONG low;memcpy(&low,&negative,sizeof(low));low=-low;memcpy(&negative,&low,sizeof(low));
 }
 grammar_case("void main(){observe(-0.1);}",1,VT_DECIMAL,0,negative,NULL,0);
 grammar_case("void main(){observe(-\"abc\");}",obor_profile_build<3831,obor_profile_build<3828?VT_EMPTY:VT_STR,0,0,"abc",0);
 grammar_case("void main(){observe(!\"abc\");}",1,obor_profile_build<3831?VT_INTEGER:VT_STR,0,0,"!abc",0);
 grammar_case("void main(){observe(!0);}",1,VT_INTEGER,1,0,NULL,0);
 grammar_case("void main(){observe(- - 2);}",1,VT_INTEGER,2,0,NULL,0);
 grammar_case("void main(){int a=1;a;observe(a);}",1,VT_INTEGER,1,0,NULL,0);
 grammar_case("void main(){observe(!1.25);}",1,obor_profile_build<3831?VT_INTEGER:VT_DECIMAL,0,0,NULL,0);
 return finish();
}
static Instruction *native_call(Interpreter *interpreter,SCRIPTFUNCTION function) {
 for(int i=0;i<interpreter->theInstructionList.size;++i) {
  Instruction *instruction=&interpreter->instructionStorage[i];
  if(instruction->OpCode==CALL && instruction->jumpTargetType==INSTRUCTION_TARGET_FUNCTION &&
     instruction->functionRef==function)return instruction;
 }
 assert(0);return NULL;
}
static void alias_case(const char *text,int literal,int expected_type,LONG value,const char *string) {
 Interpreter interpreter;++scenario;observed_count=0;observed_type=-1;observed_text[0]=0;
 assert(SUCCEEDED(compile(&interpreter,text)));
 Instruction *call=native_call(&interpreter,mapped_property);
 ScriptVariant **args=Instruction_CallReferenceValues(call);
 assert(Instruction_CallReferenceCount(call)==2);
 if(literal)assert(args[1]->vt==VT_STR);
 ProbeScript script={&interpreter};assert(Script_MapStringConstants(&script));
 if(literal)assert(args[1]->vt==VT_INTEGER && args[1]->lVal==value);
 execute(&interpreter);
 assert(observed_count==1 && observed_type==expected_type);
 if(expected_type==VT_INTEGER)assert(observed_integer==value);
 if(expected_type==VT_STR)assert(string && !strcmp(observed_text,string));
 Interpreter_Clear(&interpreter);clear_cache();
}
static int aliases(int weapon,int name) {
 alias_case("void main(){observe(property(0,\"weapon\"));}",1,VT_INTEGER,weapon,NULL);
 alias_case("void main(){observe(property(0,\"NaMe\"));}",1,VT_INTEGER,name,NULL);
 alias_case("void main(){observe(property(0,9));}",0,VT_INTEGER,9,NULL);
 alias_case("void main(){void p=\"weapon\";observe(property(0,p));}",0,VT_INTEGER,weapon,NULL);
 alias_case("void main(){observe(property(0,\"wea\"+\"pon\"));}",0,VT_INTEGER,weapon,NULL);
 alias_case("void main(){int i=0;int n=0;for(i=0;i<3;i++)n+=property(0,\"weapon\");observe(n);}",0,VT_INTEGER,3*weapon,NULL);
 alias_case("void main(){void text=\"weapon\";property(0,\"weapon\");observe(text);}",1,VT_STR,weapon,"weapon");
 alias_case("void main(){void text=\"weapon\";property(0,text);observe(text);}",0,VT_STR,0,"weapon");
 alias_case("int f(void p){return property(0,p);}void main(){observe(f(\"weapon\")+f(\"name\"));}",0,VT_INTEGER,weapon+name,NULL);
 alias_case("void main(){int i=0;int n=0;while(i<4){i++;if(i==2)continue;n+=property(0,\"weapon\");if(i==3)break;}observe(n);}",0,VT_INTEGER,2*weapon,NULL);
 return finish();
}
static void diagnostic_case(const char *text,int call_code,int argument_code,int call_count,int wrong_count) {
 Interpreter interpreter;++scenario;messages[0]=0;observed_count=0;
 assert(SUCCEEDED(compile(&interpreter,text)));
 Interpreter_Reset(&interpreter);assert(FAILED(Interpreter_EvaluateImmediate(&interpreter)));
 assert(!observed_count);
 char expected[64];snprintf(expected,sizeof(expected),"\nOpCode: %d\n",call_code);
 unsigned count=0;const char *at=messages;
 while((at=strstr(at,expected))){++count;at+=strlen(expected);}
 assert(count==(obor_profile_build<3831?(unsigned)call_count:0));
 snprintf(expected,sizeof(expected),"\nOpCode: %d\n",argument_code);
 assert((strstr(messages,expected)!=NULL)==(wrong_count && obor_profile_build<3831));
 /* The native message prints the declaration's expected count. */
 assert((strstr(messages,"argument count(1)")!=NULL)==wrong_count);
 Interpreter_Clear(&interpreter);clear_cache();
}
static int diagnostics(int call_code,int argument_code) {
 diagnostic_case("void main(){reject();observe(1);}",call_code,argument_code,1,0);
 diagnostic_case("int f(int a){return a;}void main(){observe(f());}",call_code,argument_code,1,1);
 diagnostic_case("int f(){reject();return 7;}void main(){observe(f());}",call_code,argument_code,2,0);
 diagnostic_case("void main(){if(0)observe(1);else reject();observe(2);}",call_code,argument_code,1,0);
 return finish();
}
static int opcode_numbers(const char *values) {
#if PROBE_HAS_OPCODE_DISPLAY
 const char *at=values;char *end;
 for(int i=0;i<=OPCODE_END;++i){
  ++scenario;LONG expected=strtol(at,&end,10);assert(end!=at);
  assert(obor_profile_opcode((OpCode)i)==expected);
  if(i<OPCODE_END){assert(*end==',');at=end+1;}else assert(!*end);
 }
 ++scenario;assert(obor_profile_opcode((OpCode)-1)==-1);
 ++scenario;assert(obor_profile_opcode((OpCode)(OPCODE_END+1))==-1);
 return finish();
#else
 (void)values;assert(0);return 1;
#endif
}
static void constant_case(const char *text,int accepted,int type,LONG integer,DOUBLE decimal,const char *string) {
 Interpreter interpreter;++scenario;messages[0]=0;
 assert(SUCCEEDED(compile(&interpreter,text))==accepted);
 if(accepted)for(int run=0;run<2;++run){
  observed_count=0;trace_constants=1;execute(&interpreter);trace_constants=0;
  if(observed_count!=3){fprintf(stderr,"constant refresh profile=%u scenario=%u count=%d\n",obor_profile_build,scenario,observed_count);abort();}
  for(unsigned i=0;i<3;++i){
   int valid=constant_trace[i].type==type;
   if(type==VT_INTEGER)valid=valid && constant_trace[i].integer==integer;
   if(type==VT_DECIMAL)valid=valid && !memcmp(&constant_trace[i].decimal,&decimal,sizeof(decimal));
   if(type==VT_STR)valid=valid && string && !strcmp(constant_trace[i].text,string);
   if(!valid){fprintf(stderr,"constant refresh profile=%u scenario=%u sample=%u\n",obor_profile_build,scenario,i);abort();}
  }
 }
 Interpreter_Clear(&interpreter);clear_cache();
}
static int constants(void) {
 constant_case("void main(){int i=0;for(i=0;i<3;i++)observe(-2);}",1,VT_INTEGER,-2,0,NULL);
 constant_case("void main(){int i=0;for(i=0;i<3;i++)observe(!0);}",1,VT_INTEGER,1,0,NULL);
 constant_case("void main(){int i=0;for(i=0;i<3;i++)observe(- - 2);}",1,VT_INTEGER,2,0,NULL);
 DOUBLE negative=-0.1;
 if(obor_profile_build>=3828 && obor_profile_build<3831){
  LONG low;memcpy(&low,&negative,sizeof(low));low=-low;memcpy(&negative,&low,sizeof(low));
 }
 constant_case("void main(){int i=0;for(i=0;i<3;i++)observe(-0.1);}",1,VT_DECIMAL,0,negative,NULL);
 constant_case("void main(){int i=0;for(i=0;i<3;i++)observe(!\"abc\");}",1,obor_profile_build<3831?VT_INTEGER:VT_STR,0,0,"!abc");
 constant_case("void main(){int i=0;for(i=0;i<3;i++)observe(-\"abc\");}",obor_profile_build<3831,
               obor_profile_build<3828?VT_EMPTY:VT_STR,0,0,"abc");
#if PROBE_HAS_CONSTANT_REFRESH
 if(obor_profile_build<3831){
  ++scenario;Interpreter interpreter;assert(SUCCEEDED(compile(&interpreter,"void main(){observe(-2);}")));
  Instruction *constant=NULL;
  for(int i=0;i<interpreter.theInstructionList.size;++i)
   if(interpreter.instructionStorage[i].OpCode==CONSTINT){constant=&interpreter.instructionStorage[i];break;}
  assert(constant && !constant->theRef2 && constant->theVal->lVal==2);
  interpreter.pCurrentInstruction=constant;fail_next_owned_allocation=1;
  assert(FAILED(Interpreter_EvalInstruction(&interpreter)));
  assert(!fail_next_owned_allocation && !constant->theRef2 && constant->theVal->lVal==2);
  observed_count=0;execute(&interpreter);
  assert(observed_count==1 && observed_type==VT_INTEGER && observed_integer==-2 && constant->theRef2);
  Interpreter_Clear(&interpreter);clear_cache();
 }
#endif
 return finish();
}
static void call_setup(Interpreter *interpreter,Instruction *current,Instruction *parent,int reset,int complete) {
 Interpreter_Reset(interpreter);interpreter->pCurrentInstruction=current;
 interpreter->pCurrentCall=parent;interpreter->bReset=reset;interpreter->bCallCompleted=complete;
}
static void call_flag(Interpreter *interpreter,int reset) {
 assert(interpreter->bReset==reset);
 assert(interpreter->bCallCompleted==(obor_profile_build<3834?FALSE:!reset));
}
static int call_contracts(void) {
 Interpreter interpreter;
 assert(SUCCEEDED(compile(&interpreter,"int value(){return 7;}void main(){marker();other();value();reject();reenter();}")));
 Instruction *marker_instruction=native_call(&interpreter,marker);
 Instruction *parent_instruction=native_call(&interpreter,other);
 Instruction *reject_instruction=native_call(&interpreter,reject_call);
 Instruction *reenter_instruction=native_call(&interpreter,reenter_call),*user=NULL;
 for(int i=0;i<interpreter.theInstructionList.size;++i) {
  Instruction *instruction=&interpreter.instructionStorage[i];
  if(instruction->OpCode==CALL && instruction->jumpTargetType==INSTRUCTION_TARGET_JUMP) {
   assert(!user);user=instruction;
  }
 }
 assert(user);
 for(int reset=0;reset<2;++reset)for(int completed=0;completed<2;++completed) {
  ++scenario;marker_calls=0;
  call_setup(&interpreter,marker_instruction,parent_instruction,reset,completed);
  assert(SUCCEEDED(Interpreter_Call(&interpreter)) && marker_calls==1);
  assert(interpreter.pCurrentInstruction==marker_instruction && interpreter.pCurrentCall==parent_instruction);
  call_flag(&interpreter,reset);
 }
 for(int reset=0;reset<2;++reset) {
  ++scenario;call_setup(&interpreter,user,parent_instruction,reset,FALSE);
  assert(SUCCEEDED(Interpreter_Call(&interpreter)));
  assert(interpreter.pCurrentInstruction==user && interpreter.pCurrentCall==parent_instruction);
  assert(user->theVal && user->theVal->vt==VT_INTEGER && user->theVal->lVal==7);
  call_flag(&interpreter,reset);
 }
 for(int reset=0;reset<2;++reset)for(int completed=0;completed<2;++completed) {
  ++scenario;Instruction unavailable=*marker_instruction;
  unavailable.jumpTargetType=INSTRUCTION_TARGET_NONE;unavailable.functionRef=NULL;
  call_setup(&interpreter,&unavailable,parent_instruction,reset,completed);
  assert(FAILED(Interpreter_Call(&interpreter)));
  assert(interpreter.pCurrentInstruction==&unavailable && interpreter.pCurrentCall==&unavailable);
  call_flag(&interpreter,reset);
 }
 for(int reset=0;reset<2;++reset)for(int completed=0;completed<2;++completed) {
  ++scenario;call_setup(&interpreter,NULL,parent_instruction,reset,completed);
  assert(FAILED(Interpreter_Call(&interpreter)) && !interpreter.pCurrentInstruction);
  assert(interpreter.pCurrentCall==parent_instruction);call_flag(&interpreter,reset);
 }
 for(int reset=0;reset<2;++reset)for(int completed=0;completed<2;++completed) {
  ++scenario;call_setup(&interpreter,reject_instruction,parent_instruction,reset,completed);
  assert(FAILED(Interpreter_Call(&interpreter)));
  assert(interpreter.pCurrentInstruction==reject_instruction && interpreter.pCurrentCall==parent_instruction);
  call_flag(&interpreter,reset);
 }
 for(int reset=0;reset<2;++reset) {
  ++scenario;native_depth=marker_calls=0;call_context=&interpreter;reentry_target=marker_instruction;
  call_setup(&interpreter,reenter_instruction,parent_instruction,reset,FALSE);
  assert(SUCCEEDED(Interpreter_Call(&interpreter)) && marker_calls==1 && native_depth==1);
  assert(interpreter.pCurrentInstruction==reenter_instruction && interpreter.pCurrentCall==parent_instruction);
  call_flag(&interpreter,reset);
 }
 Interpreter_Reset(&interpreter);Interpreter_Clear(&interpreter);clear_cache();
 ++scenario;assert(SUCCEEDED(compile(&interpreter,"void main(){marker();}")));
 Interpreter_Reset(&interpreter);interpreter.bCallCompleted=FALSE;marker_calls=0;
 assert(SUCCEEDED(Interpreter_EvaluateImmediate(&interpreter)));
 assert(interpreter.bMainCompleted && !interpreter.bCallCompleted && !interpreter.bReset && marker_calls==1);
 assert(SUCCEEDED(Interpreter_EvaluateImmediate(&interpreter)) && marker_calls==1);
 Interpreter_Reset(&interpreter);assert(SUCCEEDED(Interpreter_EvaluateImmediate(&interpreter)) && marker_calls==2);
 Interpreter_Clear(&interpreter);clear_cache();return finish();
}
static int mapper_arguments(unsigned count) {
 assert(count<=64);++scenario;char text[1024]="void main(){observe(rand(";
 for(unsigned i=0;i<count;++i)strcat(text,i?",1":"1");
 strcat(text,"));}");Interpreter interpreter;
 assert(SUCCEEDED(compile(&interpreter,text)));ProbeScript script={&interpreter};
 assert(Script_MapStringConstants(&script));observed_count=0;
 execute(&interpreter);assert(observed_count==1 && observed_type==VT_INTEGER && observed_integer==17);
 Interpreter_Clear(&interpreter);clear_cache();return finish();
}
static int grammar_tables(void) {
 ParserSet set;ParserSet_Buildup(&set);
 printf("{\"first\":[");
 for(int kind=0;kind<2;++kind) {
  if(kind)printf("],\"follow\":[");
  for(int i=0;i<NUMPRODUCTIONS;++i) {
   if(i)printf(",");printf("[");
   MY_TOKEN_TYPE *tokens=kind?set.FollowSet[i]:set.FirstSet[i];
   unsigned count=0;
   while(*tokens!=END_OF_TOKENS) {
    assert(count<=(unsigned)END_OF_TOKENS);if(count++)printf(",");printf("%d",*tokens++);
   }
   printf("]");
  }
 }
 printf("]}\n");List_Clear(&theFunctionList);StrCache_Clear();retire_arena();return 0;
}
int main(int argc,char **argv) {
 assert(argc>=3 && argc<=7);obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);int legacy=atoi(argv[2]);
 List_Init(&theFunctionList);List_InsertAfter(&theFunctionList,(void*)marker,"marker");
 List_InsertAfter(&theFunctionList,(void*)other,"other");
 List_InsertAfter(&theFunctionList,(void*)observe,"observe");
 List_InsertAfter(&theFunctionList,(void*)reject_call,"reject");
 List_InsertAfter(&theFunctionList,(void*)reenter_call,"reenter");
 List_InsertAfter(&theFunctionList,(void*)system_rand,"rand");ImportCache_Init();
 List_InsertAfter(&theFunctionList,(void*)mapped_property,"property");
 if(argc==6 && !strcmp(argv[3],"diagnostics"))return diagnostics(atoi(argv[4]),atoi(argv[5]));
 if(argc>=6){assert(!strcmp(argv[3],"aliases"));
  if(argc==7){assert(!strcmp(argv[6],"nomap"));disable_mapping=1;}
  return aliases(atoi(argv[4]),atoi(argv[5]));}
 if(argc==5 && !strcmp(argv[3],"opcodes"))return opcode_numbers(argv[4]);
 if(argc==5) {assert(!strcmp(argv[3],"mapper"));return mapper_arguments((unsigned)strtoul(argv[4],NULL,10));}
 if(argc==4 && !strcmp(argv[3],"calls"))return call_contracts();
 if(argc==4 && !strcmp(argv[3],"constants"))return constants();
 if(argc==4 && !strcmp(argv[3],"grammar"))return grammar();
 if(argc==4 && !strcmp(argv[3],"tables"))return grammar_tables();
 if(argc==4) {
  assert(!strcmp(argv[3],"precedence"));++scenario;Interpreter interpreter;
  assert(SUCCEEDED(compile(&interpreter,"#import \"collision.c\"\nvoid main() { marker(); }")));
  execute(&interpreter);assert(marker_calls==(unsigned)legacy && other_calls==(unsigned)!legacy);
  Interpreter_Clear(&interpreter);clear_cache();return finish();
 }
 ++scenario;ImportNode *first=ImportCache_ImportFile("Leaf.c");assert(first);
 ImportNode *again=ImportCache_ImportFile("Leaf.c");assert(again==first);
 ImportNode *lower=ImportCache_ImportFile("leaf.c");assert(lower);
 assert((first!=lower)==legacy && opens==(unsigned)(legacy?2:1));
 release(first);assert(List_GetSize(&imports)==(legacy?2:1));
 release(again);assert(List_GetSize(&imports)==1);release(lower);
 assert(List_GetSize(&imports)==(legacy?0:1));
 unsigned before=opens;first=ImportCache_ImportFile("leaf.c");assert(first);
 assert(opens==before+(unsigned)legacy);release(first);clear_cache();
 ++scenario;before=opens;first=ImportCache_ImportFile("dir\\leaf.c");again=ImportCache_ImportFile("dir/leaf.c");
 assert(first && again && (first!=again)==legacy && opens==before+(legacy?2u:1u));
 release(first);release(again);clear_cache();
 ++scenario;before=opens;first=ImportCache_ImportFile("leaf.c");again=ImportCache_ImportFile("parent.c");
 assert(first && again && opens==before+2 && List_GetSize(&imports)==2);
 release(first);assert(List_GetSize(&imports)==2);release(again);
 assert(List_GetSize(&imports)==(legacy?0:2));clear_cache();
 ++scenario;Interpreter a,b;before=opens;
 const char *empty="#import \"leaf.c\"\nvoid main() {}";
 assert(SUCCEEDED(compile(&a,empty)) && SUCCEEDED(compile(&b,empty)) && opens==before+1);
 Interpreter_Clear(&a);assert(List_GetSize(&imports)==1);Interpreter_Clear(&b);
 assert(List_GetSize(&imports)==(legacy?0:1));clear_cache();
 ++scenario;marker_calls=other_calls=0;
 HRESULT result=compile(&a,"#import \"leaf.c\"\nvoid main() { imported(); }");
 assert(SUCCEEDED(result)==!legacy);
 if(!legacy){execute(&a);assert(marker_calls==1 && other_calls==0);}
 Interpreter_Clear(&a);clear_cache();
 ++scenario;marker_calls=other_calls=0;
 assert(SUCCEEDED(compile(&a,"#import \"collision.c\"\nvoid main() { marker(); }")));
 execute(&a);assert(marker_calls==(unsigned)legacy && other_calls==(unsigned)!legacy);
 Interpreter_Clear(&a);clear_cache();
 ++scenario;marker_calls=other_calls=0;
 assert(SUCCEEDED(compile(&a,"#import \"leaf.c\"\nvoid imported() { other(); } void main() { imported(); }")));
 execute(&a);assert(marker_calls==0 && other_calls==1);Interpreter_Clear(&a);clear_cache();
 ++scenario;marker_calls=other_calls=0;
 result=compile(&a,"#import \"leaf.c\"\n#import \"second.c\"\nvoid main() { shared(); }");
 assert(SUCCEEDED(result)==!legacy);
 if(!legacy){execute(&a);assert(marker_calls==0 && other_calls==1);}
 Interpreter_Clear(&a);clear_cache();
 ++scenario;first=ImportCache_ImportFile("missing.c");assert(!first && !List_GetSize(&imports));
 first=ImportCache_ImportFile("bad.c");assert(!first && !List_GetSize(&imports));clear_cache();
 ++scenario;char long_path[300];memset(long_path,'x',sizeof(long_path));strcpy(long_path+sizeof(long_path)-7,"leaf.c");
 if(legacy) {first=ImportCache_ImportFile(long_path);assert(first);release(first);}
 else {
  expected_refusal=1;
  if(!setjmp(refusal_jump)){ImportCache_ImportFile(long_path);assert(0);}
  expected_refusal=0;assert(refusals==1);
 }
 clear_cache();
 ++scenario;first=ImportCache_ImportFile("parent.c");assert(first && List_GetSize(&imports)==2);
 clear_cache();release(first);assert(!List_GetSize(&imports));
 return finish();
}
