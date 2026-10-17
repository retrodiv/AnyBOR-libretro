"""Exercise historical preprocessor and setter rejection boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function

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
        methods='\n'.join(function(source,n) for n in (
            'mapstrings_levelproperty','openbor_changelevelproperty','mapstrings_textobjproperty',
            'openbor_changetextobjproperty','openbor_settextobj'))
        program=r'''
#include <assert.h>
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
typedef struct {int vt; LONG lVal; DOUBLE dblVal; const char *strVal;} ScriptVariant;
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
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;v->lVal=0;}
static void ScriptVariant_ToString(ScriptVariant *v,char *b) {
    if(v->vt==VT_STR) strcpy(b,v->strVal);else strcpy(b,"<invalid>");
}
#define StrCache_Get(x) (x)
#define MAPSTRINGS(VAR,LIST,COUNT,MESSAGE) do { \
 if((VAR)->vt==VT_STR) {for(prop=0;prop<(COUNT);prop++) \
 if(!strcmp((VAR)->strVal,(LIST)[prop])) break; \
 if(prop<(COUNT)) {ScriptVariant_ChangeType(VAR,VT_INTEGER);(VAR)->lVal=prop;} } \
 (void)propname; } while(0)
#define __reallocto(P,OLD,N) do {assert((N)<16); \
 (P)=realloc((P),(N)*sizeof(*(P)));assert(P); \
 memset((P)+(OLD),0,((N)-(OLD))*sizeof(*(P)));} while(0)
typedef struct {int font,t,x,y,z;char *text;} Text;
typedef struct {int rocking,type,cameraxoffset,camerazoffset,quake;
 float bgspeed,scrollspeed,gravity,maxfallspeed,maxtossspeed;
 int numholes,numwalls,numtextobjs;float (*holes)[7],(*walls)[8];Text *textobjs;} Level;
static Level storage,*level=&storage;
enum {_top_font,_top_text,_top_time,_top_x,_top_y,_top_z,_top_the_end};

'''+declarations+methods+r'''
static ScriptVariant integer(LONG v) {return (ScriptVariant){.vt=VT_INTEGER,.lVal=v};}
static ScriptVariant string(const char *v) {return (ScriptVariant){.vt=VT_STR,.strVal=v};}
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
 a[0]=string("quake");a[1]=(ScriptVariant){.vt=VT_EMPTY};result=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changelevelproperty(v,&out,2)==(profile<3820?S_OK:E_FAIL));
 assert(storage.quake==5);assert(profile<3820 ? out==&result&&result.vt==VT_EMPTY&&result.lVal==0 : out==NULL);
 a[0]=string("quake");a[1]=integer(17);result=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changelevelproperty(v,&out,2)==S_OK&&storage.quake==17);
 assert(profile<3820?out==&result&&result.vt==VT_EMPTY:out==NULL);
 a[0]=string("unknown");out=&result;assert(openbor_changelevelproperty(v,&out,2)==E_FAIL&&out==NULL);
 /* Numeric and compiled textual wall selectors agree across the inserted type property. */
 a[0]=string("wall");a[1]=integer(0);a[2]=integer(2);a[3]=integer(77);out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==S_OK&&storage.walls[0][2]==77);
 LONG wall=profile<3820?10:11;assert(a[0].lVal==wall);
 a[0]=integer(wall);a[3]=integer(88);out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==S_OK&&storage.walls[0][2]==88);
 a[0]=string("hole");a[1]=integer(0);a[2]=integer(1);a[3]=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changelevelproperty(v,&out,4)==(profile<3820?S_OK:E_FAIL));assert(storage.holes[0][1]==0);
 a[0]=integer(0);out=&result;assert(openbor_changelevelproperty(v,&out,1)==E_FAIL&&out==NULL);
 /* Negative text indices are harmless zero-success only before3821. */
 a[0]=integer(-1);a[1]=integer(_top_x);a[2]=integer(21);out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==(profile<3821?S_OK:E_FAIL));
 assert(profile<3821?out==&result&&result.vt==VT_INTEGER&&result.lVal==0:out==NULL);
 a[0]=integer(0);a[1]=string("x");a[2]=(ScriptVariant){.vt=VT_EMPTY};out=&result;
 assert(openbor_changetextobjproperty(v,&out,3)==(profile<3821?S_OK:E_FAIL));assert(storage.textobjs[0].x==11);
 assert(profile<3821?out==&result&&result.lVal==0:out==NULL);
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
            command=shlex.split(os.environ.get('CC','cc'))+['-std=gnu99','-O1','-g','-fcommon','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),*extra,'-Wl,--gc-sections','-o',str(binary)]
            result=subprocess.run(command,text=True,capture_output=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(binary)],text=True,capture_output=True,timeout=20,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
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
 const unsigned profiles[]={3780,3783,3789,3793,3797,3801,3802,3805,3814,3818,3822,3824,3829,3831,3837,3839,3842};
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
        'text': '''    void value = changetextobjproperty(-1, "x", 17);
    if(value != 0) { log("TOLERANCE_BAD\\n"); return; }
    changetextobjproperty(0, "x", 17);
    value = changetextobjproperty(0, "x", NULL());
    if(value != 0) { log("TOLERANCE_BAD\\n"); return; }
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
