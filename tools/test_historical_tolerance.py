"""Exercise historical preprocessor and setter rejection boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from test_historical_player import function
from native_sanitizers import sanitizer_environment
from historical_text_objects import CALLBACKS, render_text_objects
from historical_stringmap_dispatch import render_dispatch
from test_color_blends import compile_checked

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
ENGINE = SOURCE / 'src/engines/3842'
DRAFT = Path(os.environ['OBOR_TOLERANCE_DRAFT']) if 'OBOR_TOLERANCE_DRAFT' in os.environ else None

def native(name):
    return (DRAFT / name if DRAFT else ENGINE / name).read_text()

class HistoricalToleranceTests(unittest.TestCase):
    def test_actual_level_and_text_setters(self):
        source = native('openborscript.c')
        start=source.index('enum levelproperty_enum')
        declarations=source[start:source.index('void mapstrings_levelproperty',start)]
        start=source.index('enum drawmethod_enum')
        declarations+=source[start:source.index('};',start)+2]
        methods='\n'.join(function(source,n) for n in (
            'mapstrings_levelproperty','mapstrings_drawmethodproperty',
            'openbor_changelevelproperty','mapstrings_textobjproperty',
            'mapstrings_changetextobjproperty',
            'obor_textobj_index','obor_textobj_store','obor_textobj_format',
            'openbor_changetextobjproperty','openbor_settextobj','openbor_cleartextobj'))
        program=r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
typedef int HRESULT;
typedef long LONG;
typedef double DOUBLE;
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
#define MAX_STR_VAR_LEN 63
enum {VT_EMPTY,VT_INTEGER,VT_DECIMAL,VT_STR,VT_PTR};
typedef struct {int vt; LONG lVal; DOUBLE dblVal; const char *strVal; void *ptrVal;} ScriptVariant;
static uint32_t obor_profile_build;
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *r) {
    if(v->vt==VT_INTEGER) {*r=v->lVal;return S_OK;}
    if(v->vt==VT_DECIMAL) {*r=(LONG)v->dblVal;return S_OK;}
    *r=123456;return E_FAIL; /* Exercise converters that clobber output on failure. */
}
static int ScriptVariant_DecimalValue(ScriptVariant *v,DOUBLE *r) {
    if(v->vt==VT_DECIMAL) {*r=v->dblVal;return S_OK;}
    if(v->vt==VT_INTEGER) {*r=v->lVal;return S_OK;}
    return E_FAIL;
}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {
    if(v->vt!=type){v->vt=type;v->lVal=0;}
}
static void ScriptVariant_ToString(ScriptVariant *v,char *b) {
    if(v->vt==VT_STR) strcpy(b,v->strVal);else strcpy(b,"<invalid>");
}
#define StrCache_Get(x) (x)
#define StrCache_GetIfPresent(x) (x)
#define MAPSTRINGS(VAR,LIST,COUNT,MESSAGE) do { \
 if((VAR)->vt==VT_STR) {for(prop=0;prop<(COUNT);prop++) \
 if(!strcmp((VAR)->strVal,(LIST)[prop])) break; \
 if(prop<(COUNT)) {ScriptVariant_ChangeType(VAR,VT_INTEGER);(VAR)->lVal=prop;} } \
 (void)propname; } while(0)
#define __reallocto(P,OLD,N) do {assert((N)<16); \
 (P)=realloc((P),(N)*sizeof(*(P)));assert(P); \
 memset((P)+(OLD),0,((N)-(OLD))*sizeof(*(P)));} while(0)
typedef struct {int font,t,x,y,z;char *text;} Text;
typedef Text s_textobj;
typedef struct {int rocking,type,cameraxoffset,camerazoffset,quake;
 float bgspeed,scrollspeed,gravity,maxfallspeed,maxtossspeed;
 int numholes,numwalls,numtextobjs;float (*holes)[7],(*walls)[8];Text *textobjs;} Level;
static Level storage,*level=&storage;
enum {_top_font,_top_text,_top_time,_top_x,_top_y,_top_z,_top_the_end};

'''+declarations+methods+r'''
static ScriptVariant integer(LONG v) {return (ScriptVariant){.vt=VT_INTEGER,.lVal=v};}
static ScriptVariant string(const char *v) {return (ScriptVariant){.vt=VT_STR,.strVal=v};}
static ScriptVariant literal_level(const char *text) {
 ScriptVariant value=string(text),*args[]={&value};
 mapstrings_levelproperty(args,1);return value;
}
static void reset(void) {
 for(int i=0;i<storage.numtextobjs;i++) free(storage.textobjs[i].text);
 free(storage.textobjs);free(storage.holes);free(storage.walls);memset(&storage,0,sizeof(storage));
 storage.numtextobjs=1;storage.textobjs=calloc(1,sizeof(Text));assert(storage.textobjs);
 storage.textobjs[0]=(Text){.font=4,.t=99,.x=11,.y=12,.z=13};storage.quake=5;
}
static void exercise(unsigned profile) {
 obor_profile_build=profile;reset();
 ScriptVariant a[10],result,*out,*v[10];for(int i=0;i<10;i++){a[i]=integer(0);v[i]=a+i;}
 /* The pre3820 implementation preserved the caller's return type, setting lVal=0 on rejection. */
 a[0]=literal_level("quake");a[1]=(ScriptVariant){.vt=VT_EMPTY};result=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changelevelproperty(v,&out,2)==(profile<3820?S_OK:E_FAIL));
 assert(storage.quake==5);assert(profile<3820 ? out==&result&&result.vt==VT_EMPTY&&result.lVal==0 : out==NULL);
 a[0]=literal_level("quake");a[1]=integer(17);result=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changelevelproperty(v,&out,2)==S_OK&&storage.quake==17);
 assert(profile<3820?out==&result&&result.vt==VT_EMPTY:out==NULL);
 /* Real union/cache-index behavior of computed strings has its own probe. */
 a[0]=integer(999);out=&result;assert(openbor_changelevelproperty(v,&out,2)==E_FAIL&&out==NULL);
 /* Numeric and compiled textual wall selectors agree across the inserted type property. */
 a[0]=literal_level("wall");a[1]=integer(0);a[2]=integer(2);a[3]=integer(77);out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==S_OK&&storage.walls[0][2]==77);
 LONG wall=profile<3820?10:11;assert(a[0].lVal==wall);
 a[0]=integer(wall);a[3]=integer(88);out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==S_OK&&storage.walls[0][2]==88);
 a[0]=literal_level("hole");a[1]=integer(0);a[2]=integer(1);a[3]=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==(profile<3820?S_OK:E_FAIL));assert(storage.holes[0][1]==0);
 a[0]=integer(0);out=&result;assert(openbor_changelevelproperty(v,&out,1)==E_FAIL&&out==NULL);
 /* Negative text indices are harmless zero-success only before3821. */
 a[0]=integer(-1);a[1]=integer(_top_x);a[2]=integer(21);out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==(profile<3821?S_OK:E_FAIL));
 assert(profile<3821?out==&result&&result.vt==VT_INTEGER&&result.lVal==0:out==NULL);
 a[0]=integer(0);a[1]=integer(_top_x);a[2]=(ScriptVariant){.vt=VT_EMPTY};result=integer(77);out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==(profile<3821?S_OK:E_FAIL));assert(storage.textobjs[0].x==11);
 assert(profile<3821?out==&result&&result.lVal==77:out==NULL);
 a[2]=integer(21);out=&result;assert(openbor_changetextobjproperty(v,&out,3)==S_OK&&storage.textobjs[0].x==21);
 assert(profile<3821?out==&result&&result.lVal==1:out==NULL);
 a[1]=integer(1234);out=&result;assert(openbor_changetextobjproperty(v,&out,3)==E_FAIL&&out==NULL);
 a[0]=integer(-1);out=&result;assert(openbor_settextobj(v,&out,6)==(profile<3821?S_OK:E_FAIL));
 a[0]=integer(0);a[1]=(ScriptVariant){.vt=VT_EMPTY};a[2]=integer(32);a[3]=integer(8);a[4]=integer(33);a[5]=string("test");a[6]=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_settextobj(v,&out,7)==(profile<3821?S_OK:E_FAIL));
 assert(storage.textobjs[0].x==21&&storage.textobjs[0].t==99);
 if(profile<3821) {assert(out==&result&&result.lVal==1&&storage.textobjs[0].y==32);assert(!strcmp(storage.textobjs[0].text,"test"));}
 else assert(out==NULL&&storage.textobjs[0].y==12);
 a[1]=integer(31);out=&result;assert(openbor_settextobj(v,&out,6)==S_OK&&storage.textobjs[0].x==31);
 assert(storage.textobjs[0].t==(profile<3821?99:0));
 a[0]=(ScriptVariant){.vt=VT_EMPTY};out=&result;assert(openbor_settextobj(v,&out,6)==E_FAIL&&out==NULL);
 /* Before3821, valid coordinates were committed even if the later text failed. */
 a[0]=integer(0);a[1]=integer(47);a[2]=integer(48);a[3]=integer(9);a[4]=integer(49);
 a[5]=(ScriptVariant){.vt=VT_EMPTY};a[6]=integer(111);out=&result;
 int prior_time=storage.textobjs[0].t;
 assert(openbor_settextobj(v,&out,7)==(profile<3821?E_FAIL:S_OK));
 assert(storage.textobjs[0].x==47 && storage.textobjs[0].y==48);
 assert(storage.textobjs[0].t==(profile<3821?prior_time:111));
 assert(out==NULL);
 if(profile<3821)assert(result.vt==VT_INTEGER&&result.lVal==1);
 /* Replacing the same text owns one buffer; old profiles still require text. */
 a[1]=string("text");a[2]=string("replacement");out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==S_OK);
 char *owned=storage.textobjs[0].text;
 a[1]=string("text");a[2]=string("again");out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==S_OK && storage.textobjs[0].text==owned);
 assert(!strcmp(owned,"again"));
 a[1]=string("text");a[2]=integer(17);out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==(profile<3821?E_FAIL:S_OK));
 assert(profile<3821 ? !strcmp(owned,"again") : !strcmp(owned,"17"));
 /* A valid older clear preserves an existing integer; outside indices return zero. */
 for(int index=-1;index<=1;++index) {
   a[0]=integer(index);result=integer(77);out=&result;
   assert(openbor_cleartextobj(v,&out,1)==S_OK);
   assert(profile<3821 ? out==&result&&result.vt==VT_INTEGER&&result.lVal==(index==0?77:0) : out==NULL);
 }
 assert(storage.textobjs[0].text==NULL && storage.textobjs[0].x==0);
 printf("tolerance_profile=%u level_boundary=3820 text_boundary=3821 passed\n",profile);
}
int main(void) {
 const unsigned profiles[]={3780,3783,3789,3793,3797,3801,3802,3805,3814,3818,3819,3820,3821,3822,3824,3829,3831,3837,3839,3842};
 for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);i++)exercise(profiles[i]);
 reset();free(storage.textobjs);return 0;
}
'''
        self.compile_run(program, [])

    def compile_run(self, program, extra):
        with tempfile.TemporaryDirectory(prefix='historical-tolerance-') as name:
            work=Path(name);src=work/'test.c';src.write_text(program);binary=work/'test'
            link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
            command=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))+['-std=gnu99','-O1','-g','-fcommon','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),*extra,*link,'-o',str(binary)]
            result=subprocess.run(command,text=True,capture_output=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(binary)],text=True,capture_output=True,timeout=20,env=sanitizer_environment())
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout,flush=True)

    def test_actual_preprocessor_reserved_names_and_expansion(self):
        # Compile the complete actual lexer/parser/expression/list path, with its standalone IO stubs.
        with tempfile.TemporaryDirectory(prefix='historical-pp-source-') as name:
            parser=Path(name)/'pp_parser.c';parser.write_text(native('pp_parser.c' if DRAFT else 'source/preprocessorlib/pp_parser.c'))
            program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "pp_parser.h"
uint32_t obor_profile_build;
char *get_full_path(char *filename) {return filename;}
void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line) {
 (void)assertion;(void)func;(void)file;(void)line;if(!value)abort();
}
static void check(unsigned profile,char *source,int accepted,const char *wanted) {
 pp_context context;pp_parser parser;pp_token *token;TEXTPOS start={1,0};
 obor_profile_build=profile;pp_context_init(&context);pp_parser_init(&parser,&context,"fixture.c",source,start);
 int eof=0;char output[2048]={0};
 while((token=pp_parser_emit_token(&parser))) {
  if(token->theType==PP_TOKEN_EOF){eof=1;break;}
  assert(strlen(output)+strlen(token->theSource)<sizeof(output));strcat(output,token->theSource);
 }
 assert(eof==accepted);
 if(accepted&&wanted)assert(strstr(output,wanted));
 pp_context_destroy(&context);
}
int main(void) {
 const unsigned profiles[]={3761,3769,3773,3780,3783,3789,3793,3797,3801,3802,3805,3814,3818,3822,3824,3829,3831,3837,3839,3842};
 for(unsigned i=0;i<sizeof(profiles)/sizeof(*profiles);i++) {
  unsigned p=profiles[i];
  check(p,"#define __LINE__ 77\n__LINE__\n",p<3802,p<3802?"77":NULL);
  check(p,"#define __FILE__ 88\n__FILE__\n",p<3802,p<3802?"88":NULL);
  check(p,"#undef __DATE__\n#define __DATE__ 99\n__DATE__\n",p<3802,p<3802?"99":NULL);
  check(p,"#define defined 55\ndefined\n",p<3802,"55");
  check(p,"#define regular 17\nregular\n",1,"17");
  check(p,"#ifdef \"unterminated\nTOKEN\n#endif\n",0,NULL);
 }
 return 0;
}
'''
            script=ENGINE/'source/scriptlib';pp=ENGINE/'source/preprocessorlib'
            extra=['-DPP_TEST=1','-DSAFEALLOC_H=1','-Dstricmp=strcasecmp','-Dstrnicmp=strncasecmp','-I',str(script),'-I',str(pp),'-I',str(ENGINE/'source'),'-I',str(ENGINE/'source/gamelib'),'-I',str(SOURCE/'src/port/libretro'),str(parser),str(DRAFT/'lexers/3842/pp_lexer.c' if DRAFT else pp/'pp_lexer.c'),str(pp/'pp_expr.c'),str(script/'List.c')]
            self.compile_run(program,extra)

    def test_actual_preprocessor_conditionals_and_function_macros(self):
        fixture=json.loads((Path(__file__).parent /
            'fixtures/profile-preprocessor-contracts.json').read_text())
        rows=fixture['sources']
        revisions={row['revision'] for row in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        checks=[]
        for row in rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            for digest in row['functions'].values():
                self.assertRegex(digest,r'^[0-9a-f]{64}$')
            for index,case in enumerate(fixture['scenarios']):
                expected=case['legacy' if row['legacy'] else 'modern']
                checks.append('check(%d,%d,%s,%d,%s,%s,%d);' % (
                    row['revision'],index,json.dumps(case['source']),expected['accepted'],
                    json.dumps(expected['tokens']),json.dumps(expected['diagnostic']),
                    expected['newlines']))
        program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "pp_parser.h"
uint32_t obor_profile_build;
char *get_full_path(char *filename) {return filename;}
void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line) {
 (void)assertion;(void)func;(void)file;(void)line;if(!value)abort();
}
static unsigned scenario;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Preprocessor revision=%u case=%u line=%d\n",obor_profile_build,scenario,__LINE__);abort();}}while(0)
static void check(unsigned profile,unsigned which,const char *input,int accepted,
                  const char *wanted,const char *diagnostic,int wanted_lines) {
 obor_profile_build=profile;scenario=which;
 pp_context context;pp_parser parser;pp_token *token;TEXTPOS start={1,0};
 char *source=strdup(input);assert(source);
 FILE *messages=tmpfile();assert(messages);fflush(stderr);
 int saved=dup(STDERR_FILENO);assert(saved>=0);assert(dup2(fileno(messages),STDERR_FILENO)>=0);
 pp_context_init(&context);pp_parser_init(&parser,&context,"fixture.c",source,start);
 int eof=0,lines=0,steps=0;char output[2048]={0};
 while((token=pp_parser_emit_token(&parser))) {
  assert(++steps<4096);
  if(token->theType==PP_TOKEN_EOF){eof=1;break;}
  if(token->theType==PP_TOKEN_NEWLINE){++lines;continue;}
  if(token->theType==PP_TOKEN_WHITESPACE)continue;
  assert(strlen(output)+strlen(token->theSource)<sizeof(output));strcat(output,token->theSource);
 }
 /* The fixture also owns parsers left active after an expected rejection. */
 while(parser.child) {
  pp_parser *parent=&parser;while(parent->child->child)parent=parent->child;
  pp_parser *child=parent->child;
  if(child->freeFilename)free((void*)child->filename);
  if(child->freeSourceCode)free(child->sourceCode);
  free(child->macroName);free(child);parent->child=NULL;
 }
 pp_context_destroy(&context);free(source);fflush(stderr);
 assert(dup2(saved,STDERR_FILENO)>=0);close(saved);
 rewind(messages);char errors[4096]={0};size_t length=fread(errors,1,sizeof(errors)-1,messages);
 assert(!ferror(messages) && length<sizeof(errors)-1);fclose(messages);
 if(eof!=accepted || strcmp(output,wanted) ||
    (diagnostic[0] && !strstr(errors,diagnostic)) || (wanted_lines>=0 && lines!=wanted_lines)) {
  fprintf(stderr,"Expected accepted=%d tokens=[%s] lines=%d diagnostic=[%s]; got accepted=%d tokens=[%s] lines=%d errors=[%s]\n",accepted,wanted,wanted_lines,diagnostic,eof,output,lines,errors);assert(0);
 }
}
int main(void) { CHECKS return 0; }
'''.replace('CHECKS','\n'.join(checks))
        script=ENGINE/'source/scriptlib';pp=ENGINE/'source/preprocessorlib'
        extra=['-DPP_TEST=1','-DSAFEALLOC_H=1','-Dstricmp=strcasecmp','-Dstrnicmp=strncasecmp',
               '-I',str(script),'-I',str(pp),'-I',str(ENGINE/'source'),
               '-I',str(ENGINE/'source/gamelib'),'-I',str(SOURCE/'src/port/libretro'),
               str(pp/'pp_parser.c'),str(pp/'pp_lexer.c'),str(pp/'pp_expr.c'),str(script/'List.c')]
        self.compile_run(program,extra)



class NativeTextReturnTests(unittest.TestCase):
    """Available-storage contracts with actual callbacks and native variants."""
    fixture_name="text-object-return-contracts.json"
    scope_marker="no capacity"
    @classmethod
    def setUpClass(cls):
        fixture=Path(__file__).with_name('fixtures')/cls.fixture_name
        cls.fixture=json.loads(fixture.read_text())
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='native-text-returns-')
        cls.addClassCleanup(temporary.cleanup)
        work=Path(temporary.name)
        cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for row in cls.fixture['models']:
            root=SOURCE/'src/engines'/row['engine']
            script=(root/'openborscript.c').read_text()
            enums='\n'.join(re.findall(r'enum (?:gtop|ctop)_enum\s*\{[^}]*\};',script))
            if not enums:raise ValueError('Complete native text-property enums required')
            names=[];mappers=[]
            for name in ['mapstrings_gettextobjproperty','mapstrings_textobjproperty','mapstrings_changetextobjproperty']:
                if re.search(r'(?m)^(?:void|int)\s+'+name+r'\s*\(',script):
                    names.append(name);mappers.append(function(script,name))
            if any(re.search(r'\bsearchList\s*\(',method) for method in mappers):
                mappers.insert(0,function((root/'source/utils.c').read_text(),'searchList'))
            dispatcher=(root/row['dispatcher_file']).read_text()
            helpers=render_dispatch(function(dispatcher,'Script_GetStringMapFunction'),
                retained_references=[CALLBACKS['get'],CALLBACKS['change'],*names])
            options={key:row[key]for key in ['physical_fixed','seed_slots','slots','header_includes','cases']}
            if 'field_paths' in row:
                options['field_paths']=row['field_paths']
            for key in ['create_strings','string_limit']:
                if key in row:options[key]=row[key]
            for helper in ['obor_textobj_index','obor_textobj_store','obor_textobj_format',
                           'openbor_textobj_set_text']:
                if re.search(r'(?m)^static (?:int|HRESULT) '+helper+r'\s*\(',script):
                    helpers+='\n'+function(script,helper)
            engine=(root/'openbor.c').read_text()
            if re.search(r'(?m)^static int obor_textobjs_initialize\s*\(',engine):
                helpers+='\n'+function(engine,'obor_textobjs_initialize')
                options.update(seed_slots=0,initializer='obor_textobjs_initialize')
            code=render_text_objects(revisions=row['revisions'],
                callbacks={key:function(script,name)for key,name in CALLBACKS.items()},
                mapping=enums+'\n'+'\n'.join(mappers),helpers=helpers,**options)
            source=work/(row['id']+'.c');source.write_text(code);binary=source.with_suffix('')
            includes=[root/'source/scriptlib',root,SOURCE/'src/port/libretro',root/'source',
                      *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
            compile_checked(compiler+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-error=misleading-indentation',
                '-Wno-error=sign-compare','-Wno-unused-variable','-Wno-unused-function',
                '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough',
                '-O0','-g','-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
                '-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+row['engine'],*host,*warnings,
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                *['-I'+str(p)for p in includes],str(source),
                str(root/'source/scriptlib/ScriptVariant.c'),*link,'-lm','-o',str(binary)])
            if row['id']in cls.executables:raise ValueError('Duplicate native return model')
            cls.executables[row['id']]=binary

    def test_each_own_source_return_and_update_contract(self):
        for row in self.fixture['models']:
            with self.subTest(model=row['id']):
                observed=subprocess.run([str(self.executables[row['id']])],
                    text=True,capture_output=True,timeout=15,env=sanitizer_environment())
                self.assertEqual(observed.returncode,0,observed.stdout+observed.stderr)
                self.assertEqual(json.loads(observed.stdout),dict(status='PASS',
                    contexts=len(row['revisions']),
                    checks=sum(step.get('repeat',1)for case in row['cases']for step in case['steps'])*len(row['revisions']),
                    original_orphans=0))

    def test_registered_profiles_in_declared_scope_have_own_contracts(self):
        declared={revision:row['engine']for row in self.fixture['models']for revision in row['revisions']}
        for profile in self.pin['profiles']:
            revision=int(profile.get('revision',profile['build']))
            for scope in self.fixture['coverage']:
                if profile['engine']==scope['engine']and scope['first']<=revision<=scope['last']:
                    self.assertIn(revision,declared)
                    self.assertEqual(profile['engine'],declared[revision])

    def test_original_sources_and_available_storage_scope_are_explicit(self):
        self.assertEqual(self.fixture['schema'],1)
        seen=set()
        for row in self.fixture['models']:
            self.assertEqual(row['revisions'],sorted(set(row['revisions'])))
            self.assertFalse(seen.intersection(row['revisions']))
            seen.update(row['revisions'])
            self.assertEqual(row['revisions'],[v['revision']for v in row['original_sources']])
            for original in row['original_sources']:
                self.assertRegex(original['commit'],r'^[0-9a-f]{40}$')
                self.assertEqual(set(original['callbacks']),set(CALLBACKS.values()))
                for value in original['callbacks'].values():self.assertRegex(value,r'^[0-9a-f]{64}$')
            self.assertTrue(row['cases'])
            self.assertTrue(all(case['orphan_allocations']==0 for case in row['cases']))
            self.assertIn(self.scope_marker,row['scope'])



class NativeTextArgumentTests(NativeTextReturnTests):
    fixture_name='text-object-argument-contracts.json'
    scope_marker='input validation'


class NativeLaterClassicTextTests(NativeTextReturnTests):
    """Native positioned text, bounded storage and unavailable table growth."""
    fixture_name='text-object-later-classic-contracts.json'
    scope_marker='later text storage'


class NativeModernTextArgumentTests(NativeTextReturnTests):
    """Native positioned text calls with complete argument and result entries."""
    fixture_name='text-object-modern-argument-contracts.json'
    scope_marker='modern input validation'

    def test_profile_labels_and_candidate_only_cases_are_explicit(self):
        for row in self.fixture['models']:
            with self.subTest(model=row['id']):
                covered={v['profile']for v in row['original_sources']+row['reconstructed_profile_aliases']}
                required={p['build']for p in self.pin['profiles']if p['engine']==row['engine']}
                self.assertTrue(required<=covered)
                original=row['original_case_indices'];candidate=row['candidate_only_case_indices']
                self.assertFalse(set(original)&set(candidate))
                self.assertEqual(sorted(original+candidate),list(range(len(row['cases']))))
                self.assertTrue(row['create_strings'])


class NativeTextCapacityTests(NativeTextReturnTests):
    """Own fixed/dynamic limits, cold native tables and unavailable growth."""
    fixture_name="text-object-capacity-contracts.json"
    scope_marker="capacity"



class NativeTextStringTests(NativeTextReturnTests):
    """Native string limits, owned buffer reuse and unavailable storage."""
    fixture_name="text-object-string-contracts.json"
    scope_marker="text strings"


    def test_original_and_candidate_only_string_cases_are_distinct(self):
        for row in self.fixture['models']:
            with self.subTest(model=row['id']):
                original=row['original_case_indices']
                candidate=row['candidate_only_case_indices']
                self.assertTrue(original)
                self.assertTrue(candidate)
                self.assertFalse(set(original).intersection(candidate))
                self.assertEqual(sorted(original+candidate),list(range(len(row['cases']))))
                dependency=SOURCE/'src/engines'/row['engine']/'source/scriptlib/depends.h'
                definitions=re.findall(r'^\s*#define\s+MAX_STR_VAR_LEN\s+(\d+)\s*$',dependency.read_text(),re.M)
                self.assertEqual(len(definitions),1)
                limit=int(definitions[0])
                full_cache=False
                for index,case in enumerate(row['cases']):
                    if index in original:
                        self.assertTrue(case.get('level_present',True))
                    for step in case['steps']:
                        if index in original:
                            self.assertNotIn('refuse',step)
                        for argument in step['arguments']:
                            if argument['kind']=='string':
                                if index in original:self.assertLess(len(argument['value']),limit)
                                elif len(argument['value'])==limit:full_cache=True
                self.assertTrue(full_cache)


def tolerance_fixture(members, kind):
    """Authored scripts exercise real compilation and API dispatch in a level."""
    result=dict(members)
    result['data/script.txt']=b'alwaysupdate 1\n'
    prefix='''void main() {
    if(!openborvariant("in_level") || getglobalvar("tolerance_checked") == 1) return;
    setglobalvar("tolerance_checked", 1);
    log("TOLERANCE_BEFORE\\n");
'''
    cases={
        'level': '''    changelevelproperty("quake", 5);
    void value = changelevelproperty("quake", NULL());
    if(value != NULL() || getlevelproperty("quake") != 5) { log("TOLERANCE_BAD\\n"); return; }
''',
        'text': '''    void value = changetextobjproperty(-1, 3, 17);
    if(value != 0) { log("TOLERANCE_BAD\\n"); return; }
    changetextobjproperty(0, 3, 17);
    changetextobjproperty(0, 3, NULL());
    if(gettextobjproperty(0, 3) != 17) { log("TOLERANCE_BAD\\n"); return; }
    value = settextobj(0, NULL(), 12, 0, 10, "fixture");
    if(value != 1) { log("TOLERANCE_BAD\\n"); return; }
''',
        'macro': '''    if(__LINE__ != 77 || __FILE__ != 88 || defined != 55) { log("TOLERANCE_BAD\\n"); return; }
''',
    }
    macro = ('#define __LINE__ 77\n#define __FILE__ 88\n#define defined 55\n'
             if kind == 'macro' else '')
    result['data/scripts/updated.c']=(macro+prefix+cases[kind]+'    log("TOLERANCE_AFTER\\n");\n}\n').encode()
    return result


def check_tolerance_continuation(log, profile, kind):
    import re
    boundary={'macro':3802,'level':3820,'text':3821}[kind]
    legacy=int(profile)<boundary
    markers=re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                       r'(TOLERANCE_[A-Z_]+)[ \t]*\r?$',log)
    expected=['TOLERANCE_BEFORE','TOLERANCE_AFTER'] if legacy else ([] if kind=='macro' else ['TOLERANCE_BEFORE'])
    if markers!=expected:
        raise RuntimeError('Historical '+kind+' executed continuation differs: '+log)
    if legacy and "There's an exception while executing script" in log:
        raise RuntimeError('Legacy tolerance unexpectedly aborted: '+log)
    if not legacy:
        refusal='builtin macro and cannot be redefined' if kind=='macro' else "There's an exception while executing script"
        if refusal not in log:raise RuntimeError('Modern strict rejection missing: '+log)


class ToleranceContinuationTests(unittest.TestCase):
    def test_only_executed_records_prove_tolerance(self):
        legacy = '[game] TOLERANCE_BEFORE\n[game] TOLERANCE_AFTER\n'
        for kind, boundary in [('macro',3802),('level',3820),('text',3821)]:
            modern = ('builtin macro and cannot be redefined' if kind == 'macro' else
                      "[game] TOLERANCE_BEFORE\nThere's an exception while executing script updated\n")
            check_tolerance_continuation(legacy, str(boundary-1), kind)
            check_tolerance_continuation(modern, str(boundary), kind)
            for log, profile in [(modern,str(boundary-1)),(legacy,str(boundary)),
                                 ('log("TOLERANCE_AFTER");',str(boundary-1)),
                                 (legacy+legacy,str(boundary-1))]:
                with self.subTest(kind=kind,profile=profile), self.assertRaises(RuntimeError):
                    check_tolerance_continuation(log,profile,kind)


if __name__=='__main__':unittest.main()
