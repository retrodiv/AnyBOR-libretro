/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * AnyBOR adaptations: retrodiv <retrodiv@proton.me>
 */
#include "obor_transform_vm.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SOURCE_LIMIT 65536u
#define DEPTH_LIMIT 64u
#define LOOP_JUMPS 128u

typedef struct SourceLocal { char name[64]; unsigned reg; } SourceLocal;
typedef struct SourceLoop {
  struct SourceLoop *parent;
  size_t breaks[LOOP_JUMPS],count,continuation;
} SourceLoop;
typedef struct SourceParser {
  const char *source,*at,*end,*start,*token_end;
  char token[64];
  uint64_t number;
  uint8_t code[OBOR_TRANSFORM_MAX_PROGRAM_BYTES];
  uint8_t parameters[OBOR_TRANSFORM_MAX_PARAMETER_BYTES];
  size_t code_size,parameter_size;
  SourceLocal locals[32];
  unsigned local_count,depth;
  uint32_t used;
  SourceLoop *loop;
  int failed;
  char *error;
  size_t error_size;
} SourceParser;

static int source_fail(SourceParser *p,const char *message){
  if(!p->failed && p->error && p->error_size){
    size_t line=1,column=1;
    for(const char *s=p->source;s<p->start;s++){
      if(*s=='\r' || (*s=='\n' && (s==p->source || s[-1]!='\r'))){ line++; column=1; }
      else if(*s!='\n') column++;
    }
    snprintf(p->error,p->error_size,"line %u, column %u: %s",
             (unsigned)line,(unsigned)column,message);
  }
  p->failed=1; return 0;
}
static int ident_start(unsigned char c){
  return (c>='a' && c<='z') || (c>='A' && c<='Z') || c=='_';
}
static int ident_part(unsigned char c){ return ident_start(c) || (c>='0' && c<='9'); }
static int digit(unsigned char c){
  if(c>='0' && c<='9') return c-'0';
  if(c>='a' && c<='f') return c-'a'+10;
  if(c>='A' && c<='F') return c-'A'+10;
  return -1;
}
static int escaped_byte(SourceParser *p,const char **cursor,const char *end,unsigned *value){
  const char *s=*cursor;
  if(s==end) return source_fail(p,"unfinished literal");
  unsigned c=(unsigned char)*s++;
  if(c=='\\'){
    if(s==end) return source_fail(p,"unfinished escape");
    c=(unsigned char)*s++;
    if(c=='n') c='\n'; else if(c=='r') c='\r'; else if(c=='t') c='\t';
    else if(c=='0') c=0;
    else if(c=='x'){
      if(end-s<2 || digit((unsigned char)s[0])<0 || digit((unsigned char)s[1])<0)
        return source_fail(p,"expected two hexadecimal escape digits");
      c=(unsigned)(digit((unsigned char)s[0])*16+digit((unsigned char)s[1])); s+=2;
    } else if(c!='\\' && c!='\"' && c!='\'') return source_fail(p,"unsupported escape");
  } else if(c<32 || c>126) return source_fail(p,"literal must contain printable ASCII or escapes");
  *cursor=s; *value=c; return 1;
}
static void next(SourceParser *p){
  p->token[0]=0;
  if(p->failed) return;
  for(;;){
    while(p->at<p->end && (*p->at==' ' || *p->at=='\t' || *p->at=='\r' || *p->at=='\n')) p->at++;
    p->start=p->at;
    if(p->end-p->at>=2 && p->at[0]=='/' && p->at[1]=='/'){
      while(p->at<p->end && *p->at!='\n' && *p->at!='\r') p->at++;
    } else if(p->end-p->at>=2 && p->at[0]=='/' && p->at[1]=='*'){
      p->at+=2;
      while(p->end-p->at>=2 && !(p->at[0]=='*' && p->at[1]=='/')) p->at++;
      if(p->end-p->at<2){ source_fail(p,"unfinished comment"); return; }
      p->at+=2;
    } else break;
  }
  if(p->at==p->end){ p->token_end=p->at; return; }
  unsigned char c=(unsigned char)*p->at++;
  if(ident_start(c)){
    while(p->at<p->end && ident_part((unsigned char)*p->at)) p->at++;
    size_t n=(size_t)(p->at-p->start);
    if(n>=sizeof p->token){ source_fail(p,"identifier too long"); return; }
    memcpy(p->token,p->start,n); p->token[n]=0;
  } else if(c>='0' && c<='9'){
    unsigned base=10; const char *s=p->start;
    if(p->end-s>=2 && s[0]=='0' && (s[1]=='x' || s[1]=='X')){ base=16; s+=2; }
    else if(c=='0' && p->at<p->end && *p->at>='0' && *p->at<='9'){
      source_fail(p,"octal literals are not supported"); return;
    }
    const char *first=s; uint64_t value=0;
    while(s<p->end && digit((unsigned char)*s)>=0 && (unsigned)digit((unsigned char)*s)<base){
      unsigned v=(unsigned)digit((unsigned char)*s++);
      if(value>(UINT64_MAX-v)/base){ source_fail(p,"integer literal exceeds uint64_t"); return; }
      value=value*base+v;
    }
    if(s==first || (s<p->end && ident_part((unsigned char)*s))){ source_fail(p,"invalid integer literal"); return; }
    p->at=s; p->number=value; strcpy(p->token,"$number");
  } else if(c=='\'' || c=='\"'){
    const char *s=p->at; unsigned value=0; size_t count=0;
    while(s<p->end && *s!=c){ if(!escaped_byte(p,&s,p->end,&value)) return; count++; }
    if(s==p->end || (c=='\'' && count!=1)){ source_fail(p,"invalid or unfinished literal"); return; }
    p->at=s+1; p->number=value; strcpy(p->token,c=='\''?"$number":"$string");
  } else {
    p->token[0]=(char)c; p->token[1]=0;
    if(p->at<p->end){
      char pair[3]={(char)c,*p->at,0};
      if(!strcmp(pair,"==") || !strcmp(pair,"!=") || !strcmp(pair,"<=") || !strcmp(pair,">=") ||
         !strcmp(pair,"<<") || !strcmp(pair,">>") || !strcmp(pair,"&&") || !strcmp(pair,"||") ||
         !strcmp(pair,"++") || !strcmp(pair,"--") ||
         (*p->at=='=' && strchr("+-*/%&|^",c))){ strcpy(p->token,pair); p->at++; }
    }
    if(!strchr("{}();,+-*/%&|^~!=<>",c)){ source_fail(p,"unsupported source character"); return; }
  }
  p->token_end=p->at;
}
static int is(SourceParser *p,const char *token){ return !strcmp(p->token,token); }
static int take(SourceParser *p,const char *token){ if(!is(p,token)) return 0; next(p); return 1; }
static int expect(SourceParser *p,const char *token){
  if(take(p,token)) return !p->failed;
  char message[96]; snprintf(message,sizeof message,"expected '%s'",token); return source_fail(p,message);
}
static size_t emit(SourceParser *p,unsigned op,unsigned d,unsigned a,unsigned b,uint64_t immediate){
  size_t at=p->code_size;
  if(p->failed || at+12>sizeof p->code){ source_fail(p,"compiled program exceeds instruction limit"); return 0; }
  uint8_t *code=p->code+at;
  code[0]=(uint8_t)op; code[1]=(uint8_t)d; code[2]=(uint8_t)a; code[3]=(uint8_t)b;
  for(unsigned i=0;i<8;i++) code[4+i]=(uint8_t)(immediate>>(8u*i));
  p->code_size+=12; return at;
}
static void patch(SourceParser *p,size_t at){
  uint64_t target=p->code_size/12;
  for(unsigned i=0;i<8;i++) p->code[at+4+i]=(uint8_t)(target>>(8u*i));
}
static unsigned reg_new(SourceParser *p){
  for(unsigned i=3;i<32;i++) if(!(p->used&(UINT32_C(1)<<i))){ p->used|=UINT32_C(1)<<i; return i; }
  source_fail(p,"too many live variables or expression values"); return 2;
}
static void reg_free(SourceParser *p,unsigned reg){ p->used&=~(UINT32_C(1)<<reg); }
static unsigned constant(SourceParser *p,uint64_t value){
  unsigned reg=reg_new(p); emit(p,OBOR_TRANSFORM_CONSTANT,reg,0,0,value); return reg;
}
static int local(SourceParser *p,const char *name){
  for(unsigned i=0;i<p->local_count;i++) if(!strcmp(name,p->locals[i].name)) return (int)p->locals[i].reg;
  return -1;
}
static void scope_end(SourceParser *p,unsigned count){
  while(p->local_count>count) reg_free(p,p->locals[--p->local_count].reg);
}
static int memory(SourceParser *p){
  static const char *names[]={"input","work","parameters","scratch","metadata"};
  for(int i=0;i<5;i++) if(take(p,names[i])) return i;
  source_fail(p,"expected input, work, parameters, scratch or metadata"); return 0;
}
static unsigned expression(SourceParser *p,unsigned minimum);
static unsigned unary(SourceParser *p){
  if(++p->depth>DEPTH_LIMIT){ source_fail(p,"source nesting limit exceeded"); p->depth--; return 2; }
  unsigned result=2;
  if(is(p,"!") || is(p,"~") || is(p,"-") || is(p,"+")){
    char op=p->token[0]; next(p); result=unary(p);
    if(op!='+'){
      unsigned value=constant(p,op=='~'?UINT64_MAX:0);
      emit(p,op=='!'?OBOR_TRANSFORM_EQUAL:op=='~'?OBOR_TRANSFORM_XOR:OBOR_TRANSFORM_SUBTRACT,
           result,value,result,0); reg_free(p,value);
    }
  } else if(is(p,"$number")){ result=constant(p,p->number); next(p); }
  else if(take(p,"true")) result=constant(p,1);
  else if(take(p,"false")) result=constant(p,0);
  else if(take(p,"(")){ result=expression(p,1); expect(p,")"); }
  else if(is(p,"read8") || is(p,"read32") || is(p,"read64")){
    unsigned op=is(p,"read8")?OBOR_TRANSFORM_LOAD8:is(p,"read32")?OBOR_TRANSFORM_LOAD32:OBOR_TRANSFORM_LOAD64;
    next(p); expect(p,"("); int space=memory(p); expect(p,","); result=expression(p,1); expect(p,")");
    emit(p,op,result,result,(unsigned)space,0);
  } else {
    int reg=local(p,p->token);
    if(reg<0) source_fail(p,"unknown variable or unsupported expression");
    else { result=reg_new(p); emit(p,OBOR_TRANSFORM_MOVE,result,(unsigned)reg,0,0); next(p); }
  }
  p->depth--; return result;
}
typedef struct SourceOperator { const char *name; unsigned precedence,op; } SourceOperator;
static const SourceOperator operators[]={
  {"||",1,0},{"&&",2,0},{"|",3,OBOR_TRANSFORM_OR},{"^",4,OBOR_TRANSFORM_XOR},
  {"&",5,OBOR_TRANSFORM_AND},{"==",6,OBOR_TRANSFORM_EQUAL},{"!=",6,OBOR_TRANSFORM_EQUAL},
  {"<",7,OBOR_TRANSFORM_LESS},{">",7,OBOR_TRANSFORM_LESS},
  {"<=",7,OBOR_TRANSFORM_LESS},{">=",7,OBOR_TRANSFORM_LESS},
  {"<<",8,OBOR_TRANSFORM_SHIFT_LEFT},{">>",8,OBOR_TRANSFORM_SHIFT_RIGHT},
  {"+",9,OBOR_TRANSFORM_ADD},{"-",9,OBOR_TRANSFORM_SUBTRACT},
  {"*",10,OBOR_TRANSFORM_MULTIPLY},{"/",10,OBOR_TRANSFORM_DIVIDE},{"%",10,OBOR_TRANSFORM_REMAINDER}
};
static void boolean(SourceParser *p,unsigned reg,int invert){
  unsigned zero=constant(p,0);
  emit(p,OBOR_TRANSFORM_EQUAL,reg,reg,zero,0);
  if(!invert) emit(p,OBOR_TRANSFORM_EQUAL,reg,reg,zero,0);
  reg_free(p,zero);
}
static unsigned expression(SourceParser *p,unsigned minimum){
  if(++p->depth>DEPTH_LIMIT){ source_fail(p,"source nesting limit exceeded"); p->depth--; return 2; }
  unsigned left=unary(p);
  while(!p->failed){
    const SourceOperator *op=NULL;
    for(size_t i=0;i<sizeof operators/sizeof operators[0];i++) if(is(p,operators[i].name)){ op=&operators[i]; break; }
    if(!op || op->precedence<minimum) break;
    next(p);
    size_t skip=0;
    if(op->precedence<=2){
      boolean(p,left,0);
      skip=emit(p,op->precedence==1?OBOR_TRANSFORM_JUMP_NONZERO:OBOR_TRANSFORM_JUMP_ZERO,0,left,0,0);
    }
    unsigned right=expression(p,op->precedence+1);
    if(op->precedence<=2){
      boolean(p,right,0); emit(p,OBOR_TRANSFORM_MOVE,left,right,0,0); patch(p,skip);
    } else {
      int swap=!strcmp(op->name,">") || !strcmp(op->name,"<=");
      emit(p,op->op,left,swap?right:left,swap?left:right,0);
      if(!strcmp(op->name,"!=") || !strcmp(op->name,"<=") || !strcmp(op->name,">=")) boolean(p,left,1);
    }
    reg_free(p,right);
  }
  p->depth--; return left;
}
static int reserved(const char *name){
  static const char *words[]={"input","work","parameters","scratch","input_size","parameter_size",
    "metadata","metadata_size",
    "buffer","uint64_t","if","else","while","for","break","continue","return","true","false",
    "read8","read32","read64","write8","write32","write64","slice","scratch_slice","reject"};
  for(size_t i=0;i<sizeof words/sizeof words[0];i++) if(!strcmp(words[i],name)) return 1;
  return 0;
}
static void simple(SourceParser *p,int declaration){
  char name[64]; unsigned reg;
  if(declaration){
    if(!ident_start((unsigned char)p->token[0]) || reserved(p->token) || local(p,p->token)>=0 || p->local_count>=32){
      source_fail(p,"invalid, reserved or shadowed variable name"); return;
    }
    strcpy(name,p->token); next(p); expect(p,"=");
    /* Resolve the initializer before introducing the name: no uninitialized reads. */
    unsigned value=expression(p,1); reg=reg_new(p);
    if(!p->failed){ strcpy(p->locals[p->local_count].name,name); p->locals[p->local_count++].reg=reg; }
    emit(p,OBOR_TRANSFORM_MOVE,reg,value,0,0); reg_free(p,value); return;
  }
  int found=local(p,p->token);
  if(found<3){ source_fail(p,"assignment requires a mutable local variable"); return; }
  reg=(unsigned)found; next(p);
  char op[64]; strcpy(op,p->token); next(p);
  if(!strcmp(op,"++") || !strcmp(op,"--")){
    unsigned one=constant(p,1); emit(p,op[0]=='+'?OBOR_TRANSFORM_ADD:OBOR_TRANSFORM_SUBTRACT,reg,reg,one,0); reg_free(p,one);
  } else if(!strcmp(op,"=") || (strlen(op)==2 && op[1]=='=' && strchr("+-*/%&|^",op[0]))){
    unsigned value=expression(p,1),opcode=OBOR_TRANSFORM_MOVE;
    if(op[0]!='=') for(size_t i=0;i<sizeof operators/sizeof operators[0];i++)
      if(operators[i].name[0]==op[0] && !operators[i].name[1]) opcode=operators[i].op;
    emit(p,opcode,reg,opcode==OBOR_TRANSFORM_MOVE?value:reg,opcode==OBOR_TRANSFORM_MOVE?0:value,0); reg_free(p,value);
  } else source_fail(p,"unsupported assignment");
}
static void statement(SourceParser *p);
static void scoped_statement(SourceParser *p){
  unsigned count=p->local_count; statement(p); scope_end(p,count);
}
static void loop_statement(SourceParser *p,int is_for){
  unsigned scope=p->local_count;
  expect(p,"(");
  if(is_for){
    if(!is(p,";")) simple(p,take(p,"uint64_t"));
    expect(p,";");
  }
  size_t condition=p->code_size/12;
  unsigned test=is_for && is(p,";")?constant(p,1):expression(p,1);
  size_t done=emit(p,OBOR_TRANSFORM_JUMP_ZERO,0,test,0,0); reg_free(p,test);
  SourceLoop loop={0}; loop.parent=p->loop; loop.continuation=condition;
  if(is_for){
    expect(p,";"); size_t body=emit(p,OBOR_TRANSFORM_JUMP,0,0,0,0);
    loop.continuation=p->code_size/12;
    if(!is(p,")")) simple(p,0);
    emit(p,OBOR_TRANSFORM_JUMP,0,0,0,condition); patch(p,body);
  }
  expect(p,")"); p->loop=&loop; scoped_statement(p); p->loop=loop.parent;
  emit(p,OBOR_TRANSFORM_JUMP,0,0,0,loop.continuation); patch(p,done);
  for(size_t i=0;i<loop.count;i++) patch(p,loop.breaks[i]);
  scope_end(p,scope);
}
static void statement(SourceParser *p){
  if(p->failed) return;
  if(++p->depth>DEPTH_LIMIT){ source_fail(p,"source nesting limit exceeded"); p->depth--; return; }
  if(take(p,"{")){
    unsigned count=p->local_count;
    while(!p->failed && !is(p,"}") && p->token[0]) statement(p);
    expect(p,"}"); scope_end(p,count);
  } else if(take(p,"if")){
    expect(p,"("); unsigned test=expression(p,1); expect(p,")");
    size_t otherwise=emit(p,OBOR_TRANSFORM_JUMP_ZERO,0,test,0,0); reg_free(p,test);
    scoped_statement(p);
    if(take(p,"else")){
      size_t done=emit(p,OBOR_TRANSFORM_JUMP,0,0,0,0); patch(p,otherwise); scoped_statement(p); patch(p,done);
    } else patch(p,otherwise);
  } else if(take(p,"while")) loop_statement(p,0);
  else if(take(p,"for")) loop_statement(p,1);
  else if(is(p,"break") || is(p,"continue")){
    int is_break=is(p,"break"); next(p); expect(p,";");
    if(!p->loop) source_fail(p,"loop control outside a loop");
    else if(!is_break) emit(p,OBOR_TRANSFORM_JUMP,0,0,0,p->loop->continuation);
    else if(p->loop->count==LOOP_JUMPS) source_fail(p,"too many loop exits");
    else p->loop->breaks[p->loop->count++]=emit(p,OBOR_TRANSFORM_JUMP,0,0,0,0);
  } else if(take(p,"return")){
    unsigned scratch=take(p,"scratch_slice");
    if(!scratch) expect(p,"slice");
    expect(p,"("); unsigned offset=expression(p,1); expect(p,",");
    unsigned length=expression(p,1); expect(p,")"); expect(p,";");
    emit(p,OBOR_TRANSFORM_RETURN,scratch,offset,length,0); reg_free(p,offset); reg_free(p,length);
  } else if(take(p,"reject")){
    expect(p,"("); expect(p,")"); expect(p,";"); emit(p,OBOR_TRANSFORM_REJECT,0,0,0,0);
  } else if(is(p,"write8") || is(p,"write32") || is(p,"write64")){
    unsigned op=is(p,"write8")?OBOR_TRANSFORM_STORE8:is(p,"write32")?OBOR_TRANSFORM_STORE32:OBOR_TRANSFORM_STORE64;
    next(p); expect(p,"("); int space=memory(p);
    if(space!=1 && space!=3) source_fail(p,"cannot write to read-only memory");
    expect(p,","); unsigned address=expression(p,1); expect(p,","); unsigned value=expression(p,1);
    expect(p,")"); expect(p,";"); emit(p,op,value,address,(unsigned)space,0); reg_free(p,address); reg_free(p,value);
  } else if(take(p,";")) { /* Empty statement. */ }
  else { simple(p,take(p,"uint64_t")); expect(p,";"); }
  p->depth--;
}

