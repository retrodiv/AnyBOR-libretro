"""Observe native attack sound defaults and hitfx command parsing.

The native argument reader, macro and command branch remain intact. Sample
loading records path/context and returns the independently supplied result;
complete audio decoding, model loading and playback have separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from native_header_fixtures import graphics_refusals, inline_refusals


def render_attack_sound(parts, *, revision, cases, unused_graphics_inlines=False,
                        unused_inline_declarations=None, sample_log=0):
    basic={'parse_args','argument_macro','attack_default','hitfx_case'}
    companions={'diesound_case','sound_case','blockfx_case'}
    if (not isinstance(parts,dict) or set(parts) not in (basic,basic|companions) or
            any(not isinstance(v,str) or not v.strip() or len(v)>32768 for v in parts.values()) or
            not re.search(r'\bcase\s+CMD_MODEL_HITFX\s*:',parts['hitfx_case'])):
        raise ValueError('Complete bounded native argument reader, default and hitfx branch required')
    if type(revision) is not int or not 0<revision<=0xffffffff:
        raise ValueError('Explicit native profile required')
    if type(sample_log) is not int or sample_log not in (0,1):
        raise ValueError('Explicit native sample diagnostic flag required')
    if not isinstance(cases,list) or not 1<=len(cases)<=128:
        raise ValueError('Bounded independently expected native sound cases required')
    rows=[]
    for case in cases:
        names={'line','argc','default_sample','load_result','expected_default','expected_sound','load_calls','path'}
        if not isinstance(case,dict) or set(case) not in (names,names|{'command'}):
            raise ValueError('Complete independent parser/default/sample expectations required')
        command=case.get('command','hitfx')
        if command not in ('hitfx','diesound','sound','blockfx') or (
                command!='hitfx' and set(parts)!=basic|companions):
            raise ValueError('Complete native command branches required for each selected command')
        bounds=dict(argc=(1,2),default_sample=(-1,15),load_result=(-1,15),
                    expected_default=(-1,15),expected_sound=(-1,15),load_calls=(0,1))
        if (any(type(case[k]) is not int or not a<=case[k]<=b for k,(a,b) in bounds.items()) or
                not isinstance(case['line'],str) or not case['line'].isascii() or
                not 0<len(case['line'])<120 or any(c in case['line'] for c in '\0\r\n') or
                not re.match(r'^'+command+r'(?:\s|$)',case['line']) or
                not isinstance(case['path'],str) or not case['path'].isascii() or len(case['path'])>80 or
                any(c in case['path'] for c in '\0\r\n') or
                (case['load_calls']==0 and case['path']!='')):
            raise ValueError('Bounded native sound command, callback path and values required')
        rows.append('{CMD_MODEL_'+command.upper()+','+json.dumps(case['line'])+','+
                    ','.join(str(case[k]) for k in bounds)+','+json.dumps(case['path'])+'}')
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include "openbor.h"
#include "commands.h"
#ifndef stricmp
#define stricmp strcasecmp
#endif
#undef printf
#undef assert
#ifdef NDEBUG
#error Native attack sound assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native attack sound mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
static s_attack attack;
s_attack emptyattack;
static s_model fixture_model,*newchar=&fixture_model;
static int soundtoplay;
int SAMPLE_BEAT;
char packfile[4096]="native-contract";
static int load_result,load_calls;
static char loaded_path[128];
int sound_load_sample(char *name,char *pak,int log){
 assert(name && pak==packfile && log==@SAMPLE_LOG@ && strlen(name)<sizeof(loaded_path));
 assert(load_calls==0);++load_calls;strcpy(loaded_path,name);return load_result;
}
@ARGUMENT_MACRO@
@PARSE_ARGS@
static void reset_attack(void){
 @ATTACK_DEFAULT@
}
static void command_under_test(ArgList arglist,int command){
 switch(command){
 @HITFX_CASE@
 @COMPANION_CASES@
 }
}
struct sound_case {int command;const char *line;int argc,default_sample,load_result,expected_default,expected_sound,load_calls;const char *path;};
static const struct sound_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct sound_case *test=&tests[active_case];
  memset(&attack,0,sizeof(attack));memset(&emptyattack,0,sizeof(emptyattack));
  emptyattack.attack_force=13;emptyattack.pain_time=3;
  SAMPLE_BEAT=test->default_sample;reset_attack();
  assert(attack.hitsound==test->expected_default && attack.attack_force==13 && attack.pain_time==3);
  memset(&fixture_model,0,sizeof(fixture_model));newchar->diesound=-3;
  soundtoplay=-4;attack.blocksound=-2;
  char input[MAX_ARG_LEN],output[MAX_ARG_LEN];ArgList arguments;
  assert(strlen(test->line)<sizeof(input));strcpy(input,test->line);
  memset(output,0,sizeof(output));memset(&arguments,0,sizeof(arguments));
  ParseArgs(&arguments,input,output);assert(arguments.count==(size_t)test->argc);
  load_calls=0;loaded_path[0]='\0';load_result=test->load_result;
  command_under_test(arguments,test->command);
  assert(attack.hitsound==(test->command==CMD_MODEL_HITFX?test->expected_sound:test->expected_default));
  assert(attack.blocksound==(test->command==CMD_MODEL_BLOCKFX?test->expected_sound:-2));
  assert(newchar->diesound==(test->command==CMD_MODEL_DIESOUND?test->expected_sound:-3));
  assert(soundtoplay==(test->command==CMD_MODEL_SOUND?test->expected_sound:-4));
  assert(load_calls==test->load_calls);
  assert(!strcmp(loaded_path,test->path));
  assert(attack.attack_force==13 && attack.pain_time==3);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values=dict(REVISION=str(revision)+'u',CASES=',\n'.join(rows),SAMPLE_LOG=str(sample_log),
                COMPANION_CASES='\n'.join(parts[k] for k in sorted(companions)) if companions<=set(parts) else '',
                GRAPHICS=graphics_refusals(unused_graphics_inlines),
                REFUSALS=inline_refusals(unused_inline_declarations,
                    forbidden_names=('ParseArgs','command_under_test','reset_attack','sound_load_sample')),
                ARGUMENT_MACRO=parts['argument_macro'],PARSE_ARGS=parts['parse_args'],
                ATTACK_DEFAULT=parts['attack_default'],HITFX_CASE=parts['hitfx_case'])
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
