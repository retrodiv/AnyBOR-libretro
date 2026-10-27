"""Render native menu key-name translation and configuration commands.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_keyboard_names(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    body = function(source, 'keyboard_setup')
    first = body.index('if(command[0]){')
    brace = body.index('{', first)
    end, depth = brace + 1, 1
    while depth:
        depth += (body[end] == '{') - (body[end] == '}')
        end += 1
    block = body[first:end]
    constants = '\n'.join(re.findall(r'(?m)^#define\s+SDID_\w+\s+[^\n]+', header))
    checks = '\n'.join('obor_profile_build=%d;check(%d,%d);' % (
        row['revision'], row['escape_key_name'], row['unknown_menu_command_warning'])
        for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <ctype.h>
#ifndef PROBE_FOCUS
#define PROBE_FOCUS 0
#endif
#define stricmp strcasecmp
@CONSTANTS@
static uint32_t obor_profile_build;
static unsigned cases,warnings;
static int word,variant,cmd,label_index;
static char warning_text[256],*arguments[3];
static int disabledkey[13];
static char buttonnames[13][16];
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"keyboard names profile=%u focus=%d word=%d variant=%d cmd=%d label=%d line=%d\n",obor_profile_build,PROBE_FOCUS,word,variant,cmd,label_index,__LINE__);abort();}}while(0)
@TRANSLATE@
static int tracked_printf(const char *format,...){
    ++warnings;va_list args;va_start(args,format);
    int n=vsnprintf(warning_text,sizeof(warning_text),format,args);va_end(args);return n;
}
#define GET_ARG(i) arguments[(i)]
#define printf tracked_printf
static void command(void){int sdid;char *command=GET_ARG(0),*filename="menu.test";
    (void)filename;(void)tracked_printf;@BLOCK@
}
#undef printf
static void text(char *out,const char *input,int upper){
    while(*input){*out++=upper?(char)toupper((unsigned char)*input):*input;++input;}*out=0;
}
static void check(int escape,int warn){
    const char *words[]={"moveup","movedown","moveleft","moveright","attack","attack2",
        "attack3","attack4","jump","special","start","screenshot","esc","unknown",""};
    const char *commands[]={"disablekey","renamekey","fontmonospace","fontmbs","other",""};
    const char *labels[]={"","Label","123456789012345"};
    for(variant=0;variant<2;++variant)for(word=0;word<15;++word){
        char key[32];text(key,words[word],variant);int index=word<12?word:word==12 && escape?12:-1;
        if(PROBE_FOCUS!=2){assert(translate_SDID(key)==index);++cases;}
        if(PROBE_FOCUS==1)continue;
        for(cmd=0;cmd<6;++cmd)for(label_index=0;label_index<3;++label_index){
            char keyword[32];text(keyword,commands[cmd],variant);
            memset(disabledkey,0,sizeof(disabledkey));memset(buttonnames,0,sizeof(buttonnames));
            for(int i=0;i<13;++i)snprintf(buttonnames[i],16,"Default%d",i);
            int expected_disabled[13]={0};char expected_names[13][16];
            memcpy(expected_names,buttonnames,sizeof(buttonnames));
            if(index>=0 && cmd==0)expected_disabled[index]=1;
            if(index>=0 && cmd==1){memset(expected_names[index],0,16);
                memcpy(expected_names[index],labels[label_index],strlen(labels[label_index]));}
            arguments[0]=keyword;arguments[1]=key;arguments[2]=(char*)labels[label_index];
            warnings=0;warning_text[0]=0;command();
            assert(!memcmp(disabledkey,expected_disabled,sizeof(disabledkey)));
            assert(!memcmp(buttonnames,expected_names,sizeof(buttonnames)));
            assert(warnings==(unsigned)(warn && cmd==4));
            if(warnings){char expected[256];
                snprintf(expected,sizeof(expected),"Command '%s' not understood in file '%s'!",keyword,"menu.test");
                assert(!strcmp(warning_text,expected));}
            ++cases;
        }
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@CONSTANTS@', constants).replace('@TRANSLATE@', function(source, 'translate_SDID')).replace(
        '@BLOCK@', block).replace('@CHECKS@', checks)
