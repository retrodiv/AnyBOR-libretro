"""Check drawing methods inside real entity and layer arrays on every engine.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from native_sanitizers import sanitizer_environment

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/drawmethod-alignment.json'


def program(shape):
    fields={'entity_size','entity_alignment','method_size','method_alignment',
            'entity_method_offset','layer_size','layer_method_offset','entity_embedded'}
    if (not isinstance(shape,dict) or set(shape)!=fields or
            type(shape.get('entity_embedded')) is not bool or
            any(type(v) is not int or not 0<=v<=1<<20 for k,v in shape.items() if k!='entity_embedded') or
            any(shape[k]<=0 for k in ['entity_size','entity_alignment','method_size','method_alignment']) or
            shape['method_alignment'] not in (1,2,4,8,16)):
        raise ValueError('Explicit bounded native drawing-record representation required')
    checks=''
    for record,field,expected in [('entity','',shape['entity_size']),('s_drawmethod','',shape['method_size'])]:
        checks+='_Static_assert(sizeof('+record+')=='+str(expected)+',"Preserve native record extent");\n'
    checks+='_Static_assert(_Alignof(entity)=='+str(shape['entity_alignment'])+',"Preserve owner alignment");\n'
    checks+='_Static_assert(_Alignof(s_drawmethod)=='+str(shape['method_alignment'])+',"Safe embedded alignment");\n'
    checks+='_Static_assert(offsetof(entity,drawmethod)=='+str(shape['entity_method_offset'])+',"Preserve method offset");\n'
    if shape['entity_embedded']:
        checks+='_Static_assert(_Alignof(entity)>=_Alignof(s_drawmethod),"Owner must align its method");\n'
        checks+='_Static_assert(sizeof(((entity*)0)->drawmethod)==sizeof(s_drawmethod),"Embedded method required");\n'
        owners='''entity *owners=calloc(2,sizeof(*owners));assert(owners);
 for(int i=0;i<2;++i){set_table(&owners[i].drawmethod,markers+i);assert(owners[i].drawmethod.table==markers+i);}
 free(owners);'''
    else:
        checks+='_Static_assert(sizeof(((entity*)0)->drawmethod)==sizeof(s_drawmethod*),"Method pointer required");\n'
        owners='''entity *owners=calloc(2,sizeof(*owners));s_drawmethod *methods=calloc(2,sizeof(*methods));
 assert(owners && methods);
 for(int i=0;i<2;++i){owners[i].drawmethod=methods+i;set_table(owners[i].drawmethod,markers+i);assert(methods[i].table==markers+i);}
 free(methods);free(owners);'''
    layers=''
    if shape['layer_size']:
        checks+='_Static_assert(sizeof(s_layer)=='+str(shape['layer_size'])+' && offsetof(s_layer,drawmethod)=='+str(shape['layer_method_offset'])+',"Preserve layer representation");\n'
        checks+='_Static_assert(_Alignof(s_layer)>=_Alignof(s_drawmethod),"Layer must align its method");\n'
        layers='''s_layer *layers=calloc(2,sizeof(*layers));assert(layers);
 for(int i=0;i<2;++i){set_table(&layers[i].drawmethod,markers+i);assert(layers[i].drawmethod.table==markers+i);}
 free(layers);'''
    return r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "openbor.h"
/* Owned layout fixtures use libc, not the engine allocator. */
#undef calloc
#undef free
#undef assert
#define assert(c) do {if(!(c)){fputs("Drawing record assertion failed\n",stderr);abort();}}while(0)
#ifdef NDEBUG
#error Drawing alignment assertions must remain enabled
#endif
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@CHECKS@
static __attribute__((noinline)) void set_table(s_drawmethod *method,unsigned char *value){method->table=value;}
int main(void){
 unsigned char markers[2]={1,2};
 @OWNERS@
 @LAYERS@
 puts("{\"status\":\"PASS\"}");return 0;
}
'''.replace('@CHECKS@',checks).replace('@LAYERS@',layers).replace('@OWNERS@',owners)


class DrawmethodAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FIXTURE.read_text());cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-drawing-alignment-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        for row in cls.pin['engines']:
            engine=row['build'];root=SOURCE/'src/engines'/engine
            includes=[root,SOURCE/'src/glue',SOURCE/'src/port/libretro',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source=work/(engine+'.c');executable=source.with_suffix('')
            source.write_text(program(cls.fixture['shapes'][engine]))
            result=subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',*warnings,
                '-O1','-g','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,*host,
                '-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all',str(source),*links,'-o',str(executable)],
                capture_output=True,text=True,timeout=45)
            if result.stdout:sys.stderr.write(result.stdout)
            if result.stderr:sys.stderr.write(result.stderr)
            if result.returncode:raise RuntimeError('Drawing-record alignment compilation failed')
            cls.executables[engine]=executable

    def check_engine(self,engine):
        observed=subprocess.check_output([str(self.executables[engine])],text=True,timeout=10,
                                         env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS'))

    def test_each_physical_engine_preserves_record_extents_and_aligned_access(self):
        for row in self.pin['engines']:
            with self.subTest(engine=row['build']):self.check_engine(row['build'])

    def test_each_registered_profile_uses_safe_drawing_records(self):
        for profile in self.pin['profiles']:
            with self.subTest(profile=profile['build']):self.check_engine(profile['engine'])


if __name__=='__main__':unittest.main()
