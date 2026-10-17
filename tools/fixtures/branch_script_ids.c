/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <limits.h>
#include <string.h>
#include "source/openborscript/collision_attack.c"
#include "source/openborscript/recursive_damage.c"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
uint32_t obor_profile_build;
int max_attack_types=28;
void ScriptVariant_Clear(ScriptVariant *v) {memset(v,0,sizeof(*v));}
void ScriptVariant_ChangeType(ScriptVariant *v,VARTYPE t) {ScriptVariant_Clear(v);v->vt=t;}
char *StrCache_Get(int n) {(void)n;return "unknown";}
int searchList(const char *list[],const char *value,int length) {
 for(int i=0;i<length;++i)if(!strcmp(list[i],value))return i;return -1;
}
void writeToLogFile(const char *text,...) {(void)text;}
CONVERSIONS
int main(void) {
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p) {
  int legacy=p!=2;obor_profile_build=profiles[p];
  for(int probe=-4;probe<=30;++probe)for(int kind=0;kind<2;++kind) {
   int id=probe==30?INT_MAX:probe;
   int physical=legacy&&id>=21?(id>INT_MAX-2?-1:id+2):id;
   if(legacy&&id==-2)physical=21;
   if(legacy&&id==-3)physical=22;
   int valid=physical>=0&&physical<max_attack_types;
   s_collision_attack collision={.attack_type=7};s_damage_recursive recurring={.type=7};
   ScriptVariant handle={.vt=VT_PTR,.ptrVal=kind?(void *)&recurring:(void *)&collision};
   ScriptVariant property={.vt=VT_INTEGER,.lVal=kind?_RECURSIVE_DAMAGE_TYPE:ATTACK_PROP_DAMAGE_TYPE};
   ScriptVariant value={.vt=VT_INTEGER,.lVal=id},out={0},*result=&out,*args[]={&handle,&property,&value};
   HRESULT status=kind?openbor_set_recursive_damage_property(args,&result,3):openbor_set_attack_property(args,&result,3);
   assert(status==(valid?S_OK:E_FAIL));
   assert((kind?recurring.type:collision.attack_type)==(valid?physical:7));
   if(valid) {
    result=&out;status=kind?openbor_get_recursive_damage_property(args,&result,2):openbor_get_attack_property(args,&result,2);
    assert(status==S_OK && result==&out && out.vt==VT_INTEGER && out.lVal==id);
   }
  }
 }
}
