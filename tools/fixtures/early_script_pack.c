/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Valid script values retain their results at either record alignment.
 * Original controls supply their own unmodified headers and C bodies.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@DECLARATIONS@
#undef printf
#define CHECK(c) do{if(!(c)){fprintf(stderr,"Script packing revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static char strings[][8]={"","bar","foo"};
static unsigned char arena[2];
CHAR *StrCache_Get(int index){CHECK(index>=0 && index<3);return strings[index];}
@FUNCTIONS@
enum {INTEGER,DECIMAL,STRING,POINTER,EMPTY};
struct value {int kind;double number;};
struct pair {struct value a,b;int expected[6];};
/* Column order: ==, !=, <, >, <=, >=. String != retains libc's actual
 * strcmp result, whose magnitude is not specified across operating systems. */
static const struct pair pairs[]={
 {{INTEGER,13},{INTEGER,13},{1,0,0,0,1,1}},
 {{INTEGER,4},{INTEGER,7},{0,1,1,0,1,0}},
 {{INTEGER,7},{DECIMAL,7},{1,0,0,0,1,1}},
 {{DECIMAL,-1.25},{INTEGER,-1},{0,1,1,0,1,0}},
 {{DECIMAL,7.5},{INTEGER,7},{0,1,0,1,0,1}},
 {{STRING,2},{STRING,2},{1,0,0,0,1,1}},
 {{STRING,1},{STRING,2},{0,0,1,0,1,0}},
 {{STRING,2},{STRING,1},{0,0,0,1,0,1}},
 {{POINTER,0},{POINTER,0},{1,0,0,0,1,1}},
 {{POINTER,0},{POINTER,1},{0,1,1,0,1,0}},
 {{POINTER,1},{POINTER,0},{0,1,0,1,0,1}},
 {{EMPTY,0},{EMPTY,0},{1,0,0,0,0,0}},
 {{EMPTY,0},{INTEGER,0},{0,1,0,0,0,0}},
 {{INTEGER,0},{POINTER,-1},{0,1,1,0,1,0}},
 {{POINTER,-1},{INTEGER,0},{0,1,0,1,0,1}},
 {{STRING,0},{INTEGER,0},{0,1,0,1,0,1}}
};
static void value(ScriptVariant *out,struct value input,unsigned char tail){
 memset(out,0,sizeof(*out));
 switch(input.kind){
 case INTEGER:out->vt=VT_INTEGER;out->lVal=(LONG)input.number;break;
 case DECIMAL:out->vt=VT_DECIMAL;out->dblVal=input.number;break;
 case STRING:out->vt=VT_STR;out->strVal=(int)input.number;break;
 case POINTER:out->vt=VT_PTR;out->ptrVal=input.number<0?NULL:arena+(int)input.number;break;
 default:out->vt=VT_EMPTY;break;
 }
 size_t first=offsetof(ScriptVariant,vt)+sizeof(out->vt);
 memset((unsigned char*)out+first,tail,sizeof(*out)-first);
}
static void check(unsigned revision,int original_packed){
 obor_profile_build=revision;CHECK(original_packed==0 || original_packed==1);
 CHECK(sizeof(LONG)==4 && sizeof(DOUBLE)==8 && sizeof(void*)==8);
 CHECK(sizeof(ScriptVariant)==EXPECTED_VARIANT_SIZE);
 CHECK(_Alignof(ScriptVariant)==EXPECTED_VARIANT_ALIGNMENT && offsetof(ScriptVariant,vt)==8);
 ScriptVariant *(*ops[])(ScriptVariant*,ScriptVariant*)={ScriptVariant_Eq,ScriptVariant_Ne,ScriptVariant_Lt,ScriptVariant_Gt,ScriptVariant_Le,ScriptVariant_Ge};
 for(unsigned p=0;p<sizeof(pairs)/sizeof(*pairs);p++)for(int poison=0;poison<4;poison++){
  ScriptVariant a,b;value(&a,pairs[p].a,poison&1?0xa5:0);value(&b,pairs[p].b,poison&2?0x5a:0);
  for(int op=0;op<6;op++){
   LONG expected=pairs[p].expected[op];
   if(op==1 && pairs[p].a.kind==STRING && pairs[p].b.kind==STRING)
    expected=strcmp(strings[(int)pairs[p].a.number],strings[(int)pairs[p].b.number]);
   ScriptVariant *result=ops[op](&a,&b);CHECK(result && result->vt==VT_INTEGER && result->lVal==expected);
  }
 }
 const struct value truth[]={{INTEGER,0},{INTEGER,7},{DECIMAL,0},{DECIMAL,-1.25},
  {STRING,0},{STRING,2},{POINTER,-1},{POINTER,0},{EMPTY,0}};
 const int true_results[]={0,1,0,1,0,1,0,1,0};
 for(unsigned i=0;i<sizeof(truth)/sizeof(*truth);i++){
  ScriptVariant a;value(&a,truth[i],0xa5);CHECK(ScriptVariant_IsTrue(&a)==true_results[i]);
 }
 const double numbers[]={-13.75,0,7,13.75};
 for(unsigned i=0;i<sizeof(numbers)/sizeof(*numbers);i++){
  ScriptVariant a;value(&a,(struct value){DECIMAL,numbers[i]},0xa5);LONG n=77;DOUBLE d=77;
  CHECK(ScriptVariant_IntegerValue(&a,&n)==S_OK && n==(LONG)numbers[i]);
  CHECK(ScriptVariant_DecimalValue(&a,&d)==S_OK && d==numbers[i]);
 }
}
int main(void){
 @CHECKS@
 printf("{\"status\":\"PASS\",\"variant_size\":%zu,\"variant_alignment\":%zu,\"tag_offset\":%zu}\n",
  sizeof(ScriptVariant),_Alignof(ScriptVariant),offsetof(ScriptVariant,vt));
 return 0;
}
