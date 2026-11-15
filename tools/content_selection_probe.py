"""Compile the actual Auto decision without linking or executing an engine.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import os
import shlex
from pathlib import Path
import re
import subprocess

def compile_probe(glue, header, includes, third_party, output, sanitizers=False):
    inputs = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in {glue, header, *includes.glob('*.h'), includes/'anybor_transform_vm.c',
                        includes/'anybor_transform_source.c', third_party/'libretro.h'}}
    source = glue.read_text()
    definitions = header.read_text()
    start = definitions.index('typedef struct { int build; const char *name; const char *disp;')
    profiles = definitions[start:definitions.index('\n};', start) + 3]
    fallback = next(s for s in definitions.splitlines() if s.startswith('#define OBOR_FALLBACK_BUILD '))
    start = source.index('/* Sparse (commit date -> build)')
    detection = source[start:source.index('/* ------------------------------------------------------- core options', start)]
    start = source.index('static void decide_engine(void)\n{')
    decision = source[start:source.index('/* mkdir -p:', start)]
    program = r'''
#include <ctype.h>
#include <limits.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libretro.h"
#include "anybor_legacy_api.h"
#define PATH_SEP '/'
PROFILES
FALLBACK
static char g_pak_path[4096],g_engine[48],g_logical_engine[48],g_selection_error[160];
static char g_engine_source_path[4096];
static bool g_raw;
static bool g_engine_error_context,g_engine_log_fresh;
static const char *system_dir, *manual="Auto";
static bool environment(unsigned command,void *data) {
 if(command==RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY) {*(const char **)data=system_dir;return system_dir!=NULL;}
 return false;
}
static void mkdir_p(const char *) {}
static retro_environment_t env_cb=environment;
static void get_engine_option(char *out,size_t n) {snprintf(out,n,"%s",manual);}
static void log_cb(int,const char *format,...) {
 va_list ap;va_start(ap,format);vprintf(format,ap);va_end(ap);
}
DETECTION
DECISION
int main(int argc,char **argv) {
#ifdef OBOR_CONTENT_CONTRACTS_H
 if(argc==5&&!strcmp(argv[1],"--inspect-contracts")) {
  int profile=atoi(argv[3]),engine=atoi(argv[4]);
  g_content_triage=true;build_from_content(argv[2]);
  printf("{\"complete\":%s,\"script_bindings_ambiguous\":%s,\"lower\":%d,\"upper\":%d,\"facts\":[",
         g_content_scan_complete?"true":"false",g_contract_scripts_ambiguous?"true":"false",
         g_content_lower,g_content_upper);
  bool comma=false;
  for(size_t i=0;i<sizeof(kContentContracts)/sizeof(*kContentContracts);++i) {
   if(!content_contract_active(i))continue;
   const obor_contract_rule *r=&kContentContracts[i];
   printf("%s{\"name\":\"%s\",\"kind\":%d,\"supported\":%s}",comma?",":"",r->name,
          (int)r->kind,content_contract_allows(r,profile,engine)?"true":"false");
   comma=true;
  }
  puts("]}");return 0;
 }
 if(argc==2&&!strcmp(argv[1],"--rules")) {
  for(size_t i=0;i<sizeof(kContentContracts)/sizeof(*kContentContracts);++i) {
   const obor_contract_rule *r=&kContentContracts[i];
#ifdef OBOR_CONTENT_CONTRACT_GAPS
   printf("%u %d %s %d %d %u %d %d\n",(unsigned)i,(int)r->kind,r->name,r->lower,r->upper,r->flags,r->gap_lower,r->gap_upper);
#else
   printf("%u %d %s %d %d %u 0 0\n",(unsigned)i,(int)r->kind,r->name,r->lower,r->upper,r->flags);
#endif
  }
  return 0;
 }
 if(argc==5&&!strcmp(argv[1],"--rule-probe")) {
  unsigned id=(unsigned)atoi(argv[2]);
  if(id>=sizeof(kContentContracts)/sizeof(*kContentContracts))return 2;
  printf("%d\n",content_contract_allows(&kContentContracts[id],atoi(argv[3]),atoi(argv[4])));
  return 0;
 }
#endif
 if((argc==6||argc==8)&&!strcmp(argv[1],"--external")) {
  system_dir=argv[3];manual=argv[4];
  snprintf(g_content_choice.source,sizeof(g_content_choice.source),"%s",argv[2]);
  snprintf(g_content_choice.engine,sizeof(g_content_choice.engine),"%s",argv[5]);
  snprintf(g_content_choice.descriptor,sizeof(g_content_choice.descriptor),"synthetic.anybor");
  if(argc==8) {
   snprintf(g_content_choice.archive,sizeof(g_content_choice.archive),"%s",argv[6]);
   snprintf(g_content_choice.zip_engine,sizeof(g_content_choice.zip_engine),"%s",argv[7]);
   snprintf(g_content_choice.zip_descriptor,sizeof(g_content_choice.zip_descriptor),"inside.anybor");
  }
  argv[1]=argv[2];argc=2;
 }
 if(argc!=2||strlen(argv[1])>=sizeof(g_pak_path))return 2;
 strcpy(g_pak_path,argv[1]);decide_engine();
 printf("selection_profile=%s selection_engine=%s error=%s\n",g_logical_engine,g_engine,g_selection_error);
 return *g_logical_engine?0:3;
}
'''
    for key, value in [('PROFILES', profiles), ('FALLBACK', fallback),
                       ('DETECTION', detection), ('DECISION', decision)]:
        program = program.replace(key, value)
    cpp = output.with_suffix('.cpp')
    cpp.write_text(program)
    extra = ['-g', '-fsanitize=address,undefined'] if sanitizers else []
    objects = []
    for name in ('anybor_transform_vm', 'anybor_transform_source'):
        obj = output.with_name(output.name + '-' + name + '.o')
        subprocess.run([*shlex.split(os.environ.get('HOST_CC', 'cc')), '-std=gnu99', '-O2', *extra,
                        '-c', str(includes / (name + '.c')), '-o', str(obj)], check=True, timeout=60)
        objects.append(str(obj))
    subprocess.run([*shlex.split(os.environ.get('HOST_CXX', 'c++')), '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror', *extra,
                    '-Wno-unused-function', '-I', str(includes), '-I', str(third_party),
                    str(cpp), *objects, '-o', str(output)], check=True, timeout=60)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in inputs.items())
    return inputs

