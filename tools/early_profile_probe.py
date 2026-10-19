"""Compile actual early-engine native entry points with authored inputs.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from test_historical_player import function


VARIANTS = r'''
#include <stdint.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef intptr_t LONG;
typedef void VOID;
typedef int HRESULT;
enum { VT_EMPTY=0, VT_INTEGER=1, VT_PTR=5, VT_STR=6 };
typedef struct {
    union { LONG lVal; void *ptrVal; int strVal; };
    int vt;
} ScriptVariant;
static uint32_t obor_profile_build;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(value) ((value)<0)
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {
    memset(v,0,sizeof(*v));v->vt=type;
}
'''


def attack_program(source):
    getter = function(source, 'openbor_getentityproperty')
    start = getter.index('case _ep_attack_staydown:')
    branch = getter[start:getter.index('case _ep_attack_steal:', start)]
    return VARIANTS + r'''
typedef struct { unsigned rise; } s_staydown;
typedef struct { s_staydown staydown; } s_attack;
enum { _ep_attack_staydown=1 };
static void native_attack(s_attack *attack,ScriptVariant **pretvar) {
    switch(_ep_attack_staydown) {
''' + branch + r'''
    }
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    s_attack attack={{(unsigned)strtoul(argv[2],NULL,10)}};
    ScriptVariant result={.lVal=0,.vt=0},*output=&result;
    native_attack(&attack,&output);
    printf("{\"type\":%d,\"value\":%" PRIuPTR "}\n",
           result.vt,result.vt==VT_PTR?(uintptr_t)result.ptrVal:(uintptr_t)result.lVal);
    return 0;
}
'''


def shutdown_program(source):
    return VARIANTS + r'''
#define DEFAULT_SHUTDOWN_MESSAGE "default message"
static char *cache[]={"cached zero","cached one","cached two","requested message"};
static int selected_index=-1,shutdown_calls,exit_status;
static char observed[256];
static char *StrCache_GetIfPresent(int index) {
    selected_index=index;
    return index>=0&&index<4?cache[index]:NULL;
}
static char *StrCache_Get(int index) {
    char *result=StrCache_GetIfPresent(index);
    if(!result)exit(90); /* Never run an undefined original cache read. */
    return result;
}
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt!=VT_INTEGER)return E_FAIL;
    *out=v->lVal;return S_OK;
}
static void shutdown(int status,const char *format,...) {
    exit_status=status;++shutdown_calls;
    /* A script supplies no printf arguments. Intercept undefined original
     * formats in the mock instead of executing an invalid variadic read. */
    for(const char *p=format;*p;++p) {
        if(*p=='%') {
            if(p[1]!='%') {
                snprintf(observed,sizeof(observed),"unvalidated format");return;
            }
            ++p;
        }
    }
    va_list ap;va_start(ap,format);vsnprintf(observed,sizeof(observed),format,ap);va_end(ap);
}
''' + function(source, 'openbor_shutdown') + r'''
int main(int argc,char **argv) {
    if(argc!=5)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    ScriptVariant status={.lVal=0,.vt=0},message={.lVal=0,.vt=0};
    ScriptVariant result={.lVal=0,.vt=0},*output=&result;
    status.vt=VT_INTEGER;status.lVal=(LONG)strtol(argv[2],NULL,10);
    message.vt=VT_STR;message.strVal=3;
    int format_case=atoi(argv[4]);
    if(format_case)
        for(unsigned i=0;i<sizeof(cache)/sizeof(*cache);++i)
            cache[i]=format_case==1?"progress 100%%":"missing %s argument";
    ScriptVariant *args[]={&status,&message};
    int returned=openbor_shutdown(args,&output,atoi(argv[3]));
    printf("{\"result\":%d,\"calls\":%d,\"status\":%d,\"index\":%d,"
           "\"requested\":%d,\"default\":%d,\"percent_escape\":%d}\n",
           returned,shutdown_calls,exit_status,selected_index,
           !strcmp(observed,"requested message"),!strcmp(observed,DEFAULT_SHUTDOWN_MESSAGE),
           !strcmp(observed,"progress 100%"));
    return 0;
}
'''


def playback_program(source):
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define LINUX 1
#define PREMIX_SIZE 1024
static uint32_t obor_profile_build;
static int mixing_inited=1,playbits=16,playfrequency=44100,max_channels=2;
static int mixing_active=1,samplesplayed=37,hard_shift,dmamixpos;
static int stop_calls,sample_stops,start_calls,started_bits,started_frequency;
static void sound_stop_playback(void) {++stop_calls;mixing_active=0;}
static void sound_stop_sample(int channel) {(void)channel;++sample_stops;}
static void SB_playstop(void) {}
static int SB_playstart(int bits,int frequency) {
    ++start_calls;started_bits=bits;started_frequency=frequency;return 1;
}
''' + function(source, 'sound_start_playback') + r'''
int main(int argc,char **argv) {
    if(argc!=4)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    int returned=sound_start_playback(atoi(argv[2]),atoi(argv[3]));
    printf("{\"result\":%d,\"stops\":%d,\"sample_stops\":%d,\"starts\":%d,"
           "\"bits\":%d,\"frequency\":%d,\"active\":%d,\"samples\":%d}\n",
           returned,stop_calls,sample_stops,start_calls,started_bits,started_frequency,
           mixing_active,samplesplayed);
    return 0;
}
'''


def cache_program(source):
    return r'''
#include <stdio.h>
#include <stdlib.h>
typedef char CHAR;
typedef struct { char *str; } Varstr;
static Varstr entries[]={{"zero"},{"one"},{NULL},{"outside capacity"}};
static Varstr *strcache=entries;
static int strcache_size=3;
''' + function(source, 'StrCache_GetIfPresent') + r'''
int main(int argc,char **argv) {
    if(argc!=4)return 2;
    if(atoi(argv[3]))strcache=NULL;
    char *result=StrCache_GetIfPresent(atoi(argv[2]));
    printf("{\"readable\":%d}\n",result!=NULL);
    return 0;
}
'''


def system_program(source, header, utilities):
    start = header.index('enum systemvariant_enum')
    enumeration = header[start:header.index('};', start) + 2]
    match = re.search(r'static const char\s*\*\s*svlist\[\]', source)
    if match is None:
        raise AssertionError('Missing native systemvariant names')
    names = source[match.start():source.index('};', match.start()) + 2]
    macro_start = source.index('#define MAPSTRINGS(')
    mapping_macro = source[macro_start:source.index('\n\n', macro_start)]
    helpers = ''
    for name in ('obor_systemvariant_available', 'obor_systemvariant_native'):
        if re.search(r'\b' + name + r'\s*\(', source):
            helpers += function(source, name)
    methods = '\n'.join(function(source, name) for name in (
        'mapstrings_systemvariant', 'openbor_systemvariant', 'openbor_changesystemvariant'))
    return VARIANTS + r'''
#if defined(_WIN32)
#define stricmp _stricmp
#else
#include <strings.h>
#define stricmp strcasecmp
#endif
static const char *lookup;
static int handler=-1;
static char *StrCache_Get(int index) {(void)index;return (char *)lookup;}
static char *StrCache_GetIfPresent(int index) {return index==1?(char *)lookup:NULL;}
static void ScriptVariant_Clear(ScriptVariant *v) {memset(v,0,sizeof(*v));}
''' + enumeration + '\n' + names + '\n' + function(utilities, 'searchList') + r'''
static int getsyspropertybyindex(ScriptVariant *v,int index) {
    handler=index;v->vt=VT_INTEGER;v->lVal=index;
    return index>=0&&index<_sv_the_end;
}
static int changesyspropertybyindex(int index,ScriptVariant *v) {
    handler=index;
    return v->vt==VT_INTEGER&&v->lVal==123&&index>=0&&index<_sv_the_end;
}
''' + mapping_macro + '\n' + helpers + methods + r'''
static void observe(const char *name,int logical,int numeric,int writing) {
    lookup=name;handler=-1;
    ScriptVariant arg={.lVal=0,.vt=0},value={.lVal=123,.vt=VT_INTEGER};
    ScriptVariant result={.lVal=0,.vt=0},*output=&result,*args[]={&arg,&value};
    arg.vt=numeric?VT_INTEGER:VT_STR;
    if(numeric)arg.lVal=logical;else arg.strVal=1;
    int returned=writing?openbor_changesystemvariant(args,&output,2):
                         openbor_systemvariant(args,&output,1);
    const char *native=handler>=0&&handler<_sv_the_end?svlist[handler]:"<none>";
    printf("{\"input\":\"%s\",\"mode\":\"%c%c\",\"result\":%d,\"arg_type\":%d,"
           "\"arg_id\":%" PRIdPTR ",\"handler_name\":\"%s\",\"null_result\":%d}\n",
           name,numeric?'n':'t',writing?'w':'r',returned,arg.vt,arg.lVal,native,output==NULL);
}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    char name[128];int logical;
    while(scanf("%127s %d",name,&logical)==2)
        for(int numeric=0;numeric<2;++numeric)
            for(int writing=0;writing<2;++writing)
                observe(name,logical,numeric,writing);
    return 0;
}
'''


def menu_flags_program(source):
    methods = []
    for name, replacement in (('sound_options', 'native_sound_finish'),
                              ('config_settings', 'native_config_finish')):
        body = function(source, name)
        start = body.rfind('savesettings();')
        if start < 0:
            raise AssertionError('Missing native menu completion ' + name)
        methods.append('static void ' + replacement + '(void) {\n' +
                       body[start:body.rfind('}')] + '\n}\n')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t obor_profile_build;
static int bothnewkeys=17,soundoptionsMenu=1,save_calls;
static void savesettings(void) {++save_calls;}
''' + '\n'.join(methods) + r'''
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    if(!strcmp(argv[2],"sound"))native_sound_finish();
    else if(!strcmp(argv[2],"config"))native_config_finish();
    else return 2;
    printf("{\"keys\":%d,\"sound_flag\":%d,\"saves\":%d}\n",
           bothnewkeys,soundoptionsMenu,save_calls);
    return 0;
}
'''


def layer_program(source):
    body = function(source, 'load_layer')
    has_mask = 'maskfilename' in body.split('{', 1)[0]
    call = 'load_layer(filename,mask_argument,i);' if has_mask else 'load_layer(filename,i);'
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
typedef struct s_sprite { struct s_sprite *mask; } s_sprite;
typedef struct { int width,height; } s_screen;
typedef struct {
    union { void *handle; s_sprite *sprite; s_screen *screen; } gfx;
    struct { int x,y; } size;
    struct { int x,z; } offset;
    struct { int alpha,transbg,xrepeat,yrepeat; struct {int watermode;} water; } drawmethod;
} s_layer;
typedef struct { s_layer layers[2]; } s_level;
static s_level object,*level=&object;
static s_sprite sprites[2],masks[2];
static s_screen screens[2];
static uint32_t obor_profile_build;
static char packfile[]="authored",*mode;
static char mask[16]="",*mask_argument=mask,*filename="base";
static int pixelformat=1,sprite_calls,screen_calls,shutdown_calls,active_layer,count;
static int requested;
static jmp_buf failure;
static void shutdown(int status,const char *format,...) {
    (void)status;(void)format;++shutdown_calls;longjmp(failure,1);
}
static s_sprite *loadsprite2(char *name,int *width,int *height) {
    ++sprite_calls;
    int mask=!strcmp(name,"mask");
    if((!mask&&!strcmp(mode,"missing_masked_base")) ||
       (mask&&!strcmp(mode,"missingmask")))return NULL;
    *width=80;*height=40;
    return mask?&masks[active_layer]:&sprites[active_layer];
}
static int loadscreen(char *name,char *pack,void *palette,int format,s_screen **out) {
    (void)name;(void)pack;(void)palette;(void)format;++screen_calls;
    if(!strcmp(mode,"missing")||!strcmp(mode,"missing_masked_base"))return 0;
    screens[active_layer]=(s_screen){80,40};*out=&screens[active_layer];return 1;
}
''' + body + r'''
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);mode=argv[2];
    count=!strcmp(mode,"twice")?2:1;
    if(!strcmp(mode,"mask")||!strcmp(mode,"maskwater")||!strcmp(mode,"maskalpha")||
       !strcmp(mode,"missingmask")||!strcmp(mode,"missing_masked_base")||
       !strcmp(mode,"twice"))strcpy(mask,"mask");
    requested=*mask!=0;
    if(!strcmp(mode,"nolevel"))level=NULL;
    if(!strcmp(mode,"null")){filename=NULL;mask_argument=NULL;}
    for(int i=0;i<2;++i) {
        object.layers[i].offset.x=7;object.layers[i].offset.z=11;
        if(!strcmp(mode,"alpha")||!strcmp(mode,"maskalpha")||
           !strcmp(mode,"wateralpha"))object.layers[i].drawmethod.alpha=1;
        if(!strcmp(mode,"trans"))object.layers[i].drawmethod.transbg=1;
        if(!strcmp(mode,"maskwater")||!strcmp(mode,"wateralpha"))
            object.layers[i].drawmethod.water.watermode=1;
        if(!strcmp(mode,"repeat")) {
            object.layers[i].drawmethod.xrepeat=-1;object.layers[i].drawmethod.yrepeat=-1;
        }
    }
    if(!setjmp(failure))
        for(int i=0;i<count;++i){active_layer=i;CALL}
    printf("{\"sprites\":%d,\"screens\":%d,\"error\":%d,\"mask\":%d,"
           "\"consumed\":%d,\"width\":%d,\"height\":%d,\"x\":%d,\"z\":%d,"
           "\"xrepeat\":%d,\"yrepeat\":%d,\"first\":%d,\"second\":%d}\n",
           sprite_calls,screen_calls,shutdown_calls,sprites[0].mask!=NULL,
           requested&&!mask[0],object.layers[0].size.x,object.layers[0].size.y,
           object.layers[0].offset.x,object.layers[0].offset.z,
           object.layers[0].drawmethod.xrepeat,object.layers[0].drawmethod.yrepeat,
           object.layers[0].gfx.handle!=NULL,object.layers[1].gfx.handle!=NULL);
    return 0;
}
'''.replace('CALL', call)


def level_commands_program(source, header):
    start = header.index('typedef enum levelCommand')
    end = header.index('} levelCommands;', start) + len('} levelCommands;')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t obor_profile_build;
typedef struct { const char *names[256];int count; } List;
static List storage;
static List *prepareList(void) {return &storage;}
static void List_InsertAfter(List *list,void *value,const char *name) {
    (void)value;if(list->count>=256)exit(91);list->names[list->count++]=name;
}
''' + header[start:end] + '\n' + function(source, 'createLevelCommandList') + r'''
static int contains(List *list,const char *name) {
    for(int i=0;i<list->count;++i)if(!strcmp(list->names[i],name))return 1;
    return 0;
}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    List *commands=createLevelCommandList();
    printf("{\"alpha\":%d,\"at\":%d,\"background\":%d,\"music\":%d,\"count\":%d}\n",
           contains(commands,"alphamask"),contains(commands,"at"),
           contains(commands,"background"),contains(commands,"music"),commands->count);
    return 0;
}
'''


def background_program(source):
    body = function(source, 'load_background')
    # Observe the actual loading branch before unrelated palette/UI updates.
    body = body[:body.index('    if(createtables)')] + '\n}\n'
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
enum { PIXEL_8=0,PIXEL_x8=1,PIXEL_32=2 };
typedef struct {int pixelformat;unsigned char palette[768];} s_screen;
static uint32_t obor_profile_build;
static int pixelformat,screenformat,indexed_ok,rgb_ok,error,ordinary_calls,rgb_calls;
static s_screen screen,*background;
static unsigned char pal[768],neontable[768];
static char *packfile="authored.pak";
#define PAL_BYTES 768
static jmp_buf escape;
static void unload_background(void) {background=NULL;}
static void shutdown(int status,const char *format,...) {(void)status;(void)format;error=1;longjmp(escape,1);}
static int loadscreen(char *name,char *pack,unsigned char *palette,int format,s_screen **out) {
    (void)name;(void)pack;(void)palette;++ordinary_calls;
    if(!indexed_ok)return 0;
    screen.pixelformat=format;memset(screen.palette,71,sizeof(screen.palette));*out=&screen;return 1;
}
static int loadscreen32(char *name,char *pack,s_screen **out) {
    (void)name;(void)pack;++rgb_calls;if(!rgb_ok)return 0;
    screen.pixelformat=PIXEL_32;*out=&screen;return 1;
}
''' + body + r'''
int main(int argc,char **argv) {
    if(argc!=6)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    pixelformat=atoi(argv[2]);screenformat=atoi(argv[3]);
    indexed_ok=atoi(argv[4]);rgb_ok=atoi(argv[5]);
    memset(pal,19,sizeof(pal));memset(neontable,23,sizeof(neontable));
    if(!setjmp(escape))load_background("authored",0);
    printf("{\"error\":%d,\"ordinary\":%d,\"rgb\":%d,\"format\":%d,\"pal\":%d,\"neon\":%d}\n",
           error,ordinary_calls,rgb_calls,background?background->pixelformat:-1,pal[7],neontable[7]);
    return 0;
}
'''


def scene_program(source):
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#define WEBM 1
#define MAX_ARG_LEN 1024
#define MAX_PLAYERS 4
#define stricmp strcasecmp
static uint32_t obor_profile_build;
typedef struct {char *values[8];int count;} ArgList;
static const char *scenario;
static char *currentScene;
static int music_calls,gif_calls,video_calls,silence_calls,video_skip,media_status;
static struct {int newkeys,playkeys;} player[MAX_PLAYERS];
static int buffer_pakfile(char *filename,char **out,size_t *size) {
    (void)filename;*size=strlen(scenario);*out=malloc(*size+1);memcpy(*out,scenario,*size+1);return 1;
}
static void ParseArgs(ArgList *args,const char *line,char *buffer) {
    size_t size=strcspn(line,"\n");memcpy(buffer,line,size);buffer[size]=0;args->count=0;
    for(char *word=strtok(buffer," ");word&&args->count<8;word=strtok(NULL," "))
        args->values[args->count++]=word;
}
#define GET_ARG(i) ((i)<arglist.count?arglist.values[(i)]:"")
#define GET_INT_ARG(i) atoi(GET_ARG(i))
static int getNewLineStart(const char *line) {size_t n=strcspn(line,"\n");return (int)(n+(line[n]=='\n'));}
static void music(const char *file,int loop,long offset) {(void)file;(void)loop;(void)offset;++music_calls;}
static void sound_close_music(void) {++silence_calls;}
static int playgif(char *file,int x,int y,int noskip) {(void)file;(void)x;(void)y;(void)noskip;++gif_calls;return 1;}
static int playwebm(const char *file,int noskip) {(void)file;++video_calls;video_skip=noskip;return media_status;}
static void shutdown(int status,const char *format,...) {(void)format;exit(status?status:91);}
''' + function(source, 'playscene') + r'''
int main(int argc,char **argv) {
    if(argc!=5)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    media_status=atoi(argv[2]);char text[512];
    snprintf(text,sizeof(text),"music before 0 0\nvideo authored.webm %d %d\nmusic after 0 0\nanimation authored.gif 0 0 0 0\nsilence\nunknown value\n",atoi(argv[3]),atoi(argv[4]));
    scenario=text;for(int i=0;i<MAX_PLAYERS;++i)player[i].newkeys=player[i].playkeys=7;
    playscene("authored-scene");
    int keys=0;for(int i=0;i<MAX_PLAYERS;++i)keys+=player[i].newkeys+player[i].playkeys;
    printf("{\"music\":%d,\"gif\":%d,\"video\":%d,\"silence\":%d,\"noskip\":%d,\"keys\":%d,\"scene_cleared\":%d}\n",
           music_calls,gif_calls,video_calls,silence_calls,video_skip,keys,currentScene==NULL);
    return 0;
}
'''


def collision_program(source):
    body = function(source, 'checkhit')
    structured = 's_hitbox coords1' in body
    shape = ('typedef struct {int x,y,width,height,z1,z2;} s_hitbox;\n'
             'typedef s_hitbox hitbox;\n' if structured else 'typedef int hitbox[6];\n')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define DIRECTION_LEFT 0
#define diff(a,b) fabsf((a)-(b))
''' + shape + r'''
typedef struct {hitbox attack_coords;int counterattack,attack_type;} attack;
typedef struct {hitbox *bbox_coords;attack **attacks;int *vulnerable;} animation;
typedef struct {float x,y,z;} position;
typedef struct entity {animation *animation;int animpos,direction;position position;struct {float grabdistance;} modeldata;} entity;
static struct {position position;int type,confirm;} lasthit;
''' + body + r'''
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    int mode=atoi(argv[2]);(void)argv[1];
    hitbox attacker_box,target_box;
    int a[6]={-8,-5,8,5,0,0},b[6]={-4,-4,4,4,0,0};
    if(mode==2){a[4]=-3;a[5]=9;b[4]=-2;b[5]=8;}
    if(mode==3){a[4]=6;b[4]=4;}
    memcpy(&attacker_box,a,sizeof(a));memcpy(&target_box,b,sizeof(b));
    attack aa={.counterattack=1,.attack_type=9},ta={.counterattack=0,.attack_type=7};
    memcpy(&aa.attack_coords,&attacker_box,sizeof(attacker_box));memcpy(&ta.attack_coords,&target_box,sizeof(target_box));
    attack *ap[1]={&aa},*tp[1]={&ta};int vulnerable[1]={1};
    animation an={&attacker_box,ap,vulnerable},tn={&target_box,tp,vulnerable};
    entity attacker={&an,0,mode%2,{10,2,12},{24}},target={&tn,0,(mode/2)%2,{12,2,12},{24}};
    if(mode==4)target.position.x=100;
    if(mode==5)target.position.z=100;
    if(mode==6)vulnerable[0]=0;
    if(mode==7)tn.attacks=NULL;
    if(mode==8)ta.counterattack=3;
    int result=checkhit(&attacker,mode==9?&attacker:&target,mode>=7);
    printf("{\"result\":%d,\"confirm\":%d,\"type\":%d,\"x\":%.3f,\"y\":%.3f,\"z\":%.3f}\n",
           result,lasthit.confirm,lasthit.type,lasthit.position.x,lasthit.position.y,lasthit.position.z);
    return 0;
}
'''


def png_bounds_program(source):
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
typedef size_t png_size_t;
typedef unsigned char *png_bytep;
typedef struct {void *input;} png_struct,*png_structp;
typedef struct {const unsigned char *data;size_t remaining;} obor_png_input;
static jmp_buf escape;
static int error;
static void *png_get_io_ptr(png_structp png) {return png->input;}
static void png_error(png_structp png,const char *message) {(void)png;(void)message;error=1;longjmp(escape,1);}
''' + function(source, 'png_read_fn') + r'''
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    unsigned char *data=malloc(2),out[4]={0};data[0]=17;data[1]=23;
    obor_png_input input={data,2};png_struct png={&input};
    if(!setjmp(escape))png_read_fn(&png,out,(size_t)atoi(argv[1]));
    printf("{\"error\":%d,\"first\":%d,\"remaining\":%zu}\n",error,out[0],input.remaining);
    free(data);return 0;
}
'''


def expression_program(source):
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
typedef struct {int unused;} pp_parser;
typedef struct {int value;} pp_expr;
static int source_value,destroyed;
static pp_expr *pp_expr_parse(pp_parser *parser,bool unused) {
    (void)parser;(void)unused;if(source_value==99)return NULL;
    pp_expr *expression=malloc(sizeof(*expression));expression->value=source_value;return expression;
}
static void pp_expr_fix_precedence(pp_expr *expression) {(void)expression;}
static int pp_expr_eval(pp_expr *expression) {return expression->value;}
static void pp_expr_destroy(pp_expr *expression) {++destroyed;free(expression);}
''' + function(source, 'pp_expr_eval_expression') + r'''
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    source_value=atoi(argv[1]);pp_parser parser={0};
    int result=pp_expr_eval_expression(&parser);
    printf("{\"result\":%d,\"destroyed\":%d}\n",result,destroyed);return 0;
}
'''


def keyboard_program(source):
    body = function(source, 'keyboard_setup')
    start = body.index('                    setting = selector;')
    body = body[start:body.index('\n                }', start)]
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static uint32_t obor_profile_build;
static int calls;
static struct {int keys[4][12];} savedata;
static int keyboard_getlastkey(void) {++calls;return 19;}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    int player=0,selector=3,setting=-1,ok=0;savedata.keys[0][3]=7;
''' + body + r'''
    printf("{\"calls\":%d,\"setting\":%d,\"old_key\":%d,\"new_key\":%d}\n",
           calls,setting,ok,savedata.keys[0][3]);return 0;
}
'''


def frame_boxes_program(source, header):
    structured = 'bbox_con.x =' in source
    if structured:
        end = header.index('} s_hitbox;') + len('} s_hitbox;')
        start = header.rfind('typedef struct', 0, end)
        shape = header[start:end] + '\ntypedef s_hitbox hitbox;\n'
        shape += '_Static_assert(sizeof(hitbox)==6*sizeof(int), "native hitbox size");\n'
        for index, name in enumerate(('x', 'y', 'width', 'height', 'z1', 'z2')):
            shape += '_Static_assert(offsetof(hitbox,%s)==%d*sizeof(int), "native field offset");\n' % (name, index)
    else:
        shape = 'typedef int hitbox[6];\n'
    model = function(source, 'load_cached_model')
    start = model.index('                bbox_con.x =' if structured else
                        '                bbox_con[0] =')
    frame = model[start:model.index('                if(platform[0]', start)]
    add = function(source, 'addframe')
    start = add.index('    if((bbox')
    store = add[start:add.index('    if(drawmethod->flag)', start)]
    signature = 'hitbox *bbox' if structured else 'int *bbox'
    call = '&bbox_con' if structured else 'bbox_con'
    return r'''
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
''' + shape + r'''
typedef struct {hitbox attack_coords;} s_attack;
typedef struct {hitbox *bbox_coords;s_attack **attacks;int vulnerable[1];} s_anim;
static void store_boxes(s_anim *a,SIGNATURE,s_attack *attack) {
    int currentframe=0,framecount=1;
'''.replace('SIGNATURE', signature) + store + r'''
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    (void)argv[1];int seed=atoi(argv[2]);
    int b[6]={seed-3,-5,seed+9,5,seed%3?3:-2,seed%2?8:-2};
    int a[6]={-7,2,7,10,0,0},offset[2]={seed-4,seed+2};
    hitbox bbox,bbox_con,abox;memcpy(&bbox,b,sizeof(b));memcpy(&abox,a,sizeof(a));
    if(seed==3){b[2]=0;memcpy(&bbox,b,sizeof(b));}
    s_attack attack;memcpy(&attack.attack_coords,b,sizeof(b));
''' + frame + r'''
    s_anim animation={0};store_boxes(&animation,CALL,&attack);
    int values[24];memcpy(values,&bbox,24);memcpy(values+6,&bbox_con,24);
    memcpy(values+12,&attack.attack_coords,24);
    if(animation.bbox_coords)memcpy(values+18,animation.bbox_coords,24);
    else memset(values+18,0,24);
    printf("{\"vulnerable\":%d,\"attack_stored\":%d,\"values\":[",animation.vulnerable[0],animation.attacks!=NULL);
    for(int i=0;i<24;++i)printf("%s%d",i?",":"",values[i]);
    puts("]}");
    free(animation.bbox_coords);
    if(animation.attacks){free(animation.attacks[0]);free(animation.attacks);}return 0;
}
'''.replace('CALL', call)


def menu_state_program(source):
    method = function(source, 'getsyspropertybyindex')
    start = method.index('    case _sv_in_menuscreen:')
    branch = method[start:method.index('\n    case ', start + 1)]
    return VARIANTS + r'''
static int selectScreen,titleScreen,hallOfFame,gameOver,showComplete,level;
static int currentScene,enginecreditsScreen,menuScreen=7;
enum {_sv_in_menuscreen=1};
static void query(ScriptVariant *var) {
    switch(_sv_in_menuscreen) {
''' + branch + r'''
    }
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);int flags=atoi(argv[2]);
    enginecreditsScreen=flags&1;selectScreen=flags&2;titleScreen=flags&4;currentScene=flags&8;
    ScriptVariant result={0};query(&result);
    printf("{\"type\":%d,\"value\":%ld}\n",result.vt,(long)result.lVal);return 0;
}
'''


def credits_program(source):
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef uint32_t u32;
static uint32_t obor_profile_build;
static u32 time;
static int bothnewkeys,fade,unloads,fades,frames;
static struct {int logo;} savedata;
static struct {int hRes,vRes,vShift;} videomodes={640,480,0};
#define GAME_SPEED 100
#define FLAG_START 1
#define FLAG_ESC 2
static struct {int x,y,font,color;char text[128];} calls[64];
static int count;
static int fontmonowidth(int font) {(void)font;return 8;}
#define _strmidx(font,text) ((videomodes.hRes-(int)strlen(text)*8)/2)
static void fade_out(int a,int b) {(void)a;(void)b;++fades;}
static void unload_level(void) {++unloads;}
static void update(int a,int b) {(void)a;(void)b;++frames;time+=10*GAME_SPEED+1;}
static void font_printf(int x,int y,int font,int color,const char *format,...) {
    if(count>=64)exit(90);
    calls[count].x=x;calls[count].y=y;calls[count].font=font;calls[count].color=color;
    va_list args;va_start(args,format);vsnprintf(calls[count].text,128,format,args);va_end(args);++count;
}
''' + function(source, 'display_credits') + r'''
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);savedata.logo=atoi(argv[2]);
    display_credits();
    printf("{\"unloads\":%d,\"fades\":%d,\"frames\":%d,\"fade\":%d,\"calls\":[",unloads,fades,frames,fade);
    for(int i=0;i<count;++i) {
        printf("%s[%d,%d,%d,%d,\"%s\"]",i?",":"",calls[i].x,calls[i].y,calls[i].font,calls[i].color,calls[i].text);
    }
    puts("]}");return 0;
}
'''


def credit_entry_program(source):
    method = function(source, 'shutdown')
    start = method.index('    savesettings();') + len('    savesettings();')
    branch = method[start:method.index('    if(!disablelog)', start)]
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static uint32_t obor_profile_build;
static int enginecreditsScreen,seen=-1,calls,startup_done;
static void term_videomodes(void) {}
static void display_credits(void) {seen=enginecreditsScreen;++calls;}
static void finish(int status) {
''' + branch + r'''
}
int main(int argc,char **argv) {
    if(argc!=4)return 2;
    obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    startup_done=atoi(argv[3]);finish(atoi(argv[2]));
    printf("{\"calls\":%d,\"seen\":%d,\"after\":%d}\n",calls,seen,enginecreditsScreen);return 0;
}
'''


def shutdown_format_program(source):
    method = function(source, 'shutdown')
    declaration = re.search(r'    char buf\[[0-9]+\] = "";', method)[0]
    start = method.index('    va_start(arglist, msg);')
    end = method.index('    va_end(arglist);', start) + len('    va_end(arglist);')
    return r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
static size_t observed;
static int last;
static void render(char *msg,...) {
''' + declaration + '\n    va_list arglist;\n' + method[start:end] + r'''
    observed=strlen(buf);last=observed?(unsigned char)buf[observed-1]:0;
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    (void)argv[1];int mode=atoi(argv[2]);char text[4097];
    if(mode==0)render("native %d",17);
    else {
        size_t length=mode==1?1023:mode==2?2046:4096;
        memset(text,mode==2?'%':'a',length);text[length]=0;render(text);
    }
    printf("{\"length\":%zu,\"last\":%d}\n",observed,last);return 0;
}
'''


def compile_program(program, output, sanitizers=True, extra_flags=()):
    output = Path(output)
    source = output.with_suffix('.c')
    source.write_text(program)
    flags = ['-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
             '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-parameter',
             '-Wno-unused-but-set-variable',
             '-Wno-deprecated-declarations', '-Wno-int-to-pointer-cast']
    if sanitizers:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    if sys.platform == 'linux':
        flags += ['-fno-pie', '-no-pie']
    compiler = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
    subprocess.run([*compiler, *flags, str(source), '-o', str(output), *extra_flags],
                   check=True, timeout=60)