int obor_content_transform_compile(const char *source,size_t size,size_t *consumed,
    uint8_t **program,size_t *program_size,uint8_t **parameters,size_t *parameter_size,
    char *error,size_t error_size){
  *program=NULL; *parameters=NULL; *program_size=*parameter_size=*consumed=0;
  if(error && error_size) error[0]=0;
  SourceParser p={0}; p.source=p.at=p.start=source;
  p.end=source+(size<SOURCE_LIMIT?size:SOURCE_LIMIT); p.used=7; p.error=error; p.error_size=error_size;
  strcpy(p.locals[0].name,"input_size"); p.locals[0].reg=0;
  strcpy(p.locals[1].name,"parameter_size"); p.locals[1].reg=1;
  strcpy(p.locals[2].name,"metadata_size"); p.locals[2].reg=2; p.local_count=3;
  next(&p); expect(&p,"buffer");
  if(!ident_start((unsigned char)p.token[0]) || reserved(p.token)) source_fail(&p,"expected a function name");
  next(&p); expect(&p,"("); expect(&p,")"); expect(&p,"{");
  if(take(&p,"parameters")){
    expect(&p,"(");
    if(!is(&p,"$string")) source_fail(&p,"expected a parameter string");
    if(!p.failed){
      const char *s=p.start+1,*end=p.token_end-1;
      while(s<end && !p.failed){
        unsigned value=0;
        if(p.parameter_size==sizeof p.parameters){ source_fail(&p,"parameter limit exceeded"); break; }
        if(escaped_byte(&p,&s,end,&value)) p.parameters[p.parameter_size++]=(uint8_t)value;
      }
    }
    next(&p); expect(&p,")"); expect(&p,";");
  }
  while(!p.failed && !is(&p,"}") && p.token[0]) statement(&p);
  if(!is(&p,"}")) source_fail(&p,"expected function closing brace within source limit");
  /* A path reaching the end without a return rejects; all forward targets remain valid. */
  emit(&p,OBOR_TRANSFORM_REJECT,0,0,0,0);
  if(p.failed) return 0;
  uint8_t *code=(uint8_t*)malloc(p.code_size),*data=(uint8_t*)malloc(p.parameter_size?p.parameter_size:1u);
  if(!code || !data){ free(code); free(data); return source_fail(&p,"allocation failed"); }
  memcpy(code,p.code,p.code_size); memcpy(data,p.parameters,p.parameter_size);
  *program=code; *program_size=p.code_size; *parameters=data; *parameter_size=p.parameter_size;
  *consumed=(size_t)(p.token_end-source); return 1;
}
