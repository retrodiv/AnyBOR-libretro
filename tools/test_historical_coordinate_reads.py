"""Check source-defined coordinate queries and bounded prepared refusals.

Selected native entry/case bytes and variant conversions execute with reduced
model tables and numeric routing fixtures, independently of full VM/gameplay.
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

from historical_coordinate_reads import coordinate_entry,render_reads
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
CONTRACT_PATH=Path(__file__).parent/'fixtures/profile-coordinate-read-contracts.json'


def source_parts(engine):
    root=SOURCE/'src/engines'/engine
    code=(root/'openborscript.c').read_text()
    variant=(root/'source/scriptlib/ScriptVariant.c').read_text()
    header=(root/'openbor.h').read_text()
    declarations=list(re.finditer(r'^[ \t]*(short|int)[ \t]+attack_coords\[([0-9]+)\];',header,re.M))
    if len(declarations)!=1:
        raise ValueError('One native coordinate shape required')
    return (dict(entry=coordinate_entry(code),clear=function(variant,'ScriptVariant_Clear'),
                 change_type=function(variant,'ScriptVariant_ChangeType')),
            declarations[0][1],int(declarations[0][2]))


def program(engine,rows):
    parts,scalar,components=source_parts(engine)
    first=rows[0]
    code=render_reads(parts,scalar=scalar,components=components,
        visible_components=first['coordinate_components'],revision=first['revision'],
        labels=['prepared_source'],check_invalid=True)
    marker='int main(void) {'
    if code.count(marker)!=1:
        raise ValueError('One authored coordinate-query entry required')
    replacement='''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@',','.join(str(row['revision']) for row in rows))
    return code.replace(marker,replacement)


class CoordinateReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=load_contract_fixture(CONTRACT_PATH)['sources']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-coordinate-reads-')
        cls.addClassCleanup(temporary.cleanup);cls.work=Path(temporary.name)
        cls.groups={}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'],row['coordinate_components']),[]).append(row)
        cls.executables={}
        for index,(key,rows) in enumerate(cls.groups.items()):
            code=cls.work/('contract-%d.c'%index);executable=code.with_suffix('')
            code.write_text(program(key[0],rows))
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc'))+[
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-function','-g',
                '-fsanitize=address,undefined,float-cast-overflow',
                str(code),'-o',str(executable)],check=True,timeout=60)
            cls.executables[key]=executable

    def test_profile_registry_and_coordinate_boundary_have_own_sources(self):
        by_revision={row['revision']:row for row in self.rows}
        self.assertEqual(len(by_revision),len(self.rows))
        self.assertEqual(by_revision[3728]['coordinate_components'],5)
        self.assertEqual(by_revision[3729]['coordinate_components'],6)
        engines={row['engine'] for row in self.rows}
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-coordinate-read-contracts.json', pin['profiles']):
            if profile['engine'] in engines:
                row=by_revision[int(profile.get('revision',profile['build']))]
                self.assertEqual(row['engine'],profile['engine'])
        for row in self.rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            for value in row['source_sha256'].values():self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_each_profile_valid_queries_and_defined_prepared_refusals(self):
        for key,rows in self.groups.items():
            for row in rows:
                with self.subTest(revision=row['revision'],engine=row['engine']):
                    subprocess.run([str(self.executables[key]),str(row['revision'])],
                        check=True,timeout=15,env=sanitizer_environment(),stdout=subprocess.DEVNULL)


if __name__=='__main__':unittest.main()
