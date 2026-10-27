"""Check each profile's authored collision coordinates and hit positions.

Exact prepared bodies run with reduced native-shaped entities and loaders.
Script queries, AI, full model loading and gameplay need separate checks.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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
        cls.rows=json.loads(CONTRACT_PATH.read_text())['sources']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-collision-coordinates-')
        cls.addClassCleanup(temporary.cleanup)
        cls.work=Path(temporary.name)
        cls.groups={}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'],row['ranges'],row['tolerance_bonus']),[]).append(row)
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
        self.assertIs(by_revision[3684]['tolerance_bonus'],False)
        self.assertIs(by_revision[3685]['tolerance_bonus'],True)
        self.assertIs(by_revision[3728]['ranges'],False)
        self.assertIs(by_revision[3729]['ranges'],True)
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        engines={row['engine'] for row in self.rows}
        for profile in pin['profiles']:
            if profile['engine'] in engines:
                row=by_revision[int(profile.get('revision',profile['build']))]
                self.assertEqual(row['engine'],profile['engine'])
        for row in self.rows:
            with self.subTest(revision=row['revision']):
                self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
                self.assertEqual(row['coordinate_components'],6 if row['ranges'] else 5)
                for value in row['source_sha256'].values():
                    self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_each_profile_loader_frame_sequence_and_hit_results(self):
        for key,rows in self.groups.items():
            for row in rows:
                with self.subTest(revision=row['revision'],engine=row['engine']):
                    subprocess.run([str(self.executables[key]),str(row['revision'])],
                        check=True,timeout=15,env=sanitizer_environment(),
                        stdout=subprocess.DEVNULL)


if __name__=='__main__':
    unittest.main()
