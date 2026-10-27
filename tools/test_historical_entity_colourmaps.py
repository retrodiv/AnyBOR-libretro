"""Check entity colourmap mutations against each original source contract.

This reduced fixture covers target selection, palette pointers, map indices
and hidden-map bounds, plus branch results. The actual callback entry/exit is
tested separately by test_historical_entity_returns. Property mapping and game
acceptance remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = json.loads((Path(__file__).parent /
    'fixtures/profile-entity-colourmap-contracts.json').read_text())


def colourmap_cases(source):
    _, cases = switch_cases(source, 'openbor_changeentityproperty', 'propind')
    result = []
    for name in ('colourmap', 'hmapl', 'hmapu'):
        label = '_ep_' + name
        if label not in cases:
            raise AssertionError('Unique colourmap setter case required: ' + name)
        result.append('case ' + label + ':' + cases[label]['body'])
    return '\n'.join(result)


def colourmap_program(contracts=None, components=None):
    contracts = CONTRACTS['sources'] if contracts is None else contracts
    generated = components is None
    if components is None:
        engine = SOURCE / 'src/engines/3741'
        script = (engine / 'openborscript.c').read_text()
        game = (engine / 'openbor.c').read_text()
        components = {'cases': colourmap_cases(script),
            'helpers': '\n'.join(function(game, name) for name in
                ('model_get_colourmap', 'ent_set_colourmap'))}
    declarations = []
    for row in contracts:
        mode = {'raw_self': 0, 'indexed_self': 1, 'pointer_entity': 2}[row['mode']]
        declarations.append('{%d,%d,%d,%d,%d},' %
            (row['revision'], mode, row['fixed_colourmap_slots'],row['has_result'],
             row['helper_bound']=='fixed'))
    program = r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef long LONG;
typedef void VOID;
typedef struct { LONG lVal; int vt; } ScriptVariant;
enum { VT_EMPTY, VT_INTEGER, _ep_colourmap=101, _ep_hmapl, _ep_hmapu };
#define MAX_COLOUR_MAPS 30
#define SUCCEEDED(x) ((x)>=0)
typedef struct {
    unsigned char **colourmap, *palette;
    unsigned maps_loaded, colourmap_capacity;
    struct { int hide_start, hide_end; } maps;
} s_model;
typedef struct { s_model modeldata; unsigned char *colourmap; int map; } entity;
static uint32_t obor_profile_build;
static int fixture_has_result;
static LONG last_result;
static entity actor, target, *self;
static unsigned char palettes[2][4];
static unsigned char *tables[2][MAX_COLOUR_MAPS];
static int ScriptVariant_IntegerValue(ScriptVariant *value, LONG *out) {
    if(value->vt!=VT_INTEGER) return -1;
    *out=value->lVal; return 0;
}
HELPERS
static void write_property(int property, ScriptVariant *value) {
    entity *ent=&target;
    ScriptVariant result={0,VT_INTEGER}, *output=fixture_has_result?&result:NULL, **pretvar=&output;
    ScriptVariant *varlist[]={NULL,NULL,value};
    LONG ltemp=0;
    (void)ent; (void)pretvar;
    switch(property) { CASES }
    last_result=output?output->lVal:-1234;
}
static void reset(void) {
    memset(&actor,0,sizeof(actor)); memset(&target,0,sizeof(target));
    memset(tables,0,sizeof(tables)); self=&actor;
    for(int i=0;i<2;++i) for(int j=0;j<3;++j) tables[i][j]=&palettes[i][j+1];
    actor.modeldata=(s_model){tables[0],palettes[0],3,MAX_COLOUR_MAPS,{11,12}};
    target.modeldata=(s_model){tables[1],palettes[1],3,MAX_COLOUR_MAPS,{21,22}};
    actor.colourmap=palettes[0]; target.colourmap=palettes[1];
    actor.map=71; target.map=73;
}
struct contract { int revision, mode, slots, has_result, fixed_helper; };
static const struct contract contracts[]={ CONTRACTS };
static void check(const struct contract *c) {
    obor_profile_build=c->revision;
    fixture_has_result=c->has_result;
    const int bounded[]={-2,-1,0,1,2,3,4,29,30,31,INT_MAX};
    for(unsigned i=0;i<sizeof(bounded)/sizeof(*bounded);++i) {
        int which=bounded[i];
        // Original raw-array reads outside these bounds are undefined. The
        // generated safety policy is tested separately, never as an oracle.
        if(c->mode==0 && (which<1 || which>c->slots)) continue;
        reset();
        ScriptVariant value={which,VT_INTEGER};
        write_property(_ep_colourmap,&value);
        assert(last_result==(c->has_result?1:-1234));
        entity *changed=c->mode==2?&target:&actor;
        entity *unchanged=c->mode==2?&actor:&target;
        unsigned char *expected=NULL;
        if(which>=1 && which<=3) expected=changed->modeldata.colourmap[which-1];
        else if(c->mode!=0) expected=changed->modeldata.palette;
        assert(changed->colourmap==expected);
        assert(changed->map==(c->mode==1?(which>=1&&which<=3?which:0):
            (c->mode==2?73:71)));
        assert(unchanged->colourmap==unchanged->modeldata.palette);
        assert(unchanged->map==(c->mode==2?71:73));
    }
    if(c->mode==0) {
        // Filling a fixed-table hole can lower maps_loaded while later slots
        // remain occupied. Those valid raw slots retain their palette pointer.
        reset();actor.modeldata.maps_loaded=1;target.modeldata.maps_loaded=1;
        ScriptVariant value={3,VT_INTEGER};write_property(_ep_colourmap,&value);
        assert(actor.colourmap==tables[0][2] && actor.map==71);
        assert(target.colourmap==palettes[1] && target.map==73);
        reset();target.modeldata.maps_loaded=1;ent_set_colourmap(&target,3);
        assert(target.colourmap==tables[1][2] && target.map==3);
    }
    for(int property=_ep_hmapl;property<=_ep_hmapu;++property) {
        reset(); ScriptVariant value={27,VT_INTEGER};
        write_property(property,&value);
        assert(last_result==(c->has_result?1:-1234));
        entity *changed=c->mode==2?&target:&actor;
        entity *unchanged=c->mode==2?&actor:&target;
        assert((property==_ep_hmapl?changed->modeldata.maps.hide_start:
            changed->modeldata.maps.hide_end)==27);
        assert(unchanged->modeldata.maps.hide_start==(c->mode==2?11:21));
        assert(unchanged->modeldata.maps.hide_end==(c->mode==2?12:22));
    }
    for(unsigned i=0;i<sizeof(bounded)/sizeof(*bounded);++i) {
        reset();unsigned which=(unsigned)bounded[i];
        unsigned limit=c->fixed_helper?(unsigned)c->slots:3u;
        unsigned selected=which>limit?0:which;
        ent_set_colourmap(&target,which);
        unsigned char *expected=selected==0?palettes[1]:
            selected<=3?tables[1][selected-1]:NULL;
        assert(target.colourmap==expected && target.map==(int)selected);
        assert(actor.colourmap==palettes[0] && actor.map==71);
    }
    puts("entity colourmap mutation contract: OK");
}
int main(int argc,char **argv) {
    assert(argc==2);
    int revision=atoi(argv[1]), matched=0;
    for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
        if(contracts[i].revision!=revision) continue;
        check(&contracts[i]); ++matched;
    }
    assert(matched==1); return 0;
}
'''
    program = program.replace('HELPERS', components['helpers']).replace('CASES', components['cases'])
    if generated:
        # These inputs have no defined original oracle. Require the generated
        # memory-safety policy separately from historical mutation equivalence.
        checks = r'''
    for(int property=_ep_colourmap;property<=_ep_hmapu;++property) {
        reset(); ScriptVariant value={2,VT_EMPTY};
        entity before_actor=actor,before_target=target;
        write_property(property,&value);
        assert(!memcmp(&actor,&before_actor,sizeof(actor)));
        assert(!memcmp(&target,&before_target,sizeof(target)));
        reset(); self=NULL; value=(ScriptVariant){2,VT_INTEGER};
        before_actor=actor;before_target=target;
        write_property(property,&value);
        assert(!memcmp(&actor,&before_actor,sizeof(actor)));
        if(c->mode!=2) assert(!memcmp(&target,&before_target,sizeof(target)));
        else if(property==_ep_colourmap) {
            assert(target.colourmap==tables[1][1] && target.map==73);
        } else assert((property==_ep_hmapl?target.modeldata.maps.hide_start:
            target.modeldata.maps.hide_end)==2);
    }
    if(c->mode==0) {
        const int invalid[]={INT_MIN,-1,0,MAX_COLOUR_MAPS+1,INT_MAX};
        for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
            reset(); entity before_actor=actor,before_target=target;
            ScriptVariant value={invalid[i],VT_INTEGER};
            write_property(_ep_colourmap,&value);
            assert(!memcmp(&actor,&before_actor,sizeof(actor)));
            assert(!memcmp(&target,&before_target,sizeof(target)));
        }
    }
'''
        program = program.replace('    puts("entity colourmap mutation contract: OK");',
            checks + '    puts("entity colourmap mutation contract: OK");')
    return program.replace('CONTRACTS', '\n'.join(declarations))


class EntityColourmapTests(unittest.TestCase):
    def test_registry_covers_own_sources_for_each_native_profile(self):
        rows = CONTRACTS['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine']=='3741':
                self.assertIn(int(profile.get('revision',profile['build'])), revisions)
        for row in rows:
            with self.subTest(profile=row['revision']):
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertRegex(row['setter_sha256'], r'^[0-9a-f]{64}$')
                self.assertEqual(set(row['case_sha256']), {'colourmap','hmapl','hmapu'})
                for value in row['case_sha256'].values():
                    self.assertRegex(value, r'^[0-9a-f]{64}$')
                self.assertIn(row['mode'], ('raw_self','indexed_self','pointer_entity'))
                self.assertEqual(row['fixed_colourmap_slots'],30)
                self.assertIs(type(row['has_result']),bool)
                self.assertIn(row['helper_bound'],('fixed','loaded'))
                self.assertRegex(row['helper_sha256'],r'^[0-9a-f]{64}$')

    def test_mutations_per_profile_and_both_sides_of_boundaries(self):
        program = colourmap_program()
        with tempfile.TemporaryDirectory(prefix='anybor-entity-colourmaps-') as temporary:
            work = Path(temporary)
            source, executable = work/'probe.c', work/'probe'
            source.write_text(program)
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc')) + [
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-g','-fsanitize=address,undefined',str(source),'-o',str(executable)],
                check=True,timeout=60)
            executed=[]
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(executable),str(row['revision'])], check=True,
                        timeout=10,env=sanitizer_environment(),stdout=subprocess.DEVNULL)
                    executed.append(row['revision'])
            self.assertEqual(executed,[row['revision'] for row in CONTRACTS['sources']])
            print(json.dumps({'executed_profiles':executed,
                'scope':'colourmap mutation and branch results; callback entry tested separately'}))


if __name__=='__main__':
    unittest.main()
