"""Render buffered-file precedence with native loose files and bounded readers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from test_historical_player import function


def render_file_precedence(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    bodies = '\n'.join(function(source, name) for name in ('buffer_file', 'buffer_pakfile'))
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (
        row['revision'], row['direct_loose_first']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#define LIBRETRO 1
static uint32_t obor_profile_build;
static unsigned cases,direct_opens,alias_calls,pack_calls,pack_closes;
static int mode,mask;
static char filename[1024],*packfile="test.pak";
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"file precedence profile=%u mode=%d mask=%d line=%d\n",obor_profile_build,mode,mask,__LINE__);abort();}}while(0)
static void shutdown(int code,const char *format,...){(void)code;(void)format;assert(0);}
static FILE *tracked_fopen(const char *name,const char *flags){++direct_opens;return fopen(name,flags);}
static int obor_buffer_content_alias(char *name,char **out,size_t *size){
    assert(!strcmp(name,filename));++alias_calls;
    if(!(mask&4))return 0;
    *size=5;*out=malloc(6);assert(*out);memcpy(*out,"alias",6);return 1;
}
static int openpackfile(char *name,char *pak){
    assert(!strcmp(name,filename) && pak==packfile);++pack_calls;
    if(!mode && (mask&2))return 22;
    return mask&1?21:-1;
}
static size_t seekpackfile(int fd,int offset,int whence){
    assert((fd==21 || fd==22) && offset==0);return whence==SEEK_END?(fd==21?6:5):0;
}
static size_t readpackfile(int fd,char *out,size_t size){
    const char *text=fd==21?"packed":"loose";assert(size==strlen(text));
    memcpy(out,text,size);return size;
}
static void closepackfile(int fd){assert(fd==21 || fd==22);++pack_closes;}
#define fopen tracked_fopen
@BODIES@
#undef fopen
static void check(int direct){
    for(int reader=0;reader<2;++reader)for(int variant=0;variant<8;++variant){
        mode=1-reader;mask=(variant+3)%8;
        remove(filename);
        if(mask&2){FILE *file=fopen(filename,"wb");assert(file);
            assert(fwrite("loose",1,5,file)==5);assert(fclose(file)==0);}
        direct_opens=alias_calls=pack_calls=pack_closes=0;
        char *buffer=NULL;size_t size=0;
        int result=buffer_pakfile(filename,&buffer,&size);
        const char *expected=(direct && (mask&2))?"loose":
            (mask&4)?"alias":(!mode && (mask&2))?"loose":(mask&1)?"packed":NULL;
        assert(result==(expected!=NULL));
        if(expected){assert(size==strlen(expected));assert(buffer && !strcmp(buffer,expected));}
        else assert(!buffer && !size);
        assert(direct_opens==(unsigned)direct);
        assert(alias_calls==(unsigned)!(direct && (mask&2)));
        unsigned pack_expected=!(direct && (mask&2)) && !(mask&4);
        assert(pack_calls==pack_expected);
        assert(pack_closes==(unsigned)(pack_expected && expected!=NULL));
        free(buffer);remove(filename);++cases;
    }
}
int main(void){
    const char *tmp=getenv("ANYBOR_NATIVE_ARTIFACTS")?getenv("TMPDIR"):".";
    if(!tmp)tmp=".";
    assert(snprintf(filename,sizeof(filename),"%s/loose-precedence.txt",tmp)>0);
    @CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@BODIES@', bodies).replace('@CHECKS@', checks)
