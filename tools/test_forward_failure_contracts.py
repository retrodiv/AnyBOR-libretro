"""Check native allocation and multimedia failure boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-failure-contracts.json'


def fill(name, values):
    result = Path(__file__).with_name(name).read_text()
    for key, value in values.items():
        result = result.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved native failure dependency')
    return result


def allocation_program(data, engine):
    header = (engine / 'source/safealloc.h').read_text()
    # Bind allocator services before the native wrappers and replace those
    # temporary bindings immediately before their native public macros.
    at = header.index('#define realloc(ptr, size)')
    header = header[:at]+'\n#undef realloc\n#undef malloc\n#undef calloc\n#undef strdup\n#undef strlen\n'+header[at:]
    helper = function((engine / 'source/utils.c').read_text(), 'checkAlloc')
    return fill('forward_allocation_failure_contract.c.in', dict(HEADER=header, HELPER=helper,
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['checked_allocations']) for r in data['sources'])))


def media_program(data, engine):
    units = {n: (engine / 'source/webmlib' / path).read_text() for n, path in
             [('halloc', 'halloc/halloc.c'), ('nestegg', 'nestegg/nestegg.c'), ('vorbis', 'vorbis.c')]}
    units['nestegg'] = units['nestegg'].replace('static int\nne_get_uint(', 'static int ne_get_uint(')
    names = {'halloc': 'halloc_set_allocator', 'nestegg': 'ne_get_uint', 'vorbis': 'vorbis_getpcm'}
    functions = []
    positions = []
    for key in units:
        text = units[key]
        first = text.index('/* Keep safety checks active')
        end = text.index('#endif', first)+len('#endif')
        macro = text[first:end]
        body = function(text, names[key])
        if key == 'halloc':
            positions.append(100+text[:text.index(body)+body.index('assert(')].count('\n'))
            functions.append('#define NDEBUG 1\n#line 100 "halloc-profile.c"\n'+text+
                '\n#ifdef NDEBUG\n#error Halloc safety metadata must remain enabled\n#endif\n#undef assert\n')
        else:
            positions.append(100+body[:body.index('assert(')].count('\n'))
            functions.append(macro+'\n#line 100 "'+key+'-profile.c"\n'+body+'\n#undef assert\n')
    body = function(units['halloc'], 'halloc')
    # Its first assertion is default-allocator admission; the next consumes
    # the initialized header magic before any resize/free operation.
    at = body.index('assert(p->magic == HH_MAGIC)')
    positions.append(100+units['halloc'][:units['halloc'].index(body)+at].count('\n'))
    types = ''
    for pattern in [r'enum ebml_type_enum\s*\{[\s\S]*?\};',
                    r'struct ebml_binary\s*\{[\s\S]*?\};',
                    r'struct ebml_type\s*\{[\s\S]*?\n\};']:
        match = re.search(pattern, units['nestegg'])
        if match is None:
            raise ValueError('Complete native media type required')
        types += match[0]+'\n'
    utility = (engine / 'source/utils.c').read_text()
    port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
    return fill('forward_media_failure_contract.c.in', dict(TYPES=types,
        HELPERS=function(utility, 'checkAlloc')+'\n'+function(utility, 'exitIfFalse')+'\n'+function(port, 'obor_port_assert'),
        FUNCTIONS='\n'.join(functions), POSITIONS=','.join(map(str, positions)),
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['logged_media_assertions'])
                        for r in data['sources'] if r['native_media'])))


def integration_program(engine):
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#ifndef SAFEALLOC_H
#error Native globals must include the allocation wrappers
#endif
#ifndef malloc
#error Native allocation call macros required
#endif
uint32_t obor_profile_build=4213;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
void *checkAlloc(void *p,size_t size,const char *f,const char *file,int line)
{(void)f;(void)file;(void)line;if(size && !p)abort();return p;}
int main(void){char *p=malloc(4);if(!p)return 1;memcpy(p,"abc",4);
 p=realloc(p,8);if(!p||strcmp(p,"abc"))return 2;free(p);
 p=calloc(4,2);if(!p)return 3;for(int i=0;i<8;++i)if(p[i])return 4;free(p);
 p=strdup("native");if(!p||strcmp(p,"native"))return 5;free(p);
 puts("INTEGRATION_PASS");return 0;}
'''


def preparation_program(data, engine):
    source = (engine / 'source/webmlib/vorbis.c').read_text()
    # Use this unit's own includes: an unrelated game header must not supply
    # an exit alias that the native translation unit does not actually see.
    prefix = source[:source.index('void vorbis_init(')]
    return fill('forward_audio_preparation_contract.c.in', dict(PREFIX=prefix,
        PREPARE=function(source, 'vorbis_prepare'),
        PROFILES=','.join(str(r['revision'])+'u' for r in data['sources'] if r['native_media'])))


class ForwardFailureContractTests(unittest.TestCase):
    def fixture(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_FAILURE_ENGINE', ROOT / 'src/engines' / data['engine']))
        return data, engine

    def test_native_allocation_wrappers_and_failure_metadata(self):
        data, engine = self.fixture()
        result = [json.loads(line) for line in native_output(allocation_program(data, engine),
                    data, engine_source=engine).splitlines()]
        self.assertEqual(result, [dict(revision=r['revision'], allocation='PASS') for r in data['sources']])

    def test_native_media_assertion_routes_and_early_returns(self):
        data, engine = self.fixture()
        dependencies = ROOT / 'src/deps'
        result = [json.loads(line) for line in native_output(media_program(data, engine), data,
                    engine_source=engine, configure_ogg=True, extra_includes=[
                        engine / 'source/webmlib', engine / 'source/webmlib/halloc', dependencies / 'libogg/include',
                        dependencies / 'libvorbis/include']).splitlines()]
        self.assertEqual(result, [dict(revision=r['revision'], media='PASS')
                                 for r in data['sources'] if r['native_media']])

    def test_globals_include_the_live_allocation_macros(self):
        data, engine = self.fixture()
        self.assertEqual(native_output(integration_program(engine), data, engine_source=engine), 'INTEGRATION_PASS\n')

    def test_audio_preparation_stops_only_the_selected_engine(self):
        data, engine = self.fixture()
        dependencies = ROOT / 'src/deps'
        rows = [json.loads(line) for line in native_output(preparation_program(data, engine), data,
                    engine_source=engine, configure_ogg=True, extra_includes=[
                        engine / 'source/webmlib', dependencies / 'libogg/include',
                        dependencies / 'libvorbis/include']).splitlines()]
        self.assertEqual(rows, [dict(revision=r['revision'], preparation='PASS')
                               for r in data['sources'] if r['native_media']])


if __name__ == '__main__':
    unittest.main()
