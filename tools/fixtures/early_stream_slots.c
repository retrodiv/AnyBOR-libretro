/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "openborscript.h"
#undef exit
#undef time
#undef pause
#undef shutdown
uint32_t obor_profile_build;
static s_level scene, *level=&scene;
List theFunctionList;
static int registered, calls, refuse, pak_failure, missing_file, file_failure;
static void *allocations[128];
static unsigned live;
static FILE *opened;
static char filename[]="fixture.dat";
void writeToLogFile(const char *format,...) { (void)format; }
typedef struct {
 const char *name;
 int mode, count, occupied, hole, argument, type, nargs, refuse, pak_failure, missing_file, file_failure;
 int results[2][7];
} scenario;
static const scenario cases[] = { @CASES@ };
static void *owned_malloc(size_t size) {
 if(refuse) return NULL;
 void *p=malloc(size); assert(p);
 for(unsigned i=0;i<128;i++) if(!allocations[i]) {allocations[i]=p;live++;return p;}
 abort();
}
static void owned_free(void *p) {
 if(!p) return;
 for(unsigned i=0;i<128;i++) if(allocations[i]==p) {allocations[i]=NULL;assert(live);live--;free(p);return;}
 abort();
}
static void *owned_calloc(size_t count,size_t size) {
 if(size && count>SIZE_MAX/size) return NULL;
 void *p=owned_malloc(count*size);if(p)memset(p,0,count*size);return p;
}
static void *owned_realloc(void *p,size_t size) { (void)p;(void)size;abort(); }
CHAR *StrCache_Get(int index) {assert(!index);return filename;}
void StrCache_Collect(int index) {(void)index;abort();}
int StrCache_Pop(void) {abort();}
static int load_pak(char *name,char **buffer,size_t *size) {
 assert(!strcmp(name,filename));calls++;
 if(pak_failure) return 0;
 *buffer=owned_malloc(4);if(!*buffer)return 0;
 memcpy(*buffer,"abc",4);*size=3;return 1;
}
static void base_path(char *path,char *directory,int suffix) {assert(!strcmp(directory,"Saves") && !suffix);strcpy(path,"Saves");}
static int exists(char *path) {assert(!strcmp(path,"Saves/fixture.dat"));return !missing_file;}
static FILE *open_file(char *path,char *mode) {
 assert(!strcmp(path,"Saves/fixture.dat") && !strcmp(mode,"rb") && !opened);calls++;
 if(file_failure)return NULL;
 opened=tmpfile();assert(opened);assert(fwrite("abc",1,3,opened)==3);return opened;
}
static int close_file(FILE *f) {assert(f==opened);opened=NULL;return fclose(f);}
#define buffer_pakfile load_pak
#define getBasePath base_path
#define fileExists exists
#define fopen open_file
#define fclose close_file
#define malloc owned_malloc
#define calloc owned_calloc
#define realloc owned_realloc
#define free owned_free
@ALLOCATION@
@VARIANTS@
@BODIES@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef fopen
#undef fclose
static void insert(List *list,void *api,const char *name) {
 assert(list==&theFunctionList && api==(void*)openbor_closefilestream && !strcmp(name,"closefilestream"));registered++;
}
#define List_InsertAfter insert
static void register_close(void) { @REGISTER@ }
static const char *lookup(void *functionRef) { if(0) return NULL; @LOOKUP@ return NULL; }
static void check(unsigned revision,unsigned era) {
 obor_profile_build=revision;registered=0;register_close();assert(registered==(int)era);
 const char *name=lookup((void*)openbor_closefilestream);assert((name!=NULL)==(int)era);if(name)assert(!strcmp(name,"closefilestream"));
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  const scenario *c=&cases[i];assert(!live && !opened);memset(&scene,0,sizeof(scene));
  refuse=0;calls=0;
  for(int k=0;k<LEVEL_MAX_FILESTREAMS;k++) {
   scene.filestreams[k].size=17;scene.filestreams[k].pos=7;
   if(k<c->occupied && k!=c->hole) {scene.filestreams[k].buf=owned_malloc(4);memcpy(scene.filestreams[k].buf,"old",4);scene.filestreams[k].obor_capacity=4;}
  }
  scene.numfilestreams=c->count;refuse=c->refuse;pak_failure=c->pak_failure;missing_file=c->missing_file;file_failure=c->file_failure;
  ScriptVariant file={.strVal=0,.vt=VT_STR},arg={.lVal=c->argument,.vt=c->type},location={.lVal=c->mode==2,.vt=VT_INTEGER},value={.vt=VT_EMPTY};
  ScriptVariant *result=&value,*args[]={&file,&location};HRESULT status;
  if(c->mode==0)status=openbor_createfilestream(args,&result,0);
  else if(c->mode==3) {args[0]=&arg;status=openbor_closefilestream(args,&result,c->nargs);}
  else status=openbor_openfilestream(args,&result,2);
  int slot=c->mode==3?c->argument:(result && result->vt==VT_INTEGER?(int)result->lVal:-1);
  int got[]={SUCCEEDED(status),result?(int)result->vt:-1,result && result->vt==VT_INTEGER?(int)result->lVal:-1,scene.numfilestreams,(int)live,calls,0};
  if(slot>=0 && slot<LEVEL_MAX_FILESTREAMS) {
   if(c->mode!=3 && SUCCEEDED(status)) {assert(scene.filestreams[slot].pos==0);assert(scene.filestreams[slot].size==(size_t)(c->mode==1?3:17));}
   if(c->mode==3 && SUCCEEDED(status)) {assert(!scene.filestreams[slot].buf && !scene.filestreams[slot].obor_capacity);assert(scene.filestreams[slot].pos==7 && scene.filestreams[slot].size==17);}
   got[6]=scene.filestreams[slot].buf!=NULL;
  }
  for(int f=0;f<7;f++) if(got[f]!=c->results[era][f]) {
   fprintf(stderr,"%s revision=%u field=%d got=%d expected=%d\n",c->name,revision,f,got[f],c->results[era][f]);abort();
  }
  assert(!opened);refuse=0;
  for(int k=0;k<LEVEL_MAX_FILESTREAMS;k++) {owned_free(scene.filestreams[k].buf);scene.filestreams[k].buf=NULL;}
  assert(!live);
 }
 /* API-driven reuse after close, without manufacturing an occupied-table hole. */
 memset(&scene,0,sizeof(scene));refuse=pak_failure=missing_file=file_failure=0;
 if(era) {
  ScriptVariant value={.vt=VT_EMPTY},*out=&value,index={.lVal=0,.vt=VT_INTEGER},*args[]={&index};
  assert(SUCCEEDED(openbor_createfilestream(NULL,&out,0)) && out->lVal==0);out=&value;
  assert(SUCCEEDED(openbor_closefilestream(args,&out,1)) && !out);out=&value;
  assert(SUCCEEDED(openbor_createfilestream(NULL,&out,0)) && out->lVal==0);
  owned_free(scene.filestreams[0].buf);scene.filestreams[0].buf=NULL;assert(!live);
 }
}
int main(void) { @CHECKS@ puts("early_stream_slots=1");return 0; }
