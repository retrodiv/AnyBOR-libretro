/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
static void authored_large_header(unsigned start,unsigned count) {
 FILE *file=fopen(packfile,"wb");CHECK(file);
 CHECK(fwrite("PACK\0\0\0\0P",1,9,file)==9);
 CHECK(!fseek(file,(long)start,SEEK_SET));
 for(unsigned i=0;i<count;i++) {
  char name[16];CHECK(snprintf(name,sizeof(name),"m%05u",i)==6);
  directory_entry(file,name,8);
 }
 unsigned char footer[4];put32(footer,start);
 CHECK(fwrite(footer,1,4,file)==4 && !fclose(file));
}
static void check_large_headers(void) {
 /* Each directory entry is12header bytes plus a six-character name/NUL.
  * The misaligned case keeps the directory below512KiB while its cached
  * sector span crosses that threshold. Every member names the same valid
  * one-byte payload; member names are distinct. */
 const unsigned base_count=(524288u-4)/19u;
 const unsigned starts[]={2048,2048,2080};
 const unsigned counts[]={base_count,base_count+1,base_count};
 for(unsigned test=0;test<3;test++) {
  authored_large_header(starts[test],counts[test]);
  const unsigned span=((starts[test]&2047)+counts[test]*19+4+2047)&~2047u;
  CHECK(span==(test?526336u:524288u));
  for(unsigned row=0;row<sizeof(rows)/sizeof(*rows);row++) {
   const Row *c=rows+row;obor_profile_build=c->revision;startup_done=1;phase=30+test;
   reset_backend();int result=pak_init();
   int accepted=!test || c->header_warning;
   CHECK((result>0)==accepted && pak_initialized==accepted && cache_inits==accepted);
   char expected[128];expected[0]=0;
   if(test)snprintf(expected,sizeof(expected),c->header_warning?
       "Warning: pak header is too large: %u / 524288\n":"pak header is too large: %u\n",span);
   CHECK(!strcmp(messages,expected));
   if(accepted) {
    char last[16];CHECK(snprintf(last,sizeof(last),"m%05u",counts[test]-1)==6);
    const char *queries[]={"m00000",last};
    for(unsigned q=0;q<2;q++) {
     int fd=openpackfile(queries[q],packfile);char value=0;
     CHECK(fd>=0 && readpackfile(fd,&value,1)==1 && value=='P');
     CHECK(readpackfile(fd,&value,1)==0 && !closepackfile(fd));
    }
   }
   reset_backend();scenarios++;
  }
  CHECK(!remove(packfile));
 }
}
