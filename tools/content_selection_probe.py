"""Compile the actual Auto decision without linking or executing an engine.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
from pathlib import Path
import re
import subprocess

def compile_probe(glue, header, includes, third_party, output, sanitizers=False):
    inputs = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in {glue, header, *includes.glob('*.h'), third_party/'libretro.h'}}
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
#include "obor_legacy_api.h"
#define PATH_SEP '/'
PROFILES
FALLBACK
static char g_pak_path[4096],g_engine[48],g_logical_engine[48],g_selection_error[160];
static bool g_raw;
static bool environment(unsigned,void *) {return false;}
static retro_environment_t env_cb=environment;
static void get_engine_option(char *out,size_t n) {snprintf(out,n,"Auto");}
static void log_cb(int,const char *format,...) {
 va_list ap;va_start(ap,format);vprintf(format,ap);va_end(ap);
}
DETECTION
DECISION
int main(int argc,char **argv) {
#ifdef OBOR_CONTENT_CONTRACTS_H
 if(argc==2&&!strcmp(argv[1],"--rules")) {
  for(size_t i=0;i<sizeof(kContentContracts)/sizeof(*kContentContracts);++i) {
   const obor_contract_rule *r=&kContentContracts[i];
   printf("%u %d %s %d %d %u\n",(unsigned)i,(int)r->kind,r->name,r->lower,r->upper,r->flags);
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
 if(argc!=2||strlen(argv[1])>=sizeof(g_pak_path))return 2;
 strcpy(g_pak_path,argv[1]);decide_engine();
 printf("selection_profile=%s selection_engine=%s\n",g_logical_engine,g_engine);
 return *g_logical_engine?0:3;
}
'''
    for key, value in [('PROFILES', profiles), ('FALLBACK', fallback),
                       ('DETECTION', detection), ('DECISION', decision)]:
        program = program.replace(key, value)
    cpp = output.with_suffix('.cpp')
    cpp.write_text(program)
    extra = ['-g', '-fsanitize=address,undefined'] if sanitizers else []
    subprocess.run(['c++', '-std=c++11', '-O2', '-Wall', '-Wextra', '-Werror', *extra,
                    '-Wno-unused-function', '-I', str(includes), '-I', str(third_party),
                    str(cpp), '-o', str(output)], check=True, timeout=60)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in inputs.items())
    return inputs

