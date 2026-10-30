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

from contract_fixtures import contract_profiles, load_contract_fixture
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

    def _exercise(self, fixture, lookup=False):
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
            entries.append('{%d,%d,%d,%d,%s,%d}' % (row['revision'], row.get('startup_enabled', False),
                row.get('raw_directory_check', False), row.get('handle_message', False),
                json.dumps(row.get('error_format', '')), row.get('filename_cache', False)))
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
            LOOKUP=(FIXTURE.parent / 'early_packfile_lookup.c').read_text() if lookup else '')
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
            observation = 'OBOR_PACK_LOOKUP_OBSERVATIONS' if lookup else 'OBOR_PACK_BACKEND_OBSERVATIONS'
            if os.environ.get(observation):
                Path(os.environ[observation]).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), scope=fixture['scope'],
                    retirement='TemporaryDirectory removes authored PAK,loose data,objects,source and binary'),
                    indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_pack_lookup=1' if lookup else 'early_pack_backend=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
