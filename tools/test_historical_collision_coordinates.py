"""Check each profile's authored collision coordinates and hit positions.

Exact prepared bodies run with reduced native-shaped entities and loaders.
Script queries, AI, full model loading and gameplay need separate checks.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from historical_collision_coordinates import render_collision
from native_sanitizers import sanitizer_environment
from test_historical_common_think import native_output
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
CONTRACT_PATH=Path(__file__).parent/'fixtures/profile-collision-coordinate-contracts.json'


def one(source,pattern):
    matches=list(re.finditer(pattern,source,re.M))
    if len(matches)!=1:
        raise ValueError('One exact collision source component required')
    return matches[0][0]


def source_parts(engine):
    root=SOURCE/'src/engines'/engine
    code=(root/'openbor.c').read_text()
    header=(root/'openbor.h').read_text()
    parts={'checkhit':function(code,'checkhit')}
    for name in ('BBOX','BBOXZ','ATTACKZ'):
        parts[name.lower()]=one(code,r'^[ \t]*case CMD_MODEL_'+name+
                               r':[^\n]*(?:\n[\s\S]*?)?^[ \t]*break;')
    parts['frame_coordinates']=one(code,r'^[ \t]*bbox_con\[0\][ \t]*=[^\n]*\n'
        r'[\s\S]*?^[ \t]*//attack\.attack_coords\[4\][^\r\n]*')
    declaration=one(header,r'^[ \t]*(?:short|int)[ \t]+attack_coords\[[0-9]+\];[^\r\n]*')
    scalar=re.search(r'\b(short|int)\b',declaration)[0]
    components=int(re.search(r'\[([0-9]+)\]',declaration)[1])
    return parts,scalar,components


def program(engine,rows):
    parts,scalar,components=source_parts(engine)
    first=rows[0]
    code=render_collision(parts,scalar=scalar,components=components,
        ranges=first['ranges'],tolerance_bonus=first['tolerance_bonus'],
        separation_padding=first.get('separation_padding',1),
        coop_filters_players=first.get('coop_filters_players',True),
        revision=first['revision'],labels=['prepared_source'])
    marker='int main(void) {'
    if code.count(marker)!=1:
        raise ValueError('One authored collision entry required')
    revisions=','.join(str(row['revision']) for row in rows)
    replacement='''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@',revisions)
    return '#include <stdlib.h>\n'+code.replace(marker,replacement)


class CollisionCoordinateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=load_contract_fixture(CONTRACT_PATH)['sources']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-collision-coordinates-')
        cls.addClassCleanup(temporary.cleanup)
        cls.work=Path(temporary.name)
        cls.groups={}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'],row['ranges'],row['tolerance_bonus'],
                                   row.get('separation_padding',1),
                                   row.get('coop_filters_players',True)),[]).append(row)
        cls.executables={}
        for index,(key,rows) in enumerate(cls.groups.items()):
            code=cls.work/('contract-%d.c'%index);executable=code.with_suffix('')
            code.write_text(program(key[0],rows))
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc'))+[
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-g','-fsanitize=address,undefined,float-cast-overflow',
                str(code),'-o',str(executable)],check=True,timeout=60)
            cls.executables[key]=executable

    def test_registered_profiles_and_boundaries_have_own_sources(self):
        by_revision={row['revision']:row for row in self.rows}
        self.assertEqual(len(by_revision),len(self.rows))
        self.assertTrue({3684,3685,3728,3729}<=set(by_revision))
        self.assertEqual(by_revision[3573]['separation_padding'],0)
        self.assertEqual(by_revision[3574]['separation_padding'],1)
        self.assertIs(by_revision[3684]['tolerance_bonus'],False)
        self.assertIs(by_revision[3685]['tolerance_bonus'],True)
        self.assertIs(by_revision[3728]['ranges'],False)
        self.assertIs(by_revision[3729]['ranges'],True)
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        engines={row['engine'] for row in self.rows}
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-collision-coordinate-contracts.json', pin['profiles']):
            if profile['engine'] in engines:
                row=by_revision[int(profile.get('revision',profile['build']))]
                self.assertEqual(row['engine'],profile['engine'])
        for row in self.rows:
            with self.subTest(revision=row['revision']):
                self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
                self.assertEqual(row['coordinate_components'],6 if row['ranges'] else 5)
                self.assertIn(row.get('separation_padding',1),(0,1))
                for value in row['source_sha256'].values():
                    self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_each_profile_loader_frame_sequence_and_hit_results(self):
        for key,rows in self.groups.items():
            for row in rows:
                with self.subTest(revision=row['revision'],engine=row['engine']):
                    subprocess.run([str(self.executables[key]),str(row['revision'])],
                        check=True,timeout=15,env=sanitizer_environment(),
                        stdout=subprocess.DEVNULL)


class ModernBodyBoxDepthTests(unittest.TestCase):
    def test_overlap_center_and_edges_at_original_depth_boundaries(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', SOURCE / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
@CHECK_COLLISION@

struct depth_result { int center, background, foreground; };

static void check_depth(int target_z, int hit, struct depth_result expected)
{
    s_hitbox seeker_box = {.width = 10, .height = 6, .z_background = 12, .z_foreground = 20};
    s_hitbox target_box = {.width = 10, .height = 6, .z_background = 14, .z_foreground = 9};
    s_axis_principal_int seeker_position = {.x = 20, .y = 10, .z = 10};
    s_axis_principal_int target_position = {.x = 20, .y = 10, .z = target_z};
    s_box overlap = {.center_x = -1, .center_y = -1, .center_z = -1,
                     .background = -2, .foreground = -3};
    s_collision_check_data test = {
        .return_overlap = &overlap,
        .seeker_pos = &seeker_position, .seeker_coords = &seeker_box,
        .seeker_direction = DIRECTION_RIGHT,
        .target_pos = &target_position, .target_coords = &target_box,
        .target_direction = DIRECTION_RIGHT,
    };
    int accepted = check_collision(&test);
    if(accepted != hit || overlap.center_z != expected.center ||
       overlap.background != expected.background || overlap.foreground != expected.foreground ||
       overlap.center_x != (hit ? 25 : -1) || overlap.center_y != (hit ? 7 : -1))
    {
        fprintf(stderr, "Unexpected collision depth for profile %u at %d\n", obor_profile_build, target_z);
        abort();
    }
}

int main(void)
{
    static const struct {
        uint32_t revision;
        struct depth_result expected[3];
    } cases[] = {
        {7369, {{16,-2,-3}, {21,-2,-3}, {23,-2,-3}}},
        {7391, {{16,-2,-3}, {21,-2,-3}, {23,-2,-3}}},
        {7419, {{16,-2,-3}, {13,-2,-3}, {14,-2,-3}}},
        {7420, {{16,-2,-3}, {17, 6,29}, {19, 8,30}}},
        {7438, {{16,-2,-3}, {17, 6,29}, {19, 8,30}}},
        {7439, {{12, 1,24}, {17, 6,29}, {19, 8,30}}},
        {7533, {{12, 1,24}, {17, 6,29}, {19, 8,30}}},
    };
    static const int positions[] = {15, 20, 22};
    for(size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        obor_profile_build = cases[i].revision;
        for(size_t j = 0; j < sizeof(positions) / sizeof(*positions); ++j)
            check_depth(positions[j], 1, cases[i].expected[j]);
        check_depth(100, 0, (struct depth_result){-1, -2, -3});
    }
    return 0;
}
'''
        code = code.replace('@CHECK_COLLISION@', function(source, 'check_collision'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_foreground_depth_at_7420_boundary(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', SOURCE / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        loader = function(source, 'load_cached_model')
        case = loader.split('case CMD_MODEL_BBOX:', 1)[1].split('case CMD_MODEL_BBOX_INDEX:', 1)[0]
        depth = one(case, r'^\s*tempInt = GET_INT_ARG\(5\);[\s\S]*?->z_foreground = [^;]+;')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
static unsigned warnings;
#undef printf
#define printf(...) (++warnings)
#undef assert
#define assert(expression) do { if(!(expression)) abort(); } while(0)
@IS_NUMERIC@
@VALID_INT@
#undef printf

static s_hitbox coordinates;
#define collision_body_upsert_coordinates_property(...) (&coordinates)

static void check_depth(char *foreground, int expected_depth, unsigned expected_warnings)
{
    ArgList arglist = {.count = foreground ? 7 : 6, .args = {[5] = "9", [6] = foreground}};
    char *filename = "model", *command = "bbox", *value;
    int tempInt;
    warnings = 0;
    coordinates = (s_hitbox){0};
    @LOAD_DEPTH@
    if(coordinates.z_background != 9 || coordinates.z_foreground != expected_depth ||
       warnings != expected_warnings)
    {
        fprintf(stderr, "Unexpected body-box depth for profile %u\n", obor_profile_build);
        abort();
    }
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7391, 7419, 7420, 7530, 7533};
    for(size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int symmetric_depth = obor_profile_build >= 7420;
        check_depth(NULL, symmetric_depth ? 9 : 0, 0);
        check_depth("text", symmetric_depth ? 9 : 0, symmetric_depth ? 0 : 1);
        check_depth("0", 0, 0);
        check_depth("4", 4, 0);
    }
    return 0;
}
'''
        code = code.replace('@LOAD_DEPTH@', depth)
        code = code.replace('@IS_NUMERIC@', function(source, 'isNumeric'))
        code = code.replace('@VALID_INT@', function(source, 'getValidInt'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')


if __name__=='__main__':
    unittest.main()
