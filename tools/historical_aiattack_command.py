"""Render native AI attack command parsing, updates and diagnostics.

The command branch, optional helper, argument macros and parser are native
source inputs. A bounded observer records diagnostics and stops a native fatal
load before the rest of a model load; complete loading remains separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from native_header_fixtures import graphics_refusals, inline_refusals


def render_aiattack_command(parts, *, revision, cases,
                             unused_graphics_inlines=False,
                             unused_inline_declarations=None):
    names = {'parse_args', 'argument_macros', 'command_case', 'loader'}
    if (not isinstance(parts, dict) or set(parts) != names or
            any(not isinstance(v, str) or len(v) > 65536 or
                (key != 'loader' and not v.strip()) for key, v in parts.items()) or
            not re.search(r'\bcase\s+CMD_MODEL_AIATTACK\s*:', parts['command_case'])):
        raise ValueError('Complete bounded parser, argument macros and native command required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit native revision required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 1024:
        raise ValueError('Bounded independent command cases required')
    entries = []
    for case in cases:
        names = {'line', 'argc', 'before', 'set_before', 'after', 'set_after',
                 'diagnostic', 'fatal', 'message'}
        if not isinstance(case, dict) or set(case) != names:
            raise ValueError('Complete parser, state and diagnostic expectations required')
        line, message = case['line'], case['message']
        if (not isinstance(line, str) or not line.isascii() or not 0 < len(line) < 128 or
                any(c in line for c in ('\0', '\n', '\r')) or
                not re.match(r'^\s*aiattack(?:\s|$)', line, re.I) or
                not isinstance(message, str) or not message.isascii() or
                len(message) > 255 or '\0' in message or
                any(type(case[key]) is not int or not 0 <= case[key] <= 0xffffffff
                    for key in ('before', 'after')) or
                any(type(case[key]) is not int or case[key] not in (0, 1)
                    for key in ('set_before', 'set_after', 'diagnostic', 'fatal')) or
                type(case['argc']) is not int or not 1 <= case['argc'] <= 16 or
                case['diagnostic'] + case['fatal'] > 1 or
                bool(message) != bool(case['diagnostic'] + case['fatal'])):
            raise ValueError('Bounded native arguments, flags and diagnostic text required')
        entries.append('{%s,%d,%du,%d,%du,%d,%d,%d,%s}' % (
            json.dumps(line), case['argc'], case['before'], case['set_before'],
            case['after'], case['set_after'], case['diagnostic'], case['fatal'],
            json.dumps(message)))
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <setjmp.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#ifndef stricmp
#define stricmp strcasecmp
#endif
#ifndef strnicmp
#define strnicmp strncasecmp
#endif
#undef assert
#undef printf
#undef shutdown
#ifdef NDEBUG
#error Native command assertions must remain enabled
#endif
static const char *phase="initial";
static unsigned active_case;
#define assert(c) do {if(!(c)) {fprintf(stderr,"Native AI command mismatch: %s case=%u\n",phase,active_case);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@GRAPHICS@
@REFUSALS@
static s_model model;
static int aiattackset;
static unsigned diagnostics,fatal;
static char message[256];
static jmp_buf stopped;
static int observed_printf(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(message,sizeof(message),format,args);
 va_end(args);assert(n>=0 && (size_t)n<sizeof(message));++diagnostics;return n;
}
static void observed_shutdown(int status,const char *format,...) {
 assert(status==1);va_list args;va_start(args,format);
 int n=vsnprintf(message,sizeof(message),format,args);va_end(args);
 assert(n>=0 && (size_t)n<sizeof(message));++fatal;longjmp(stopped,1);
}
#define printf observed_printf
#define shutdown observed_shutdown
@ARGUMENT_MACROS@
@PARSE_ARGS@
@LOADER@
static void command_under_test(ArgList arglist) {
 s_model *newchar=&model;char *filename="native-model";
 switch(CMD_MODEL_AIATTACK) {
 @COMMAND@
 }
}
static void stopped_command(ArgList arguments) {
 if(setjmp(stopped)==0)command_under_test(arguments);
}
#undef printf
#undef shutdown
struct command_case {
 const char *line;unsigned argc;uint32_t before;int set_before;
 uint32_t after;int set_after;unsigned diagnostic,fatal;const char *message;
};
static const struct command_case cases[]={@CASES@};
int main(void) {
 for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);++i) {
  active_case=i;const struct command_case *test=&cases[i];
  memset(&model,0,sizeof(model));model.aiattack=test->before;aiattackset=test->set_before;
  diagnostics=fatal=0;message[0]=0;
  char input[MAX_ARG_LEN],output[MAX_ARG_LEN];ArgList arguments;
  assert(strlen(test->line)<sizeof(input));strcpy(input,test->line);
  memset(output,0,sizeof(output));memset(&arguments,0,sizeof(arguments));
  phase="parse";ParseArgs(&arguments,input,output);assert(arguments.count==test->argc);
  phase="native command";
  stopped_command(arguments);
  phase="flags";assert((uint32_t)model.aiattack==test->after);
  assert(aiattackset==test->set_after);
  phase="diagnostics";assert(diagnostics==test->diagnostic && fatal==test->fatal);
  assert(!strcmp(message,test->message));
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",(unsigned)(sizeof(cases)/sizeof(*cases)));return 0;
}
'''
    values = dict(REVISION=str(revision),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=('ParseArgs', 'lcmHandleCommandAiattack')),
        ARGUMENT_MACROS=parts['argument_macros'], PARSE_ARGS=parts['parse_args'],
        LOADER=parts['loader'], COMMAND=parts['command_case'], CASES=',\n'.join(entries))
    for name, value in values.items():
        code = code.replace('@' + name + '@', value)
    return code
