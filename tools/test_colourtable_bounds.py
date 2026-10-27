"""Check every engine/profile's colourtable case and native palette helper.

The actual case body executes with numeric variants and a reduced model. These
tests establish valid pointer results and bounded malformed queries, not full
callback mapping, native model layout, bitmap loading or gameplay acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/colourtable-engine-contracts.json').read_text())


def read_source(path):
    return path.read_bytes().decode('utf-8', 'surrogateescape')


def engine_fragments(engine):
    root=SOURCE/'src/engines'/engine
    row=FIXTURE['engines'][engine]
    _, cases=switch_cases(read_source(root/'openborscript.c'),
                         'openbor_getentityproperty',row['selector'])
    return {'case':cases[row['case']]['body'],
        'helper':'' if row['fixed_storage'] else
            function(read_source(root/'openbor.c'),'model_get_colourmap')}


def bounds_program(engine, fragments=None, *, original=False):
    row=FIXTURE['engines'][engine]
    fragments=engine_fragments(engine) if fragments is None else fragments
    table='unsigned char *colourmap[30];' if row['fixed_storage'] else 'unsigned char **colourmap;'
    counter='char maps_loaded:8;' if engine=='3400' else 'int maps_loaded:8;' if engine=='3741' else 'int maps_loaded;'
    program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
typedef int32_t LONG;
typedef void VOID;
enum {VT_EMPTY=0,VT_INTEGER=1,VT_PTR=5};
typedef struct {int vt;union {LONG lVal;void *ptrVal;};} ScriptVariant;
typedef struct {@TABLE@ @COUNTER@ unsigned char *palette;unsigned colourmap_capacity;} s_model;
typedef struct {s_model modeldata;} entity;
#define MAX_COLOUR_MAPS 30
static uint32_t obor_profile_build;
static entity subject;
static unsigned char base_palette[1],colours[3];
static void ScriptVariant_ChangeType(ScriptVariant *value,int type) {value->vt=type;}
@HELPER@
static int has_table(const s_model *model) {
#if @FIXED@
 (void)model;return 1;
#else
 return model->colourmap!=NULL;
#endif
}
static ScriptVariant query(LONG index,int paramCount) {
 (void)paramCount;entity *ent=&subject;LONG ltemp=0;
 ScriptVariant value={.vt=VT_INTEGER,.lVal=index},*varlist[]={NULL,NULL,&value};
 ScriptVariant result={.vt=VT_EMPTY,.ptrVal=NULL},*output=&result,**pretvar=&output;
 switch(0) {case 0:@CASE@}
 return result;
}
static void check(int mode,unsigned extent,LONG index,int count) {
 unsigned char *expected=NULL;unsigned which=(unsigned)index+1u;
 int defined=count>=3;
 if(mode==2) {
  if(index==INT32_MAX) defined=0;
  if(which==0 || which>(unsigned)subject.modeldata.maps_loaded) expected=subject.modeldata.palette;
  else if(which>extent || !has_table(&subject.modeldata)) defined=0;
  else expected=subject.modeldata.colourmap[which-1];
 } else if(index<0 || (unsigned)index>=extent) defined=0;
 else expected=subject.modeldata.colourmap[index];
#if !@GENERATED@
 if(!defined) return;
#else
 if(!defined && !(mode==2 && (which==0 || which>(unsigned)subject.modeldata.maps_loaded))) expected=NULL;
#endif
 ScriptVariant result=query(index,count);
 if(count<3) assert(result.vt==VT_EMPTY);
 else {assert(result.vt==VT_PTR);assert(result.ptrVal==expected);}
}
static void run(unsigned revision,int mode) {
 obor_profile_build=revision;subject=(entity){0};subject.modeldata.palette=base_palette;
 unsigned extent=mode==0?30:3;
#if !@FIXED@
 subject.modeldata.colourmap=calloc(extent,sizeof(*subject.modeldata.colourmap));assert(subject.modeldata.colourmap);
#endif
 subject.modeldata.maps_loaded=3;subject.modeldata.colourmap_capacity=extent;
 for(int i=0;i<3;++i) subject.modeldata.colourmap[i]=&colours[i];
 for(int palette_present=0;palette_present<2;++palette_present) {
  subject.modeldata.palette=palette_present?base_palette:NULL;
  for(int loaded=0;loaded<=3;++loaded) {
   subject.modeldata.maps_loaded=loaded;
   for(LONG i=-2;i<=(LONG)extent+1;++i) check(mode,extent,i,3);
   check(mode,extent,INT32_MIN,3);check(mode,extent,INT32_MAX-1,3);check(mode,extent,INT32_MAX,3);
  }
 }
 subject.modeldata.palette=base_palette;subject.modeldata.maps_loaded=3;
#if @GENERATED@
 check(mode,extent,0,2);
#if !@FIXED@
 assert(model_get_colourmap(NULL,1)==NULL);
 unsigned char **saved=subject.modeldata.colourmap;subject.modeldata.colourmap=NULL;
 assert(model_get_colourmap(&subject.modeldata,0)==base_palette);
 assert(model_get_colourmap(&subject.modeldata,1)==NULL);subject.modeldata.colourmap=saved;
#endif
#endif
#if !@FIXED@
 free(subject.modeldata.colourmap);
#endif
}
int main(int argc,char **argv) {
 assert(argc==3);run((unsigned)strtoul(argv[1],NULL,10),atoi(argv[2]));return 0;
}
'''
    if original:
        mode=0 if row['fixed_storage'] else 2
        program=program[:program.index('int main(int argc,char **argv)')]+(
            'int main(void) {run('+engine+','+str(mode)+');puts('+json.dumps(json.dumps({
                'status':'PASS','engine':engine,'mode':mode})) + ');return 0;}\n')
    insertions={'TABLE':table,'COUNTER':counter,'HELPER':fragments['helper'],
        'CASE':fragments['case'],'GENERATED':str(int(not original)),
        'FIXED':str(int(row['fixed_storage']))}
    return re.sub(r'@('+'|'.join(insertions)+r')@',lambda m:insertions[m[1]],program)


class ColourtableBoundsTests(unittest.TestCase):
    def test_engine_registry_matches_every_registered_engine(self):
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        self.assertEqual(set(FIXTURE['engines']),{x['build'] for x in pin['engines']})
        for engine,row in FIXTURE['engines'].items():
            self.assertEqual(row['integer_bits'],32)
            self.assertRegex(row['original_case_sha256'],r'^[0-9a-f]{64}$')
            if engine!='3400':self.assertRegex(row['original_helper_sha256'],r'^[0-9a-f]{64}$')

    def test_valid_results_and_defined_bounds_for_each_registered_profile(self):
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        historical=json.loads((Path(__file__).parent/'fixtures/profile-colourtable-read-contracts.json').read_text())
        modes={x['revision']:{'fixed_table':0,'dynamic_table':1,'helper':2}[x['getter_mode']]
               for x in historical['sources']}
        executed=[]
        with tempfile.TemporaryDirectory(prefix='anybor-colourtable-bounds-') as temporary:
            work=Path(temporary)
            for engine in FIXTURE['engines']:
                with self.subTest(engine=engine):
                    source=work/(engine+'.c');exe=work/engine
                    source.write_bytes(bounds_program(engine).encode('utf-8','surrogateescape'))
                    subprocess.run(shlex.split(os.environ.get('HOST_CC','cc'))+[
                        '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                        '-Wno-unused-variable','-Wno-unused-function','-Wno-sign-compare','-fsigned-char',
                        '-g','-fsanitize=address,undefined',str(source),'-o',str(exe)],check=True,timeout=60)
                    for profile in pin['profiles']:
                        if profile['engine']!=engine:continue
                        revision=int(profile.get('revision',profile['build']))
                        mode=0 if engine=='3400' else modes[revision] if engine=='3741' else 2
                        subprocess.run([str(exe),str(revision),str(mode)],check=True,
                            timeout=20,env=sanitizer_environment());executed.append(profile['build'])
        self.assertCountEqual(executed,[x['build'] for x in pin['profiles']])
        print(json.dumps({'executed_profiles':executed,'scope':'Actual colourtable case/helper; reduced numeric fixture'}))


if __name__=='__main__':
    unittest.main()
