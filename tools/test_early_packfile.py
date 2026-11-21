"""Check own historical packfile backend and release diagnostic policies.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-pack-backend.json'


class EarlyPackfileTests(unittest.TestCase):
    def test_authored_archive_uses_historical_directory_separators(self):
        from make_fixture import write_pak
        members = {'data/sprites/font.png': b'font',
                   'data\\sounds\\beep.wav': b'sound', 'outside.txt': b'leaf'}
        with tempfile.TemporaryDirectory(prefix='pack-directory-') as name:
            path = Path(name) / 'fixture.pak'
            write_pak(path, members)
            data = path.read_bytes()
        self.assertEqual(data[:8], b'PACK\0\0\0\0')
        cursor, = struct.unpack_from('<I', data, len(data) - 4)
        observed = {}
        while cursor < len(data) - 4:
            length, start, size = struct.unpack_from('<III', data, cursor)
            encoded = data[cursor + 12:cursor + length]
            self.assertTrue(encoded.endswith(b'\0'))
            self.assertNotIn(b'/', encoded)
            observed[encoded[:-1].decode('ascii')] = data[start:start + size]
            cursor += length
        self.assertEqual(cursor, len(data) - 4)
        self.assertEqual(observed, {key.replace('/', '\\'): value
                                    for key, value in members.items()})

    def test_backend_startup_and_fallback(self):
        self._exercise(load_contract_fixture(FIXTURE))

    def test_cached_name_lookup(self):
        self._exercise(load_contract_fixture(FIXTURE.with_name(
            "profile-early-pack-lookup.json")), lookup=True)

    def test_large_header_acceptance(self):
        self._exercise(load_contract_fixture(FIXTURE.with_name(
            'profile-early-pack-header.json')), header=True)

    def test_direct_member_name_capacity(self):
        self.check_direct_member_name_capacity('profile-4432-pack-member-names.json')

    def test_6391_direct_member_name_capacity(self):
        self.check_direct_member_name_capacity('profile-6391-packed-members.json')

    def check_direct_member_name_capacity(self, fixture_name):
        from make_fixture import write_pak

        fixture = load_contract_fixture(FIXTURE.with_name(fixture_name))
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(fixture['sources']), len(revisions))
        self.assertEqual(revisions, contract_revisions(fixture, fixture['expected_revisions']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(fixture, pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and 4510 <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine_variable = 'OBOR_PACK_MEMBER_ENGINE' if fixture['engine'] == '4432' else 'OBOR_HISTORICAL_ENGINE'
        engine = Path(os.environ.get(engine_variable,
                                     ROOT / 'src/engines' / fixture['engine']))
        gamelib = engine / 'source/gamelib'
        unit = (gamelib / 'packfile.c').read_text(encoding='latin-1')
        definitions = '\n'.join(re.findall(
            r'(?m)^#define[ \t]+(?:MAXPACKHANDLES|PACKMAGIC|PACKVERSION|PACKFILE_PATH_MAX|PACKFILE_PATH_STORAGE)\b[^\n]*'
            r'|^static [^\n]*\b(?:packhandle|packfilepointer|packfilesize)\[MAXPACKHANDLES\][^\n]*;', unit))
        names = ('packfile_path_capacity', 'slashback', 'slashfwd', 'getFreeHandle', 'openPackfile',
                 'readPackfile', 'closePackfile')
        bodies = '\n'.join(function(unit, name) for name in names)
        program = r'''
#include <assert.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "packfile.h"
#include "borendian.h"
#define stricmp strcasecmp
uint32_t obor_profile_build;
static int obor_loose_may_exist(const char *path) { (void)path; return 0; }
void writeToLogFile(const char *message, ...) { (void)message; abort(); }
void exitIfFalse(int value, const char *assertion, const char *fn, const char *file, int line)
{
    if(!value)
    {
        fprintf(stderr, "%s:%d: %s: %s\n", file, line, fn, assertion);
        abort();
    }
}
@DEFINITIONS@
@FUNCTIONS@
int main(int argc, char **argv)
{
    assert(argc == 8);
    obor_profile_build = (uint32_t)strtoul(argv[1], NULL, 10);
    size_t capacity = (size_t)strtoul(argv[2], NULL, 10);
    for(int i = 4; i < argc; ++i)
    {
        int handle = openPackfile(argv[i], argv[3]);
        if(strlen(argv[i]) >= capacity)
        {
            assert(handle == -1);
        }
        else
        {
            char content[2];
            assert(handle >= 0);
            assert(readPackfile(handle, content, sizeof(content)) == 1);
            assert(content[0] == 'a' + i - 4);
            assert(closePackfile(handle) == 0);
        }
    }
    return 0;
}
'''.replace('@DEFINITIONS@', definitions).replace('@FUNCTIONS@', bodies)
        filenames = ['data/' + c * (length - len('data/.bin')) + '.bin'
                     for c, length in [('a', 79), ('b', 80), ('c', 255)]]
        if fixture['engine'] == '6391':
            filenames = [filenames[0], filenames[2], 'data/' + 'Scenery/' * 48 + 'Actor.bin']
        filenames.append('data/z.bin')
        with tempfile.TemporaryDirectory(prefix='pack-member-names-') as name:
            work = Path(name)
            pak, source, binary = (work / filename for filename in ('names.pak', 'probe.c', 'probe'))
            write_pak(pak, {key: bytes([ord('a') + index]) for index, key in enumerate(filenames)})
            source.write_text(program)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            build = subprocess.run(compiler + ['-std=gnu99', '-O1', '-UNDEBUG',
                '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-I', str(gamelib), '-I', str(engine / 'source'),
                '-I', str(ROOT / 'src/port/libretro'),
                str(source), *links, '-o', str(binary)],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            for row in fixture['sources']:
                with self.subTest(revision=row['revision']):
                    self.assertEqual(row['engine'], fixture['engine'])
                    capacity = row['capacity'] if fixture['engine'] == '4432' else row['direct_capacity']
                    run = subprocess.run([str(binary), str(row['revision']), str(capacity),
                        str(pak), *(filename.upper() for filename in filenames)],
                        cwd=work, env=sanitizer_environment(), capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_4432_loose_and_cached_name_capacity(self):
        from make_fixture import write_pak

        fixture = load_contract_fixture(FIXTURE.with_name('profile-4432-packfile-paths.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(fixture, fixture['expected_revisions']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(fixture, pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and 4510 <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

        engine = Path(os.environ.get('OBOR_PACK_MEMBER_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        gamelib = engine / 'source/gamelib'
        scriptlib = engine / 'source/scriptlib'
        unit = (gamelib / 'packfile.c').read_text(encoding='latin-1')
        definitions = '\n'.join(re.findall(
            r'(?m)^#define[ \t]+(?:MAXPACKHANDLES|CACHEBLOCKSIZE|PACKFILE_PATH_MAX)\b[^\n]*'
            r'|^static const size_t USED_FLAG[^\n]*;', unit))
        names = ('tolowerOneChar', 'fnlc', 'myfilenamecmp', 'packfile_path_capacity', 'slashback',
                 'slashfwd', 'casesearch', 'pak_header_entry', 'makefilenamecache',
                 'freefilenamecache', 'openreadaheadpackfile', 'openPackfileCached')
        bodies = '\n'.join(function(unit, name) for name in names)
        endian = function((engine / 'source/utils.c').read_text(), 'readlsb32')
        program = Path(__file__).with_name('packfile_path_contract.c.in').read_text()
        program = program.replace('@DEFINITIONS@', definitions).replace('@FUNCTIONS@', endian + bodies)
        filenames = ['data/' + letter * (length - len('data/.bin')) + '.bin'
                     for letter, length in zip('abcde', (10, 255, 256, 511, 512))]
        short_path = Path('Assets/Item.txt')
        long_path = Path('Assets', 'A' * 130, 'B' * 130, 'Item.txt')
        with tempfile.TemporaryDirectory(prefix='packfile-paths-') as name:
            work = Path(name)
            pak, source, binary, obj = (work / file for file in ('valid.pak', 'probe.c', 'probe', 'list.o'))
            write_pak(pak, {key: bytes([index]) for index, key in enumerate(filenames)})
            for path in (short_path, long_path):
                (work / path).parent.mkdir(parents=True, exist_ok=True)
                (work / path).write_bytes(b'asset')
            source.write_text(bind_named_allocation_support(program, engine))
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-UNDEBUG', '-DUNIT_TEST=1',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-I', str(scriptlib), '-I', str(gamelib), '-I', str(ROOT / 'src/port/libretro')]
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            build = subprocess.run(compiler + flags + ['-c', str(scriptlib / 'List.c'), '-o', str(obj)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(compiler + flags + ['-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                                   str(source), str(obj), *links, '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            for row in rows:
                with self.subTest(revision=row['revision']):
                    run = subprocess.run([str(binary), str(row['revision']), str(row['capacity']),
                        str(pak), short_path.as_posix(), long_path.as_posix(), *filenames],
                        cwd=work, env=sanitizer_environment(), capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_6391_cached_member_names(self):
        from make_fixture import write_pak
        from test_historical_common_think import native_output
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-packed-members.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        gamelib = engine / 'source/gamelib'
        unit = (gamelib / 'packfile.c').read_text(encoding='latin-1')
        header = (gamelib / 'packfile.h').read_text(encoding='latin-1')
        utils = (engine / 'source/utils.c').read_text(encoding='latin-1')
        constants = re.findall(r'(?m)^#define\s+(?:MAXPACKHANDLES|CACHEBLOCKSIZE|PACKFILE_PATH_MAX|PACKFILE_PATH_STORAGE)\b[^\n]*'
                              r'|^static const size_t USED_FLAG[^\n]*;', unit + '\n' + header)
        prefix = 'Data/' + 'Scenery/' * 61
        filenames = ('Data/Actors/Walk.bin', prefix + 'SceneFragments.bin', prefix + 'ScreenFragments.bin',
                     'Data/' + 'Scenery/' * 220 + 'DistantScene.bin')
        self.assertEqual([len(name) for name in filenames[:3]], [20, 511, 512])
        functions = ('tolowerOneChar', 'fnlc', 'myfilenamecmp', 'packfile_path_capacity', 'slashback',
                     'slashfwd', 'casesearch', 'pak_header_entry', 'makefilenamecache',
                     'freefilenamecache', 'openreadaheadpackfile', 'openPackfileCached')
        with tempfile.TemporaryDirectory(prefix='packed-member-names-') as work:
            directory = Path(work)
            path = directory / 'members.pak'
            write_pak(path, {tag: bytes([index + 1]) for index, tag in enumerate(filenames)})
            image = path.read_bytes()
            loose_names = (Path('Assets', 'Actor.bin'), Path('Assets', *('ScenerySection' for _ in range(40)), 'Actor.bin'))
            for loose in loose_names:
                (directory / loose).parent.mkdir(parents=True, exist_ok=True)
                (directory / loose).write_bytes(b'asset')
            fields = {
                'CONSTANTS': '\n'.join(constants),
                'FUNCTIONS': function(utils, 'readlsb32') + '\n'.join(function(unit, name) for name in functions),
                'IMAGE': ','.join(str(byte) for byte in image),
                'NAMES': ',\n'.join(json.dumps(name) for name in filenames),
                'LOOSE_ROOT': json.dumps(work),
                'LOOSE_NAMES': ','.join(json.dumps(loose.as_posix()) for loose in loose_names),
                'PROFILES': ',\n'.join('{%du,%d}' % (r['revision'], r['member_capacity']) for r in rows),
            }
            template = Path(__file__).with_name('packed_member_names_contract.c.in').read_text()
            code = re.sub(r'@([A-Z_]+)@', lambda match: fields[match[1]], template)
            actual = native_output(bind_named_allocation_support(code, engine), data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def _exercise(self, fixture, lookup=False, header=False):
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(row.get('revision', row['build']))
            if row['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key in ('filename_cache',) if lookup else ('startup_enabled', 'raw_directory_check', 'handle_message'):
                self.assertIs(type(row[key]), bool)
            entries.append('{%d,%d,%d,%d,%s,%d,%d}' % (row['revision'], row.get('startup_enabled', False),
                row.get('raw_directory_check', False), row.get('handle_message', False),
                json.dumps(row.get('error_format', '')), row.get('filename_cache', False),
                row.get('large_header_warning', False)))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        unit = (engine / 'source/gamelib/packfile.c').read_text()
        core = (engine / 'openbor.c').read_text()
        startup = function(core, 'startup')
        # Keep the complete cache prefix. The later engine startup is outside
        # this contract, rather than supplied with success-returning mocks.
        self.assertEqual(startup.count('pak_init()'), 1)
        startup = startup[:startup.index('#if PSP')] + '\n}\n'
        shutdown = function(core, 'shutdown').splitlines(True)
        at = [i for i, line in enumerate(shutdown) if 'Release FileCaching System...' in line]
        self.assertEqual(len(at), 1)
        retirement = ''.join(shutdown[at[0]:at[0]+3])
        self.assertIn('if(startup_done) pak_term();', retirement)
        self.assertIn('Done!', retirement)
        self.assertEqual(retirement.count('pak_term()'), 1)
        names = ['pak_initialized', 'packhandle', 'packfilepointer', 'packfilesize', 'filenamelist',
                 'pakfd', 'paksize', 'pak_vfdexists', 'pak_vfdstart', 'pak_vfdsize', 'pak_vfdpos',
                 'pak_vfdreadahead', 'pak_headerstart', 'pak_headersize', 'pak_cdheader',
                 'pak_header', 'USED_FLAG', 'printFileUsageStatistics']
        declarations = []
        for name in names:
            matches = re.findall(r'(?m)^(?![ \t#/\n]|extern\b)[^\n]*\b' + name +
                                 r'\s*(?:\[[^\n]*\])?\s*(?:=[^\n]*)?;[ \t]*$', unit)
            self.assertEqual(len(matches), 1, name)
            declarations.append(matches[0])
        first = unit.index('typedef int (*OpenPackfile)')
        last = unit.index('static ClosePackfile pClosePackfile;', first) + len('static ClosePackfile pClosePackfile;')
        declarations.append(unit[first:last])
        constants = []
        for name in ('MAXPACKHANDLES', 'PACKMAGIC', 'PACKVERSION', 'CACHEBLOCKSIZE'):
            matches = re.findall(r'(?m)^#define[ \t]+' + name + r'\b[^\n]*', unit)
            self.assertEqual(len(matches), 1, name)
            constants += matches
        constants.append(re.search(r'(?ms)^#ifndef DINGOO\n#define CACHEBLOCKS.*?^#endif', unit)[0])
        functions = ['tolowerOneChar', 'fnlc', 'myfilenamecmp', 'slashback', 'slashfwd', 'casesearch',
                     'getFreeHandle', 'packfile_mode', 'isRawData', 'openpackfile', 'openPackfile',
                     'update_filecache_vfd', 'pak_header_entry', 'makefilenamecache', 'freefilenamecache',
                     'openreadaheadpackfile', 'openPackfileCached', 'readpackfile', 'readPackfile',
                     'pak_isvalidhandle', 'pak_rawread', 'readpackfileblocking', 'readPackfileCached',
                     'closepackfile', 'closePackfile', 'closePackfileCached', 'seekpackfile',
                     'seekPackfile', 'seekPackfileCached', 'pak_getsectors', 'pak_term', 'pak_init']
        bodies = '\n'.join(function(unit, name) for name in functions)
        program = (FIXTURE.parent / 'early_packfile_backend.c').read_text()
        replacements = dict(ROWS=',\n'.join(entries), GLOBALS='\n'.join(declarations),
            CONSTANTS='\n'.join(constants), FUNCTIONS=bodies, STARTUP=startup, RETIRE=retirement,
            READ_LE=function((engine / 'source/utils.c').read_text(), 'readlsb32'),
            LOOKUP=(FIXTURE.parent / 'early_packfile_lookup.c').read_text() if lookup else '',
            HEADER=(FIXTURE.parent / 'early_packfile_header.c').read_text() if header else '')
        for key, value in replacements.items():
            program = program.replace('@'+key+'@', value)
        self.assertNotRegex(program, r'@[A-Z_]+@')
        with tempfile.TemporaryDirectory(prefix='early-pack-backend-') as name:
            work = Path(name)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(bind_named_allocation_support(program, engine))
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DLIBRETRO=1',
                     '-DDARWIN=1' if sys.platform == 'darwin' else '-DLINUX=1',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-I', str(engine / 'source/scriptlib'), '-I', str(engine / 'source/gamelib'),
                     '-I', str(ROOT / 'src/port/libretro')]
            if lookup:
                flags.append('-DTEST_CACHED_NAMES=1')
            if header:
                flags.append('-DTEST_LARGE_HEADERS=1')
            obj = work / 'list.o'
            build = subprocess.run(compiler + flags + ['-c', str(engine / 'source/scriptlib/List.c'),
                                   '-o', str(obj)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(compiler + flags + ['-Wall', '-Wextra', '-Werror',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-but-set-variable',
                '-Wno-sign-compare', '-Wno-error=deprecated-declarations', str(source), str(obj),
                *links, '-o', str(binary)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True,
                                 timeout=30, env=sanitizer_environment())
            observation = ('OBOR_PACK_HEADER_OBSERVATIONS' if header else
                           'OBOR_PACK_LOOKUP_OBSERVATIONS' if lookup else 'OBOR_PACK_BACKEND_OBSERVATIONS')
            if os.environ.get(observation):
                Path(os.environ[observation]).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), scope=fixture['scope'],
                    retirement='TemporaryDirectory removes authored PAK,loose data,objects,source and binary'),
                    indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_pack_header=1' if header else
                          'early_pack_lookup=1' if lookup else 'early_pack_backend=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
