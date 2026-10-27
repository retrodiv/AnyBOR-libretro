"""Render native video-mode parsing and level spawn-coordinate cases.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_video_spawn(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    video = function(source, 'init_videomodes')
    first = video.index('if(stricmp(command, "video")==0){')
    brace = video.index('{', first)
    end, depth = brace + 1, 1
    while depth:
        depth += (video[end] == '{') - (video[end] == '}')
        end += 1
    parser = video[brace + 1:end - 1]
    modes = video[video.index('switch (videoMode)'):
                  video.index('#if SDL || WII', video.index('VIDEOMODES:'))]
    types = (engine / 'source/gamelib/types.h').read_text()
    declaration = re.search(r'typedef struct\s*\{[^{}]*\}s_videomodes;', types)[0]
    level = function(source, 'load_level')
    first = level.index('case CMD_LEVEL_SPAWN1: case CMD_LEVEL_SPAWN2:')
    spawn = level[first:level.index('case CMD_LEVEL_FRONTPANEL:', first)]
    checks = '\n'.join('obor_profile_build=%d;check(%d,%d,%d);' % (
        row['revision'], row['direct_dimensions'], row['direct_offset'], row['spawn_z_clamp'])
        for row in fixture['sources'])
    standards = ',\n'.join('{' + ','.join(map(str, row[:8])) + ',' +
                            ','.join(str(float(v)) + 'f' for v in row[8:]) + '}'
                            for row in fixture['standard_modes'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#ifndef PROBE_FOCUS
#define PROBE_FOCUS 0
#endif
static uint32_t obor_profile_build;
static unsigned cases,numeric_warnings,debug_messages;
static int sample,port,error_status,videoMode,PLAYER_MIN_Z,PLAYER_MAX_Z,BGHEIGHT;
static char error_text[512];
static jmp_buf refusal;
@DECLARATION@
static s_videomodes videomodes;
static struct {char screen[7][2];} savedata;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"video spawn profile=%u focus=%d sample=%d port=%d line=%d\n",obor_profile_build,PROBE_FOCUS,sample,port,__LINE__);abort();}}while(0)
static int tracked_printf(const char *format,...){
    if(strstr(format,"WARNING:"))++numeric_warnings;
    if(strstr(format,"Using debug video"))++debug_messages;
    return 0;
}
static _Noreturn void shutdown(int status,char *format,...){
    error_status=status;va_list args;va_start(args,format);
    vsnprintf(error_text,sizeof(error_text),format,args);va_end(args);longjmp(refusal,1);
}
#define printf tracked_printf
@NUMERIC@
#define GET_ARG(i) ((void)(i),input)
#define GET_INT_ARG(i) getValidInt(GET_ARG(i),filename,command)
static int apply_video(char *input){
    char *value=NULL,*value2=NULL,*filename="video.test",*command="video";
    (void)value2;(void)filename;(void)command;
    if(setjmp(refusal))return 0;
    @PARSER@
    @MODES@
    return 1;
}
#undef GET_ARG
#undef GET_INT_ARG
#undef printf
typedef struct {int spawn[4][3];} Level;
enum {CMD_LEVEL_SPAWN1=10,CMD_LEVEL_SPAWN2,CMD_LEVEL_SPAWN3,CMD_LEVEL_SPAWN4};
#define GET_INT_ARG(n) args[(n)]
static void spawn_case(Level *level,int cmd,int *args){int i=0;switch(cmd){@SPAWN@}}
#undef GET_INT_ARG
static void setup(void){
    memset(&videomodes,0,sizeof(videomodes));videomodes.hRes=640;videomodes.vRes=480;
    videomodes.hShift=17;videomodes.vShift=19;videomodes.dOffset=41;
    videomodes.mode=11;videomodes.filter=12;videomodes.pixel=13;
    videomodes.hScale=3.25f;videomodes.vScale=4.5f;
    for(int i=0;i<4;++i)videomodes.shiftpos[i]=(short)(i+29);
    for(int i=0;i<7;++i){savedata.screen[i][0]=(char)(i+1);savedata.screen[i][1]=(char)(i+10);}
    PLAYER_MIN_Z=31;PLAYER_MAX_Z=32;BGHEIGHT=33;
    numeric_warnings=debug_messages=0;error_status=0;error_text[0]=0;videoMode=-7;
}
static const struct {int h,v,x,y,offset,minz,maxz,bg;float hs,vs;} standard[]={@STANDARDS@};
static void check(int custom,int offset,int clamp){
    if(PROBE_FOCUS==2 && !(custom && !offset))return;
    const char *inputs[]={"0","1","2","3","4","5","6","255","640x480","321x241",
        "1x2","640X480","bad","","-1","7","3abc","+2","2x3"};
    if(PROBE_FOCUS!=3)for(sample=0;sample<19;++sample){
        setup();int mode=0,h=640,v=480,expected_offset=41;
        if(sample<7)mode=sample;
        else if(sample==7)mode=255;
        else if(sample==8){mode=custom?255:640;h=640;v=480;}
        else if(sample==9){mode=custom?255:321;h=321;v=241;}
        else if(sample==10){mode=custom?255:1;if(custom){h=1;v=2;}}
        else if(sample==11)mode=640;
        else if(sample==14)mode=-1;
        else if(sample==15)mode=7;
        else if(sample==16)mode=3;
        else if(sample==17)mode=2;
        else if(sample==18){mode=custom?255:2;if(custom){h=2;v=3;}}
        int valid=(mode>=0 && mode<=6) || (mode==255 && custom);
        int success=apply_video((char*)inputs[sample]);
        assert(success==valid && error_status==(valid?0:1) && videoMode==mode);
        assert(numeric_warnings==(unsigned)(sample==12));
        assert(debug_messages==(unsigned)(valid && mode==255));
        if(!valid){char wanted[64];snprintf(wanted,sizeof(wanted),"Invalid video mode: %d",mode);
            assert(strstr(error_text,wanted));++cases;continue;}
        if(mode<7){
            assert(videomodes.hRes==standard[mode].h && videomodes.vRes==standard[mode].v);
            assert(videomodes.hShift==standard[mode].x && videomodes.vShift==standard[mode].y);
            assert(videomodes.dOffset==standard[mode].offset);
            assert(videomodes.hScale==standard[mode].hs && videomodes.vScale==standard[mode].vs);
            assert(videomodes.mode==mode+1 && videomodes.filter==mode+10);
            assert(PLAYER_MIN_Z==standard[mode].minz && PLAYER_MAX_Z==standard[mode].maxz && BGHEIGHT==standard[mode].bg);
        }else{
            if(offset){if(v==480)expected_offset=462;else if(v==241)expected_offset=231;
                else if(v==2)expected_offset=1;else if(v==3)expected_offset=2;else assert(0);}
            assert(videomodes.hRes==h && videomodes.vRes==v && videomodes.dOffset==expected_offset);
            assert(videomodes.hShift==17 && videomodes.vShift==19);
            assert(videomodes.hScale==3.25f && videomodes.vScale==4.5f);
            assert(videomodes.mode==11 && videomodes.filter==12);
            assert(PLAYER_MIN_Z==31 && PLAYER_MAX_Z==32 && BGHEIGHT==33);
        }
        assert(videomodes.pixel==13);
        for(int i=0;i<4;++i)assert(videomodes.shiftpos[i]==i+29);
        ++cases;
    }
    const int z[]={-2147483647,-1,0,1,231,232,233,300,2147483647};
    if(PROBE_FOCUS==0 || PROBE_FOCUS==3)for(sample=0;sample<9;++sample)for(port=0;port<4;++port){
        Level level={0};int args[]={0,83,z[sample],-1};spawn_case(&level,CMD_LEVEL_SPAWN1+port,args);
        assert(level.spawn[port][0]==83 && level.spawn[port][1]==
            (clamp && (z[sample]<0 || z[sample]>232)?232:z[sample]) && level.spawn[port][2]==300);
        for(int i=0;i<4;++i)if(i!=port)for(int j=0;j<3;++j)assert(level.spawn[i][j]==0);
        ++cases;
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@DECLARATION@', declaration).replace('@NUMERIC@', function(source, 'isNumeric') +
        function(source, 'getValidInt')).replace('@PARSER@', parser).replace('@MODES@', modes).replace(
        '@SPAWN@', spawn).replace('@STANDARDS@', standards).replace('@CHECKS@', checks)
