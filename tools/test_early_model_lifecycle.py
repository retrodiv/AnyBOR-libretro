"""Check model lookup, input copies and cleanup policy against own sources.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-model-lifecycle.json'


def ints(values):
    return '{' + ','.join(map(str, values)) + '}'


class EarlyModelLifecycleTests(unittest.TestCase):
    def test_registry_and_loader_policy(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            for field, count in [('initial', 4), ('during_remove', None), ('after_remove', 3),
                                 ('free_order', 4), ('level_order', 2), ('after_level', 2)]:
                values = row[field]
                self.assertTrue(all(type(value) is int and 0 <= value < 4 for value in values))
                self.assertEqual(len(set(values)), len(values))
                self.assertEqual(len(values), count if count is not None else (3 if row['early_detach'] else 4))
            for field in ['early_detach', 'renamed_found', 'old_key_found', 'caller_available', 'copy_inputs']:
                self.assertIs(type(row[field]), bool)
            self.assertTrue(0 <= row['model_name_limit'] <= 1024)
            self.assertIn(row['name_slot'], (1, 4))
            self.assertEqual(len(row['nested_names']), len(fixture['nested_cases']))
            self.assertEqual(len(row['external_names']), len(fixture['nested_cases']))
            self.assertTrue(all(isinstance(value, str) and len(value) < 128 for value in row['nested_names']))
            label = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s={%s,%s,%s,%s,%s,%s,%d,%d,%d,%d,%d,%d,%d,%s,%s,%s};' % (
                label, ints(row['initial']), ints(row['during_remove']), ints(row['after_remove']),
                ints(row['free_order']), ints(row['level_order']), ints(row['after_level']),
                row['early_detach'], row['renamed_found'], row['old_key_found'],
                row['caller_available'], row['copy_inputs'], row['model_name_limit'], row['name_slot'],
                '{' + ','.join(map(json.dumps, row['nested_names'])) + '}',
                '{' + ','.join(map(json.dumps, row['external_names'])) + '}',
                json.dumps(row['level_message'])))
            checks.append('check_profile(%d,&%s);' % (row['revision'], label))
        for row in fixture['name_controls']:
            self.assertIn(row['slot'], (1, 4))
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            checks.append('check_name_control(%d,%d);' % (row['revision'], row['slot']))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        freetype = re.findall(r'typedef enum\s*\{[^{}]*}\s*ModelFreetype;', header)
        cache = re.findall(r'typedef struct\s*\{[^{}]*}\s*s_modelcache;', header)
        self.assertEqual((len(arglist), len(freetype), len(cache)), (1, 1, 1))
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        max_name = re.findall(r'(?m)^#define\s+MAX_NAME_LEN\s+(\d+)\b', header)
        max_maps = re.findall(r'(?m)^#define\s+MAX_COLOUR_MAPS\s+(\d+)\b', header)
        self.assertEqual((len(max_arg), len(max_name), len(max_maps)), (1, 1, 1))
        self.assertEqual(int(max_name[0]), fixture['max_name_len'])
        macros = []
        for name in ['GET_ARG', 'GET_ARG_LEN', 'GET_ARGP', 'GET_INT_ARG', 'GET_MODEL_LOAD_FLAG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1, name)
            macros += found
        functions = '\n'.join(function(source, name) for name in [
            'isNumeric', 'getValidInt', 'getValidFloat', 'ParseArgs', 'findarg',
            'obor_legacy_arg', 'obor_model_input', 'hasFreetype', 'update_model_loadflag',
            'get_cached_model_index', 'lcmHandleCommandName'])
        utility = (engine / 'source/utils.c').read_text()
        functions += '\n' + function(utility, 'lc')
        # This registry probe models one aggregate cleanup event. Slot order
        # and script ownership are covered by test_early_callback_order.
        callback_enum = re.search(r'enum\s*\{\s*OBOR_CALLBACK_KILL[^}]+\};', source)
        self.assertIsNotNone(callback_enum)
        free_model = function(source, 'free_model')
        free_models = function(source, 'free_models')
        animation_globals = re.findall(r'if\((anim\w+)\)', free_models)
        self.assertTrue(animation_globals)
        unload = function(source, 'unload_level')
        self.assertEqual(unload.count('level = NULL;'), 1)
        level_declaration = re.findall(r'char legacy_level_name\[\d+\] = "";', unload)
        level_copy = re.findall(r'if\(obor_profile_build[^)]*\)\s*'
                                r'snprintf\(legacy_level_name,[^;]+;', unload)
        self.assertEqual((len(level_declaration), len(level_copy)), (1, 1))
        unload = unload.split('level = NULL;', 1)[1].split('getRamStatus(BYTES);', 1)[0]
        loader = function(source, 'load_cached_model')
        copies = re.findall(r'char legacy_name\[MAX_NAME_LEN\+1\], legacy_owner\[256\];\s*'
                            r'name = obor_model_input\(name, legacy_name, sizeof\(legacy_name\)\);\s*'
                            r'owner = obor_model_input\(owner, legacy_owner, sizeof\(legacy_owner\)\);', loader)
        self.assertEqual(len(copies), 1)
        self.assertEqual(source.count('case CMD_MODEL_LOAD:'), 1)
        nested = source.split('case CMD_MODEL_LOAD:', 1)[1].split('case CMD_MODEL_SCORE:', 1)[0]
        level_load = source.split('case CMD_LEVEL_LOAD:', 1)[1].split('case CMD_LEVEL_BACKGROUND:', 1)[0]
        menu = function(source, 'selectplayer')
        marker = 'else if(stricmp(command, "load")==0)'
        self.assertEqual(menu.count(marker), 1)
        start = menu.index('{', menu.index(marker))
        menu_load = function('void selected_load(void) ' + menu[start:], 'selected_load')
        menu_load = menu_load.split('{', 1)[1].rsplit('}', 1)[0]
        # Whole registry/List units execute with a small dependency model. This
        # does not establish complete record layout, scripts or animation IO.
        model_header = r'''
#ifndef PROBE_MODELS_H
#define PROBE_MODELS_H
#include <stdint.h>
#include <strings.h>
#include "List.h"
@FREETYPE@
typedef struct {int id;} s_scripts;
typedef struct model {
 char *name;int index,unload,ownweapons,animation_capacity,alpha;
 ModelFreetype freetypes;s_scripts scripts;
 void *colourmap[@MAX_MAPS@],*palette,*weapon,*branch,*animation;
 void *defense_factors,*defense_pain,*defense_knockdown,*defense_blockpower;
 void *defense_blockthreshold,*defense_blockratio,*defense_blocktype;
 void *offense_factors,*special,*smartbomb;
} s_model;
typedef struct probe_sprite_map s_sprite_map;
@MODEL_DECLARATIONS@
#endif
'''
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "models.h"
#define MAX_ARG_LEN @MAX_ARG_LEN@
#define MAX_NAME_LEN @MAX_NAME_LEN@
#define MAX_COLOUR_MAPS @MAX_MAPS@
@ARGLIST@
@CACHE@
uint32_t obor_profile_build;
s_sprite_map *sprite_map;
static int models_loaded,models_cached,max_animations;
static void *anim_list,@ANIMATION_GLOBALS@;
static s_modelcache cache[5],*model_cache=cache;
typedef struct {
 int initial[4],during_remove[4],after_remove[3],free_order[4],level_order[2],after_level[2];
 int early_detach,renamed_found,old_key_found,caller_available,copy_inputs,model_name_limit,name_slot;
 const char *nested_names[@NESTED_COUNT@];
 const char *external_names[@NESTED_COUNT@];
 const char *level_message;
} expectation;
@ARRAYS@
static const expectation *expected;
void probe_validate_list(void);
static jmp_buf stop;
static char stopped_message[128];
static void probe_shutdown(int status,const char *format,...) {
 va_list ap;assert(status==1);va_start(ap,format);
 vsnprintf(stopped_message,sizeof(stopped_message),format,ap);va_end(ap);longjmp(stop,1);
}
static int phase,cleaned,cleanup_order[4],load_calls,loaded_flag;
static char loaded_name[128],loaded_owner[128];
static char level_finished[256];
static int empty_lines;
static const char *names[]={"Zulu","alpha","Mike","beta"};
static const char *nested_cases[]=@NESTED_CASES@;
static const char *level_names[]=@LEVEL_NAMES@;
static int probe_printf(const char *format,...) {
 char text[512];va_list ap;va_start(ap,format);
 int count=vsnprintf(text,sizeof(text),format,ap);va_end(ap);
 assert(count>=0 && count<(int)sizeof(text));
 if(!strncmp(text,"Level Unloaded:",15) || !strcmp(text,"Done.\n")) {
  assert(strlen(text)<sizeof(level_finished));memcpy(level_finished,text,strlen(text)+1);
 }
 if(!strcmp(text,"\n"))empty_lines++;
 return count;
}
static void order(const int *ids,int count) {
 probe_validate_list();
 for(int i=0;i<count;i++) {s_model *m=getModelAt(i);assert(m && m->index==ids[i]);}
 assert(!getModelAt(count));assert(!getModelAt(-1));
}
static void *anim_list_delete(void *head,int index) {
 (void)head;(void)index;assert(!"Animation cleanup is outside this provider");return NULL;
}
static void clear_all_scripts(s_scripts *scripts,int how) {
 assert(how==2 && cleaned<4);
 if(phase) {
  int before=phase==1?0:cleaned;
  assert(models_loaded==4-before-expected->early_detach);
  assert((model_cache[scripts->id].model==NULL)==expected->early_detach);
  if(phase==1)order(expected->during_remove,expected->early_detach?3:4);
 }
 cleanup_order[cleaned++]=scripts->id;
}
static void free_all_scripts(s_scripts *scripts) {(void)scripts;}
@CALLBACK_ENUM@
static void obor_profile_callback_scripts(s_scripts *origin,s_scripts *scripts,int how,int event) {
 assert(!origin && event==OBOR_CALLBACK_FREE_MODEL);
 clear_all_scripts(scripts,how);
}
@MACROS@
#define shutdown probe_shutdown
#define printf probe_printf
@FUNCTIONS@
#undef shutdown
@FREE_MODEL@
@FREE_MODELS@
static void unload_models_for_level(const char *name) {
 s_model *temp;
 struct {char *name;} provider={(char*)name},*level=&provider;
 @LEVEL_DECLARATION@
 @LEVEL_COPY@
 @UNLOAD@
}
static s_model *load_cached_model(char *name,char *owner,int flag) {
 snprintf(loaded_name,sizeof(loaded_name),"%s",name);
 snprintf(loaded_owner,sizeof(loaded_owner),"%s",owner);
 loaded_flag=flag;load_calls++;
 s_model *existing=findmodel(name);
 if(existing)update_model_loadflag(existing,flag);
 return existing;
}
static void root_copies(char *name,char *owner,char *after_name,char *after_owner) {
 @COPIES@
 if(expected->copy_inputs)assert(name==legacy_name && owner==legacy_owner);
 else assert(name!=legacy_name && owner!=legacy_owner);
 snprintf(after_name,128,"%s",name);snprintf(after_owner,128,"%s",owner);
}
static void nested_load(const char *text) {
 ArgList arglist;char line[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1];
 char filename[]="fixture.txt",command[]="load",*name="parent",*value;s_model *tempmodel;
 strcpy(line,text);ParseArgs(&arglist,line,output);
 switch(0) {case 0: @NESTED@}
}
static void external_load(const char *text,int menu) {
 ArgList arglist;char line[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1];
 char filename[]="fixture.txt",command[]="load";s_model *tempmodel;
 strcpy(line,text);ParseArgs(&arglist,line,output);
 if(menu) { @MENU_LOAD@ }
 else switch(0) {case 0: @LEVEL_LOAD@}
}
static s_model *add(int id) {
 s_model *m=calloc(1,sizeof(*m));assert(m);
 m->name=(char*)names[id];m->index=id;m->scripts.id=id;m->freetypes=MF_SCRIPTS;
 m->unload=(id==0 || id==2);
 cache[id].model=m;models_loaded++;addModel(m);return m;
}
static void setup(void) {
 createModelList();models_loaded=0;models_cached=5;memset(cache,0,sizeof(cache));
 for(int i=0;i<4;i++)cache[i].name=(char*)names[i];
 cache[4].name="zzTop";
 phase=cleaned=0;for(int i=0;i<4;i++){add(i);probe_validate_list();}
 order(expected->initial,4);
 for(int i=0;i<4;i++) {
  char query[32];strcpy(query,names[i]);assert(findmodel(query)==cache[i].model);
 }
 assert(!findmodel("missing"));assert(!free_model(NULL));
}
static void finish(void) {
 phase=0;cleaned=0;free_models();assert(!models_loaded);freeModelList();
}
static void name_line(s_model *model,const char *value,int slot) {
 ArgList args;char line[MAX_ARG_LEN+1],buffer[MAX_ARG_LEN+1];
 snprintf(line,sizeof(line),"name %s\n",value);ParseArgs(&args,line,buffer);
 lcmHandleCommandName(&args,model,slot);
}
static void check_name_policy(int slot) {
 s_model *model=cache[1].model;
 cache[4].name="zzTop";cache[4].model=NULL;
 name_line(model,"zzTop",1);
 assert(model->name==cache[slot].name && cache[slot].model==model);
 model->name=(char*)names[1];model->alpha=0;
 cache[4].name="steam";name_line(model,"steam",1);
 assert(model->alpha==(slot==4));model->name=(char*)names[1];model->alpha=0;
 /* Only the effective out-of-table index is candidate-only. Defined
    duplicate diagnostics are checked separately in the selected contexts. */
 stopped_message[0]=0;
 if(!setjmp(stop)) {
  name_line(model,slot==4?"missing":"alpha",slot==4?1:models_cached);
  assert(!"Expected a controlled name-table stop");
 }
 assert(!strncmp(stopped_message,"Unknown model name '",20));
}
static void check_name_control(unsigned revision,int slot) {
 obor_profile_build=revision;phase=0;createModelList();models_loaded=0;models_cached=5;
 memset(cache,0,sizeof(cache));for(int i=0;i<4;i++)cache[i].name=(char*)names[i];
 s_model *model=calloc(1,sizeof(*model));assert(model);
 model->name=(char*)names[1];model->index=1;cache[1].model=model;addModel(model);
 check_name_policy(slot);deleteModel(model->name);freeModelList();
}
static void check_callers(void) {
 char input[80],owner[]="parent",result[128],parent[128];
 memset(input,'x',50);input[50]=0;root_copies(input,owner,result,parent);
 assert(strlen(result)==(expected->copy_inputs?(size_t)expected->model_name_limit:50));
 assert(!strcmp(parent,"parent"));
 if(expected->copy_inputs) {
  char prefix[MAX_NAME_LEN];memset(prefix,'x',sizeof(prefix));
  root_copies(prefix,owner,result,parent);
  assert(strlen(result)==sizeof(prefix) && !memcmp(result,prefix,sizeof(prefix)));
 }
 for(size_t i=0;i<sizeof(nested_cases)/sizeof(nested_cases[0]);i++) {
  for(int caller=0;caller<3;caller++) {
  for(int existing=0;existing<2;existing++) {
   const char *wanted=caller?expected->external_names[i]:expected->nested_names[i];
   if(existing && expected->copy_inputs && strlen(wanted)>MAX_NAME_LEN)continue;
   createModelList();models_loaded=0;models_cached=4;phase=cleaned=0;
   s_model *model=NULL;
   if(existing) {
    model=calloc(1,sizeof(*model));assert(model);
    model->name=(char*)wanted;model->unload=17;addModel(model);models_loaded=1;
   }
   load_calls=0;loaded_flag=99;loaded_name[0]=loaded_owner[0]=0;
   if(caller)external_load(nested_cases[i],caller==2);
   else nested_load(nested_cases[i]);
   int wanted_calls=expected->copy_inputs || !existing;
   assert(load_calls==wanted_calls);
   if(wanted_calls) {
    assert(!strcmp(loaded_name,wanted));
    assert(!strcmp(loaded_owner,caller?"fixture.txt":"parent"));assert(loaded_flag==(i==3?0:1));
   }
   if(existing) {assert(model->unload==(i==3?0:1));deleteModel(model->name);models_loaded=0;}
   freeModelList();
  }
  }
 }
}
static void check_profile(unsigned revision,const expectation *oracle) {
 obor_profile_build=revision;expected=oracle;
 setup();check_name_policy(expected->name_slot);
 stopped_message[0]=0;
 if(!setjmp(stop)) {name_line(cache[1].model,"Zulu",1);assert(!"Expected duplicate diagnostic");}
 assert(!strcmp(stopped_message,"Duplicate model name 'Zulu'"));finish();
 setup();s_model *renamed=cache[1].model;renamed->name="zzTop";
 assert((findmodel("zzTop")==renamed)==expected->renamed_found);
 assert((findmodel("alpha")==renamed)==expected->old_key_found);
 renamed->name=(char*)names[1];finish();
 setup();phase=1;cleaned=0;int result=free_model(findmodel("aLpHa"));
 assert(result==(expected->early_detach?3:4));assert(cleaned==1 && cleanup_order[0]==1);
 order(expected->after_remove,3);finish();
 setup();phase=2;cleaned=0;free_models();assert(!models_loaded && cleaned==4);
 for(int i=0;i<4;i++)assert(cleanup_order[i]==expected->free_order[i]);
 freeModelList();
 for(size_t sample=0;sample<sizeof(level_names)/sizeof(level_names[0]);sample++) {
  for(int empty=0;empty<2;empty++) {
   char wanted[256];setup();phase=3;cleaned=0;level_finished[0]=0;empty_lines=0;
   if(empty)for(int i=0;i<4;i++)getModelAt(i)->unload=0;
   unload_models_for_level(level_names[sample]);
   assert(models_loaded==(empty?4:2) && cleaned==(empty?0:2));
   if(!empty)for(int i=0;i<2;i++)assert(cleanup_order[i]==expected->level_order[i]);
   order(empty?expected->initial:expected->after_level,empty?4:2);
   snprintf(wanted,sizeof(wanted),expected->level_message,level_names[sample]);
   assert(!strcmp(level_finished,wanted));
   assert(empty_lines==(expected->early_detach && !empty));finish();
  }
 }
 if(expected->caller_available)check_callers();
}
int main(void) {@CHECKS@ puts("early_model_lifecycle=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=max_arg[0], MAX_NAME_LEN=max_name[0], MAX_MAPS=max_maps[0],
                            ARGLIST=arglist[0], FREETYPE=freetype[0], CACHE=cache[0],
                            MODEL_DECLARATIONS=(engine / 'source/gamelib/models.h').read_text().replace('#include "openbor.h"', ''),
                            CALLBACK_ENUM=callback_enum[0],
                            FUNCTIONS=functions, MACROS='\n'.join(macros), FREE_MODEL=free_model,
                            FREE_MODELS=free_models, UNLOAD=unload, COPIES=copies[0], NESTED=nested,
                            LEVEL_LOAD=level_load, MENU_LOAD=menu_load,
                            LEVEL_DECLARATION=level_declaration[0], LEVEL_COPY=level_copy[0],
                            LEVEL_NAMES='{' + ','.join(map(json.dumps, fixture['level_names'])) + '}',
                            ANIMATION_GLOBALS=','.join('*' + name for name in animation_globals),
                            NESTED_COUNT=str(len(fixture['nested_cases'])),
                            NESTED_CASES='{' + ','.join(map(json.dumps, fixture['nested_cases'])) + '}',
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
            model_header = model_header.replace('@' + key + '@', value)
        self.assertNotRegex(program, r'@[A-Z_]+@')
        with tempfile.TemporaryDirectory(prefix='early-model-lifecycle-') as directory:
            work = Path(directory)
            (work / 'models.h').write_text(model_header)
            (work / 'utils.h').write_text('#include <stddef.h>\nvoid lc(char*,size_t);\n')
            # Append inspection only: retain all candidate unit bytes, then
            # validate its private links, hashes and an activated index cache.
            inspect = r'''
void probe_validate_list(void) {
    Node *node,*previous=NULL;
    int index=0;
    if(!modellist->mindices)List_CreateIndices(modellist);
    for(node=modellist->first;node;node=node->next,index++) {
        assert(node->prev==previous);
        assert(List_GetNodeIndex(modellist,node)==index);
        assert(List_GetNodeByName(modellist,node->name)==node);
        previous=node;
    }
    assert(previous==modellist->last && index==modellist->size);
}
'''
            (work / 'models.c').write_bytes((engine / 'source/gamelib/models.c').read_bytes() + inspect.encode())
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-Dstricmp=strcasecmp',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-I', str(work), '-I', str(engine / 'source/scriptlib')]
            objects = []
            for source_file in [engine / 'source/scriptlib/List.c', work / 'models.c']:
                obj = work / (source_file.stem + '.o')
                run = subprocess.run(cc + flags + ['-c', str(source_file), '-o', str(obj)],
                                     capture_output=True, text=True, timeout=45)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                objects.append(str(obj))
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            run = subprocess.run(cc + flags + ['-Wall', '-Wextra', '-Werror',
                                 '-Wno-error=deprecated-declarations', '-Wno-sign-compare',
                                 '-Wno-implicit-fallthrough', str(unit), *objects, *links, '-o', str(binary)],
                                 capture_output=True, text=True, timeout=45)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_lifecycle=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
