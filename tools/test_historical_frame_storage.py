"""Check complete native frame functions with each profile's value contract.

The native engine header supplies real records and array types. Allocation is
tracked and bounded; model parsing, raster, state and gameplay are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_frame_storage import render_frames
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
CONTRACT_PATH=Path(__file__).parent/'fixtures/profile-frame-storage-contracts.json'


def source_parts(engine):
    source=(SOURCE/'src/engines'/engine/'openbor.c').read_text()
    parts={name:function(source,name) for name in
           ('alloc_frames','free_frames','addframe','setDrawMethod','getDrawMethod')}
    marker='#define ANIM_DRAWMETHOD_BUCKETS'
    parts['cache']=''
    if marker in source:
        if source.count(marker)!=1:
            raise ValueError('One native drawing cache required')
        first=source.index(marker);release=function(source,'release_anim_drawmethod')
        last=source.index(release,first)+len(release)
        parts['cache']=source[first:last]
    return parts


def program(engine,rows):
    first=rows[0]
    code=render_frames(source_parts(engine),visible_components=first['coordinate_components'],
                       revision=first['revision'],labels=['prepared_source'])
    marker='int main(void) {'
    if code.count(marker)!=1:
        raise ValueError('One authored frame storage entry required')
    entry='''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@',','.join(str(row['revision']) for row in rows))
    return code.replace(marker,entry)


class FrameStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads(CONTRACT_PATH.read_text())['sources']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-frame-storage-')
        cls.addClassCleanup(temporary.cleanup);cls.work=Path(temporary.name)
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warning_flags=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        link_flags=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-Wl,--gc-sections']
        host_flags=[] if sys.platform=='darwin' else ['-DLINUX=1']
        cls.groups={};cls.executables={}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'],row['coordinate_components']),[]).append(row)
        for index,(key,rows) in enumerate(cls.groups.items()):
            root=SOURCE/'src/engines'/key[0]
            includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            code=cls.work/('contract-%d.c'%index);executable=code.with_suffix('')
            code.write_text(program(key[0],rows))
            include_flags=['-I'+str(p) for p in includes]
            subprocess.run(compiler+include_flags+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-unused-parameter',
                *warning_flags,'-g','-O1','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+key[0],
                *host_flags,'-fsigned-char','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                str(code),*link_flags,'-lm','-o',str(executable)],check=True,timeout=60)
            cls.executables[key]=executable

    def test_profiles_and_native_epoch_controls_have_own_sources(self):
        by_revision={row['revision']:row for row in self.rows}
        self.assertEqual(len(by_revision),len(self.rows))
        self.assertTrue({3728,3729,3747,3748}<=set(by_revision))
        self.assertEqual(by_revision[3728]['coordinate_components'],5)
        self.assertEqual(by_revision[3729]['coordinate_components'],6)
        self.assertEqual(by_revision[3747]['coordinate_scalar_type'],'short')
        self.assertEqual(by_revision[3748]['coordinate_scalar_type'],'int')
        engines={row['engine'] for row in self.rows}
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] in engines:
                row=by_revision[int(profile.get('revision',profile['build']))]
                self.assertEqual(row['engine'],profile['engine'])
        for row in self.rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            for value in row['source_sha256'].values():self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_each_profile_full_frame_values_and_owned_cleanup(self):
        for key,rows in self.groups.items():
            for row in rows:
                with self.subTest(revision=row['revision'],engine=row['engine']):
                    subprocess.run([str(self.executables[key]),str(row['revision'])],
                        check=True,timeout=15,env=sanitizer_environment(),stdout=subprocess.DEVNULL)


if __name__=='__main__':unittest.main()
