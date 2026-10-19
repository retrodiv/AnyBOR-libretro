"""Compile real palette/model dispatch code with authored in-memory files.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def function(source, name):
    declaration = re.search(r'(?m)^(?:static\s+)?(?:int|void)\s+' + name + r'\s*\(', source)
    if declaration is None:
        return ''
    opening = source.index('{', declaration.start())
    depth = 0
    token = r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]'
    for match in re.finditer(token, source[opening:]):
        if match[0] == '{':
            depth += 1
        elif match[0] == '}':
            depth -= 1
            if depth == 0:
                return source[declaration.start():opening + match.end()] + '\n'
    raise ValueError('Incomplete C function: ' + name)


def program(image_source, engine_source):
    auto = image_source.index('// ============================== auto loading')
    interface = image_source.index('// ============================== Interface', auto)
    pcx = ''
    if 'static int openpcx(' in image_source:
        pcx = image_source[image_source.index('// ============================== PCX loading'):auto]
    case = engine_source.index('case CMD_MODEL_PALETTE:')
    case_end = engine_source.index('case CMD_MODEL_ALTERNATEPAL:', case)
    return PREFIX + pcx + image_source[auto:interface] + '\n' + function(image_source, 'loadimagepalette') + '\n' + ''.join(
        function(engine_source, name) for name in ('_load_palette16', '_load_palette32', 'load_palette')) + MODEL_PREFIX + engine_source[case:case_end] + MODEL_SUFFIX + MAIN


PREFIX = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
#define SwapLSB16(x) (x)
#define MAX_PAL_SIZE 1024
#define MAX_BUFFER_LEN 256
#define HANDLE_UNUSED (-1)
#define COLOR_COMPONENT_RED 0
#define COLOR_COMPONENT_GREEN 1
#define COLOR_COMPONENT_BLUE 2
#define COLOR_COMPONENT_RGB 3
enum { PIXEL_8, PIXEL_16, PIXEL_32, PIXEL_x8 };
static int screenformat=PIXEL_32, pixelformat=PIXEL_x8;
static int palette_bytes=1024;
#define PAL_BYTES palette_bytes
static char packfile[]="authored-memory-pack";
static int handle=-1, res[2], position, length, opened, image_load_handle=-1;
static struct { int width,height; } image_res;
static char active_name[256];
static unsigned char input[2048];
static uint32_t obor_profile_build;
static unsigned short colour16(unsigned char r,unsigned char g,unsigned char b) {
    return ((b&248)<<8) | ((g&252)<<3) | (r>>3);
}
static unsigned colour32(unsigned char r,unsigned char g,unsigned char b) {
    return ((unsigned)b<<16) | ((unsigned)g<<8) | r;
}
static int openpackfile(const char *name,const char *pack) {
    if (strcmp(name,active_name)) return -1;
    assert(!opened); opened=1; position=0; return 1;
}
static void closepackfile(int fd) { assert(fd==1 && opened); opened=0; }
static int readpackfile(int fd,void *out,int n) {
    assert(fd==1 && opened && position>=0 && position<=length);
    if(n>length-position)n=length-position;
    memcpy(out,input+position,n);position+=n;return n;
}
static int seekpackfile(int fd,int offset,int origin) {
    assert(fd==1 && opened);
    int next=origin==SEEK_END?length+offset:origin==SEEK_CUR?position+offset:offset;
    if(next<0 || next>length)return -1;
    position=next;return position;
}
/* The authored RGB prefix cannot be PNG, GIF or BMP. No decoder is substituted
 * for the PCX or raw palette path under investigation. */
static int openpng(char *a,char *b) { return 0; }
static int opengif(char *a,char *b) { return 0; }
static int openbmp(char *a,char *b) { return 0; }
static int readpng(unsigned char *a,unsigned char *b,int c,int d) { abort(); }
static int readgif(unsigned char *a,unsigned char *b,int c,int d) { abort(); }
static int readbmp(unsigned char *a,unsigned char *b,int c,int d) { abort(); }
static void closepng(void) { abort(); }
'''

MODEL_PREFIX = r'''
/* Oversized backing observes the original's writes beyond its declared
 * palette allocation without invoking undefined behavior in this probe. */
static union { uint64_t align; unsigned char data[4096]; } backing;
static unsigned char *palette = backing.data+32;
static int allocated;
static void *model_palette_allocate(size_t bytes) {
    assert(bytes==(size_t)PAL_BYTES && !allocated); allocated=1; return palette;
}
static int model_palette(char *name) {
    struct { unsigned char *palette; } model={NULL}, *newchar=&model;
    char *value=NULL, *value2=NULL, *fileext=NULL, *command="palette";
    char *shutdownmessage=NULL;
    int length=0,nopalette=0;
    allocated=0;
#define GET_ARG(n) name
#define CMD_MODEL_PALETTE 1
#define malloc model_palette_allocate
    switch(1) {
'''

MODEL_SUFFIX = r'''
    }
#undef malloc
#undef GET_ARG
    return newchar->palette!=NULL;
lCleanup:
    return 0;
}
'''

MAIN = r'''
int main(int argc,char **argv) {
    assert(argc==5);
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    palette_bytes=atoi(argv[2]);
    screenformat=palette_bytes==512?PIXEL_16:palette_bytes==768?PIXEL_8:PIXEL_32;
    snprintf(active_name,sizeof(active_name),"%s",argv[3]);
    length=768;
    for(int i=0;i<768;i++)input[i]=(unsigned char)(i*17+11);
    input[0]=0;input[65]=(unsigned char)atoi(argv[4]);
    memset(backing.data,0xa5,sizeof(backing.data));
    int sprite=openimage(active_name,packfile);
    if(sprite)closeimage();
    assert(!opened);
    int loaded=model_palette(active_name);
    assert(!opened);
    int outside=0,last=-1;
    for(int i=0;i<PAL_BYTES;i++)if(palette[i]!=0xa5)last=i;
    for(int i=PAL_BYTES;i<3000;i++)if(palette[i]!=0xa5)outside++;
    printf("{\"profile\":%u,\"bytes\":%d,\"loaded\":%d,\"sprite_probe\":%d,\"outside_bytes_changed\":%d,\"last_palette_byte_changed\":%d,\"palette\":\"",
           obor_profile_build,PAL_BYTES,loaded,sprite,outside,last);
    for(int i=0;i<PAL_BYTES;i++)printf("%02x",palette[i]);
    puts("\"}");
    return 0;
}
'''
