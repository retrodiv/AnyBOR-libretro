"""Render native stream open/save checks using real temporary files.

The complete variant implementation is linked separately. Directory naming is
bounded fixture data; archive reads and unrelated interpreter calls are refused.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_filesystem(*, revisions, opening, saving, helpers, slots,
                      physical_fixed, owned_extent, pak_name_capacity,
                      open_closes_file, appends_terminator, cases,
                      record=None, record_pack=None, header_includes=None,
                      level_streams=False, size_from_file=False,
                      save_returns_null=True, dynamic_strings=False,
                      check_allocation_refusal=False):
    if (not isinstance(revisions,list) or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions) or
        revisions!=sorted(set(revisions)) or type(slots)is not int or not 4<=slots<=1024 or
        any(type(v)is not bool for v in
            [physical_fixed,owned_extent,pak_name_capacity,open_closes_file,appends_terminator,
             level_streams,size_from_file,save_returns_null,dynamic_strings,check_allocation_refusal]) or
        physical_fixed and owned_extent or level_streams and physical_fixed):
        raise ValueError('Explicit bounded stream and filesystem context required')
    header_includes=['ScriptVariant.h','openborscript.h','openbor.h']if header_includes is None else header_includes
    if (not isinstance(header_includes,list)or not 0<len(header_includes)<=16 or
        any(not isinstance(n,str)or len(n)>256 or not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',n)or
            n.startswith('/')or '..'in n.split('/')for n in header_includes)or
        len(set(header_includes))!=len(header_includes)):
        raise ValueError('Explicit ordered native headers required')
    for source,name in [(opening,'openbor_openfilestream'),(saving,'openbor_savefilestream')]:
        if (not isinstance(source,str) or not 0<len(source)<=32768 or '\0'in source or
            not re.match(r'\s*HRESULT\s+'+name+r'\s*\(',source)):
            raise ValueError('Complete bounded native open/save callbacks required')
    if not isinstance(helpers,str) or len(helpers)>32768 or '\0'in helpers:
        raise ValueError('Bounded native storage helpers required')
    if record is None:
        if record_pack is not None:raise ValueError('Packing needs an original record')
    elif (not isinstance(record,str) or not 0<len(record)<=8192 or '\0'in record or
          not re.fullmatch(r'\s*typedef\s+struct\s*\{[^{}]*\}\s*s_filestream\s*;\s*',record) or
          type(record_pack)is not int or record_pack not in (1,2,4,8,16)):
        raise ValueError('Complete original stream record and packing required')
    if not isinstance(cases,list) or not 0<len(cases)<=16:
        raise ValueError('Bounded explicit input/output byte cases required')
    for case in cases:
        if (not isinstance(case,dict) or set(case)!={'input','saved'} or
            any(not isinstance(case[k],list) or len(case[k])>4096 or
                any(type(n)is not int or not 0<=n<=255 for n in case[k])for k in case) or
            not appends_terminator and (not case['input'] or case['input'][-1]!=0)):
            raise ValueError('Bounded byte expectations and terminated original input required')
    code=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <sys/stat.h>
#include <unistd.h>
@RENAME_RECORD@
@HEADERS@
#include "obor_pak_name.h"
@OWN_RECORD@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#undef fopen
#undef fclose
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Stream filesystem mismatch: %s\n",m);abort();}}while(0)
#ifdef NDEBUG
#error Stream filesystem checks require active assertions
#endif
#ifndef LEVEL_MAX_FILESTREAMS
#define LEVEL_MAX_FILESTREAMS @SLOTS@
#endif
uint32_t obor_profile_build;
@STREAM_DECLARATION@
static char directory[256],input_path[256],output_path[256],missing_path[256];
static const char *scratch;
static FILE *handles[4];
static unsigned opens,closes,cases_checked;
static int refuse_buffer_allocation;
static void *callback_allocation(size_t size){
 if(refuse_buffer_allocation){refuse_buffer_allocation=0;return NULL;}
 return malloc(size);
}
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(value,"native assertion");
}
void abortIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(value,condition,function,file,line);
}
/* Native VM allocation wrappers retain successful allocations unchanged.
 * VM allocation failure is outside this targeted callback-refusal contract. */
void *checkAlloc(void *pointer,size_t size,const char *function,const char *file,int line){
 exitIfFalse(size==0||pointer!=NULL,"native allocation",function,file,line);return pointer;
}
static void check_path(const char *path){
 CHECK(!strcmp(path,input_path)||!strcmp(path,output_path)||!strcmp(path,missing_path),"owned file path");
}
static FILE *open_owned(const char *path,const char *mode){
 check_path(path);CHECK(!strcmp(mode,"rb")||!strcmp(mode,"wb"),"native open mode");++opens;
 FILE *f=fopen(path,mode);if(!f)return NULL;
 for(unsigned i=0;i<4;++i)if(!handles[i]){handles[i]=f;return f;}
 CHECK(0,"bounded file owner ledger");return NULL;
}
static int close_owned(FILE *f){
 for(unsigned i=0;i<4;++i)if(handles[i]==f){handles[i]=NULL;++closes;return fclose(f);}
 CHECK(0,"file release must have one owner");return -1;
}
static unsigned active_files(void){unsigned count=0;for(unsigned i=0;i<4;++i)count+=handles[i]!=NULL;return count;}
static void fixture_base(char *out,char *kind,int create){
 CHECK((!strcmp(kind,"Saves")||!strcmp(kind,"Saves/"))&&!create,"native save directory request");
 CHECK(strlen(scratch)<100,"bounded temporary root");@BASE_DIRECTORY@
}
static void fixture_name(char *out@NAME_CAPACITY@,int which){
 CHECK(which==-1,"native archive basename request");@CHECK_CAPACITY@strcpy(out,"session");
}
static int fixture_exists(const char *path){check_path(path);return access(path,F_OK)==0;}
static int fixture_directory(const char *path,int create){
 CHECK(create==1&&!strcmp(path,directory),"bounded output directory request");
 struct stat value;CHECK(!stat(path,&value)&&S_ISDIR(value.st_mode),"owned output directory exists");return 1;
}
int buffer_pakfile(char *name,char **buffer,size_t *length){(void)name;(void)buffer;(void)length;abort();}
HRESULT Interpreter_Call(Interpreter *interpreter){(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter){(void)interpreter;abort();}
#undef getBasePath
#undef getPakName
#undef fileExists
#undef dirExists
#define getBasePath fixture_base
#define getPakName fixture_name
#define fileExists fixture_exists
#define dirExists fixture_directory
#define fopen open_owned
#define fclose close_owned
#define malloc callback_allocation
@HELPERS@
@OPENING@
@SAVING@
#undef fopen
#undef fclose
#undef malloc
@CASES@
static void seed_streams(void){
 opens=closes=0;refuse_buffer_allocation=0;CHECK(!active_files(),"no retained fixture handles");
 @SEED_TABLE@
 FIXTURE_STREAMS[0].pos=9;FIXTURE_STREAMS[0].size=71;
}
static void retire_streams(void){
 for(unsigned i=0;i<@SLOTS@;++i){free(FIXTURE_STREAMS[i].buf);FIXTURE_STREAMS[i].buf=NULL;}
 @RETIRE_TABLE@
 for(unsigned i=0;i<4;++i)if(handles[i])CHECK(!close_owned(handles[i]),"fixture retires original file owner");
 CHECK(!active_files(),"file owners retired");StrCache_Clear();
}
static void string_value(ScriptVariant *value,const char *text){
 ScriptVariant_Clear(value);ScriptVariant_ChangeType(value,VT_STR);
 CHECK(strlen(text)<MAX_STR_VAR_LEN,"bounded script filename");@ASSIGN_STRING@
}
static void verify_case(const unsigned char *bytes,size_t length,
                        const unsigned char *expected,size_t expected_length){
 seed_streams();FILE *created=fopen(input_path,"wb");CHECK(created,"create input");
 CHECK(fwrite(bytes,1,length,created)==length&&!fclose(created),"prepare exact input bytes");
 ScriptVariant name={0},location={0},result={0},index={0},*out=&result;
 string_value(&name,"input.txt");location.vt=VT_INTEGER;location.lVal=1;
 ScriptVariant *args[]={&name,&location};
 CHECK(openbor_openfilestream(args,&out,2)==S_OK&&out==&result,"native file open result");
 CHECK(result.vt==VT_INTEGER&&result.lVal==0,"native file slot");
 CHECK(FIXTURE_STREAMS[0].buf&&!memcmp(FIXTURE_STREAMS[0].buf,bytes,length),"all file bytes retained");
 CHECK(FIXTURE_STREAMS[0].pos==0&&FIXTURE_STREAMS[0].size==@EXPECTED_SIZE@,"native position and size field");
 @VERIFY_TERMINATOR@
 @VERIFY_EXTENT@
 CHECK(opens==1&&active_files()==@OPEN_HANDLES@,"native input handle lifetime");
 string_value(&name,"output.txt");index.vt=VT_INTEGER;index.lVal=0;
 ScriptVariant *save_args[]={&index,&name};
 CHECK(openbor_savefilestream(save_args,&out,2)==S_OK&&(@SAVE_RESULT@),"native void save result");
 CHECK(opens==2&&active_files()==@OPEN_HANDLES@,"save closes its output handle");
 FILE *saved=fopen(output_path,"rb");CHECK(saved,"read output");
 unsigned char actual[4097];size_t read=fread(actual,1,sizeof(actual),saved);
 CHECK(!ferror(saved)&&!fclose(saved)&&read==expected_length,"exact saved length");
 CHECK(!memcmp(actual,expected,read),"native saved bytes and line endings");
 ScriptVariant_Clear(&name);ScriptVariant_Clear(&result);retire_streams();
 CHECK(!unlink(input_path)&&!unlink(output_path),"retire owned files");++cases_checked;
}
static void missing_case(void){
 seed_streams();ScriptVariant name={0},location={0},result={0},*out=&result;
 string_value(&name,"missing.txt");location.vt=VT_INTEGER;location.lVal=1;
 ScriptVariant *args[]={&name,&location};
 CHECK(openbor_openfilestream(args,&out,2)==S_OK&&out==&result&&result.vt==VT_INTEGER&&result.lVal==-1,"native missing file result");
 CHECK(!FIXTURE_STREAMS[0].buf&&FIXTURE_STREAMS[0].pos==9&&FIXTURE_STREAMS[0].size==71,"missing file retains free slot fields");
 CHECK(!opens&&!active_files(),"missing input has no file owner");
 ScriptVariant_Clear(&name);ScriptVariant_Clear(&result);retire_streams();++cases_checked;
}
@ALLOCATION_CASE@
int main(void){
 scratch=getenv("TMPDIR");CHECK(scratch&&*scratch,"owned temporary directory required");
 CHECK(snprintf(directory,sizeof(directory),"%s/session",scratch)>0&&strlen(directory)<sizeof(directory)-16,"bounded fixture directory");
 CHECK(!mkdir(directory,0700),"create owned session directory");
 CHECK(strlen(directory)+13<sizeof(input_path),"bounded file paths");
 strcpy(input_path,directory);strcat(input_path,"/input.txt");
 strcpy(output_path,directory);strcat(output_path,"/output.txt");
 strcpy(missing_path,directory);strcat(missing_path,"/missing.txt");
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];
  @RUN_CASES@
  missing_case();
  @RUN_ALLOCATION_CASE@
 }
 CHECK(!rmdir(directory),"retire owned session directory");
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"cases\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),cases_checked);return 0;
}
'''
    arrays=[];runs=[]
    for n,case in enumerate(cases):
        for key in ['input','saved']:
            arrays.append('static const unsigned char '+key+'_'+str(n)+'[]={'+
                          (','.join(map(str,case[key])) or '0')+'};')
        runs.append('verify_case(input_'+str(n)+','+str(len(case['input']))+
                    ',saved_'+str(n)+','+str(len(case['saved']))+');')
    allocation_case=r'''
static void allocation_case(void){
 seed_streams();FILE *created=fopen(input_path,"wb");CHECK(created,"create refusal input");
 CHECK(fputc(0,created)!=EOF&&!fclose(created),"prepare refusal input");
 ScriptVariant name={0},location={0},result={0},*out=&result;
 string_value(&name,"input.txt");location.vt=VT_INTEGER;location.lVal=1;
 ScriptVariant *args[]={&name,&location};refuse_buffer_allocation=1;
 HRESULT status=openbor_openfilestream(args,&out,2);
 CHECK(@ALLOCATION_RESULT@,"native allocation refusal result");
 CHECK(!refuse_buffer_allocation&&!FIXTURE_STREAMS[0].buf,"bounded callback allocation refusal");
 CHECK(opens==1&&active_files()==@OPEN_HANDLES@,"allocation refusal file lifetime");
 ScriptVariant_Clear(&name);ScriptVariant_Clear(&result);retire_streams();
 CHECK(!unlink(input_path),"retire refusal input");++cases_checked;
}
'''if check_allocation_refusal else''
    allocation_case=allocation_case.replace('@ALLOCATION_RESULT@',
        'status==E_FAIL'if level_streams else
        'status==S_OK&&out==&result&&result.vt==VT_INTEGER&&result.lVal==-1')
    allocation_case=allocation_case.replace('@OPEN_HANDLES@','0'if open_closes_file else'1')
    values=dict(RENAME_RECORD='#define s_filestream anchor_filestream'if record is not None else'',
        HEADERS='\n'.join('#include "'+n+'"'for n in header_includes),
        OWN_RECORD=('#undef s_filestream\n#pragma pack(push,'+str(record_pack)+')\n'+record+
                    '\n#pragma pack(pop)')if record is not None else'',
        STREAM_DECLARATION=('s_level *level;char packfile[4096]="session.pak";\n#define FIXTURE_STREAMS (level->filestreams)'if level_streams else
                            ('s_filestream filestreams['+str(slots)+'];'if physical_fixed else
                             's_filestream *filestreams;int numfilestreams;')+'\n#define FIXTURE_STREAMS filestreams'),
        SLOTS=str(slots),NAME_CAPACITY=',size_t capacity'if pak_name_capacity else'',
        CHECK_CAPACITY='CHECK(capacity>=8,"basename capacity");'if pak_name_capacity else'',
        HELPERS=helpers,OPENING=opening,SAVING=saving,CASES='\n'.join(arrays),RUN_CASES='\n'.join(runs),
        SEED_TABLE='level=calloc(1,sizeof(*level));CHECK(level,"owned level");'if level_streams else
                   'memset(filestreams,0,sizeof(filestreams));'if physical_fixed else
                   'numfilestreams='+str(slots)+';filestreams=calloc(numfilestreams,sizeof(*filestreams));CHECK(filestreams,"owned table");',
        RETIRE_TABLE='free(level);level=NULL;'if level_streams else
                     'memset(filestreams,0,sizeof(filestreams));'if physical_fixed else
                     'free(filestreams);filestreams=NULL;numfilestreams=0;',
        VERIFY_EXTENT='CHECK(FIXTURE_STREAMS[0].obor_capacity==length+'+str(int(appends_terminator))+',"owned buffer extent");'if owned_extent else'',
        VERIFY_TERMINATOR='CHECK(!FIXTURE_STREAMS[0].buf[length],"native appended terminator");'if appends_terminator else'',
        BASE_DIRECTORY='if(!strcmp(kind,"Saves"))strcpy(out,directory);else{strcpy(out,scratch);strcat(out,"/");}'if level_streams else
                       'strcpy(out,scratch);strcat(out,"/");',
        EXPECTED_SIZE='length'if size_from_file else'71',
        SAVE_RESULT='out==NULL'if save_returns_null else'out==&result&&result.vt==VT_EMPTY',
        ASSIGN_STRING='value->strVal=StrCache_CreateNewFrom(text);'if dynamic_strings else
                      'strcpy(StrCache_Get(value->strVal),text);',
        ALLOCATION_CASE=allocation_case,RUN_ALLOCATION_CASE='allocation_case();'if check_allocation_refusal else'',
        OPEN_HANDLES='0'if open_closes_file else'1',
        REVISIONS=','.join(str(n)+'u'for n in revisions))
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
