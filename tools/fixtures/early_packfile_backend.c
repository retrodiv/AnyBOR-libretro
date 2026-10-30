/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include "List.h"
#include "packfile.h"
#include "borendian.h"
#include "obor_packfile_profile.h"
#if !defined(LIBRETRO) || defined(VERBOSE) || (!defined(LINUX) && !defined(DARWIN))
#error This contract requires the native release lookup target
#endif
uint32_t obor_profile_build;
static unsigned phase,scenarios;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Pack backend revision=%u phase=%u line=%d: %s\n",obor_profile_build,phase,__LINE__,#c);abort();}}while(0)
@CONSTANTS@
@GLOBALS@
static char packfile[64]="member.pak";
static int startup_done,cache_active,cache_fd=-1,cache_inits,cache_terms;
static char messages[4096];
static void clear_messages(void) {messages[0]=0;}
static int capture_printf(const char *format,...) {
 size_t offset=strlen(messages);va_list args;va_start(args,format);
 int n=vsnprintf(messages+offset,sizeof(messages)-offset,format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(messages)-offset);return n;
}
void obor_port_assert(int value,const char *expression,const char *function,const char *file,int line) {
 (void)expression;(void)function;(void)file;(void)line;CHECK(value);
}
static int obor_loose_may_exist(const char *name) {CHECK(name);return 1;}
static void filecache_init(int fd,int sectors,int blocksize,unsigned char blocks,int vfds) {
 CHECK(!cache_active && fd>=0 && sectors==1 && blocksize==CACHEBLOCKSIZE && blocks==CACHEBLOCKS && vfds==MAXPACKHANDLES);
 cache_active=1;cache_fd=fd;++cache_inits;
}
static void filecache_term(void) {cache_active=0;cache_fd=-1;++cache_terms;}
static void filecache_setvfd(int fd,int start,int block,int ahead) {
 CHECK(fd>=0 && fd<MAXPACKHANDLES && start>=-1 && block>=-1 && ahead>=0);
}
static void filecache_wait_for_prebuffer(int fd,int blocks) {CHECK(fd>=0 && blocks>=0);}
static int filecache_readpakblock(unsigned char *dest,int block,int start,int bytes,int blocking) {
 CHECK(cache_active && cache_fd==pakfd && block>=0 && start>=0 && bytes>=0 && blocking==1);
 return (int)pread(cache_fd,dest,(size_t)bytes,(off_t)block*CACHEBLOCKSIZE+start);
}
@READ_LE@
#define stricmp strcasecmp
#define printf capture_printf
@FUNCTIONS@
@STARTUP@
static void retire_cache(int disablelog) {
@RETIRE@
}
#undef printf
typedef struct {unsigned revision;int startup,raw_check,handle_message;const char *error_format;int filename_cache;} Row;
static const Row rows[]={@ROWS@};
static void put32(unsigned char *p,unsigned value) {
 for(int i=0;i<4;++i)p[i]=(unsigned char)(value>>(i*8));
}
static void authored_pak(void) {
 static const char name[]="outside.txt";
 unsigned char bytes[8+1+12+sizeof(name)+4];memset(bytes,0,sizeof(bytes));
 memcpy(bytes,"PACK",4);bytes[8]='P';put32(bytes+9,12+sizeof(name));
 put32(bytes+13,8);put32(bytes+17,1);memcpy(bytes+21,name,sizeof(name));
 put32(bytes+sizeof(bytes)-4,9);
 FILE *file=fopen(packfile,"wb");CHECK(file);
 CHECK(fwrite(bytes,1,sizeof(bytes),file)==sizeof(bytes) && !fclose(file));
}
static void loose_file(void) {
 FILE *file=fopen("outside.txt","wb");CHECK(file);
 CHECK(fwrite("L",1,1,file)==1 && !fclose(file));
}
static void reset_backend(void) {
 freefilenamecache();pak_term();
 if(pakfd>=0){CHECK(!close(pakfd));pakfd=-1;}
 CHECK(!pak_cdheader && !cache_active);
 for(int i=0;i<MAXPACKHANDLES;++i)CHECK(packhandle[i]==-1);
 memset(pak_vfdexists,0,sizeof(pak_vfdexists));
 cache_inits=cache_terms=0;packfile_mode(0);clear_messages();
}
static void mode(int cached) {
 CHECK(pOpenPackfile==(cached?openPackfileCached:openPackfile));
 CHECK(pReadPackfile==(cached?readPackfileCached:readPackfile));
 CHECK(pSeekPackfile==(cached?seekPackfileCached:seekPackfile));
 CHECK(pClosePackfile==(cached?closePackfileCached:closePackfile));
}
static void member(char expected) {
 int fd=openpackfile("outside.txt",packfile);char byte=0;
 CHECK(fd>=0 && readpackfile(fd,&byte,1)==1 && byte==expected);
 CHECK(readpackfile(fd,&byte,1)==0 && !closepackfile(fd));
}
static void check(const Row *row) {
 obor_profile_build=row->revision;startup_done=1;
 for(int raw=0;raw<2;++raw) {
  phase=1;reset_backend();loose_file();if(raw)CHECK(!mkdir("data",0700));
  startup();int cached=row->startup && !raw;mode(cached);
  CHECK(cache_inits==cached && pak_initialized==row->startup);
  const char *init=row->startup?(raw?"FileCaching System Init......\tDisabled\n":"FileCaching System Init......\tEnabled\n"):"";
  CHECK(!strcmp(messages,init));
  phase=2;clear_messages();member(cached?'P':'L');CHECK(!messages[0]);
  CHECK(!remove("outside.txt"));member('P');loose_file();
  phase=3;clear_messages();retire_cache(0);
  CHECK(!strcmp(messages,row->startup?"Release FileCaching System...\tDone!\n":""));
  CHECK(!pak_initialized && !cache_active && !pak_cdheader);
  phase=4;reset_backend();int result=pak_init();cached=!(row->raw_check && raw);
  CHECK((result>0)==cached && result>=0 && pak_initialized && cache_inits==cached);mode(cached);
  CHECK(!messages[0]);member(cached?'P':'L');
  phase=5;clear_messages();CHECK(pak_init()==0 && !strcmp(messages,"pak_init already initialized!"));
  clear_messages();retire_cache(1);CHECK(!messages[0] && !pak_initialized && !cache_active);
  reset_backend();if(raw)CHECK(!rmdir("data"));++scenarios;
 }
 phase=6;reset_backend();strcpy(packfile,"missing.pak");startup();
 char error[512],expected[1024];int n=snprintf(error,sizeof(error),row->error_format,packfile,-1,strerror(ENOENT));
 CHECK(n>0 && (size_t)n<sizeof(error));
 if(row->startup)snprintf(expected,sizeof(expected),"FileCaching System Init......\t%sDisabled\n",error);
 else expected[0]=0;
 CHECK(!strcmp(messages,expected) && !pak_initialized && pakfd==-1);
 clear_messages();CHECK(pak_init()==0 && !strcmp(messages,error));
 reset_backend();strcpy(packfile,"member.pak");
 phase=7;int handles[MAXPACKHANDLES];
 for(int i=0;i<MAXPACKHANDLES;++i){handles[i]=openpackfile("outside.txt",packfile);CHECK(handles[i]==i);}
 clear_messages();CHECK(openpackfile("outside.txt",packfile)==-1);
 CHECK(!strcmp(messages,row->handle_message?"no free handles\n":""));
 CHECK(!closepackfile(handles[3]));CHECK(openpackfile("outside.txt",packfile)==3);
 for(int i=0;i<MAXPACKHANDLES;++i)CHECK(!closepackfile(i));
 phase=8;startup_done=0;clear_messages();retire_cache(1);CHECK(!messages[0] && !cache_terms);
 startup_done=1;reset_backend();++scenarios;
}
static void directory_entry(FILE *file,const char *name,unsigned start) {
 unsigned char header[12];size_t length=strlen(name)+1;
 put32(header,12+(unsigned)length);put32(header+4,start);put32(header+8,1);
 CHECK(fwrite(header,1,sizeof(header),file)==sizeof(header));
 CHECK(fwrite(name,1,length,file)==length);
}
static void check_directory(const Row *row) {
 obor_profile_build=row->revision;startup_done=1;phase=9;
 for(int dos=0;dos<2;++dos) {
  reset_backend();
  FILE *file=fopen(packfile,"wb");CHECK(file);
  CHECK(fwrite("PACK\0\0\0\0PF",1,10,file)==10);
  directory_entry(file,"outside.txt",8);
  directory_entry(file,dos?"data\\sprites\\font.png":"data/sprites/font.png",9);
  unsigned char footer[4];put32(footer,10);
  CHECK(fwrite(footer,1,4,file)==4 && !fclose(file));
  startup();mode(row->startup);
  const char *queries[]={"DATA/sprites/FONT.PNG","data\\sprites\\font.png"};
  for(unsigned i=0;i<sizeof(queries)/sizeof(queries[0]);++i) {
   int fd=openpackfile(queries[i],packfile);char byte=0;
   if(dos || row->startup) {
    CHECK(fd>=0 && readpackfile(fd,&byte,1)==1 && byte=='F');
    CHECK(readpackfile(fd,&byte,1)==0 && !closepackfile(fd));
   } else CHECK(fd==-1);
  }
  reset_backend();++scenarios;
 }
}
@LOOKUP@
int main(void) {
#ifdef TEST_CACHED_NAMES
 for(unsigned i=0;i<sizeof(rows)/sizeof(rows[0]);++i)check_lookup(&rows[i]);
 printf("early_pack_lookup=1 contexts=%zu scenarios=%u\n",sizeof(rows)/sizeof(rows[0]),scenarios);
 return 0;
#else
 CHECK(sizeof(unsigned)==4);authored_pak();
 for(unsigned i=0;i<sizeof(rows)/sizeof(rows[0]);++i)check(&rows[i]);
 for(unsigned i=0;i<sizeof(rows)/sizeof(rows[0]);++i)check_directory(&rows[i]);
 CHECK(!remove("outside.txt") && !remove(packfile));
 printf("early_pack_backend=1 contexts=%zu scenarios=%u\n",sizeof(rows)/sizeof(rows[0]),scenarios);
 return 0;
#endif
}
