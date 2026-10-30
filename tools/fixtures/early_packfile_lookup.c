/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
static char name255[256],name256[257],name300[301];
static const char *member_names[7];
static size_t authored_header;
static void lookup_pak(int invalid) {
 unsigned char bytes[2048];size_t at=8+7;memset(bytes,0,sizeof(bytes));
 memcpy(bytes,"PACK",4);
 for(int i=0;i<7;++i)bytes[8+i]=(unsigned char)('A'+i);
 authored_header=at;
 for(int i=0;i<7;++i) {
  size_t length=strlen(member_names[i])+1;
  CHECK(at+12+length+4<sizeof(bytes));
  put32(bytes+at,(unsigned)(12+length));put32(bytes+at+4,(unsigned)(8+i));
  put32(bytes+at+8,1);memcpy(bytes+at+12,member_names[i],length);at+=12+length;
 }
 if(invalid==1)put32(bytes+authored_header,0);
 if(invalid==2)put32(bytes+authored_header,(unsigned)(at-authored_header+1));
 if(invalid==3)memset(bytes+authored_header+12,'x',strlen(member_names[0])+1);
 put32(bytes+at,(unsigned)authored_header);at+=4;
 FILE *file=fopen(packfile,"wb");CHECK(file);
 CHECK(fwrite(bytes,1,at,file)==at && !fclose(file));
}
static void cached_member(const char *name,int expected) {
 int fd=openreadaheadpackfile(name,packfile,17,1);char byte=0;
 if(expected<0){CHECK(fd==-1);return;}
 CHECK(fd>=0 && pak_vfdreadahead[fd]==17 && pak_vfdpos[fd]==0);
 CHECK(readpackfile(fd,&byte,1)==1 && byte==expected);
 CHECK(readpackfile(fd,&byte,1)==0 && !closepackfile(fd));
}
static void lookup_reset(void) {
 reset_backend();lookup_pak(0);CHECK(pak_init()>0);clear_messages();mode(1);
}
static void check_lookup(const Row *row) {
 obor_profile_build=row->revision;startup_done=1;
 memset(name255,'q',255);name255[255]=0;
 memset(name256,'r',256);name256[256]=0;
 memset(name300,'s',300);name300[300]=0;
 member_names[0]="Alpha\\MiXeD.txt";member_names[1]="alpha/mixed.TXT";
 member_names[2]=name255;member_names[3]=name256;member_names[4]=name300;
 member_names[5]="";member_names[6]="z";
 phase=20;lookup_reset();CHECK(!filenamelist);
 cached_member("ALPHA/mixed.txt",'A');
 CHECK((filenamelist!=NULL)==row->filename_cache);
 if(row->filename_cache)CHECK(filenamelist->size==5);
 cached_member(name255,'C');cached_member(name256,row->filename_cache?-1:'D');
 cached_member(name300,row->filename_cache?-1:'E');
 cached_member("",'F');cached_member("Z",'G');cached_member("absent.txt",-1);
 CHECK(!messages[0]);++scenarios;
 phase=21;clear_messages();
 CHECK(openreadaheadpackfile("z","other.pak",0,0)==-1);
 CHECK(!strcmp(messages,"tried to open from unknown pack file (other.pak)\n"));
 clear_messages();int fd=openreadaheadpackfile("z","MEMBER.PAK",0,0);
 CHECK(fd>=0 && !closepackfile(fd));
 int handles[MAXPACKHANDLES];
 for(int i=0;i<MAXPACKHANDLES;++i) {
  handles[i]=openreadaheadpackfile("z",packfile,0,0);CHECK(handles[i]==i);
 }
 CHECK(openreadaheadpackfile("z",packfile,0,0)==-1 && !messages[0]);
 CHECK(!closepackfile(handles[3]));CHECK(openreadaheadpackfile("z",packfile,0,0)==3);
 for(int i=0;i<MAXPACKHANDLES;++i)CHECK(!closepackfile(i));
 reset_backend();++scenarios;
 /* These record cases check defined candidate bounds, not original oracles. */
 for(int invalid=1;invalid<=3;++invalid) {
  phase=30+(unsigned)invalid;lookup_pak(invalid);CHECK(pak_init()>0);
  cached_member("z",-1);CHECK(!messages[0]);
  for(int i=0;i<MAXPACKHANDLES;++i)CHECK(!pak_vfdexists[i]);
  reset_backend();++scenarios;
 }
 CHECK(!remove(packfile));
}
