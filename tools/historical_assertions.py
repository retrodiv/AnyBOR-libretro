"""Render historical invariant diagnostics and controlled engine termination.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from test_historical_player import function


def render_assertions(engine, legacy_engine, port, fixture, *, assertions_enabled=True):
    source = (engine / 'openbor.c').read_text()
    old_source = (legacy_engine / 'openbor.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    globals_header = (engine / 'source/globals.h').read_text()
    header = (port / 'libretroport.h').read_text()
    first = header.index('#if defined(OBOR_ENGINE_BUILD) && OBOR_ENGINE_BUILD < 3811')
    legacy_macro = header[first:header.index('#endif\n#endif', first) + len('#endif\n#endif')]
    first = globals_header.index('#undef assert')
    macros = globals_header[first:globals_header.index('\n\n', first)]

    def debug_block(text):
        body = function(text, 'shutdown')
        first = body.index('#ifdef DEBUG') + len('#ifdef DEBUG')
        return body[first:body.index('#endif', first)].strip()

    checks = '\n'.join('obor_profile_build=%d;check(%d,%d);' % (
        row['revision'], row['engine'] != '3842', row['diagnostic_style'] == 'logged_assert')
        for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
@CONFIG@
static uint32_t obor_profile_build;
static unsigned cases;
static int phase,value;
static void failed(int line){
 fprintf(stderr,"assertion profile=%u phase=%d value=%d line=%d\n",obor_profile_build,phase,value,line);
 exit(91);
}
#define CHECK(c) do {if(!(c))failed(__LINE__);}while(0)
static jmp_buf escaped;
static int predicate_calls,engine_alive,engine_exit_status,switched,logs,diagnostics,flushes,host_aborts;
static void *co_frontend=(void*)(uintptr_t)123;
static char log_text[1024],diagnostic[512];
static void co_switch(void *target){CHECK(target==co_frontend);++switched;longjmp(escaped,1);}
static void writeToLogFile(const char *format,...){
 va_list args;va_start(args,format);size_t n=strlen(log_text);
 int wrote=vsnprintf(log_text+n,sizeof(log_text)-n,format,args);va_end(args);
 CHECK(wrote>=0 && (size_t)wrote<sizeof(log_text)-n);++logs;
}
static int capture_fprintf(FILE *file,const char *format,...){
 CHECK(file==stderr);va_list args;va_start(args,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static int capture_fflush(FILE *file){CHECK(file==stderr);++flushes;return 0;}
static void capture_abort(void){++host_aborts;longjmp(escaped,2);}
#define fprintf capture_fprintf
#define fflush capture_fflush
#define abort capture_abort
@STOP@
@LEGACY_STOP@
#define exit borExit
@EXIT@
@ABORT@
#undef exit
#undef abort
#undef fprintf
#undef fflush
static int probe_value(void){++predicate_calls;return value;}
#define OBOR_CONTROLLED_ASSERTIONS 1
#define OBOR_ENGINE_BUILD 3741
@LEGACY_MACRO@
static void legacy_statement(void){
#line 100 "profile-assert.c"
 assert(probe_value());
}
static void legacy_debug_statement(int status){
 (void)status;
#line 200 "profile-assert.c"
 @LEGACY_DEBUG@
}
#undef OBOR_ENGINE_BUILD
#undef OBOR_CONTROLLED_ASSERTIONS
@MACROS@
static void assertion_statement(void){
#line 400 "profile-assert.c"
 assert(probe_value());
}
static void debug_statement(int status){
#line 300 "profile-assert.c"
 @DEBUG@
}
static void check(int old_engine,int logged){
 (void)capture_abort;
 for(phase=0;phase<2;++phase)for(value=0;value<2;++value){
  predicate_calls=logs=diagnostics=flushes=host_aborts=switched=0;
  log_text[0]=diagnostic[0]=0;engine_alive=1;engine_exit_status=-1;
  int enabled=1;
#ifdef NDEBUG
  if(!logged)enabled=0;
#endif
  int jump=setjmp(escaped);
  if(!jump){
   if(!phase){if(old_engine)legacy_statement();else assertion_statement();}
   else {if(old_engine)legacy_debug_statement(value?0:1);else debug_statement(value?0:1);}
  }
  int refusal=enabled && !value;
  CHECK(jump==(refusal?1:0) && !host_aborts && switched==refusal);
  CHECK(engine_alive==!refusal && engine_exit_status==(refusal?1:-1));
  CHECK(predicate_calls==(!phase && enabled));
  if(!refusal){CHECK(!logs && !diagnostics && !flushes && !*log_text && !*diagnostic);}
  else {
   const char *func=phase?(old_engine?"legacy_debug_statement":"debug_statement"):
                        (old_engine?"legacy_statement":"assertion_statement");
   int line=phase?(old_engine?200:logged?301:300):(old_engine?100:400);
   const char *expression=phase?"status == 0":"probe_value()";
   char expected[1024];
   if(logged && !phase){
    snprintf(expected,sizeof(expected),"\n\n********** An Error Occurred **********"
       "\n*            Shutting Down            *\n\n"
       "Assertion `%s' failed in function '%s' at profile-assert.c:%i.\n"
       "This is an OpenBOR bug.  Please report this at www.chronocrash.com.\n\n",expression,func,line);
    CHECK(logs==3 && !diagnostics && !flushes && !strcmp(log_text,expected));
   }else{
    snprintf(expected,sizeof(expected),"profile-assert.c:%i: %s: Assertion `%s' failed.\n",line,func,expression);
    CHECK(!logs && diagnostics==1 && flushes==1 && !strcmp(diagnostic,expected));
   }
  }
  ++cases;
 }
}
int main(void){@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;}
'''.replace('@CONFIG@', '#undef NDEBUG' if assertions_enabled else '#define NDEBUG 1').replace('@STOP@', function((port / 'libretroport.c').read_text(), 'borExit')).replace(
        '@LEGACY_STOP@', function((port / 'libretroport.c').read_text(), 'obor_port_assert')).replace(
        '@EXIT@', function(utils, 'exitIfFalse')).replace('@ABORT@', function(utils, 'abortIfFalse')).replace(
        '@LEGACY_MACRO@', legacy_macro).replace('@MACROS@', macros).replace(
        '@LEGACY_DEBUG@', debug_block(old_source)).replace('@DEBUG@', debug_block(source)).replace('@CHECKS@', checks)


def render_late_assertions(port, fixture, *, assertions_enabled=True):
    """Exercise the actual release include wrapper after another assertion header."""
    checks = '\n'.join('obor_profile_build=%d;check();' % row['revision']
                       for row in fixture['sources'])
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#include <assert.h>
static uint32_t obor_profile_build;
static unsigned cases;
static int value;
static void failed(int line){fprintf(stderr,"late assertion profile=%u value=%d line=%d\n",obor_profile_build,value,line);exit(91);}
#define CHECK(c) do {if(!(c))failed(__LINE__);}while(0)
static jmp_buf escaped;
static int calls,engine_alive,engine_exit_status,switched,diagnostics,flushes;
static void *co_frontend=(void*)(uintptr_t)123;
static char diagnostic[512];
static void co_switch(void *target){CHECK(target==co_frontend);++switched;longjmp(escaped,1);}
static int capture_fprintf(FILE *file,const char *format,...){
 CHECK(file==stderr);va_list args;va_start(args,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static int capture_fflush(FILE *file){CHECK(file==stderr);++flushes;return 0;}
#define fprintf capture_fprintf
#define fflush capture_fflush
@STOP@
@ASSERT@
#undef fprintf
#undef fflush
static int condition(void){++calls;return value;}
@CONFIG@
#define OBOR_CONTROLLED_ASSERTIONS 1
/* This real include must reset a previously defined assertion macro. */
#undef assert
#define assert(x) CHECK(0)
#include <assert.h>
static void invoke(void){
#line 500 "profile-late-assert.c"
 assert(condition());
}
static void check(void){
 for(value=0;value<2;++value){
  calls=switched=diagnostics=flushes=0;diagnostic[0]=0;
  engine_alive=1;engine_exit_status=-1;
  int enabled=1;
#ifdef NDEBUG
  enabled=0;
#endif
  int jump=setjmp(escaped);if(!jump)invoke();
  int refusal=enabled && !value;
  CHECK(jump==refusal && switched==refusal && calls==enabled);
  CHECK(engine_alive==!refusal && engine_exit_status==(refusal?1:-1));
  CHECK(diagnostics==refusal && flushes==refusal);
  CHECK(!strcmp(diagnostic,refusal?"profile-late-assert.c:500: invoke: Assertion `condition()' failed.\n":""));
  ++cases;
 }
}
int main(void){(void)condition;@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;}
'''.replace('@STOP@', function((port / 'libretroport.c').read_text(), 'borExit')).replace(
        '@ASSERT@', function((port / 'libretroport.c').read_text(), 'obor_port_assert')).replace(
        '@CONFIG@', '#undef NDEBUG' if assertions_enabled else '#define NDEBUG 1').replace('@CHECKS@', checks)
