"""Check each historical font-mask loader and its native lookup caller.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import tempfile
import unittest

import font_raster_probe as probe
from contract_fixtures import load_contract_fixture, contract_revisions
from test_font_raster import ROOT, ENGINE
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures')/'profile-late-font-mask-contracts.json'


def expected(available,format,flags,mode):
    if not available or mode in (1,2,8) or mode==7 and not flags&2:
        return [0,0,0,0]
    if mode==6 and format!=0:
        return [0,0,0,0]
    if mode==3 and not flags&1:
        return [0,2,0,0]
    counts=[256,256 if flags&2 and mode!=5 else 0,0]
    return [int(not flags&2 and mode!=4),*counts]


class FontMaskContracts(unittest.TestCase):
    def test_mask_loading_partial_results_and_owner_cleanup(self):
        data=load_contract_fixture(FIXTURE)
        revisions=[row['revision'] for row in data['sources']]
        self.assertEqual(set(revisions),contract_revisions(data,data['expected_revisions']))
        result=probe.run_profiles(ENGINE,ROOT/'src/port/libretro',revisions,
            mask_validation=True,blank_zero=True,retain_rows=True)
        self.assertTrue(result['sanitizers_enabled'])
        self.assertFalse(result['null_offset_oracle_exception'])
        for source in data['sources']:
            with self.subTest(revision=source['revision']):
                rows=result['profiles'][str(source['revision'])]['rows']
                self.assertEqual(len(rows),108)
                for format in (0,2,4):
                    for flags in range(4):
                        for mode in range(9):
                            key=f'WIDTHS mask {format} {flags} {mode}'
                            self.assertEqual(rows[key]['widths'],
                                expected(source['mask_available'],format,flags,mode),key)

    def test_native_font_and_mask_lookup_order(self):
        data=load_contract_fixture(FIXTURE)
        body=function((ENGINE/'openbor.c').read_text(),'load_all_fonts')
        program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#define MAX_FONTS 8
uint32_t obor_profile_build;
static char *packfile="authored";
static int fontmonospace[MAX_FONTS],fontmbs[MAX_FONTS];
static unsigned call;
static int want_masks;
static int missing_slot=-1;
static int font_load(int slot,char *path,char *pack,int flags) {
    char expected[64];
    assert(call==slot*(1u+want_masks)-(unsigned)(want_masks && missing_slot>=0 && slot>missing_slot));
    if(!slot)strcpy(expected,"data/sprites/font");
    else sprintf(expected,"data/sprites/font%d",slot+1);
    assert(!strcmp(path,expected) && pack==packfile);
    assert(flags==(fontmonospace[slot]|fontmbs[slot]));
    ++call;return slot!=missing_slot;
}
static int font_loadmask(int slot,char *path,char *pack,int flags) {
    char expected[64];assert(want_masks);
    assert(call==slot*2u+1u-(unsigned)(missing_slot>=0 && slot>missing_slot));
    if(!slot)strcpy(expected,"data/sprites/fontmask");
    else sprintf(expected,"data/sprites/fontmask%d",slot+1);
    assert(!strcmp(path,expected) && pack==packfile);
    assert(flags==(fontmonospace[slot]|fontmbs[slot]));
    ++call;return slot&1;
}
static int quiet(const char *format,...) {
    va_list args;va_start(args,format);int slot=va_arg(args,int)-1;va_end(args);
    assert(slot!=missing_slot);
    assert(!strcmp(format,want_masks && (slot&1)?"%d(m) ":"%d "));
    return 0;
}
#define printf quiet
@CALLER@
#undef printf
int main(int argc,char **argv) {
    assert(argc==3);obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);
    want_masks=atoi(argv[2]);
    for(int i=0;i<MAX_FONTS;++i) {fontmonospace[i]=i&1;fontmbs[i]=(i&2);}
    for(int partial=0;partial<2;++partial) {
        missing_slot=partial?3:-1;call=0;
        load_all_fonts();assert(call==MAX_FONTS*(1u+want_masks)-(unsigned)(partial && want_masks));
    }
    return 0;
}
'''.replace('@CALLER@',body)
        import subprocess
        from native_sanitizers import sanitizer_environment
        with tempfile.TemporaryDirectory(prefix='font-mask-caller-') as temporary:
            work=Path(temporary)
            probe.compile_probe(ENGINE,ROOT/'src/port/libretro',work,program,None,True,False)
            for source in data['sources']:
                subprocess.run([str(work/'probe'),str(source['revision']),str(int(source['mask_available']))],
                    env=sanitizer_environment(),check=True,timeout=10,capture_output=True)


if __name__=='__main__':
    unittest.main()
