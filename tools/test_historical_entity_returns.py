"""Check historical scalar setter returns with the actual callback prologue.

Only listed scalar cases execute. Numeric mapping and profile-ID translation
are stubs (their actual functions have separate domain tests); fixture fields
are wide scalar storage, not native layouts/bit widths. Diagnostics and unused
engine actions are stubs. This is not a full interpreter or gameplay test.
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

from native_sanitizers import sanitizer_environment
from test_historical_player import switch_cases, function
from historical_position_setters import render_position_setters

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',ROOT))
CONTRACTS=json.loads((Path(__file__).parent/
    'fixtures/profile-entity-return-contracts.json').read_text())


def scalar_entry(source,properties,name='openbor_changeentityproperty'):
    """Retain the actual entry/exit and selected exact case bytes."""
    method,cases=switch_cases(source,'openbor_changeentityproperty','propind')
    for prop,row in sorted(cases.items(),key=lambda item:item[1]['label_start'],reverse=True):
        if prop!='default' and prop not in properties:
            method=method[:row['label_start']]+method[row['end']:]
    method=method.replace('HRESULT openbor_changeentityproperty(', 'HRESULT '+name+'(',1)
    actions=set()
    for body in re.findall(r'static const void\*\s*(?:actions|think)\[\]\s*=\s*\{([^}]*)\}',method):
        body=re.sub(r'//[^\n]*|/\*.*?\*/','',body,flags=re.S)
        actions.update(re.findall(r'\b[A-Za-z_]\w*\b',body))
    return method,actions


def declarations(fields):
    tree={}
    for field in fields:
        if field['type'] not in ('int','float') or not re.fullmatch(r'[a-z_]\w*(?:\.[a-z_]\w*)*',field['field']):
            raise ValueError('Reviewed scalar field paths required')
        parts=field['field'].split('.');node=tree
        for part in parts[:-1]:
            if part in node and not isinstance(node[part],dict):
                raise ValueError('Conflicting scalar declaration')
            node=node.setdefault(part,{})
        if parts[-1] in node and node[parts[-1]]!=field['type']:
            raise ValueError('Conflicting scalar type')
        node[parts[-1]]=field['type']
    def render(node):
        return '\n'.join(('struct {\n'+render(value)+'\n} '+key+';') if isinstance(value,dict)
                         else value+' '+key+';' for key,value in node.items())
    model=tree.pop('modeldata')
    return 'typedef struct {\n'+render(model)+'\n} s_model;\ntypedef struct {\ns_model modeldata;\n'+render(tree)+'\n} entity;'


def scalar_program(components=None,contracts=None):
    contracts=CONTRACTS['sources'] if contracts is None else contracts
    fields=CONTRACTS['scalar_fields'];labels=[row['property'] for row in fields]
    if components is None:
        source=(SOURCE/'src/engines/3741/openborscript.c').read_text()
        entry,actions=scalar_entry(source,labels)
        components={'entries':entry,'actions':sorted(actions),
                    'invoke':'return openbor_changeentityproperty(args,result,count);'}
        if 'obor_entity_set_property_native(' in entry:
            components['translation'] = (
                'static int obor_entity_set_property_native(int property) { return property; }')
    enum='enum { '+','.join(labels)+' };'
    stubs='\n'.join('static void '+name+'(void) { abort(); }' for name in components['actions'])
    expected=[]
    for field in fields:
        expected.append('case '+field['property']+': expected.'+field['field']+' = ('+
                        field['type']+')'+('17.5' if field['input']=='decimal' else '17')+';break;')
    cases=[]
    for row in contracts:
        for case in row['cases']:
            field=next(f for f in fields if f['property']==case['property'])
            cases.append('{%d,%s,%d,%d,%d},' % (row['revision'],case['property'],
                row['has_result'],case['success_return'],field['input']=='decimal'))
    program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
typedef long LONG;
typedef double DOUBLE;
typedef int HRESULT;
typedef struct { union { LONG lVal; DOUBLE dblVal; void *ptrVal; }; int vt; } ScriptVariant;
enum { VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6 };
enum { TYPE_ENEMY=1,TYPE_NPC,TYPE_OBSTACLE,TYPE_PLAYER,TYPE_SHOT };
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
FIELDS
ENUM
static uint32_t obor_profile_build;
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) { memset(v,0,sizeof(*v));v->vt=type; }
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return S_OK; }
    if(v->vt==VT_DECIMAL) { *out=(LONG)v->dblVal;return S_OK; }
    return E_FAIL;
}
static int ScriptVariant_DecimalValue(ScriptVariant *v,DOUBLE *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return S_OK; }
    if(v->vt==VT_DECIMAL) { *out=v->dblVal;return S_OK; }
    return E_FAIL;
}
static void mapstrings_changeentityproperty(ScriptVariant **args,int count) { (void)args;(void)count; }
static int quiet_printf(const char *format,...) { (void)format;return 0; }
#define printf quiet_printf
STUBS
TRANSLATION
ENTRIES
static int invoke(ScriptVariant **args,ScriptVariant **result,int count) { INVOKE }
struct contract { int revision,property,has_result,success_return,decimal; };
static const struct contract contracts[]={ CONTRACTS };
static void check(const struct contract *c) {
    obor_profile_build=c->revision;
    for(int bad=0;bad<2;++bad) {
        entity subject,expected;memset(&subject,0,sizeof(subject));
        subject.modeldata.health=subject.modeldata.mp=99;expected=subject;
        if(!bad) switch(c->property) { EXPECTED default:abort(); }
        ScriptVariant handle={.ptrVal=&subject,.vt=VT_PTR};
        ScriptVariant property={.lVal=c->property,.vt=VT_INTEGER};
        ScriptVariant value={.lVal=17,.vt=VT_INTEGER};
        if(c->decimal) { value.vt=VT_DECIMAL;value.dblVal=17.5; }
        if(bad) value.vt=VT_EMPTY;
        ScriptVariant result={.lVal=999,.vt=VT_INTEGER},*output=&result;
        ScriptVariant *args[]={&handle,&property,&value};
        assert(invoke(args,&output,3)==S_OK);
        assert((output!=NULL)==c->has_result);
        if(output) assert(output==&result && result.vt==VT_INTEGER &&
            result.lVal==(bad?0:c->success_return));
        assert(!memcmp(&subject,&expected,sizeof(subject)));
        // The actual prologue handles missing entity, count and selector type.
        handle=(ScriptVariant){.vt=VT_EMPTY};output=&result;
        assert(invoke(args,&output,3)==S_OK && (output!=NULL)==c->has_result);
        if(output) assert(result.vt==VT_INTEGER && result.lVal==0);
        handle=(ScriptVariant){.lVal=17,.vt=VT_INTEGER};output=&result;
        assert(invoke(args,&output,3)==E_FAIL && output==NULL);
        handle=(ScriptVariant){.ptrVal=&subject,.vt=VT_PTR};output=&result;
        assert(invoke(args,&output,2)==E_FAIL && output==NULL);
        property=(ScriptVariant){.vt=VT_EMPTY};output=&result;
        assert(invoke(args,&output,3)==E_FAIL && output==NULL);
        property=(ScriptVariant){.lVal=-1,.vt=VT_INTEGER};output=&result;
        assert(invoke(args,&output,3)==E_FAIL && output==NULL);
        assert(!memcmp(&subject,&expected,sizeof(subject)));
    }
}
int main(int argc,char **argv) {
    assert(argc==2);int revision=atoi(argv[1]),matched=0;
    for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
        if(contracts[i].revision==revision) { check(&contracts[i]);++matched; }
    }
    assert(matched>0);return 0;
}
'''
    for name,value in [('FIELDS',declarations(fields)),('ENUM',enum),('STUBS',stubs),
        ('TRANSLATION',components.get('translation','')),
        ('ENTRIES',components['entries']),('INVOKE',components['invoke']),
        ('CONTRACTS','\n'.join(cases)),('EXPECTED','\n'.join(expected))]:
        program=program.replace(name,value)
    return program


class EntityReturnTests(unittest.TestCase):
    def test_position_setter_availability_and_independent_coordinates(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/profile-position-setter-contracts.json').read_text())
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        self.assertEqual(fixture['schema'],1)
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype',
                  '-Wno-error=single-bit-bitfield-constant-conversion']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for row in fixture['models']:
            with self.subTest(engine=row['engine']),tempfile.TemporaryDirectory(prefix='native-position-')as folder:
                revisions=[c['revision']for c in row['contracts']]
                required={int(p.get('revision',p['build']))for p in pin['profiles']if p['engine']==row['engine']}
                self.assertTrue(required and required<=set(revisions))
                self.assertEqual(revisions,[s['revision']for s in row['original_sources']])
                for ref in row['original_sources']:
                    self.assertRegex(ref['commit'],r'^[0-9a-f]{40}$')
                    for key in ['setter','enumeration','decimal']:self.assertRegex(ref[key],r'^[0-9a-f]{64}$')
                root=SOURCE/'src/engines'/row['engine']
                script=(root/'openborscript.c').read_bytes().decode('utf8','surrogateescape')
                variant=(root/'source/scriptlib/ScriptVariant.c').read_bytes().decode('utf8','surrogateescape')
                entry,actions=scalar_entry(script,['_ep_x','_ep_z','_ep_a','_ep_position'])
                enumeration=re.search(r'(?m)^enum\s+entityproperty_enum\s*\{[\s\S]*?\};',script)
                self.assertIsNotNone(enumeration)
                program=render_position_setters(entry=entry,enumeration=enumeration[0],
                    decimal=function(variant,'ScriptVariant_DecimalValue'),
                    mapping_names=sorted(set(re.findall(r'\b(mapstrings_\w+)\(',entry))),
                    actions=sorted(actions),contracts=row['contracts'],symbol='checked_position_unit')
                program+='\nint main(void){unsigned n=checked_position_unit();printf("{\\"status\\":\\"PASS\\",\\"checks\\":%u}\\n",n);return 0;}\n'
                work=Path(folder);code=work/'probe.c';executable=work/'probe'
                code.write_bytes(program.encode('utf8','surrogateescape'))
                includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                          *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
                compiled=subprocess.run(compiler+['-I'+str(p)for p in includes]+[
                    '-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                    '-Wno-error=deprecated-declarations','-Wno-unused-variable',
                    '-Wno-unused-function','-Wno-unused-parameter','-O0','-g',
                    '-fsigned-char','-fcommon','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+row['engine'],
                    '-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
                    '-fno-sanitize-recover=all',*host,*warnings,str(code),*link,'-lm','-o',str(executable)],
                    capture_output=True,text=True,timeout=45)
                self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
                observed=subprocess.run([str(executable)],env=sanitizer_environment(),
                    capture_output=True,text=True,timeout=15)
                self.assertEqual(observed.returncode,0,observed.stdout+observed.stderr)
                self.assertEqual(json.loads(observed.stdout),dict(status='PASS',checks=18*len(revisions)))

    def test_registry_covers_profiles_and_own_scalar_case_sources(self):
        rows=CONTRACTS['sources'];revisions=[row['revision'] for row in rows]
        self.assertEqual(len(revisions),len(set(revisions)))
        properties={row['property'] for row in CONTRACTS['scalar_fields']}
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine']=='3741':
                self.assertIn(int(profile.get('revision',profile['build'])),revisions)
        for row in rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['setter_sha256'],r'^[0-9a-f]{64}$')
            self.assertIs(type(row['has_result']),bool)
            for case in row['cases']:
                self.assertIn(case['property'],properties)
                self.assertRegex(case['source_sha256'],r'^[0-9a-f]{64}$')
                self.assertIn(case['success_return'],(0,1))

    def test_scalar_returns_and_actual_entry_validation_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-entity-returns-') as temporary:
            work=Path(temporary);source=work/'probe.c';exe=work/'probe'
            source.write_text(scalar_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc'))+[
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-const-variable','-g',
                '-fsanitize=address,undefined',str(source),'-o',str(exe)],check=True,timeout=60)
            executed=[]
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe),str(row['revision'])],check=True,
                        timeout=20,env=sanitizer_environment())
                    executed.append(row['revision'])
            self.assertEqual(executed,[row['revision'] for row in CONTRACTS['sources']])
            print(json.dumps({'executed_profiles':executed,
                'scope':'listed scalar cases and actual callback validation; reduced fixture'}))


if __name__=='__main__':
    unittest.main()
