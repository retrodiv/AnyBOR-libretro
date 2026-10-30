"""Check source-owned image failure routes and controlled assertion handoff.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement, continued_macro


def render_image_failures(engine, port, fixture, *, assertions_enabled=True):
    rows = fixture['sources']
    if (not 1 <= len(rows) <= 128 or len({r['revision'] for r in rows}) != len(rows) or
            any(type(r['revision']) is not int or not 0 < r['revision'] <= 0xffffffff or
                len(r['screen_lines']) != 2 or
                any(type(v) is not int or not 0 <= v < 1000000
                    for v in [*r['screen_lines'], r['panel_assert_line']]) or
                any(type(r[k]) is not bool for k in ('panel_log', 'panel_arguments_alias'))
                for r in rows)):
        raise ValueError('Bounded unique source-owned image failure contexts required')
    source = (engine / 'openbor.c').read_text()
    image = (engine / 'source/gamelib/loadimg.c').read_text()
    level = function(source, 'load_level')
    declaration = re.search(r'char legacy_level_error\[(\d+)\][^;]*;', level)
    if declaration is None or int(declaration[1]) != 1024:
        raise ValueError('Actual bounded level diagnostic storage required')
    entries = ',\n'.join('{%d,%d,%d,%d,%d,%d}' % (
        r['revision'], *r['screen_lines'], r['panel_assert_line'],
        r['panel_log'], r['panel_arguments_alias']) for r in rows)
    code = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef shutdown
#undef time
#undef pause
#undef printf
#undef assert
static unsigned phase,scenario;uint32_t obor_profile_build;
static void failed(int line,const char *condition){
 fprintf(stderr,"image failures profile=%u phase=%u scenario=%u line=%d: %s\n",
         obor_profile_build,phase,scenario,line,condition);abort();
}
#define CHECK(c) do{if(!(c))failed(__LINE__,#c);}while(0)
#define assert(c) CHECK(c)
static int engine_alive,engine_exit_status,stopped,frontend_token;
static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static unsigned diagnostics,flushes,preload_ends,panel_frees;
static char diagnostic[1024],message[2048],panel_log[512];
static void co_switch(void *target){
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==1);
 if(phase==2)CHECK(panel_frees==1);
 ++stopped;longjmp(frontend_return,1);
}
static int capture_fprintf(FILE *file,const char *format,...){
 CHECK(file==stderr);va_list args;va_start(args,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 CHECK(n>=0&&(size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static int capture_fflush(FILE *file){CHECK(file==stderr);++flushes;return 0;}
#define fprintf capture_fprintf
#define fflush capture_fflush
@STOP@
@ASSERT@
#undef fprintf
#undef fflush
@CONFIG@
@LOCATION@
static unsigned opens,closes,allocations,reads,screen_frees;
static int res[2]={2,2};static unsigned char own_palette[1024],external_palette[1024];
static unsigned char *used_palette;static s_screen *current_screen;
static s_screen *make_screen(void){
 s_screen *s=calloc(1,sizeof(*s)+4);CHECK(s);s->width=2;s->height=2;
 s->pixelformat=1;s->palette=own_palette;return s;
}
s_screen *allocscreen(int width,int height,int format){
 CHECK(width==2&&height==2&&format==1);++allocations;
 return scenario==1?NULL:make_screen();
}
void freescreen(s_screen **screen){
 CHECK(screen&&*screen);++screen_frees;free(*screen);*screen=NULL;
}
int openimage(char *filename,char *packfile){
 CHECK(!strcmp(filename,"image")&&!strcmp(packfile,"pack"));++opens;return scenario!=0;
}
void closeimage(void){++closes;}
int readimage(unsigned char *pixels,unsigned char *palette,int width,int height){
 CHECK(pixels&&palette&&width==2&&height==2);++reads;used_palette=palette;
 memcpy(pixels,"\x03\x05\x07\x09",4);return scenario!=2;
}
@SCREEN@
@ARGS@
@MACRO@
static int capture_printf(const char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(panel_log,sizeof(panel_log),format,args);
 va_end(args);CHECK(n>=0&&(size_t)n<sizeof(panel_log));return n;
}
int loadpanel(char *normal,char *neon,char *screen){
 CHECK(normal&&neon&&screen);
 CHECK(!strcmp(normal,"normal")&&!strcmp(neon,"neon")&&!strcmp(screen,"screen"));
 return scenario==0;
}
static uintptr_t panel_owned;
static void panel_free(void *p){CHECK((uintptr_t)p==panel_owned&&!panel_frees);++panel_frees;free(p);}
void obor_preload_end(void){++preload_ends;}
static void probe_shutdown(int status,char *format,...){
 CHECK(panel_frees==1);va_list args;va_start(args,format);
 int n=vsnprintf(message,sizeof(message),format,args);va_end(args);
 CHECK(n>=0&&(size_t)n<sizeof(message));borExit(status);
}
@ERROR_HELPER@
@ERROR_MACRO@
#define printf capture_printf
#define free panel_free
#define shutdown probe_shutdown
static void panel_window(void){
 char *buf=strdup("panel normal neon screen\n");CHECK(buf);panel_owned=(uintptr_t)buf;
 char *filename="data/level.txt";int line=7;
 ArgList arglist;char output[MAX_ARG_LEN];ParseArgs(&arglist,buf,output);
 char *errormessage=NULL;unsigned obor_panel_assert=0;@DECLARATION@
 @PANEL@
 @FOOTER@
#undef shutdown
#undef free
#undef printf
struct context {unsigned revision;int allocation_line,decode_line,panel_line,log,alias;};
static const struct context contexts[]={@CONTEXTS@};
static void reset(void){
 engine_alive=1;engine_exit_status=-1;stopped=0;diagnostics=flushes=preload_ends=panel_frees=0;
 diagnostic[0]=message[0]=panel_log[0]=0;
}
static void check_diagnostic(const char *file,const char *func,int line){
 char want[1024];snprintf(want,sizeof(want),"%s:%d: %s: Assertion %c0' failed.\n",file,line,func,96);
 CHECK(diagnostics==1&&flushes==1&&!strcmp(diagnostic,want)&&!message[0]);
}
static void check(const struct context *ctx){
 obor_profile_build=ctx->revision;phase=1;
 for(scenario=0;scenario<5;++scenario){
  reset();opens=closes=allocations=reads=screen_frees=0;used_palette=NULL;
  current_screen=(scenario==0||scenario==4)?make_screen():NULL;
  if(!setjmp(frontend_return)){
   int result=loadscreen("image","pack",scenario==4?external_palette:NULL,1,&current_screen);
   CHECK(result==(scenario>=3));
  }
  int line=scenario==1?ctx->allocation_line:scenario==2?ctx->decode_line:0;
  int fatal=@ENABLED@&&line;
  CHECK(stopped==!!fatal&&engine_alive==!fatal&&engine_exit_status==(fatal?1:-1));
  CHECK(opens==1&&closes==(scenario!=0)&&allocations==(scenario!=0)&&reads==(scenario>=2));
  CHECK(screen_frees==(scenario==0||scenario==2||scenario==4));
  if(fatal)check_diagnostic("source/gamelib/loadimg.c","loadscreen",line);
  else CHECK(!diagnostics&&!flushes&&!diagnostic[0]&&!message[0]);
  if(scenario>=3){CHECK(current_screen&&!memcmp(current_screen->data,"\x03\x05\x07\x09",4));
   CHECK(used_palette==(scenario==4?external_palette:own_palette));freescreen(&current_screen);}
  CHECK(!current_screen);
 }
 phase=2;
 for(scenario=0;scenario<2;++scenario){
  reset();if(!setjmp(frontend_return))panel_window();
  int assertion=scenario&&ctx->panel_line&&@ENABLED@;
  int formatted=scenario&&!ctx->panel_line;
  int fatal=assertion||formatted;
  CHECK(stopped==fatal&&engine_alive==!fatal&&engine_exit_status==(fatal?1:-1));
  CHECK(panel_frees==1&&preload_ends==!fatal);
  if(assertion)check_diagnostic("openbor.c","load_level",ctx->panel_line);
  else CHECK(!diagnostics&&!flushes&&!diagnostic[0]);
  if(formatted){
   CHECK(!strcmp(message,ctx->revision<3253?"Panel load error in 'data/level.txt'!":
    "ERROR: load_level, file data/level.txt, line 7, message: Panel load error!"));
  }else CHECK(!message[0]);
  if(scenario&&ctx->log){
   if(ctx->alias)CHECK(!strcmp(panel_log,"loadpanel :normal :normal :normal failed\n")||
                       !strcmp(panel_log,"loadpanel :neon :neon :neon failed\n")||
                       !strcmp(panel_log,"loadpanel :screen :screen :screen failed\n"));
   else CHECK(!strcmp(panel_log,"loadpanel :normal :neon :screen failed\n"));
  }else CHECK(!panel_log[0]);
 }
}
int main(void){for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r)check(&contexts[r]);
 puts("image_failures=1");return 0;}
'''
    values = dict(STOP=function(port.read_text(), 'borExit'),
                  ASSERT=function(port.read_text(), 'obor_port_assert'),
                  CONFIG='#undef NDEBUG' if assertions_enabled else '#define NDEBUG 1',
                  LOCATION=(engine / 'source/gamelib/obor_image_assert.h').read_text(),
                  SCREEN=function(image, 'loadscreen'),
                  ARGS='\n'.join(function(source, n) for n in ('ParseArgs', 'findarg', 'obor_legacy_arg')),
                  MACRO=re.search(r'(?m)^#define GET_ARG\(z\)[^\n]*', source).group(),
                  ERROR_HELPER=function(source, 'obor_level_error'),
                  ERROR_MACRO=continued_macro(source, 'OBOR_LEVEL_ERROR'),
                  DECLARATION=declaration.group(), PANEL=braced_statement(level, 'if(!loadpanel('),
                  FOOTER=level[level.rindex('lCleanup:'):], CONTEXTS=entries,
                  ENABLED='1' if assertions_enabled else '0')
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
