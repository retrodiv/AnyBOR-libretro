"""Exercise the historical unknown-constant result at the actual API entry.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
import json
import os
from pathlib import Path
import re
import shlex
from test_historical_player import function
import subprocess
import sys
import tempfile
import unittest


def constants_fixture(members):
    result = dict(members)
    result['data/script.txt'] = b'alwaysupdate 1\n'
    result['data/scripts/updated.c'] = b'''void main() {
    if(getglobalvar("constant_checked") == 1) return;
    setglobalvar("constant_checked", 1);
    if(openborconstant("ATK_NORMAL") != 0) {
        log("CONSTANT_CONTRACT_BAD_KNOWN\\n"); return;
    }
    log("CONSTANT_CONTRACT_BEFORE_UNKNOWN\\n");
    void result = openborconstant("SYNTHETIC_UNKNOWN_CONSTANT");
    if(result == NULL()) log("CONSTANT_CONTRACT_EMPTY_CONTINUATION\\n");
    else log("CONSTANT_CONTRACT_BAD_RESULT\\n");
}
'''
    return result


def check_constants_continuation(log, profile, restarts=0):
    legacy = int(profile) < 3826
    expected = ['CONSTANT_CONTRACT_BEFORE_UNKNOWN']
    if legacy:
        expected.append('CONSTANT_CONTRACT_EMPTY_CONTINUATION')
    markers = re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                         r'(CONSTANT_CONTRACT_[A-Z_]+)[ \t]*\r?$', log)
    exception = "There's an exception while executing script" in log
    if markers != expected * (1 + restarts) or exception == legacy:
        raise RuntimeError('Historical unknown-constant contract differs: ' + log)


def script_property_registry(script):
    return '\n'.join(function(script, name) for name in (
        'obor_has_computed_damage', 'Script_GetFunctionName', 'Script_LoadSystemFunctions'))


def render_set_property_checks(core, script, fixture):
    from test_historical_player import rename_identifiers

    api = ('openbor_get_set_property', 'openbor_set_set_property')
    registry = script_property_registry(script)
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*((?:openbor|math|system)_\w+)', registry)) - set(api))
    renamed = {name: 'probe_' + name for name in symbols}
    renamed.update(theFunctionList='probe_list', List_Reset='probe_reset', List_InsertAfter='probe_insert')
    tables, checks = [], {}
    for row in fixture['sources']:
        if not row['views']:
            checks[row['revision']] = 'check_set_properties(NULL, 0, -1);'
            continue
        table = 'set_results_%d' % row['revision']
        entries = []
        for property_view in row['views']:
            tag, field = property_view['tag'], property_view['field']
            if tag not in ('VT_INTEGER', 'VT_DECIMAL', 'VT_PTR', 'VT_STR'):
                raise ValueError('Original set property result tag required')
            value = 0 if tag in ('VT_PTR', 'VT_STR') else fixture['values'][field]
            entries.append('{%d,%s,%d}' % (property_view['index'], tag, value))
        tables.append('static const struct set_result '+table+'[]={'+','.join(entries)+'};')
        checks[row['revision']] = 'check_set_properties(%s,%d,%d);' % (
            table, len(entries), row['writable'])
    fields = fixture['values']
    if not all(re.fullmatch(r'[a-z_]+', name) and type(value) is int for name, value in fields.items()):
        raise ValueError('Explicit integer seed fields required')
    parts = dict(STUBS='\n'.join('static void probe_' + name + '(void) {}' for name in symbols),
        NATIVE='\n'.join(function(script, name) for name in ('obor_script_set_handle',
                      'obor_assign_levelorder', *api)),
        REGISTRY=rename_identifiers(registry, renamed), UNLOAD=function(core, 'unload_levelorder'),
        SEED=', '.join('.%s = %d' % (name, value) for name, value in fields.items()), TABLES='\n'.join(tables))
    template = Path(__file__).with_name('set_property_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template), checks


def render_level_getter_checks(script, fixture):
    from test_historical_player import rename_identifiers

    callback = 'openbor_get_level_property'
    registry = script_property_registry(script)
    symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*((?:openbor|math|system)_\w+)', registry)) - {callback})
    renamed = {name: 'probe_' + name for name in symbols}
    renamed.update(theFunctionList='probe_list', List_Reset='probe_reset', List_InsertAfter='probe_insert')
    values = fixture['values']
    if not all(re.fullmatch(r'[a-z_]+', field) and type(value) in (int, float)
               for field, value in values.items()):
        raise ValueError('Explicit level property seed values required')
    pointers = set()
    strings = set()
    tables = []
    for index, view in enumerate(fixture['views']):
        entries = []
        for item in view:
            if item is None:
                entries.append('{.tag = UNSUPPORTED}')
                continue
            tag, field = item
            if not re.fullmatch(r'[a-z_]+', field):
                raise ValueError('Explicit level field required')
            if tag in ('VT_INTEGER', 'VT_DECIMAL', 'DECIMAL_INTEGER'):
                entries.append('{%s, .number = %s}' % (tag, values[field]))
            elif tag in ('VT_PTR', 'POINTER_BASEMAPS'):
                if field != 'active_level':
                    pointers.add(field)
                pointer = '&stage' if field == 'active_level' else '&collection_' + field
                entries.append('{%s, .pointer = %s}' % (tag, pointer))
            elif tag == 'VT_STR':
                strings.add(field)
                entries.append('{VT_STR, .text = %s}' % json.dumps('Level ' + field))
            else:
                raise ValueError('Original level property result tag required')
        tables.append('static const struct level_result level_results_%d[] = {%s};' %
                      (index, ','.join(entries or ['{.tag = UNSUPPORTED}'])))
    seeds = ['stage.%s = %s;' % item for item in values.items() if item[0] not in ('noslow', 'boss_slow')]
    seeds += ['if(obor_profile_build < 4502) stage.noslow = %s;' % values['noslow'],
              'else stage.boss_slow = %s;' % values['boss_slow']]
    seeds += ['stage.%s = (void *)&collection_%s;' % (field, field) for field in sorted(pointers)]
    seeds += ['stage.name = "Level name";' if field == 'name' else
              'strcpy(stage.%s, %s);' % (field, json.dumps('Level ' + field)) for field in sorted(strings)]
    checks = {row['revision']: 'check_level_getter(level_results_%d, %d, %d, %d, %d);' %
              (row['view'], len(fixture['views'][row['view']]), row['getter'],
               row['compact_reverse'], row['current_level']) for row in fixture['sources']}
    parts = dict(STUBS='\n'.join('static void probe_' + name + '(void) {}' for name in symbols),
                 GETTER=function(script, callback), REGISTRY=rename_identifiers(registry, renamed),
                 COLLECTIONS='\n'.join('static double collection_%s;' % field for field in sorted(pointers)),
                 SEED='\n    '.join(seeds), TABLES='\n'.join(tables))
    template = Path(__file__).with_name('level_property_getter_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template), checks


class UnknownConstantsTests(unittest.TestCase):
    def test_4432_historical_script_constant_lookups(self):
        self._check_4432_constants('profile-script-constant-lookup-contracts.json')

    def test_4432_historical_animation_property_numbers(self):
        self._check_4432_constants('profile-animation-property-number-contracts.json', frame_properties=True)

    def test_4432_set_property_ordinals_and_collections(self):
        self._check_4432_constants('profile-4432-set-property-contracts.json', set_properties=True)

    def test_4432_stage_flag_constants(self):
        self._check_4432_constants('profile-4432-stage-runtime-contracts.json')

    def test_4432_typed_level_property_ordinals_and_getter(self):
        self._check_4432_constants('profile-4432-level-getter-contracts.json',
                                   render_checks=render_level_getter_checks)

    def _check_4432_constants(self, name, *, frame_properties=False, set_properties=False,
                              render_checks=None):
        from test_historical_common_think import ROOT, native_output
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures' / name)
        engine = ROOT / 'src/engines' / fixture['engine']
        script = (engine / 'openborscript.c').read_text()
        core = (engine / 'openbor.c').read_text()
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(fixture['engine'], '4432')
        self.assertEqual(len(revisions), len(rows))
        self.assertEqual(revisions, contract_revisions(fixture, fixture['expected_revisions']))

        mapper = function(script, 'mapstrings_transconst')
        macros = script[script.index('#define IICMPCONST('):script.index('int mapstrings_transconst(')]
        arrays = sorted(set(re.findall(r'ICMPS(?:CONST[AB]|BACKCONST)\(\w+, (\w+)\)', mapper)))
        mapped = set(re.findall(r'\b(?:I?ICMPCONST|ICMPCONST_FROM)\((\w+)', mapper))
        variables = mapped & set(re.findall(r'(?m)^extern\s+int\s+(\w+)\s*;', script))
        backwards = ('animbackpains', 'animbackfalls', 'animbackdies')
        self.assertTrue(set(backwards) <= set(arrays))
        tables = []
        for index, contract in enumerate(fixture['contracts']):
            self.assertEqual(len(contract), len(fixture['names']))
            self.assertTrue(all(v is None or type(v) is int for v in contract))
            entries = ['{%s,%d,%d}' % (json.dumps(name), value is not None, value or 0)
                       for name, value in zip(fixture['names'], contract)]
            tables.append('static const Expectation table_%d[]={%s};' % (index, ','.join(entries)))
        support = function(script, 'obor_profile_subtype_value') + function(core, 'obor_profile_animation_base')
        if 'obor_profile_name_limit(' in mapper:
            support += function(core, 'obor_profile_name_limit')
        if 'obor_uses_early_animation_properties(' in script:
            support += function(script, 'obor_uses_early_animation_properties')
            if frame_properties:
                support += function(script, 'obor_native_animation_property')
        native = macros + mapper + function(script, 'openbor_transconst')
        extra_checks = ''
        extra_context_checks = {}
        if frame_properties:
            variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
            native += function(variant, 'ScriptVariant_IntegerValue')
            native += '\n'.join(function(script, method) for method in
                                ('openbor_get_animation_property', 'openbor_set_animation_property'))
            extra_checks = Path(__file__).with_name('animation_property_number_contract.c.in').read_text()
            frames_index = fixture['names'].index('ANI_PROP_NUMFRAMES')
        if set_properties:
            extra_checks, extra_context_checks = render_set_property_checks(core, script, fixture)
        if render_checks:
            extra_checks, extra_context_checks = render_checks(script, fixture)
        checks = []
        for row in rows:
            checks.append('check(%du, table_%d, %d);' %
                          (row['revision'], row['contract'], len(fixture['names'])))
            if frame_properties:
                self.assertIs(type(row['frame_setter']), bool)
                number = fixture['contracts'][row['contract']][frames_index]
                checks.append('check_frame_property(%d, %d);' % (number, row['frame_setter']))
            if extra_context_checks:
                checks.append(extra_context_checks[row['revision']])
        parts = dict(
            TABLES='\n'.join(tables),
            CHECKS='\n'.join(checks),
            ARRAYS='\n'.join(f'static int {name}_storage[16]; int *{name} = {name}_storage;'
                             for name in arrays),
            VARIABLES='\n'.join(f'int {name};' for name in sorted(variables)),
            POPULATE='\n'.join(f'{name}[i] = base + {32 * index} + i;'
                               for index, name in enumerate(backwards)),
            SUPPORT=support, MAPPER=native, EXTRA_CODE=extra_checks)
        template = Path(__file__).with_name('script_constant_lookup_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)
        actual = json.loads(native_output(code, fixture, extra_cflags=('-fgnu89-inline',)))
        total_per_context = 3 * len(fixture['names']) + 1 + (14 if frame_properties else 0)
        self.assertEqual(actual, {'contexts': len(rows), 'checks': len(rows) * total_per_context})
        print(json.dumps(actual, separators=(',', ':')), flush=True)

    def test_mapper_names_values_and_mapping_phase_per_profile(self):
        from historical_constant_mapper import render_constant_mapper
        from test_historical_behavior import native
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-constant-mapper-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((root / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['suffix_in_mapper'], row['revision'] >= 3826)
            self.assertEqual(row['unknown_empty_success'], row['revision'] < 3826)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in [row['header_sha256'], *row['source_sha256'].values()]:
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_constant_mapper(root / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_numbered_animation_prefixes_across_3826(self):
        from historical_constant_mapper import render_constant_mapper
        from test_historical_behavior import native
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch

        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-constant-mapper-contracts.json')
        controls = {3825, 3826, 3827}
        rows = [row for row in fixture['sources'] if row['revision'] in controls]
        self.assertEqual({row['revision'] for row in rows}, controls)
        expanded = next(row['expanded_suffix_prefixes'] for row in rows if row['revision'] == 3826)
        self.assertEqual(len(expanded), 11)
        self.assertEqual(expanded['ANI_BACKWALK'], '79')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_constant_mapper(root / 'src/engines/3842', dict(fixture, sources=rows)),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_forward_property_mapper_values_diagnostics_and_status(self):
        from native_sanitizers import sanitizer_environment

        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        engine = root / 'src/engines/3842'
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-forward-property-mappers.json')
        cases = fixture['cases']
        rows = fixture['sources']
        self.assertEqual({row['revision'] for row in rows}, set(fixture['boundary_controls']))
        names = {case['case'] for case in cases}
        self.assertEqual(len(names), len(cases))
        mappers = {case['mapper'] for case in cases}
        c_cases = []
        for case in cases:
            self.assertRegex(case['mapper'], r'^[a-z]+$')
            self.assertTrue(0 < len(case['args']) <= 6)
            args = ','.join(
                '{%s,0}' % json.dumps(v) if isinstance(v, str) else '{NULL,%d}' % v
                for v in case['args'])
            c_cases.append('{%s,mapstrings_%s,%d,{%s}}' %
                           (json.dumps(case['case']), case['mapper'], len(case['args']), args))
        provider = function((engine / 'source/utils.c').read_text(), 'searchList')
        program = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "openborscript.h"
#undef printf
#define stricmp strcasecmp
uint32_t obor_profile_build;
void writeToLogFile(const char *format,...) {
 va_list args;va_start(args,format);vprintf(format,args);va_end(args);
}
void exitIfFalse(int value,const char *assertion,const char *function,const char *file,int line) {
 if(!value){fprintf(stderr,"%s:%d (%s): %s\n",file,line,function,assertion);abort();}
}
typedef struct { const char *text; int number; } Argument;
typedef struct { const char *name; int (*mapper)(ScriptVariant**,int); int count; Argument args[6]; } Case;
static const Case cases[]={@CASES@};
static const Case *active;
CHAR *StrCache_Get(int index) {
 assert(active && index>=0 && index<active->count && active->args[index].text);
 return (CHAR*)active->args[index].text;
}
CHAR *StrCache_GetIfPresent(int index) { return StrCache_Get(index); }
void ScriptVariant_ChangeType(ScriptVariant *arg,VARTYPE type) { arg->vt=type;arg->lVal=0; }
@SEARCH@
int main(int argc,char **argv) {
 assert(argc==2);obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
 for(unsigned n=0;n<sizeof(cases)/sizeof(*cases);++n) {
  ScriptVariant values[6]={0},*params[6]={0};active=&cases[n];
  for(int i=0;i<active->count;++i) {
   params[i]=&values[i];
   if(active->args[i].text){values[i].vt=VT_STR;values[i].strVal=i;}
   else{values[i].vt=VT_INTEGER;values[i].lVal=active->args[i].number;}
  }
  int status=active->mapper(params,active->count);
  printf("@%s %d",active->name,obor_profile_build>=3862?status:-1);
  for(int i=0;i<active->count;++i) {
   if(values[i].vt==VT_STR){assert(values[i].strVal==i);printf(" s%d",i);}
   else{assert(values[i].vt==VT_INTEGER);printf(" %ld",(long)values[i].lVal);}
  }
  puts("");
 }
 return 0;
}
'''.replace('@CASES@', ',\n'.join(c_cases)).replace('@SEARCH@', provider)
        includes = [engine, root / 'src/port/libretro', engine / 'source',
                    *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
        mac = sys.platform == 'darwin'
        host = ['-DDARWIN=1', '-D_DARWIN_C_SOURCE=1'] if mac else ['-DLINUX=1']
        link = ['-Wl,-dead_strip'] if mac else ['-no-pie', '-Wl,--gc-sections']
        with tempfile.TemporaryDirectory(prefix='anybor-native-property-mappers-') as temporary:
            probe = Path(temporary) / 'probe.c'
            binary = probe.with_suffix('')
            probe.write_text(program)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output([*compiler, '--version'], text=True, timeout=10)
            # Unused game callback tables must stay discardable when linking
            # the mapper unit by itself. The mapper code remains instrumented.
            globals_flag = (['-mllvm', '-asan-globals=0'] if 'clang' in version.lower()
                            else ['--param', 'asan-globals=0'])
            flags = ['-std=gnu99', '-g', '-fsigned-char', '-fcommon', '-fgnu89-inline',
                     '-ffunction-sections', '-fdata-sections', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD=3842', '-DOBOR_CONTROLLED_ASSERTIONS=1',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
            subprocess.run([*compiler, *flags, *globals_flag, *host, *('-I'+str(p) for p in includes),
                            str(probe), str(engine / 'openborscript.c'), *link, '-lm',
                            '-o', str(binary)], check=True, timeout=90)
            for row in rows:
                with self.subTest(revision=row['revision']):
                    self.assertEqual(set(row['providers']), mappers)
                    self.assertEqual(set(row['observations']), names)
                    expected = []
                    for case in cases:
                        evidence = row['providers'][case['mapper']]
                        self.assertEqual(evidence['commit'], row['commit'])
                        self.assertRegex(evidence['source_sha256'], r'^[0-9a-f]{64}$')
                        outcome = row['observations'][case['case']]
                        status = outcome['result'] if outcome['result'] is not None else -1
                        args = ' '.join('s%d' % i if isinstance(arg, str) else str(arg)
                                        for i, arg in enumerate(outcome['args']))
                        expected.append('%s@%s %d %s' % (outcome['diagnostic'], case['case'], status, args))
                    actual = subprocess.run([str(binary), str(row['revision'])], check=True,
                        capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                    self.assertEqual(actual.stdout.splitlines(), '\n'.join(expected).splitlines())

    def test_compiled_continuation_requires_executed_markers(self):
        legacy = "[game] CONSTANT_CONTRACT_BEFORE_UNKNOWN\n[game] CONSTANT_CONTRACT_EMPTY_CONTINUATION\n"
        modern = ("[OpenBOR] CONSTANT_CONTRACT_BEFORE_UNKNOWN\n"
                  "There's an exception while executing script updated\n"
                  'log("CONSTANT_CONTRACT_EMPTY_CONTINUATION\\n");')
        check_constants_continuation(legacy, '3824')
        check_constants_continuation(modern, '3829')
        check_constants_continuation(legacy + legacy, '3780', restarts=1)
        for log, profile in ((legacy, '3829'), (modern, '3780'),
                             (legacy + legacy, '3780'),
                             ('log("CONSTANT_CONTRACT_BEFORE_UNKNOWN");', '3780')):
            with self.subTest(profile=profile), self.assertRaises(RuntimeError):
                check_constants_continuation(log, profile)

    def test_profile_boundary_empty_result_known_values_and_bad_arguments(self):
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        source = (root / 'src/engines/3842/openborscript.c').read_text()
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef long LONG;
#define strnicmp strncasecmp
#define OBOR_ATTACK_BASE 16
#define OBOR_ATTACK_SPECIAL 6
static int *animdowns,*animups,*animbackwalks,*animwalks,*animidles;
static int *animfalls,*animrises,*animriseattacks,*animpains,*animdies;
static int *animattacks,*animfollows,*animspecials;
int max_downs,max_ups,max_backwalks,max_walks,max_idles,max_attack_types;
int max_attacks,max_follows,max_freespecials;
enum { VT_EMPTY, VT_INTEGER, VT_DECIMAL, VT_PTR, VT_STR };
typedef struct { int vt; long lVal; const char *text; } ScriptVariant;
#define strVal text
static const char *StrCache_Get(const char *text) { return text; }
typedef int HRESULT;
#define S_OK 0
#define E_FAIL (-1)
static uint32_t obor_profile_build;
static unsigned cleared;
static void ScriptVariant_Clear(ScriptVariant *value) {
    ++cleared; memset(value,0,sizeof(*value));
}
static void ScriptVariant_ChangeType(ScriptVariant *value,int type) {
    memset(value,0,sizeof(*value));value->vt=type;
}
static void ScriptVariant_Copy(ScriptVariant *to,const ScriptVariant *from) { *to=*from; }
static void ScriptVariant_ToString(const ScriptVariant *value,char *text) {
    snprintf(text,128,"%.100s",value->vt==VT_STR?value->text:"non-string");
}
/* Keep mapping separate from the result/error contract under test. The
 * compiled script fixture additionally exercises the complete real mapper. */
static void mapstrings_transconst(ScriptVariant **args,int count) {
    assert(count>=1);
    if(args[0]->vt==VT_STR && !strcmp(args[0]->text,"ATK_NORMAL")) {
        args[0]->vt=VT_INTEGER;args[0]->lVal=0;
    }
}
METHOD
int main(void) {
    (void)&ScriptVariant_Clear;
    (void)obor_profile_build;
    const unsigned profiles[]={3780,3783,3789,3793,3797,3805,3814,3818,
        3822,3824,3825,3826,3829,3831,3837,3839,3842};
    const char *unknown[]={"UNKNOWN_SYNTHETIC_CONSTANT","","ANI_UNKNOWN17"};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(unsigned n=0;n<sizeof(unknown)/sizeof(*unknown);++n) {
            ScriptVariant arg={VT_STR,19,unknown[n]},before=arg;
            ScriptVariant result={VT_STR,71,"old-result"},*out=&result,*args[]={&arg};
            unsigned previous=cleared;
            int status=openbor_transconst(args,&out,1);
            assert(!memcmp(&arg,&before,sizeof(arg)));
            if(profiles[p]<3826) {
                assert(status==S_OK && out==&result && result.vt==VT_EMPTY);
                assert(!result.lVal && !result.text && cleared==previous+1);
            } else assert(status==E_FAIL && out==NULL && cleared==previous);
        }
        ScriptVariant arg={VT_STR,0,"ATK_NORMAL"},result={VT_EMPTY,0,NULL};
        ScriptVariant *out=&result,*args[]={&arg};
        assert(openbor_transconst(args,&out,1)==S_OK && out==&result);
        assert(result.vt==VT_INTEGER && result.lVal==0 && arg.vt==VT_INTEGER);
        arg=(ScriptVariant){VT_INTEGER,-17,NULL};out=&result;
        assert(openbor_transconst(args,&out,1)==S_OK && out==&result && result.lVal==-17);
        const int bad_types[]={VT_EMPTY,VT_DECIMAL,VT_PTR};
        for(unsigned n=0;n<sizeof(bad_types)/sizeof(*bad_types);++n) {
            arg=(ScriptVariant){bad_types[n],0,NULL};out=&result;
            assert(openbor_transconst(args,&out,1)==E_FAIL && out==NULL);
        }
        out=&result;
        assert(openbor_transconst(NULL,&out,0)==E_FAIL && out==NULL);
    }
    return 0;
}
'''.replace('METHOD', function(source, 'openbor_transconst'))
        with tempfile.TemporaryDirectory(prefix='anybor-unknown-constant-') as temp:
            work = Path(temp)
            (work / 'probe.c').write_text(program)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                            '-g', '-fsanitize=address,undefined', str(work / 'probe.c'),
                            '-o', str(work / 'probe')], check=True, timeout=30)
            subprocess.run([str(work / 'probe')], check=True, timeout=10,
                           stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
