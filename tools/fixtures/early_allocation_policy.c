/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
uint32_t obor_profile_build;
static unsigned phase,scenarios;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Allocation policy revision=%u phase=%u line=%d: %s\n",obor_profile_build,phase,__LINE__,#c);abort();}}while(0)
#define BYTES 1
static unsigned char allocation[128];
static size_t requested;
static int fail_allocation,malloc_calls,calloc_calls,realloc_calls,free_calls,log_calls,ram_calls;
static char diagnostic[512];
static void *provide_malloc(size_t size) {
 ++malloc_calls;requested=size;if(fail_allocation)return NULL;
 CHECK(size<=sizeof(allocation));return allocation;
}
static void *provide_calloc(size_t count,size_t size) {
 ++calloc_calls;CHECK(count==1);requested=size;if(fail_allocation)return NULL;
 CHECK(size<=sizeof(allocation));memset(allocation,0,size);return allocation;
}
static void *provide_realloc(void *pointer,size_t size) {
 ++realloc_calls;CHECK(!pointer || pointer==allocation);requested=size;
 if(fail_allocation)return NULL;
 CHECK(size<=sizeof(allocation));return allocation;
}
static void provide_free(void *pointer) {CHECK(pointer==allocation);++free_calls;}
static uint64_t getFreeRam(int unit) {CHECK(unit==1);++ram_calls;return UINT64_C(4294967297);}
static void writeToLogFile(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(diagnostic));++log_calls;
}
#define malloc provide_malloc
#define calloc provide_calloc
#define realloc provide_realloc
#define free provide_free
@FUNCTIONS@
#undef malloc
#undef calloc
#undef realloc
#undef free
static const struct {unsigned revision;int proxy;} rows[]={@ROWS@};
static const char *packfile="input.pak";
static int opened,closed,stopped;
static int obor_buffer_content_alias(const char *name,char **out,size_t *bytes) {
 CHECK(!strcmp(name,"input.txt") && out && bytes);return 0;
}
static int openpackfile(const char *name,const char *pak) {
 CHECK(!strcmp(name,"input.txt") && pak==packfile);++opened;return 7;
}
static int seekpackfile(int fd,int offset,int origin) {
 CHECK(fd==7 && !offset && (origin==SEEK_SET || origin==SEEK_END));return origin==SEEK_END?3:0;
}
static int readpackfile(int fd,void *out,int bytes) {
 CHECK(fd==7 && bytes==3 && out==allocation);memcpy(out,"abc",3);return 3;
}
static int closepackfile(int fd) {CHECK(fd==7);++closed;return 0;}
static void shutdown(int status,const char *format,...) {
 CHECK(status==1 && !strcmp(format,"Can't create buffer for packfile '%s'"));++stopped;
}
@BUFFER_CALLER@
static void reset(int fail) {
 memset(allocation,0xa5,sizeof(allocation));requested=0;fail_allocation=fail;
 opened=closed=stopped=0;
 malloc_calls=calloc_calls=realloc_calls=free_calls=log_calls=ram_calls=0;diagnostic[0]=0;
}
static void log_result(int expected,const char *name,size_t bytes) {
 CHECK(log_calls==expected && ram_calls==expected);
 if(expected) {
  char text[512];snprintf(text,sizeof(text),"name: %s Requested: %zu Bytes, Remaining, 4294967297 Bytes\n",name,bytes);
  CHECK(!strcmp(text,diagnostic));
 }else CHECK(!diagnostic[0]);
}
int main(void) {
 for(unsigned r=0;r<sizeof(rows)/sizeof(rows[0]);++r) {
  obor_profile_build=rows[r].revision;int proxy=rows[r].proxy;
  phase=1;reset(0);CHECK(obor_profile_malloc_named("sample",17)==allocation);
  CHECK(requested==17 && malloc_calls==1 && !calloc_calls && !realloc_calls && !free_calls);
  CHECK(allocation[0]==0xa5);log_result(0,"",0);++scenarios;
  phase=2;reset(1);CHECK(!obor_profile_malloc_named("sample",23));
  CHECK(requested==23 && malloc_calls==1);log_result(proxy,"sample",23);++scenarios;
  phase=3;reset(0);CHECK(obor_profile_calloc_named("zero",37)==allocation);
  CHECK(requested==37 && malloc_calls==proxy && calloc_calls==!proxy);
  for(int i=0;i<37;++i){CHECK(!allocation[i]);}
  CHECK(allocation[37]==0xa5);
  log_result(0,"",0);++scenarios;
  phase=4;reset(1);CHECK(!obor_profile_calloc_named("zero",37));
  CHECK(malloc_calls==proxy && calloc_calls==!proxy);log_result(proxy,"zero",37);++scenarios;
  phase=5;reset(0);CHECK(obor_profile_realloc_named(NULL,41)==allocation);
  CHECK(requested==41 && malloc_calls==proxy && realloc_calls==!proxy);log_result(0,"",0);++scenarios;
  phase=6;reset(1);CHECK(!obor_profile_realloc_named(NULL,41));
  CHECK(malloc_calls==proxy && realloc_calls==!proxy);log_result(proxy,"tracerealloc",41);++scenarios;
  phase=7;reset(0);CHECK(obor_profile_realloc_named(allocation,53)==allocation);
  CHECK(realloc_calls==1 && requested==53 && !malloc_calls && !free_calls);log_result(0,"",0);++scenarios;
  phase=8;reset(1);CHECK(!obor_profile_realloc_named(allocation,53));
  CHECK(realloc_calls==1 && !malloc_calls && !free_calls);log_result(0,"",0);++scenarios;
  phase=9;reset(0);void *zero=obor_profile_realloc_named(allocation,0);
  CHECK(zero==(proxy?NULL:allocation) && free_calls==proxy && realloc_calls==!proxy);log_result(0,"",0);++scenarios;
  phase=10;reset(0);CHECK(obor_profile_calloc_named("empty",0)==allocation);
  CHECK(!requested && malloc_calls==proxy && calloc_calls==!proxy && allocation[0]==0xa5);log_result(0,"",0);++scenarios;
  /* Defined candidate admission outside the old signed byte-count domain. */
  phase=11;reset(1);CHECK(!obor_profile_malloc_named("large",SIZE_MAX));
  CHECK(requested==SIZE_MAX);log_result(proxy,"large",SIZE_MAX);++scenarios;
  phase=12;reset(1);CHECK(!obor_profile_malloc_named(NULL,1));log_result(proxy,"",1);++scenarios;
  phase=13;reset(0);char *buffer=NULL;size_t bytes=0;
  CHECK(buffer_pakfile("input.txt",&buffer,&bytes)==1 && bytes==3 && buffer==(char*)allocation);
  CHECK(!memcmp(buffer,"abc",3) && !buffer[3] && opened==1 && closed==1 && !stopped);
  CHECK(malloc_calls==1 && requested==4);log_result(0,"",0);++scenarios;
  phase=14;reset(1);buffer=(char*)allocation;bytes=37;
  CHECK(!buffer_pakfile("input.txt",&buffer,&bytes) && !buffer && !bytes);
  CHECK(opened==1 && closed==1 && stopped==1 && malloc_calls==1 && requested==4);
  log_result(proxy,"buffer_packfile",4);++scenarios;
 }
 printf("allocation_policy=1 contexts=%zu scenarios=%u\n",sizeof(rows)/sizeof(rows[0]),scenarios);return 0;
}
