"""Exercise the actual saved-game loader and its four bonus caller routes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function
from test_historical_level_runtime import PROFILES

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT/'src/engines/3842'))


def bonus_program(source, header, profiles):
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
void getBasePath(char *path,const char *kind,int unused) {
    (void)kind;(void)unused;path[0]=0;
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
    remove("probe.save");
    num_difficulties=mode==5?(int)sizeof(s_savelevel):3;
    assert(num_difficulties>=3 && num_difficulties<4096);
    free(savelevel);savelevel=calloc((size_t)num_difficulties,sizeof(*savelevel));assert(savelevel);
    for(int i=0;i<3;++i) {savelevel[i].compatibleversion=CV_SAVED_GAME;savelevel[i].times_completed=7+i;}
    bonus=91;
    if(mode==0)return;
    FILE *file=fopen("probe.save","wb");assert(file);
    s_savelevel *rows=calloc((size_t)num_difficulties,sizeof(*rows));assert(rows);
    for(int i=0;i<num_difficulties;++i)rows[i].compatibleversion=CV_SAVED_GAME;
    rows[0].times_completed=2;rows[1].times_completed=3;
    if(mode==4 || mode==5)rows[0].compatibleversion=0;
    if(mode==3) {
        assert(fwrite(rows,sizeof(*rows),1,file)==1);
        assert(fwrite(&rows[1].compatibleversion,1,sizeof(rows[1].compatibleversion),file)==sizeof(rows[1].compatibleversion));
    } else if(mode!=2)assert(fwrite(rows,sizeof(*rows),(size_t)num_difficulties,file)==(size_t)num_difficulties);
    free(rows);assert(fclose(file)==0);
}
int main(void) {
    const unsigned profiles[]={PROFILES};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(int mode=0;mode<6;++mode)for(int route=0;route<5;++route) {
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
            printf("SAVE_BONUS %u mode=%d route=%d result=%d bonus=%d records=%d first=%u second=%u\n",
                obor_profile_build,mode,route,result,bonus,num_difficulties,
                savelevel[0].times_completed,savelevel[1].times_completed);
        }
    }
    free(savelevel);remove("probe.save");return 0;
}
'''.replace('CONSTANTS', '\n'.join(constants)).replace('RECORD', record).replace(
        'CLEAR', clear).replace('LOADER', loader).replace('CALLERS', '\n'.join(callers)).replace(
        'PROFILES', ','.join(map(str, profiles)))


class HistoricalSaveBonusTests(unittest.TestCase):
    def test_loader_and_all_original_bonus_routes(self):
        program = bonus_program((ENGINE/'openbor.c').read_text(),
                                (ENGINE/'openbor.h').read_text(), PROFILES)
        with tempfile.TemporaryDirectory(prefix='historical-save-bonus-') as temp:
            work = Path(temp)
            (work/'probe.c').write_text(program)
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-g', '-fsanitize=address,undefined', str(work/'probe.c'), '-o', str(work/'probe')],
                check=True, timeout=45)
            subprocess.run([str(work/'probe')], check=True, timeout=20, cwd=work,
                           stdout=subprocess.DEVNULL,
                           env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                                    UBSAN_OPTIONS='halt_on_error=1'))


if __name__ == '__main__':
    unittest.main()
