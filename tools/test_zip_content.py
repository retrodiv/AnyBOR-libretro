"""Recognize a unique ZIP game from references, retaining bounded extraction.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest
import zipfile
from native_sanitizers import sanitizer_environment
from make_fixture import write_pak, files as diagnostic_files

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
GLUE = Path(os.environ.get('OBOR_GLUE_DIR', ROOT / 'src/glue'))
THIRD = Path(os.environ.get('OBOR_THIRD_PARTY', ROOT / 'src/third_party'))


def build_probe(directory, *, synthetic=True):
    source = directory / 'zip-probe.cpp'
    table = ''
    if synthetic:
        rows = sorted((hashlib.sha256(value).hexdigest(), build)
                      for value, build in ((b'engine A', 4000), (b'engine B', 4100)))
        table = '''#define OBOR_ENGINE_EXECUTABLES_H
typedef struct {const char *sha256; int build; const char *variant; unsigned bytes;} obor_engine_executable;
static const obor_engine_executable obor_engine_executables[] = {''' + ','.join(
            '{"%s",%d,"",8}' % row for row in rows) + '};'
    source.write_text(r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <strings.h>
#include <filesystem>
#define RETRO_LOG_ERROR 1
#define RETRO_LOG_INFO 0
static void log_cb(int,const char *format,...) {
    va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);
}
static void mkdir_p(const char *path) { std::filesystem::create_directories(path); }
@TABLE@
#include "obor_zip.h"
int main(int argc, char **argv) {
    if(argc!=3 && argc!=4) return 2;
    char path[4096] = "";
    obor_engine_identity identity = {};
    if(!obor_storage_begin(argv[2],false,false)) return 3;
    int ok=obor_zip_prepare(argv[1],argv[2],path,sizeof(path),argc==4?argv[3]:NULL,&identity);
    printf("%d %d %d %s\n",ok,identity.status,
        identity.status==OBOR_ENGINE_IDENTIFIED?identity.engine->build:0,path);
}
'''.replace('@TABLE@', table))
    flags = ['-g', '-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    objects = []
    for name, path in (('miniz', THIRD / 'miniz.c'),
                       ('obor_transform_vm', GLUE / 'obor_transform_vm.c'),
                       ('obor_transform_source', GLUE / 'obor_transform_source.c')):
        obj = directory / (name + '.o')
        subprocess.run([*shlex.split(os.environ.get('HOST_CC', 'cc')), '-std=gnu99',
                        *flags, '-c', str(path), '-o', str(obj)], check=True, timeout=60)
        objects.append(str(obj))
    binary = directory / 'zip-probe'
    subprocess.run([*shlex.split(os.environ.get('HOST_CXX', 'c++')), '-std=c++17',
        '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', *flags,
        '-I', str(GLUE), '-I', str(THIRD), str(source), *objects, '-o', str(binary)],
        check=True, timeout=60)
    return binary


class ZipContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='anybor-zip-content-')
        cls.directory = Path(cls.work.name)
        cls.binary = build_probe(cls.directory)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.directory)
        self.folder = Path(self.case.name)

    def tearDown(self):
        self.case.cleanup()

    def game(self, prefix=''):
        return {prefix + 'data/models.txt': b'# authored\nload Block data/chars/block.txt\n',
                prefix + 'data/chars/block.txt': b'name Block\ntype player\n'}

    def pak(self):
        path = self.folder / 'authored.pak'
        write_pak(path, self.game())
        return path.read_bytes()

    def run_zip(self, members, *, system=None):
        archive = self.folder / 'content.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
            for name, data in (members.items() if isinstance(members, dict) else members):
                stream.writestr(name, data)
        command = [str(self.binary), str(archive), str(self.folder / 'save')]
        if system: command.append(str(system))
        run = subprocess.run(command, capture_output=True, text=True, check=True,
                             timeout=30, env=sanitizer_environment())
        fields = run.stdout.rstrip('\n').split(' ', 3)
        return tuple(map(int, fields[:3])), fields[3], run.stderr

    def test_single_real_pak_and_data_tree_load(self):
        result, path, _ = self.run_zip({'Paks/game.pak': self.pak()})
        self.assertEqual(result, (1, 0, 0)); self.assertTrue(path.endswith('/Paks/game.pak'))
        result, path, _ = self.run_zip(self.game('bundle/'))
        self.assertEqual(result, (1, 0, 0)); self.assertTrue(path.endswith('/bundle/data/models.txt'))

    def test_multiplatform_engine_names_inside_one_game_package(self):
        members=self.game('bundle/')
        members.update({'bundle/linux/OpenBOR':b'engine A',
                        'bundle/android/engine.apk':b'engine A',
                        'bundle/wii/boot.dol':b'engine A',
                        'bundle/tools/utility.exe':b'unknown tool'})
        result,path,_=self.run_zip(members)
        self.assertEqual(result,(1,1,4000))
        self.assertTrue(path.endswith('/bundle/data/models.txt'))

    def test_core_zip_helper_needs_no_cpp_runtime_library(self):
        source = self.folder / 'runtime-imports.cpp'
        source.write_text(r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#define RETRO_LOG_ERROR 1
#define RETRO_LOG_INFO 0
static void log_cb(int,const char *,...) {}
static void mkdir_p(const char *) {}
#include "obor_zip.h"
extern "C" int zip_game_probe(const char *path,const char *save,char *out,size_t cap) {
    return obor_zip_prepare(path,save,out,cap);
}
''')
        obj = self.folder / 'runtime-imports.o'
        subprocess.run([*shlex.split(os.environ.get('HOST_CXX', 'c++')), '-std=c++11',
            '-O1', '-fno-exceptions', '-fno-rtti', '-I', str(GLUE), '-I', str(THIRD),
            '-c', str(source), '-o', str(obj)], check=True, timeout=60)
        imports = subprocess.check_output([os.environ.get('NM', 'nm'), '-u', str(obj)],
                                          text=True, timeout=20)
        cpp = [line.strip() for line in imports.splitlines() if line.split() and
               line.split()[-1].startswith(('_Z', '__Z', '__cxa', '___cxa',
                                           '__gxx_personality', '___gxx_personality'))]
        self.assertEqual(cpp, [], '\n'.join(cpp))

    def test_wave_with_pak_extension_is_auxiliary_beside_real_game(self):
        pcm = b'\0' * 14
        wave = b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack(
            '<IHHIIHH', 16, 1, 1, 22050, 44100, 2, 16) + b'data' + struct.pack('<I', len(pcm)) + pcm
        self.assertEqual(len(wave), 58)
        members = self.game(); members['Paks/audio.pak'] = wave
        members['OpenBOR.exe'] = b'engine A'; members['Paks/utility.exe'] = b'not an engine'
        result, path, log = self.run_zip(members)
        self.assertEqual(result, (1, 1, 4000)); self.assertTrue(path.endswith('/data/models.txt'))
        self.assertIn('auxiliary RIFF/WAVE', log)

    def test_case_and_quoted_model_paths_are_recognized(self):
        members = {'bundle/DATA/MODELS.TXT': b'\xef\xbb\xbfload "Block" "data/Chars/block one.txt"\r\n',
                   'bundle/DATA/chars/Block One.txt': b'name Block\ntype player\n'}
        self.assertEqual(self.run_zip(members)[0], (1, 0, 0))

    def test_external_preparation_and_structural_header_repair_are_retained(self):
        system = self.folder / 'system'; system.mkdir()
        (system / 'AnyBOR.ini').write_text(
            '[transforms]\ninput=buffer unwrap(){return slice(4,input_size-4);}\n')
        self.assertEqual(self.run_zip({'Paks/game.pak': b'TEST' + self.pak()}, system=system)[0], (1, 0, 0))
        path = self.folder / 'diagnostic.pak'; write_pak(path, diagnostic_files())
        damaged = b'BAD!' + path.read_bytes()[4:]
        self.assertEqual(self.run_zip({'Paks/game.pak': damaged})[0], (1, 0, 0))

    def test_two_games_or_unrecognized_candidates_are_rejected(self):
        cases = [dict(self.game(), **{'Paks/game.pak': self.pak()}),
                 dict(self.game(), **{'Paks/unknown.pak': b'unknown'}),
                 {'Paks/unknown.pak': b'unknown'}, {'data/models.txt': b'# no models\n'},
                 {'data/models.txt': b'load Block data/missing.txt\n'}]
        for members in cases:
            with self.subTest(names=list(members)):
                self.assertEqual(self.run_zip(members)[0][0], 0)

    def test_distinct_engine_builds_fall_back_without_rejecting_one_game(self):
        members = self.game(); members['one.exe'] = b'engine A'; members['tools/two.exe'] = b'engine B'
        self.assertEqual(self.run_zip(members)[0], (1, 2, 0))

    def test_unsafe_paths_links_collisions_and_incomplete_wave_are_rejected(self):
        link = zipfile.ZipInfo('link'); link.create_system = 3; link.external_attr = 0o120777 << 16
        cases = [[('../escape', b'bad'), *self.game().items()],
                 [(link, b'data/models.txt'), *self.game().items()],
                 [*self.game().items(), ('DATA/models.txt', b'load X data/no.txt')],
                 [('data', b'file'), *self.game().items()],
                 [*self.game().items(), ('Paks/audio.pak', b'RIFF\0\0\0\0WAVE')]]
        for members in cases:
            with self.subTest(names=[row[0] for row in members]):
                self.assertEqual(self.run_zip(members)[0][0], 0)

    def test_extraction_ratio_and_entry_limits_are_retained(self):
        self.assertEqual(self.run_zip(dict(self.game(), **{'padding.bin': b'\0' * (2 << 20)}))[0][0], 0)
        members = self.game()
        members.update(('entry-%d' % i, b'') for i in range(8193))
        self.assertEqual(self.run_zip(members)[0][0], 0)

    def test_inconclusive_model_reference_observation_is_bounded(self):
        members = self.game()
        members['data/models.txt'] = b'know Missing data/no.txt\n' * 32 + members['data/models.txt']
        self.assertEqual(self.run_zip(members)[0][0], 0)


class LooseCasePathTests(unittest.TestCase):
    def test_nested_asset_lookup_preserves_directory_prefix_by_profile(self):
        from test_historical_player import function
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        with tempfile.TemporaryDirectory(prefix='anybor-loose-case-') as temporary:
            work = Path(temporary)
            case = work / 'content'
            case.mkdir()
            (case / 'Leaf.GIF').write_bytes(b'leaf')
            nested = case / 'Assets/Actors/Player'
            nested.mkdir(parents=True)
            (nested / 'Frame.GIF').write_bytes(b'authored')
            parts = ['A' * 190, 'B' * 190, 'C' * 190]
            long_folder = case.joinpath(*parts)
            long_folder.mkdir(parents=True)
            (long_folder / 'Frame.GIF').write_bytes(b'authored')
            long_query = '/'.join(parts + ['Frame.GIF']).lower()
            for entry in pin['engines']:
                engine = entry['build']
                unit = ROOT / 'src/engines' / engine / 'source/gamelib/packfile.c'
                body = function(unit.read_text(encoding='latin1'), 'casesearch')
                source, binary = work / (engine + '.c'), work / engine
                source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define PACKFILE_PATH_MAX 512
#define stricmp strcasecmp
uint32_t obor_profile_build;
static void obor_profile_casesearch_assert(void) { abort(); }
@FUNCTION@
int main(int argc, char **argv) {
    assert(argc == 3);
    obor_profile_build = (uint32_t)strtoul(argv[1], NULL, 10);
    char query[] = "assets/actors/player/frame.gif";
    char *path = casesearch(".", "leaf.gif");
    assert(path && !strcmp(path, "./Leaf.GIF"));
    path = casesearch(".", query);
    assert(path && !strcmp(path, "./Assets/Actors/Player/Frame.GIF"));
    assert(!strcmp(query, "assets/actors/player/frame.gif"));
    FILE *file = fopen(path, "rb");
    char bytes[8];
    assert(file && fread(bytes, 1, sizeof(bytes), file) == sizeof(bytes));
    assert(!memcmp(bytes, "authored", sizeof(bytes)) && !fclose(file));
    assert(casesearch(".", "assets/actors/missing/frame.gif") == NULL);
    assert(casesearch(".", argv[2]) == NULL);
    char oversized[1024], nested_oversized[1034];
    memset(oversized, 'Q', sizeof(oversized) - 1);
    oversized[sizeof(oversized) - 1] = 0;
    int length = snprintf(nested_oversized, sizeof(nested_oversized), "%s/leaf.gif", oversized);
    assert(length > 0 && (size_t)length < sizeof(nested_oversized));
    assert(casesearch(".", oversized) == NULL);
    assert(casesearch(".", nested_oversized) == NULL);
    assert(casesearch(NULL, "leaf.gif") == NULL);
    assert(casesearch(".", NULL) == NULL);
    puts(argv[1]);
    return 0;
}
'''.replace('@FUNCTION@', body))
                command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                    '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-Wno-error=deprecated-declarations',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(source), '-o', str(binary)]
                subprocess.run(command, check=True, timeout=45)
                profiles = [row['build'] for row in pin['profiles']
                            if row['engine'] == engine]
                self.assertTrue(profiles)
                for profile in profiles:
                    with self.subTest(profile=profile, engine=engine):
                        result = subprocess.check_output(
                            [str(binary), profile, long_query], cwd=case, text=True,
                            timeout=10, env=sanitizer_environment())
                        self.assertEqual(result.strip(), profile)


if __name__ == '__main__':
    unittest.main()
