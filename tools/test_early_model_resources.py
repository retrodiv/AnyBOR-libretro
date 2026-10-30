"""Check owned and inherited model resources at historical cleanup boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-model-resources.json'


class EarlyModelResourcesTests(unittest.TestCase):

    def test_allocation_proxy_release_policy(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-allocators.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['proxy']), bool)
            entries.append('{%d,%d}' % (row['revision'], row['proxy']))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        # Keep original literal labels at the reviewed live call sites. Comments
        # and whitespace are not C tokens; quoted labels retain their spaces.
        lexical = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\w+|[^\s]', re.S)

        def tokens(text):
            return [match[0] for match in lexical.finditer(text)
                    if not match[0].startswith(('/*', '//'))]

        units, bodies, patterns = {}, {}, {}

        def selected_source(caller):
            relative = Path(caller['path'])
            self.assertFalse(relative.is_absolute())
            self.assertNotIn('..', relative.parts)
            if caller['path'] not in units:
                units[caller['path']] = (engine / relative).read_text()
            unit = units[caller['path']]
            selector = json.dumps({key: caller.get(key) for key in ('function', 'macro', 'region')},
                                  sort_keys=True)
            cache = caller['path'], selector
            if cache not in bodies:
                if caller.get('macro'):
                    match = re.search(r'(?m)^#[ \t]*define[ \t]+' +
                                      re.escape(caller['macro']) + r'(?=[ (])', unit)
                    self.assertIsNotNone(match, 'Missing allocation macro')
                    lines = []
                    for line in unit[match.start():].splitlines(True):
                        lines.append(line)
                        if not line.rstrip().endswith('\\'):
                            break
                    selected = ''.join(lines)
                elif caller.get('region'):
                    start, end = caller['region']['start'], caller['region']['end']
                    self.assertEqual(unit.count(start), 1)
                    self.assertEqual(unit.count(end), 1)
                    first = unit.index(start)
                    selected = unit[first:unit.index(end, first)]
                else:
                    selected = function(unit, caller['function'])
                bodies[cache] = tokens(selected)
            return cache, bodies[cache]

        for caller in fixture['callers']:
            with self.subTest(path=caller['path'], function=caller['function'], label=caller['label']):
                cache, body = selected_source(caller)
                expected = tokens(caller['statement'])
                self.assertTrue(expected)
                self.assertIn(json.dumps(caller['label']), expected)
                key = cache, tuple(expected)
                if key not in patterns:
                    patterns[key] = [0, sum(body[index:index + len(expected)] == expected
                                          for index in range(len(body) - len(expected) + 1)),
                                     caller['label']]
                patterns[key][0] += 1
                for dispatch in caller.get('dispatch', []):
                    _, dispatched = selected_source(dict(path=caller['path'], **dispatch))
                    request = tokens(dispatch['statement'])
                    self.assertTrue(any(dispatched[index:index + len(request)] == request
                                        for index in range(len(dispatched) - len(request) + 1)),
                                    'Missing shared allocation dispatch')
        for expected, observed, label in patterns.values():
            self.assertEqual(observed, expected,
                             'Missing original allocation label or changed request: ' + label)
        unit = (engine / 'source/utils.c').read_text()
        functions = ['obor_profile_malloc_named', 'obor_profile_calloc_named', 'obor_profile_realloc_named']
        program = (FIXTURE.parent / 'early_allocation_policy.c').read_text().replace(
            '@FUNCTIONS@', '\n'.join(function(unit, name) for name in functions)).replace(
            '@BUFFER_CALLER@', function((engine / 'openbor.c').read_text(), 'buffer_pakfile')).replace(
            '@ROWS@', ','.join(entries))
        with tempfile.TemporaryDirectory(prefix='early-allocation-policy-') as directory:
            work = Path(directory)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(program)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = compiler + ['-std=gnu99', '-O1', '-g', '-DLIBRETRO=1', '-Wall', '-Wextra', '-Werror',
                '-Wno-sign-compare',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', str(source), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 env=sanitizer_environment(), timeout=30)
            if os.environ.get('OBOR_ALLOCATION_POLICY_OBSERVATIONS'):
                Path(os.environ['OBOR_ALLOCATION_POLICY_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), scope=fixture['scope'],
                    retirement='TemporaryDirectory removes probe source and executable'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('allocation_policy=1', run.stdout)




    def test_png_allocation_policy(self):
        from make_fixture import png
        from test_bitmap_dimensions import native_context

        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-allocators.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        loader = (engine / 'source/gamelib/loadimg.c').read_text()
        functions = ['obor_profile_png_allocate', 'obor_profile_png_release', 'png_read_fn',
                     'png_read_destroy_all', 'closepng', 'openpng']
        image = png(2, 1, lambda x, y: x + 1)
        program = (FIXTURE.parent / 'early_png_allocation_policy.c').read_text().replace(
            '@PNG_BYTES@', ','.join(map(str, image))).replace(
            '@MALLOC_POLICY@', function((engine / 'source/utils.c').read_text(), 'obor_profile_malloc_named')).replace(
            '@PNG_FUNCTIONS@', '\n'.join(function(loader, name) for name in functions)).replace(
            '@ROWS@', ','.join('{%d,%d}' % (row['revision'], row['proxy']) for row in rows))
        compiler, flags, links = native_context(fixture['engine'])
        with tempfile.TemporaryDirectory(prefix='early-png-allocation-policy-') as name:
            work = Path(name)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(program)
            command = compiler + flags + [str(source), '-o', str(binary)] + links
            build = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 env=sanitizer_environment(), timeout=30)
            if os.environ.get('OBOR_PNG_ALLOCATION_OBSERVATIONS'):
                Path(os.environ['OBOR_PNG_ALLOCATION_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr,
                    program_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    image_sha256=hashlib.sha256(image).hexdigest(),
                    scope='Actual PNG constructor/read/close and allocator policy with real libpng;authored valid indexed image and finite callback refusal. No gameplay or full model loading.',
                    retirement='TemporaryDirectory removes source and executable'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('png_allocation_policy=1', run.stdout)

    def test_casesearch_empty_component(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-casesearch.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertTrue(type(row['assert_line']) is int and 0 <= row['assert_line'] < 10000)
            self.assertEqual(bool(row['expression']), bool(row['assert_line']))
            entries.append('{%d,%d,%s}' % (row['revision'], row['assert_line'], json.dumps(row['expression'])))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'source/gamelib/packfile.c').read_text()
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <setjmp.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include "obor_packfile_profile.h"
#if !defined(LIBRETRO) || (!defined(LINUX) && !defined(DARWIN))
#error This probe requires a native case-search target
#endif
uint32_t obor_profile_build;
static unsigned phase,opened,closed,live,switched,diagnostics,flushes;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Case search revision=%u phase=%u line=%d: %s\n",obor_profile_build,phase,__LINE__,#c);abort();}}while(0)
static int engine_alive,engine_exit_status,frontend_token;
static void *co_frontend=&frontend_token;
static jmp_buf returned;
static char diagnostic[512];
static void co_switch(void *target) {
 CHECK(target==co_frontend && !engine_alive && engine_exit_status==1);
 ++switched;longjmp(returned,1);
}
@STOP@
static int capture_fprintf(FILE *file,const char *format,...) {
 CHECK(file==stderr);va_list args;va_start(args,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 CHECK(n>=0 && (size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static int capture_fflush(FILE *file) {CHECK(file==stderr);++flushes;return 0;}
#define fprintf capture_fprintf
#define fflush capture_fflush
@ASSERT@
#undef fprintf
#undef fflush
static DIR *tracked_opendir(const char *name) {
 DIR *d=opendir(name);if(d){++opened;++live;}return d;
}
static int tracked_closedir(DIR *d) {
 CHECK(d && live);int result=closedir(d);CHECK(!result);++closed;--live;return result;
}
#define opendir tracked_opendir
#define closedir tracked_closedir
#define stricmp strcasecmp
@SEARCH@
#undef opendir
#undef closedir
typedef struct {unsigned revision;int line;const char *expression;} Row;
static const Row rows[]={@ROWS@};
static void reset(void) {
 CHECK(!live);opened=closed=switched=diagnostics=flushes=0;diagnostic[0]=0;
 engine_alive=1;engine_exit_status=-1;
}
static void empty_component(const Row *row,const char *name) {
 reset();int jump=setjmp(returned);
 if(!jump)CHECK(casesearch(".",name)==NULL);
#ifdef NDEBUG
 int stop=0;
#else
 int stop=row->line!=0;
#endif
 CHECK(jump==stop && switched==(unsigned)stop && diagnostics==(unsigned)stop && flushes==(unsigned)stop);
 CHECK(engine_alive==!stop && engine_exit_status==(stop?1:-1));
 CHECK(opened==1 && closed==1 && !live);
 if(stop) {
  char expected[512];snprintf(expected,sizeof(expected),
   "source/gamelib/packfile.c:%i: casesearch: Assertion `%s' failed.\n",row->line,row->expression);
  CHECK(!strcmp(diagnostic,expected));
 } else CHECK(!diagnostic[0]);
}
int main(void) {
 FILE *file=fopen("FiLe.TxT","wb");CHECK(file && !fclose(file));CHECK(!mkdir("Folder",0700));
 file=fopen("Folder/Child.Txt","wb");CHECK(file && !fclose(file));
 char component[91],longdir[512]="";
 for(int level=0;level<3;++level) {
  memset(component,'a'+level,90);component[90]=0;
  if(level)strcat(longdir,"/");
  strcat(longdir,component);CHECK(!mkdir(longdir,0700));
 }
 char leaf[600];int n=snprintf(leaf,sizeof(leaf),"%s/Leaf.txt",longdir);
 CHECK(n>0 && (size_t)n<sizeof(leaf));file=fopen(leaf,"wb");CHECK(file && !fclose(file));
 for(unsigned i=0;i<sizeof(rows)/sizeof(rows[0]);++i) {
  const Row *row=&rows[i];obor_profile_build=row->revision;
  phase=1;reset();char *found=casesearch(".","file.txt");CHECK(found && !strcmp(found,"./FiLe.TxT"));
  CHECK(opened==1 && closed==1 && !live && !diagnostics && !switched);
  phase=2;reset();CHECK(!casesearch(".","absent.txt") && opened==1 && closed==1 && !live);
  phase=3;reset();CHECK(!casesearch("absent-directory","/file.txt") && !opened && !closed && !switched);
  phase=4;empty_component(row,"/file.txt");
  phase=5;empty_component(row,"/");
  phase=6;reset();CHECK(!casesearch(".","") && opened==1 && closed==1 && !live);
  phase=7;reset();CHECK(!casesearch(".","Folder/") && opened==2 && closed==2 && !live && !switched);
  phase=8;reset();found=casesearch(".","folder/child.txt");
  CHECK(found && !strcmp(found,"./Folder/Child.Txt") && opened==2 && closed==2 && !live);
  /* Candidate-only capacity control: no original oversized-path oracle. */
  phase=9;reset();CHECK(!casesearch(longdir,"leaf.txt") && opened==1 && closed==1 && !live && !switched);
 }
 CHECK(!remove(leaf));
 for(int level=0;level<3;++level) {
  CHECK(!rmdir(longdir));char *slash=strrchr(longdir,'/');if(slash)*slash=0;
 }
 CHECK(!remove("Folder/Child.Txt") && !remove("FiLe.TxT") && !rmdir("Folder"));
 puts("early_casesearch=1");return 0;
}
'''
        for key, value in dict(ROWS=',\n'.join(entries), STOP=function(port, 'borExit'),
                               ASSERT=function(port, 'obor_port_assert'), SEARCH=function(source, 'casesearch')).items():
            program = program.replace('@'+key+'@', value)
        with tempfile.TemporaryDirectory(prefix='early-casesearch-') as name:
            work = Path(name)
            unit = work / 'probe.c'
            unit.write_text(program)
            for disabled in (False, True):
                binary = work / ('probe-disabled' if disabled else 'probe-enabled')
                directory = work / ('disabled' if disabled else 'enabled')
                directory.mkdir()
                links = [] if sys.platform == 'darwin' else ['-no-pie']
                command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                    '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-DLIBRETRO=1', '-DOBOR_CONTROLLED_ASSERTIONS=1', '-DOBOR_ENGINE_BUILD='+fixture['engine'],
                    '-DDARWIN=1' if sys.platform == 'darwin' else '-DLINUX=1',
                    '-Wno-error=deprecated-declarations', '-DNDEBUG' if disabled else '-UNDEBUG',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                    '-I', str(engine / 'source/gamelib'), str(unit), *links, '-o', str(binary)]
                build = subprocess.run(command, capture_output=True, text=True, timeout=45)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                run = subprocess.run([str(binary)], cwd=directory, capture_output=True, text=True,
                                     timeout=10, env=sanitizer_environment())
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn('early_casesearch=1', run.stdout)

    def test_log_enablement_and_stream_lifetime(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-log-policy.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['legacy']), bool)
            entries.append('{%d,%d}' % (row['revision'], row['legacy']))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        utility = (engine / 'source/utils.c').read_text()
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <unistd.h>
#include "openbor.h"
#undef assert
#undef printf
#if !defined(LIBRETRO) || defined(DC)
#error This probe requires the maintained non-DC LIBRETRO target
#endif
uint32_t obor_profile_build;
static unsigned scenario,phase;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Log policy revision=%u scenario=%u phase=%u line=%d: %s\n",obor_profile_build,scenario,phase,__LINE__,#c);abort();}}while(0)
#define OPENBOR_LOG 1
#define SCRIPT_LOG 0
static const char *path(int which) {return which?"engine.log":"script.log";}
@EXISTS@
#define CHECK_LOGFILE(which) fileExists((char*)path(which))
#define OPEN_LOGFILE(which) fopen(path(which),"wt")
#define APPEND_LOGFILE(which) fopen(path(which),"at")
FILE *openborLog,*scriptLog;
@FUNCTIONS@
static unsigned char expected[2][8192];
static size_t used[2];
static void append(int which,const void *data,size_t size) {
 CHECK(used[which]+size<sizeof(expected[which]));
 memcpy(expected[which]+used[which],data,size);used[which]+=size;
}
static void contents(int which) {
 unsigned char bytes[8192];FILE *f=fopen(path(which),"rb");CHECK(f);
 size_t size=fread(bytes,1,sizeof(bytes),f);CHECK(!ferror(f));CHECK(!fclose(f));
 CHECK(size==used[which] && !memcmp(bytes,expected[which],size));
}
static void probe_seed_file(int which) {
 FILE *f=fopen(path(which),"wb");CHECK(f);CHECK(fwrite("stale",1,5,f)==5);CHECK(!fclose(f));
 used[which]=0;append(which,"stale",5);
}
static void close_retained(void) {
 if(openborLog){CHECK(!fclose(openborLog));openborLog=NULL;}
 if(scriptLog){CHECK(!fclose(scriptLog));scriptLog=NULL;}
}
static void check(int legacy) {
 /* A failed initial open clears the old first-write flag, even without a file. */
 if(scenario) {
  phase=1;CHECK(!mkdir(path(0),0700) && !mkdir(path(1),0700));savedata.uselog=1;
  writeToLogFile("failed\n");writeToScriptLog("failed\n");CHECK(!openborLog && !scriptLog);
  CHECK(!rmdir(path(0)) && !rmdir(path(1)));
 }
 phase=2;probe_seed_file(0);probe_seed_file(1);savedata.uselog=0;
 writeToLogFile("off%d\n",0);writeToScriptLog("off0\n");
 if(!legacy)for(int w=0;w<2;w++){used[w]=0;append(w,"off0\n",5);}
 contents(0);contents(1);CHECK((openborLog==NULL)==legacy && (scriptLog==NULL)==legacy);
 phase=3;savedata.uselog=1;
 writeToLogFile("A:%d\n",7);writeToScriptLog("A\n");
 if(legacy && !scenario)used[0]=used[1]=0;
 append(1,"A:7\n",4);append(0,"A\n",2);contents(0);contents(1);
 phase=4;savedata.uselog=0;writeToLogFile("B\n");writeToScriptLog("B\n");
 if(!legacy){append(0,"B\n",2);append(1,"B\n",2);}contents(0);contents(1);
 phase=5;savedata.uselog=-1;writeToLogFile("C:%s\n","ok");writeToScriptLog("C\n");
 append(1,"C:ok\n",5);append(0,"C\n",2);contents(0);contents(1);
 phase=6;writeToLogFile("%s%c%s","L",0,"R");
 append(1,"L\0R",legacy?1:3);contents(1);
 /* Longer-than-original formatting has a bounded candidate result only. */
 phase=7;char large[1500];memset(large,'x',sizeof(large)-1);large[sizeof(large)-1]=0;
 writeToLogFile("%s",large);append(1,large,legacy?1023:sizeof(large)-1);contents(1);
 phase=8;CHECK(!remove(path(0)) && !remove(path(1)));
 writeToLogFile("D\n");writeToScriptLog("D\n");
 if(legacy){used[0]=used[1]=0;append(0,"D\n",2);append(1,"D\n",2);contents(0);contents(1);}
 else CHECK(access(path(0),F_OK)!=0 && access(path(1),F_OK)!=0);
 close_retained();
 phase=9;writeToLogFile("E\n");writeToScriptLog("E\n");
 if(!legacy)used[0]=used[1]=0;
 append(0,"E\n",2);append(1,"E\n",2);contents(0);contents(1);close_retained();
 CHECK(!remove(path(0)) && !remove(path(1)));
}
typedef struct {unsigned revision;int legacy;} Row;
static const Row rows[]={@ROWS@};
int main(int argc,char **argv) {
 CHECK(argc==3);obor_profile_build=(unsigned)strtoul(argv[1],NULL,10);
 scenario=(unsigned)strtoul(argv[2],NULL,10);CHECK(scenario<2);
 for(unsigned i=0;i<sizeof(rows)/sizeof(rows[0]);++i)if(rows[i].revision==obor_profile_build) {
  check(rows[i].legacy);puts("early_log_policy=1");return 0;
 }
 CHECK(0);return 1;
}
'''
        program = program.replace('@ROWS@', ',\n'.join(entries))
        program = program.replace('@EXISTS@', function(utility, 'fileExists'))
        program = program.replace('@FUNCTIONS@', '\n'.join(function(utility, n) for n in [
            'obor_profile_open_log', 'writeToLogFile', 'writeToScriptLog']))
        with tempfile.TemporaryDirectory(prefix='early-log-policy-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = compiler + ['-std=gnu11', '-O1', '-g', '-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fcommon', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                '-Wno-unused-but-set-variable', *warnings,
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                *['-I'+str(p) for p in includes], str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            observations = []
            for row in rows:
                for scenario in range(2):
                    directory = work / ('case-%d-%d' % (row['revision'], scenario))
                    directory.mkdir()
                    run = subprocess.run([str(binary), str(row['revision']), str(scenario)], cwd=directory,
                                         capture_output=True, text=True, timeout=10, env=sanitizer_environment())
                    observations.append(dict(revision=row['revision'], scenario=scenario,
                                             returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
                    if run.returncode:
                        break
                if run.returncode:
                    break
            if os.environ.get('OBOR_LOG_POLICY_OBSERVATIONS'):
                Path(os.environ['OBOR_LOG_POLICY_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), completed_scenarios=len(observations), compiler=compiler,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), observations=observations,
                    scope=fixture['scope'], retirement='TemporaryDirectory removes file logs,source and binary'),
                    indent=2)+'\n')
            self.assertEqual(len(observations), len(rows)*2)
            for row in observations:
                self.assertEqual(row['returncode'], 0, row['stdout']+row['stderr'])
                self.assertIn('early_log_policy=1', row['stdout'])

    def test_map_reservation_feedback(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-map-feedback.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['emit']), 3)
            self.assertEqual(len(row['labels']), 3)
            self.assertTrue(all(type(value) is bool for value in row['emit']))
            self.assertTrue(all(isinstance(value, str) and len(value) < 64 for value in row['labels']))
            self.assertIn(row['sprite_delta'], (0, 1))
            self.assertIn(row['cache_delta'], (0, 1))
            self.assertEqual(len(row['model_events']), 3)
            counts, events = [], []
            for positions in row['model_events']:
                self.assertTrue(len(positions) <= 3 and positions == sorted(set(positions)))
                self.assertTrue(all(type(n) is int and 0 <= n < 130 for n in positions))
                counts.append(str(len(positions)))
                events.append('{'+','.join(map(str, positions+[0]*(3-len(positions))))+'}')
            entries.append('{%d,{%s},{%s},{%d,%d},{%s},{%s}}' % (
                row['revision'], ','.join(str(int(n)) for n in row['emit']),
                ','.join(json.dumps(n) for n in row['labels']),
                row['sprite_delta'], row['cache_delta'], ','.join(events), ','.join(counts)))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        self.assertEqual(function(source, 'loadsprite').count('obor_prepare_sprite_map(sprites_loaded);'), 2)
        self.assertEqual(function(source, 'cache_model').count('obor_prepare_cache_map(models_cached);'), 1)
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <limits.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "models.h"
#include "List.h"
#include "utils.h"
#if !defined(LIBRETRO) || defined(VERBOSE)
#error Profile map probe requires LIBRETRO and the maintained non-VERBOSE target mode.
#endif
#undef printf
#undef fprintf
#undef assert
#undef exit
#undef time
#undef pause
#undef shutdown
#undef malloc
#undef calloc
#undef realloc
#undef free
uint32_t obor_profile_build;
static unsigned phase,cycle,item,events;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Map feedback revision=%u phase=%u cycle=%u item=%u line=%d: %s\n",obor_profile_build,phase,cycle,item,__LINE__,#c);abort();}}while(0)
#define assert CHECK
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int sprite_map_max_items,cache_map_max_items;
static unsigned sprites_loaded,models_cached;
static void *expected_pointer;
typedef struct {unsigned revision;int emit[3];const char *labels[3];unsigned delta[2],positions[3][3],count[3];} Row;
static const Row rows[]={@ROWS@};
static const Row *active;
static int capture_printf(const char *format,...) {
 CHECK(phase<3 && active->emit[phase] && !strcmp(format,"%s %p\n"));
 va_list ap;va_start(ap,format);const char *label=va_arg(ap,const char *);
 void *pointer=va_arg(ap,void *);va_end(ap);
 CHECK(!strcmp(label,active->labels[phase])&&pointer==expected_pointer);
 ++events;return 1;
}
static void unexpected_shutdown(int status,const char *format,...) {(void)status;(void)format;abort();}
static void *checked_realloc(void *pointer,size_t bytes) {
 CHECK(bytes&&bytes<=(8u<<20));void *out=realloc(pointer,bytes);CHECK(out);return out;
}
#define printf capture_printf
#define shutdown unexpected_shutdown
#define realloc checked_realloc
@RESERVE@
@WRAPPERS@
#undef realloc
@FREE@
@LOWER@
#include @MODEL_UNIT@
#undef shutdown
#undef printf
static s_model storage[130],cache_sentinel;
static char names[130][16];
static void reserve_storage(void) {
 for(phase=0;phase<2;++phase)for(cycle=0;cycle<3;++cycle) {
  for(item=0;item<300;++item) {
   unsigned size=item+active->delta[phase];
   int capacity=phase?cache_map_max_items:sprite_map_max_items;
   expected_pointer=phase?(void *)model_cache:(void *)sprite_map;
   unsigned want=active->emit[phase]&&(!expected_pointer||size>=(unsigned)capacity);
   events=0;
   if(phase)obor_prepare_cache_map(item);else obor_prepare_sprite_map(item);
   expected_pointer=NULL;
   CHECK(events==want);
   CHECK((phase?cache_map_max_items:sprite_map_max_items)>(int)size);
   if(phase) {
    for(unsigned i=0;i<item;++i)CHECK(model_cache[i].model==&cache_sentinel&&model_cache[i].loadflag==(int)(i&1));
    memset(&model_cache[item],0,sizeof(*model_cache));
    model_cache[item].model=&cache_sentinel;model_cache[item].loadflag=item&1;
    models_cached=item+1;
   } else {
    for(unsigned i=0;i<item;++i)CHECK(sprite_map[i].centerx==(int)(3*i)&&sprite_map[i].centery==(int)(5*i));
    memset(&sprite_map[item],0,sizeof(*sprite_map));
    sprite_map[item].centerx=3*item;sprite_map[item].centery=5*item;
    sprites_loaded=item+1;
   }
  }
  int previous_capacity=phase?cache_map_max_items:sprite_map_max_items;
  if(phase){free_modelcache();CHECK(!model_cache&&!models_cached);}
  else {freesprites();CHECK(!sprite_map&&!sprites_loaded);}
  CHECK(previous_capacity==(phase?cache_map_max_items:sprite_map_max_items));
 }
}
static void registry_storage(void) {
 phase=0;cycle=0;item=0;events=0;expected_pointer=NULL;
 obor_prepare_sprite_map(0);CHECK(events==(unsigned)active->emit[0]);CHECK(sprite_map);
 expected_pointer=NULL;
 phase=2;
 for(cycle=0;cycle<3;++cycle) {
  unsigned at=0;createModelList();
  for(item=0;item<130;++item) {
   memset(&storage[item],0,sizeof(storage[item]));
   snprintf(names[item],sizeof(names[item]),"model%03u",item);
   storage[item].name=names[item];storage[item].index=item;
   expected_pointer=sprite_map;events=0;
   addModel(&storage[item]);expected_pointer=NULL;
   unsigned want=at<active->count[cycle]&&active->positions[cycle][at]==item;
   CHECK(events==want);
   if(want)++at;
  }
  CHECK(at==active->count[cycle]);
  /* Clear the actual registry while model values retain their separate lifetime. */
  freeModelList();
 }
 freesprites();
}
int main(int argc,char **argv) {
 CHECK(argc==2);
 unsigned requested=(unsigned)strtoul(argv[1],NULL,10);
 for(unsigned i=0;i<sizeof(rows)/sizeof(rows[0]);++i)
  if(rows[i].revision==requested) {active=&rows[i];break;}
 CHECK(active);obor_profile_build=active->revision;
 reserve_storage();registry_storage();
 printf("early_map_feedback=1 revision=%u\n",obor_profile_build);
 return 0;
}
'''
        replacements = dict(ROWS=',\n'.join(entries),
            RESERVE='\n'.join(function(source, n) for n in ['prepare_sprite_map', 'prepare_cache_map']),
            WRAPPERS='\n'.join(function(source, n) for n in ['obor_prepare_sprite_map', 'obor_prepare_cache_map']),
            FREE='\n'.join(function(source, n) for n in ['freesprites', 'free_modelcache']),
            LOWER=function((engine / 'source/utils.c').read_text(), 'lc'),
            MODEL_UNIT=json.dumps(str(engine / 'source/gamelib/models.c')))
        for key, value in replacements.items():
            program = program.replace('@'+key+'@', value)
        with tempfile.TemporaryDirectory(prefix='early-map-feedback-') as name:
            unit, obj, binary = Path(name)/'probe.c', Path(name)/'list.o', Path(name)/'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler+['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie','-Wl,--gc-sections']
            includes = [engine, ROOT/'src/port/libretro', ROOT/'src/glue', engine/'source',
                        *sorted(p for p in (engine/'source').iterdir() if p.is_dir())]
            flags = ['-std=gnu11','-O1','-g','-UNDEBUG','-DLIBRETRO=1','-UVERBOSE','-DSAFEALLOC_H=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'],'-Dstricmp=strcasecmp','-fcommon','-fsigned-char',
                     '-ffunction-sections','-fdata-sections','-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all','-fno-omit-frame-pointer',*['-I'+str(p) for p in includes]]
            build = subprocess.run(compiler+flags+['-c',str(engine/'source/scriptlib/List.c'),'-o',str(obj)],
                                   capture_output=True,text=True,timeout=45)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            build = subprocess.run(compiler+flags+['-Wall','-Wextra','-Werror','-Wno-unused-variable',
                '-Wno-unused-function','-Wno-unused-parameter','-Wno-sign-compare',
                '-Wno-error=deprecated-declarations',*warnings,str(unit),str(obj),*links,'-o',str(binary)],
                capture_output=True,text=True,timeout=45)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            observations = []
            for row in rows:
                run = subprocess.run([str(binary),str(row['revision'])],capture_output=True,text=True,
                                     timeout=10,env=sanitizer_environment())
                observations.append(dict(revision=row['revision'],returncode=run.returncode,
                                         stdout=run.stdout,stderr=run.stderr))
                if run.returncode:
                    break
            if os.environ.get('OBOR_MAP_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_MAP_FEEDBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows),completed_contexts=len(observations),compiler=compiler,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    model_unit_sha256=hashlib.sha256((engine/'source/gamelib/models.c').read_bytes()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),observations=observations,
                    native_defines=fixture['native_defines'],scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/object/binary'),indent=2)+'\n')
            self.assertEqual(len(observations),len(rows))
            for row in observations:
                self.assertEqual(row['returncode'],0,row['stdout']+row['stderr'])
                self.assertIn('early_map_feedback=1',row['stdout'])

    def test_load_progress_feedback_per_profile(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-load-progress-feedback.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key in ['cache_format', 'load_format']:
                self.assertIsInstance(row[key], str)
                self.assertLess(len(row[key]), 128)
            self.assertTrue(row['logo_message'] is None or type(row['logo_message']) is bool)
            entries.append('{%d,%s,%s,%d}' % (row['revision'], json.dumps(row['cache_format']),
                json.dumps(row['load_format']), -1 if row['logo_message'] is None else row['logo_message']))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        loader = function(source, 'load_cached_model')
        end = loader.index('\n\tobor_landframe_model_check(newchar);')
        starts = [loader.rfind(prefix, 0, end) for prefix in [
            '\n\tif(obor_profile_build < 3122) printf("Loading',
            '\n\tprintf("Loading']]
        start = max(starts)
        self.assertGreaterEqual(start, 0)
        load_window = loader[start+1:end]
        self.assertIn('newchar->name', load_window)
        self.assertIn('filename', load_window)
        logos = re.findall(r'if\(custBkgrds != NULL\)\s*\{[^{}]*}\s*else\s*'
                           r'\{[^{}]*load_cached_background\("data/bgs/logo", 0\);[^{}]*}',
                           function(source, 'openborMain'))
        self.assertEqual(len(logos), 1)
        program = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef exit
#undef shutdown
#undef time
#undef pause
uint32_t obor_profile_build;
static unsigned scenario;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Load feedback revision=%u scenario=%u line=%d: %s\n",obor_profile_build,scenario,__LINE__,#c);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int models_cached;
static unsigned reservations,peeks,prints,background_calls,background_kind;
static char message[512],background_name[128],tmpBuff[128];
static char *custBkgrds;
static int capture_printf(const char *format,...) {
 va_list ap;va_start(ap,format);
 int n=vsnprintf(message,sizeof(message),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(message));++prints;return n;
}
static void obor_prepare_cache_map(size_t count) {
 CHECK(count==(size_t)models_cached&&count<2&&model_cache);++reservations;
}
static void _peek_model_name(int index) {
 CHECK(index==models_cached&&model_cache[index].name&&model_cache[index].path);++peeks;
}
void load_background(char *name,int tables) {
 CHECK(!tables&&strlen(name)<sizeof(background_name));strcpy(background_name,name);
 ++background_calls;background_kind=1;
}
void load_cached_background(char *name,int tables) {
 CHECK(!tables&&strlen(name)<sizeof(background_name));strcpy(background_name,name);
 ++background_calls;background_kind=2;
}
#define printf capture_printf
@CACHE@
@FREE_CACHE@
static void loaded_message(s_model *newchar,char *filename) {
@LOAD_WINDOW@
}
static void choose_logo(void) {
@LOGO@
}
#undef printf
typedef struct {unsigned revision;const char *cache_format,*load_format;int logo;} Row;
static Row rows[]={@ROWS@};
int main(void) {
 const char *names[]={"Hero","Helper's"},*paths[]={"data/hero.txt","data/actors/help %s.txt"};
 s_model loaded;memset(&loaded,0,sizeof(loaded));
 unsigned contexts=sizeof(rows)/sizeof(rows[0]);
 for(unsigned r=0;r<contexts;++r) {
  obor_profile_build=rows[r].revision;models_cached=0;
  model_cache=calloc(2,sizeof(*model_cache));CHECK(model_cache);
  reservations=peeks=0;
  for(unsigned p=0;p<2;++p) {
   ++scenario;prints=0;message[0]=0;
   cache_model((char *)names[p],(char *)paths[p],(int)p);
   CHECK(models_cached==(int)p+1&&reservations==p+1&&peeks==p+1&&prints==1);
   CHECK(!strcmp(model_cache[p].name,names[p])&&!strcmp(model_cache[p].path,paths[p]));
   CHECK(model_cache[p].loadflag==(int)p);
   char expected[512];int n=snprintf(expected,sizeof(expected),rows[r].cache_format,names[p],paths[p]);
   CHECK(n>=0&&(size_t)n<sizeof(expected)&&!strcmp(message,expected));
  }
  free_modelcache();CHECK(!models_cached&&!model_cache);
  for(unsigned p=0;p<2;++p) {
   ++scenario;prints=0;message[0]=0;loaded.name=(char *)names[p];
   loaded_message(&loaded,(char *)paths[p]);
   char expected[512];int n=snprintf(expected,sizeof(expected),rows[r].load_format,names[p],paths[p]);
   CHECK(n>=0&&(size_t)n<sizeof(expected)&&prints==1&&!strcmp(message,expected));
  }
  if(rows[r].logo>=0) for(unsigned custom=0;custom<2;++custom) {
   ++scenario;prints=background_calls=background_kind=0;message[0]=background_name[0]=tmpBuff[0]=0;
   custBkgrds=custom?(char *)"art/":NULL;choose_logo();
   CHECK(background_calls==1&&background_kind==(custom?1u:2u));
   CHECK(!strcmp(background_name,custom?"art/logo":"data/bgs/logo"));
   CHECK(prints==(!custom&&(unsigned)rows[r].logo));
   CHECK(!strcmp(message,(!custom&&rows[r].logo)?"use cached bg\n":""));
  }
 }
 printf("early_load_progress_feedback=1 contexts=%u cases=%u\n",contexts,scenario);
 return 0;
}
'''
        replacements = dict(CACHE=function(source, 'cache_model'), FREE_CACHE=function(source, 'free_modelcache'),
                            LOAD_WINDOW=load_window, LOGO=logos[0], ROWS=',\n'.join(entries))
        for key, value in replacements.items():
            program = program.replace('@'+key+'@', value)
        with tempfile.TemporaryDirectory(prefix='early-load-progress-feedback-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else ['-Wno-stringop-truncation']
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fsigned-char', '-fcommon',
                     '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare',
                     '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-unused-variable', *warnings]
            build = subprocess.run(compiler + flags + ['-I'+str(p) for p in includes] +
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_LOAD_PROGRESS_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_LOAD_PROGRESS_FEEDBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source and binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_load_progress_feedback=1', run.stdout)

    def test_shutdown_feedback_per_profile(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-shutdown-feedback.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['payload_copies'], (1, 2))
            self.assertEqual(row['payload_before_cleanup'], row['payload_copies'] == 2)
            self.assertEqual(row['normal_format'].count('%s'), 2)
            self.assertLess(len(row['normal_format']), 256)
            entries.append('{%d,%s,%d,%d}' % (row['revision'], json.dumps(row['normal_format']),
                                             row['payload_copies'], row['payload_before_cleanup']))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        program = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef exit
#undef shutdown
#undef time
#undef pause
uint32_t obor_profile_build;
static unsigned scenario;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Shutdown feedback revision=%u scenario=%u line=%d: %s\n",obor_profile_build,scenario,__LINE__,#c);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int disablelog,startup_done,engine_alive,engine_exit_status,expected_status,frontend_token;
static List *modelcmdlist,*modelstxtcmdlist,*levelcmdlist,*levelordercmdlist;
static void *co_frontend=&frontend_token;
static jmp_buf frontend_return;
static unsigned stops,cleanup_calls,payloads,payloads_at_cleanup,prints,credits;
static char expected[512];
void co_switch(void *target) {
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==expected_status);
 ++stops;longjmp(frontend_return,1);
}
@STOP@
static void cleanup_event(const char *name) {
 CHECK(name);
 if(!cleanup_calls) payloads_at_cleanup=payloads;
 ++cleanup_calls;
 if(!strcmp(name,"display_credits")) ++credits;
}
static int capture_printf(const char *format,...) {
 char text[2048];va_list ap;va_start(ap,format);
 int n=vsnprintf(text,sizeof(text),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(text));++prints;
 if(!strcmp(text,expected)) ++payloads;
 return n;
}
#define printf capture_printf
#define exit borExit
#define getRamStatus(...) cleanup_event("getRamStatus")
#define savesettings(...) cleanup_event("savesettings")
#define display_credits(...) cleanup_event("display_credits")
#define term_videomodes(...) cleanup_event("term_videomodes")
#define unload_levelorder(...) cleanup_event("unload_levelorder")
#define unload_level(...) cleanup_event("unload_level")
#define freescreen(...) cleanup_event("freescreen")
#define freesprites(...) cleanup_event("freesprites")
#define unload_all_fonts(...) cleanup_event("unload_all_fonts")
#define free_ents(...) cleanup_event("free_ents")
#define free_models(...) cleanup_event("free_models")
#define free_modelcache(...) cleanup_event("free_modelcache")
#define clear_scripts(...) cleanup_event("clear_scripts")
#define borTimerExit(...) cleanup_event("borTimerExit")
#define control_exit(...) cleanup_event("control_exit")
#define sound_exit(...) cleanup_event("sound_exit")
#define pak_term(...) cleanup_event("pak_term")
#define freeCommandList(...) cleanup_event("freeCommandList")
#define freeModelList(...) cleanup_event("freeModelList")
#define freefilenamecache(...) cleanup_event("freefilenamecache")
@SHUTDOWN@
#undef exit
#undef printf
typedef struct {unsigned revision;const char *normal_format;unsigned copies,before_cleanup;} Row;
static Row rows[]={@ROWS@};
static unsigned context,kind,quiet;
int main(void) {
 for(context=0;context<sizeof(rows)/sizeof(rows[0]);++context) {
  obor_profile_build=rows[context].revision;
  for(kind=0;kind<4;++kind) for(quiet=0;quiet<2;++quiet) {
   ++scenario;expected_status=kind==3?0:(int)kind;
   disablelog=(int)quiet;startup_done=0;
   stops=cleanup_calls=payloads=payloads_at_cleanup=prints=credits=0;
   engine_alive=1;engine_exit_status=-1;
   if(kind==3) {
    int n=snprintf(expected,sizeof(expected),rows[context].normal_format,VERSION,__DATE__);
    CHECK(n>=0&&(size_t)n<sizeof(expected));
   } else {
    int n=snprintf(expected,sizeof(expected),"Finite exit payload %u / %s",kind,"sample");
    CHECK(n>=0&&(size_t)n<sizeof(expected));
   }
   if(!setjmp(frontend_return)) {
    if(kind==3) shutdown(0,DEFAULT_SHUTDOWN_MESSAGE);
    else shutdown(expected_status,"Finite exit payload %u / %s",kind,"sample");
    CHECK(0);
   }
   CHECK(stops==1&&cleanup_calls>=4);
   CHECK(credits==(expected_status==2?0u:1u));
   CHECK(payloads==(quiet?0u:rows[context].copies));
   CHECK(payloads_at_cleanup==(quiet?0u:rows[context].before_cleanup));
   CHECK(quiet?prints==0:prints>payloads);
  }
 }
 printf("early_shutdown_feedback=1 contexts=%u cases=%u\n",context,scenario);
 return 0;
}
'''
        program = program.replace('@STOP@', function(port, 'borExit'))
        program = program.replace('@SHUTDOWN@', function(source, 'shutdown'))
        program = program.replace('@ROWS@', ',\n'.join(entries))
        with tempfile.TemporaryDirectory(prefix='early-shutdown-feedback-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fsigned-char', '-fcommon',
                     '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare',
                     '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-unused-variable', *warnings]
            build = subprocess.run(compiler + flags + ['-I'+str(p) for p in includes] +
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_SHUTDOWN_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_SHUTDOWN_FEEDBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source and binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_shutdown_feedback=1', run.stdout)

    def test_resource_failure_feedback_per_profile(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-resource-feedback.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        defaults = load_contract_fixture(FIXTURE.with_name('profile-early-grabflip.json'))
        default_fields = {r['revision']: r['default_grabflip'] for r in defaults['sources']}
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key in ('sound_format', 'model_format'):
                self.assertIsInstance(row[key], str)
                self.assertLess(len(row[key]), 256)
            entries.append('{%d,%s,%s,%d}' % (row['revision'], json.dumps(row['sound_format']),
                json.dumps(row['model_format']), default_fields.get(row['revision'])
                if default_fields.get(row['revision']) is not None else -1))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        sound = (engine / 'source/gamelib/soundmix.c').read_text()
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        caches = re.findall(r'typedef\s+struct\s*\{[^{}]*}\s*s_soundcache\s*;', sound)
        self.assertEqual(len(caches), 1)
        diagnostic = re.findall(r'(?m)^static const char\* E_OUT_OF_MEMORY[^\n]*', source)
        self.assertEqual(len(diagnostic), 1)
        program = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef assert
#undef printf
#undef exit
#undef shutdown
#undef calloc
#undef free
#undef time
#undef pause
uint32_t obor_profile_build;
static unsigned scenario;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Resource feedback revision=%u scenario=%u line=%d: %s\n",obor_profile_build,scenario,__LINE__,#c);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int max_attack_types=MAX_ATKS+1,max_animations=MAX_ANIS,max_freespecials=MAX_SPECIALS;
static int magic_type=0;
static unsigned allocations,script_calls,lookup_calls,shutdowns,stops;
static void *owned[32];static unsigned owned_count;
static char message[512];static jmp_buf frontend_return;
static int engine_alive,engine_exit_status,frontend_token;
static void *co_frontend=&frontend_token;
void co_switch(void *target) {
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==1);
 ++stops;longjmp(frontend_return,1);
}
@STOP@
static void capture_shutdown(int status,const char *format,...) {
 CHECK(status==1);va_list ap;va_start(ap,format);
 int n=vsnprintf(message,sizeof(message),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(message));++shutdowns;borExit(status);
}
static void *observe_calloc(size_t count,size_t size) {
 CHECK(count&&size&&count<=(1u<<20)/size);++allocations;
 if(scenario==1) {CHECK(allocations==1&&count*size==sizeof(s_model));return NULL;}
 CHECK(owned_count<32);void *p=calloc(count,size);CHECK(p);owned[owned_count++]=p;return p;
}
static void *observe_malloc(size_t size) {return observe_calloc(1,size);}
static void observe_scripts(s_scripts *scripts) {CHECK(scripts);++script_calls;}
static int observe_lookup(char *name) {CHECK(!strcmp(name,"K'")||!strcmp(name,"flash"));++lookup_calls;return -1;}
@DIAGNOSTIC@
#define calloc observe_calloc
#define malloc observe_malloc
@NAMED_ALLOCATION_SUPPORT@
#undef malloc
#define shutdown capture_shutdown
#define alloc_all_scripts observe_scripts
#define get_cached_model_index observe_lookup
@CONSTRUCTOR@
#undef get_cached_model_index
#undef alloc_all_scripts
#undef shutdown
#undef calloc
@CACHE_TYPE@
#define stricmp strcasecmp
#define OBOR_PROFILE_SAMPLE_LIMIT 2
static s_soundcache soundcache[OBOR_PROFILE_SAMPLE_LIMIT];
static unsigned sample_loads,logs;
static int sample_result;
static int observe_sample(char *filename,char *pack) {
 CHECK(!strcmp(filename,"missing")&&!strcmp(pack,"fixture"));++sample_loads;return sample_result;
}
static int observe_log(const char *format,...) {
 va_list ap;va_start(ap,format);int n=vsnprintf(message,sizeof(message),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(message));++logs;return n;
}
#define sound_alloc_sample observe_sample
#define writeToLogFile observe_log
@LOAD_SAMPLE@
#undef writeToLogFile
#undef sound_alloc_sample
struct expected {uint32_t revision;const char *sound_format,*model_format;int grabflip_default;};
static const struct expected contexts[]={@CONTEXTS@};
static s_modelcache cache[2];
int main(void) {
 model_cache=cache;cache[0].name="model-a";cache[0].path="data/model-a.txt";
 cache[1].name="model-b";cache[1].path="data/model-b.txt";
 for(volatile unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r) {
  const struct expected *ctx=&contexts[r];obor_profile_build=ctx->revision;
  for(volatile unsigned index=0;index<2;++index)for(scenario=0;scenario<2;++scenario) {
   allocations=owned_count=script_calls=lookup_calls=shutdowns=stops=0;
   message[0]=0;engine_alive=1;engine_exit_status=0;
   if(!setjmp(frontend_return)) {
    s_model *model=init_model((int)index,1);CHECK(!scenario&&model&&engine_alive);
    CHECK(model->name==cache[index].name&&model->path==cache[index].path&&model->index==(int)index);
    CHECK(model->unload==1&&!model->isSubclassed&&model->freetypes==MF_ALL);
    CHECK(model->jumpheight==4&&model->jumpspeed==-1&&model->grabdistance==36);
    if(ctx->grabflip_default>=0) CHECK(model->grabflip==ctx->grabflip_default);
    CHECK(script_calls==1&&lookup_calls==2&&allocations==11&&owned_count==11);
    CHECK(model->animation_capacity==MAX_ANIS&&!model->animation[0]);
    for(int i=0;i<max_attack_types;++i)CHECK(model->offense_factors[i]==1&&model->defense_factors[i]==1&&model->defense_knockdown[i]==1);
    for(unsigned i=0;i<owned_count;++i) {free(owned[i]);}
    owned_count=0;
   } else {
    char expected[512];int n=snprintf(expected,sizeof(expected),ctx->model_format,cache[index].path);
    CHECK(n>=0&&(size_t)n<sizeof(expected)&&scenario==1&&stops==1&&shutdowns==1);
    CHECK(!strcmp(message,expected)&&allocations==1&&!owned_count&&!script_calls&&!lookup_calls);
   }
  }
  for(scenario=0;scenario<2;++scenario) {
   memset(soundcache,0,sizeof(soundcache));sample_loads=logs=0;sample_result=-1;message[0]=0;
   CHECK(sound_load_sample("missing","fixture",(int)scenario)==-1);
   CHECK(sample_loads==1&&logs==(unsigned)!scenario&&!soundcache[0].filename&&soundcache[0].index==-1);
   if(!scenario) {char expected[512];snprintf(expected,sizeof(expected),ctx->sound_format,"missing");CHECK(!strcmp(expected,message));}
   else CHECK(!message[0]);
  }
  /* Defined successful cache hit: no decoder call and no diagnostic. */
  soundcache[0].filename="MISSING";soundcache[0].index=7;sample_loads=logs=0;
  CHECK(sound_load_sample("missing","fixture",0)==7&&!sample_loads&&!logs);
  soundcache[0].filename=NULL;
 }
 puts("early_resource_feedback=1");return 0;
}
'''
        for key, value in dict(STOP=function(port, 'borExit'), DIAGNOSTIC=diagnostic[0],
                               CONSTRUCTOR=function(source, 'init_model'), CACHE_TYPE=caches[0],
                               LOAD_SAMPLE=function(sound, 'sound_load_sample'),
                               CONTEXTS=',\n'.join(entries)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-resource-feedback-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine, marker='@NAMED_ALLOCATION_SUPPORT@'))
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fsigned-char', '-fcommon',
                     '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare',
                     '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-unused-variable', *warnings]
            build = subprocess.run(compiler + flags + ['-I'+str(p) for p in includes] +
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_RESOURCE_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_RESOURCE_FEEDBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source and binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_resource_feedback=1', run.stdout)

    def test_owned_and_borrowed_resource_cleanup(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source, header = ((engine / name).read_text() for name in ['openbor.c', 'openbor.h'])
        enums = re.findall(r'typedef enum\s*\{[^{}]*}\s*ModelFreetype;', header)
        self.assertEqual(len(enums), 1)
        constants = []
        for name in ['MF_ALL', 'MAX_COLOUR_MAPS']:
            found = re.findall(r'(?m)^#define\s+' + name + r'\s+[^\n]+', header)
            self.assertEqual(len(found), 1)
            constants += found
        ctor = function(source, 'init_model')
        flag_initializers = []
        for member in ['isSubclassed', 'freetypes']:
            found = re.findall(r'newchar->' + member + r'\s*=[^;]+;', ctor)
            self.assertEqual(len(found), 1)
            flag_initializers += found
        loader = function(source, 'load_cached_model')
        _, cases = switch_cases(loader.replace('switch(cmd)', 'switch(model_command)', 1),
                                'load_cached_model', 'model_command')
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['function_sha256']['free_model'], r'^[0-9a-f]{64}$')
            self.assertIs(type(row['supported']), bool)
            checks.append('check(%d,%d,%d,%d);' %
                          (row['revision'], row['supported'], row['owned_mask'], row['colourmaps']))
        fields = fixture['fields']
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@ENUM@
@CONSTANTS@
typedef struct {void *marker;} s_scripts;
typedef struct model {
 char *name;int index,isSubclassed,ownweapons,animation_capacity;
 ModelFreetype freetypes;s_scripts scripts;void *colourmap[MAX_COLOUR_MAPS];
 @FIELDS@
} s_model;
static uint32_t obor_profile_build;
static int models_loaded,models_cached=2,max_animations=3;
static struct {s_model *model;} model_cache[2];
static void *anim_list;
static int anim_calls[2],script_calls[2],active_owner;
static s_model *current,*parent;
static struct {void *pointer;int owner,live;} allocations[256];
static size_t allocated;
static void *owned(int owner) {
 assert(allocated<sizeof(allocations)/sizeof(allocations[0]));void *p=calloc(1,8);assert(p);
 allocations[allocated].pointer=p;allocations[allocated].owner=owner;allocations[allocated++].live=1;return p;
}
static void remember_model(s_model *m,int owner) {
 assert(allocated<sizeof(allocations)/sizeof(allocations[0]));
 allocations[allocated].pointer=m;allocations[allocated].owner=owner;allocations[allocated++].live=1;
}
static void release_owned(void *pointer) {
 if(!pointer)return;
 for(size_t n=allocated;n>0;n--)if(allocations[n-1].live && allocations[n-1].pointer==pointer) {
  assert(allocations[n-1].owner==active_owner);allocations[n-1].live=0;free(pointer);return;
 }
 assert(!"resource not owned or already released");
}
static int detachModel(s_model *m) {assert(m==current);return 1;}
static void sortModels(void) {}
static void deleteModel(char *name) {assert(name==current->name);release_owned(current);}
static void *anim_list_delete(void *list,int index) {(void)index;anim_calls[active_owner]++;return list;}
#define OBOR_CALLBACK_FREE_MODEL 1
static void obor_profile_callback_scripts(void *owner,s_scripts *scripts,int policy,int event) {
 assert(!owner && scripts==&current->scripts && policy==2 && event==OBOR_CALLBACK_FREE_MODEL);
 script_calls[active_owner]++;
}
static void free_all_scripts(s_scripts *scripts) {release_owned(scripts->marker);scripts->marker=NULL;}
static void copy_all_scripts(s_scripts *from,s_scripts *to,int policy) {assert(from==&parent->scripts && policy==1 && to->marker);}
static s_model *findmodel(char *name) {assert(!strcmp(name,"Base"));return parent;}
static int quiet(const char *format,...) {(void)format;return 0;}
#define printf quiet
#define free release_owned
@HAS_FREETYPE@
@FREE_MODEL@
#undef free
#undef printf
static s_model *make_model(int owner,int fill,int sparse,int external_weapon,void *borrowed) {
 s_model *newchar=calloc(1,sizeof(*newchar));assert(newchar);remember_model(newchar,owner);
 newchar->name=owner?(char *)"Child":(char *)"Base";newchar->index=owner;
 @FLAG_INITIALIZERS@
 newchar->scripts.marker=owned(owner);newchar->ownweapons=!external_weapon;
 if(fill) {
  for(int i=0;i<MAX_COLOUR_MAPS;i++)if(!sparse || !(i&1))newchar->colourmap[i]=owned(owner);
  @ALLOCATE_FIELDS@
 }
 if(external_weapon)newchar->weapon=borrowed;
 return newchar;
}
static void inherit(s_model *newchar) {
 s_model *tempmodel=NULL;s_scripts tempscripts;char *shutdownmessage=NULL;
#define GET_ARG(z) ((void)(z),(char *)"Base")
 switch(1) {case 1:@SUBCLASS@}
#undef GET_ARG
 return;
lCleanup:assert(shutdownmessage);abort();
}
static void check(unsigned revision,int supported,int owned_mask,int colourmaps) {
 obor_profile_build=revision;assert(MF_ALL==owned_mask && MAX_COLOUR_MAPS==colourmaps);
 for(int sparse=0;sparse<2;sparse++)for(int parent_first=0;parent_first<2;parent_first++)
 for(int external_weapon=0;external_weapon<2;external_weapon++) {
  allocated=0;memset(allocations,0,sizeof(allocations));memset(anim_calls,0,sizeof(anim_calls));memset(script_calls,0,sizeof(script_calls));
  void *borrowed=external_weapon?owned(2):NULL;
  parent=make_model(0,1,sparse,external_weapon,borrowed);
  // This is a resource-cleanup probe. Child resource allocation by the full
  // constructor is outside it; retain the child's separately owned scripts.
  s_model *child=make_model(1,!supported,sparse,external_weapon,borrowed);
  if(supported) {
   void *script=child->scripts.marker;inherit(child);
   assert(child->isSubclassed && child->freetypes==MF_SCRIPTS && child->scripts.marker==script);
   @SHARED_FIELDS@
   for(int i=0;i<MAX_COLOUR_MAPS;i++)assert(child->colourmap[i]==parent->colourmap[i]);
  } else assert(!child->isSubclassed && child->freetypes==MF_ALL);
  assert(parent->freetypes==MF_ALL && hasFreetype(parent,MF_SCRIPTS));
  models_loaded=2;model_cache[0].model=parent;model_cache[1].model=child;
  for(int n=0;n<2;n++) {
   active_owner=parent_first?n:1-n;current=active_owner?child:parent;
   free_model(current);assert(models_loaded==1-n);
  }
  assert(anim_calls[0]==max_animations && anim_calls[1]==(supported?0:max_animations));
  assert(script_calls[0]==1 && script_calls[1]==1);
  active_owner=2;release_owned(borrowed);
  for(size_t i=0;i<allocated;i++)assert(!allocations[i].live);
 }
}
int main(void) {assert(!free_model(NULL));@CHECKS@ puts("early_model_resources=1");return 0;}
'''
        replacements = dict(ENUM=enums[0], CONSTANTS='\n'.join(constants), FIELDS='\n'.join('void *%s;' % field for field in fields),
                            HAS_FREETYPE=function(source, 'hasFreetype'), FREE_MODEL=function(source, 'free_model'),
                            FLAG_INITIALIZERS='\n'.join(flag_initializers), SUBCLASS=cases['CMD_MODEL_SUBCLASS']['body'],
                            ALLOCATE_FIELDS='\n'.join('if(%s)newchar->%s=owned(owner);' %
                                                     ('!external_weapon' if field == 'weapon' else '!sparse' if i & 1 else '1', field)
                                                     for i, field in enumerate(fields)),
                            SHARED_FIELDS='\n'.join('assert(child->%s==parent->%s);' % (field, field) for field in fields),
                            CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-model-resources-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-sign-compare', '-Wno-error=deprecated-declarations']
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_MODEL_RESOURCES_OBSERVATIONS'):
                Path(os.environ['OBOR_MODEL_RESOURCES_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'cases_per_context': 8,
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'header_sha256': hashlib.sha256(header.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'scope': fixture['scope'], 'retirement': 'TemporaryDirectory removes source/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_resources=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
