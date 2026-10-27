"""Exercise the actual saved-game loader and its four bonus caller routes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
import json
import os
from pathlib import Path
import re
import unittest
from test_historical_player import function
from native_sanitizers import sanitizer_environment

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT/'src/engines/3842'))


def saved_bonus_model_rows():
    fixture = load_contract_fixture(Path(__file__).parent /
        'fixtures/profile-saved-bonus-model-contracts.json')
    rows = fixture['sources']
    revisions = {row['revision'] for row in rows}
    if len(rows) != len(revisions) or not (
            contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions):
        raise ValueError('Own saved-bonus/model profiles and boundary controls required')
    for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
        if profile['engine'] == '3842' and int(profile.get('revision', profile['build'])) not in revisions:
            raise ValueError('Registered profile lacks its own saved-bonus/model source')
    for row in rows:
        revision = row['revision']
        expected = {'loader_reconstructs_bonus': revision >= 3820,
                    'selection_callers_reconstruct_bonus': revision < 3820,
                    'save_selectable_models': revision >= 3822,
                    'save_model_reloads': 3822 <= revision < 3835,
                    'shadow_uses_parsecolor': revision >= 3819}
        if (any(row[name] != value for name, value in expected.items()) or
                not re.fullmatch(r'[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch(r'[0-9a-f]{64}', value)
                        for value in row['source_sha256'].values())):
            raise ValueError('Invalid own-source saved-bonus/model contract')
    return rows


def bonus_program(source, header, profiles, *, trace=True):
    """Allow private own-build source oracles without shipping upstream fixtures."""
    end = re.search(r'\}\s*s_savelevel\s*;', header)
    if end is None:
        raise AssertionError('Missing original saved-game record')
    start = header.rfind('typedef struct', 0, end.start())
    record = header[start:end.end()]
    constants = []
    for name in ('MAX_NAME_LEN', 'MAX_PLAYERS', 'CV_SAVED_GAME'):
        match = re.search(r'^#define\s+' + name + r'\s+[^\n]+', header, re.M)
        if match is None:
            raise AssertionError('Missing native constant ' + name)
        constants.append(match[0])
    callers = []
    for name, boundary in (('selectplayer', r'\n\s*if\s*\(filename'),
                           ('choose_difficulty', r'\n\s*while\s*\(!quit\)')):
        body = function(source, name)
        load = re.search(r'(?m)^[ \t]*(?:if\s*\()?loadGameFile\(', body)
        if load is None or body.count('loadGameFile(') != 1:
            raise AssertionError('Ambiguous original caller ' + name)
        stop = re.search(boundary, body[load.start():])
        if stop is None:
            raise AssertionError('Missing caller boundary ' + name)
        callers.append('static int call_' + name + '(void) { int i=-1;\n' +
                       body[load.start():load.start()+stop.start()] + '\nreturn i; }')
    body = function(source, 'load_saved_game')
    start = body.index('loadGameFile(')
    start = body.rfind('\n', 0, start) + 1
    stop = body.index(';', start) + 1
    callers.append('static int call_saved_menu(void) { int savedStatus=0;char name[256]={0};\n' +
                   body[start:stop] + '\nreturn savedStatus; }')
    body = function(source, 'openborMain')
    if re.search(r'loadGameFile\(\);\s*playgame\(', body) is None:
        raise AssertionError('Skip-to-set loader order changed')
    start = body.index('loadGameFile(')
    callers.append('static int call_skip_to_set(void) { ' + body[start:body.index(';', start)+1] +
                   ' return -1; }')
    loader = function(source, 'loadGameFile')
    clear = function(source, 'clearSavedGame')
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
CONSTANTS
RECORD
static unsigned obor_profile_build;
static int num_difficulties;
static int bonus;
static s_savelevel *savelevel;
static char probe_prefix[256],probe_file[256]="probe.save";
static int probe_mode,probe_route;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"saved bonus profile=%u mode=%d route=%d line=%d\n",obor_profile_build,probe_mode,probe_route,__LINE__);abort();}}while(0)
void getBasePath(char *path,const char *kind,int unused) {
    (void)kind;(void)unused;strcpy(path,probe_prefix);
}
void getPakName(char *name,...) { strcpy(name,"probe.save"); }
int obor_pak_path_append(char *path,size_t capacity,const char *name) {
    if(strlen(path)+strlen(name)>=capacity)return 0;
    strcat(path,name);return 1;
}
void borExit(int status) { (void)status;abort(); }
CLEAR
LOADER
CALLERS
static void prepare(int mode) {
    remove(probe_file);
    num_difficulties=mode==5?(int)sizeof(s_savelevel):3;
    assert(num_difficulties>=3 && num_difficulties<4096);
    free(savelevel);savelevel=calloc((size_t)num_difficulties,sizeof(*savelevel));assert(savelevel);
    for(int i=0;i<3;++i) {savelevel[i].compatibleversion=CV_SAVED_GAME;savelevel[i].times_completed=7+i;}
    bonus=91;
    if(mode==0)return;
    FILE *file=fopen(probe_file,"wb");assert(file);
    s_savelevel *rows=calloc((size_t)num_difficulties,sizeof(*rows));assert(rows);
    for(int i=0;i<num_difficulties;++i)rows[i].compatibleversion=CV_SAVED_GAME;
    rows[0].times_completed=2;rows[1].times_completed=3;
    if(mode==4 || mode==5)rows[0].compatibleversion=0;
    if(mode==3) {
        assert(fwrite(rows,sizeof(*rows),1,file)==1);
        /* compatibleversion is a 32-bit bit-field in some native records. */
        assert(fwrite(&rows[1],1,sizeof(unsigned int),file)==sizeof(unsigned int));
    } else if(mode!=2)assert(fwrite(rows,sizeof(*rows),(size_t)num_difficulties,file)==(size_t)num_difficulties);
    free(rows);assert(fclose(file)==0);
}
int main(void) {
    if(getenv("ANYBOR_NATIVE_ARTIFACTS")) {
        const char *scratch=getenv("TMPDIR");assert(scratch);
        int n=snprintf(probe_prefix,sizeof(probe_prefix),"%s/",scratch);
        assert(n>0 && (size_t)n<sizeof(probe_prefix));
        n=snprintf(probe_file,sizeof(probe_file),"%sprobe.save",probe_prefix);
        assert(n>0 && (size_t)n<sizeof(probe_file));
    }
    CASE_COUNTER
    const unsigned profiles[]={PROFILES};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(int mode=0;mode<6;++mode)for(int route=0;route<5;++route) {
            probe_mode=mode;probe_route=route;
            prepare(mode);
            int result=-1;
            switch(route) {
                case 0: result=loadGameFile();break;
                case 1: result=call_selectplayer();break;
                case 2: result=call_choose_difficulty();break;
                case 3: result=call_saved_menu();break;
                case 4: result=call_skip_to_set();break;
            }
            int success=mode!=0 && mode!=5;
            int sum=mode==2?24:mode==3?19:5;
            int expected=success && (obor_profile_build>=3820 || route==1 || route==2)?sum:91;
            assert(bonus==expected);
            if(route==0 || route==3)assert(result==success);
            if(route==1 || route==2)assert(result==(success && obor_profile_build<3820?num_difficulties:-1));
            if(mode==5)for(int i=0;i<num_difficulties;++i)assert(savelevel[i].times_completed==0);
            COUNT_CASE
            TRACE_BEGIN
            printf("SAVE_BONUS %u mode=%d route=%d result=%d bonus=%d records=%d first=%u second=%u\n",
                obor_profile_build,mode,route,result,bonus,num_difficulties,
                savelevel[0].times_completed,savelevel[1].times_completed);
            TRACE_END
        }
    }
    free(savelevel);remove(probe_file);SUMMARY return 0;
}
'''.replace('CONSTANTS', '\n'.join(constants)).replace('RECORD', record).replace(
        'CLEAR', clear).replace('LOADER', loader).replace('CALLERS', '\n'.join(callers)).replace(
        'PROFILES', ','.join(map(str, profiles))).replace(
        'CASE_COUNTER', '' if trace else 'unsigned cases=0;').replace(
        'COUNT_CASE', '' if trace else '++cases;').replace(
        'TRACE_BEGIN', '' if trace else '/*').replace('TRACE_END', '' if trace else '*/').replace(
        'SUMMARY', '' if trace else 'printf("{\\"status\\":\\"PASS\\",\\"cases\\":%u}\\n",cases);')


class HistoricalSaveBonusTests(unittest.TestCase):
    def test_game_loader_result_matches_each_source_profile(self):
        from test_historical_behavior import native
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-save-load-contracts.json')
        rows = fixture['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(fixture['boundary_controls']) <= {r['revision'] for r in rows})
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(s['engine'] == profile['engine'] and s['first'] <= revision <= s['last']
                   for s in fixture['coverage']):
                self.assertIn(revision, {r['revision'] for r in rows})
        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                root = ROOT / 'src/engines' / engine
                program = bonus_program((root / 'openbor.c').read_text(),
                    (root / 'openbor.h').read_text(), ())
                prefix = program[:program.index('int main(void)')]
                checks = []
                for row in rows:
                    if row['engine'] == engine:
                        self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                        checks.append('obor_profile_build=%d;check(%d);' % (
                            row['revision'], row['rejected_game_returns_failure']))
                native(prefix + r'''
static void check(int rejected_fails) {
 for(int mode=0;mode<6;++mode) {
  prepare(mode);int result=loadGameFile();
  assert(result==(mode==0 || (mode==5 && rejected_fails)?0:1));
  if(mode==5)for(int i=0;i<num_difficulties;++i) {
   assert(savelevel[i].times_completed==0 && savelevel[i].compatibleversion==0);
  }
 }
}
int main(void) {@CHECKS@free(savelevel);remove("probe.save");return 0;}
'''.replace('@CHECKS@', '\n'.join(checks)), extra_flags=('-Wno-unused-function',))

    def test_script_save_route_and_caller_match_each_source_profile(self):
        from test_historical_behavior import native
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-save-load-contracts.json')
        rows = fixture['sources']
        for engine in sorted({r['engine'] for r in rows}):
            with self.subTest(engine=engine):
                source = (ROOT / 'src/engines' / engine / 'openbor.c').read_text()
                play = function(source, 'playgame')
                caller = re.search(r'(?:if\(obor_profile_build < 3708\) loadScriptFile\(\);\s*else )?'
                    r'if\(!loadScriptFile\(\)\) printf\("Warning, failed to load script save!\\n"\);', play)
                self.assertIsNotNone(caller)
                checks = []
                for row in rows:
                    if row['engine'] == engine:
                        checks.append('obor_profile_build=%d;check(%d);' % (
                            row['revision'], row['script_uses_native_file']))
                native(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {int initialized;} Script;
static unsigned obor_profile_build;
static int current_set,present,append_ok,execute_ok;
static char events[64],expected_path[256],loaded_path[256],appended[64],warning[128];
static FILE *owned_file;
static void event(char ch) {size_t n=strlen(events);assert(n+1<sizeof(events));events[n]=ch;events[n+1]=0;}
static void getBasePath(char *out,const char *kind,int flag) {assert(!strcmp(kind,"Saves") && !flag);strcpy(out,"Saves/");}
static void getPakName(char *out,size_t size,int kind) {assert(kind==2 && size>=10);strcpy(out,"probe.scr");}
static int obor_pak_path_append(char *out,size_t size,const char *name) {
 assert(strlen(out)+strlen(name)<size);strcat(out,name);return 1;
}
static void borExit(int code) {(void)code;abort();}
static FILE *controlled_open(const char *path,const char *mode) {
 event('O');assert(!strcmp(path,expected_path) && !strcmp(mode,"rb"));
 if(!present)return NULL;
 assert(!owned_file);owned_file=tmpfile();assert(owned_file);
 assert(fwrite("abc\n",1,4,owned_file)==4);rewind(owned_file);return owned_file;
}
static void Script_Init(Script *s,const char *name,void *unused,int flag) {
 assert(!strcmp(name,"loadScriptFile") && !unused && flag==1);event('I');s->initialized=1;
}
int load_script(Script *s,char *path) {
 event('L');assert(!strcmp(path,expected_path));strcpy(loaded_path,path);
 s->initialized=present && append_ok;return s->initialized;
}
static void Script_Clear(Script *s,int level) {assert(level==2);event('Z');s->initialized=0;}
static int Script_Compile(Script *s) {(void)s;event('C');return 1;}
int Script_IsInitialized(Script *s) {event('N');return s->initialized;}
static int Script_Execute(Script *s) {assert(s->initialized);event('E');return execute_ok;}
static int Script_AppendText(Script *s,char *text,char *path) {
 assert(s->initialized && !strcmp(path,expected_path));event('A');
 snprintf(appended,sizeof(appended),"%s",text);return append_ok;
}
#define fopen controlled_open
@LOADER@
#undef fopen
static int caller_result,caller_count;
static int caller_load(void) {++caller_count;return caller_result;}
static int record_warning(const char *text) {snprintf(warning,sizeof(warning),"%s",text);return 0;}
#define loadScriptFile caller_load
#define printf record_warning
static void call_warning(void) {@CALLER@}
#undef printf
#undef loadScriptFile
static void check(int native_file) {
 const int sets[]={0,12,99};
 for(unsigned k=0;k<3;++k)for(present=0;present<2;++present)
 for(append_ok=0;append_ok<2;++append_ok)for(execute_ok=0;execute_ok<2;++execute_ok) {
  current_set=sets[k];snprintf(expected_path,sizeof(expected_path),"Saves/probe.s%02d",current_set);
  *events=*loaded_path=*appended=0;assert(!owned_file);
  int result=loadScriptFile();
  const char *wanted=native_file?(!present?"O":!append_ok?"OIAZ":"OIACEZ"):
      (present && append_ok?"ILCNEZ":"ILZCNZ");
  assert(!strcmp(events,wanted));
  if(native_file) {
   assert(result==(present && append_ok && execute_ok));
   if(present)assert(!strcmp(appended,"abc"));
   assert(!*loaded_path);
  } else {
   /* The original loader is void and its caller ignores this internal result. */
   assert(!strcmp(loaded_path,expected_path) && !*appended);
  }
  /* Teardown owns the service stream; this does not claim core stream cleanup. */
  if(owned_file){assert(fclose(owned_file)==0);owned_file=NULL;}
 }
 for(caller_result=0;caller_result<2;++caller_result) {
  caller_count=0;*warning=0;call_warning();assert(caller_count==1);
  assert(!strcmp(warning,native_file && !caller_result?"Warning, failed to load script save!\n":""));
 }
}
int main(void) {@CHECKS@return 0;}
'''.replace('@LOADER@', function(source, 'loadScriptFile')).replace('@CALLER@', caller[0])
                   .replace('@CHECKS@', '\n'.join(checks)))

    def test_loader_and_all_original_bonus_routes(self):
        from test_historical_behavior import native
        from unittest.mock import patch
        profiles = [row['revision'] for row in saved_bonus_model_rows()]
        program = bonus_program((ENGINE/'openbor.c').read_text(),
                                (ENGINE/'openbor.h').read_text(), profiles, trace=False)
        with patch.dict(os.environ, sanitizer_environment()):
            native(program, extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))


if __name__ == '__main__':
    unittest.main()
