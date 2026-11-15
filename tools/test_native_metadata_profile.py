"""Verify native capability detection through the engine's bound root metadata.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

GLUE = Path(os.environ.get('OBOR_TEST_GLUE', Path(__file__).resolve().parents[1] / 'src/glue'))


class NativeMetadataProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='anybor-native-metadata-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        source = cls.root / 'probe.cpp'
        source.write_text(r'''
#include <stdio.h>
#include <string.h>
#define obor_detection_expired original_detection_expired
#include "anybor_detection_clock.h"
#undef obor_detection_expired
static bool forced_expiry;
static bool obor_detection_expired(uint64_t started) {
    return forced_expiry || original_detection_expired(started);
}
#include "anybor_native_metadata.h"
int main(int argc,char **argv) {
    if(argc!=2 && argc!=3)return 2;
    forced_expiry=argc==3;
    printf("%u\n",obor_native_metadata_features(argv[1]));
    return 0;
}
''')
        cls.binary = cls.root / 'probe'
        subprocess.run([*shlex.split(os.environ.get('HOST_CXX', 'c++')), '-std=c++11',
            '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-g',
            '-fsanitize=address,undefined', '-I', str(GLUE), str(source), '-o', str(cls.binary)],
            check=True, timeout=60)

    def pak(self, members, offset=8):
        path = self.root / 'synthetic.pak'
        with path.open('wb') as stream:
            stream.write(b'PACK' + bytes(4))
            stream.seek(offset)
            entries = []
            for name, payload in members:
                if isinstance(payload, str):
                    payload = payload.encode()
                entries.append((name.encode() + b'\0', stream.tell(), len(payload)))
                stream.write(payload)
            directory = stream.tell()
            for name, start, size in entries:
                stream.write(struct.pack('<III', len(name) + 12, start, size) + name)
            stream.write(struct.pack('<I', directory))
        return path

    def detect(self, members, expected, *, offset=8, expired=False):
        path = self.pak(members, offset)
        result = subprocess.run([str(self.binary), str(path), *(['expired'] if expired else [])],
            capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(result.stdout, str(expected) + '\n')
        return path

    def test_exclusive_native_directives_and_adjacent_common_commands(self):
        for command in ('hallfame_difficulties difficulty Easy Hard', 'hallfame_initials ABC',
                        'hallfame_times 30 6 6', 'HALLFAME_TIMES 0'):
            with self.subTest(command=command):
                self.detect([('data/levels.txt', command + '\r\n')], 4)
        for text in ('set Example\nfile data/level.txt\n', 'hallfame 1\n', 'hallfame_difficulty_credits 1\n',
                     'hallfame_times\n', 'hallfame_times # absent\n'):
            with self.subTest(text=text):
                self.detect([('data/levels.txt', text)], 0)

    def test_comments_strings_unused_members_and_script_shadows_are_not_invocations(self):
        members = [('data/levels.txt', '# hallfame_times 30\n"hallfame_times" 30\n'
                    'name "hallfame_times 30"\nscript data/scripts/main.c\n'),
                   ('data/models.txt', 'hallfame_times 30\n'),
                   ('data/unused.txt', 'hallfame_times 30\n'),
                   ('data/scripts/main.c', 'void hallfame_times(int n) {}\nvoid main(){hallfame_times(30);}\n')]
        self.detect(members, 0)

    def test_video_precedence_and_last_levels_binding(self):
        positive = 'hallfame_times 30 6 6\n'
        cases = [
            ([('data/video.txt', 'levels custom.txt\n'), ('data/custom.txt', positive)], 4),
            ([('data/video.txt', 'levels missing.txt\n'), ('data/levels.txt', positive)], 0),
            ([('data/video.txt', 'levels custom.txt\n'), ('data/custom.txt', 'set Plain\n'), ('data/levels.txt', positive)], 0),
            ([('data/video.txt', 'levels old.txt\nlevels custom.txt\n'), ('data/old.txt', positive), ('data/custom.txt', 'set Plain\n')], 0),
            ([('data/video.txt', 'levels old.txt\nlevels custom.txt\n'), ('data/old.txt', ''), ('data/custom.txt', positive)], 4),
            ([('data/video.txt', 'levels missing.txt\n'), ('data/videopc.txt', 'levels custom.txt\n'), ('data/custom.txt', positive)], 4),
            ([('data/video.txt', 'levels custom.txt\n'), ('data/videopc.txt', 'video 0\n'), ('data/custom.txt', positive)], 0),
        ]
        for members, expected in cases:
            with self.subTest(members=members):
                self.detect(members, expected)

    def test_case_slash_binding_duplicates_and_alias_refusal(self):
        self.detect([('DATA\\VIDEOPC.TXT', 'levels MODES\\ORDER.TXT\n'),
                     ('DATA\\MODES\\ORDER.TXT', 'hallfame_initials ABC\n')], 4)
        for duplicate in ('DATA/LEVELS.TXT', 'data\\levels.txt', 'data/./levels.txt', '/data/levels.txt'):
            with self.subTest(duplicate=duplicate):
                self.detect([('data/levels.txt', 'hallfame_times 30\n'), (duplicate, 'set Other\n')], 0)
        self.detect([('data/video.txt', ''), ('DATA\\VIDEO.TXT', ''),
                     ('data/levels.txt', 'hallfame_times 30\n')], 0)
        self.detect([('data/video.txt', 'levels ../levels.txt\n'), ('data/levels.txt', 'hallfame_times 30\n')], 0)

    def test_complete_metadata_scan_is_independent_of_unrelated_model_script_limits(self):
        members = [('data/levels.txt', 'hallfame_times 30\n')]
        members.extend(('data/models/%04d.txt' % i, 'name Example\n') for i in range(2000))
        self.detect(members, 4)
        self.detect([('data/levels.txt', 'hallfame_times 30\n')], 4, offset=(1 << 31) + 32)

    def test_incomplete_lines_members_and_deadlines_refuse_partial_positive(self):
        positive = 'hallfame_times 30\n'
        for tail in ('name "unterminated\n', 'name ' + 'x' * 1024 + '\n', '\0'):
            with self.subTest(tail=tail[:40]):
                self.detect([('data/levels.txt', positive + tail)], 0)
        self.detect([('data/video.txt', 'x' * 65537), ('data/levels.txt', positive)], 0)
        self.detect([('data/levels.txt', positive + '#' * (2 << 20))], 0)
        self.detect([('data/levels.txt', positive)], 0, expired=True)

    def test_complete_multipart_binding_and_missing_volume_refusal(self):
        path = self.root / 'multipart.pak'
        def volume(target, members, companions):
            with target.open('wb') as stream:
                stream.write(b'PACK' + struct.pack('<III', 0x10100, companions, 0))
                entries = []
                for name, payload in members:
                    payload = payload.encode()
                    entries.append((name.encode() + b'\0', stream.tell(), len(payload)))
                    stream.write(payload)
                directory = stream.tell()
                for name, start, size in entries:
                    stream.write(struct.pack('<III', len(name) + 12, start, size) + name)
                stream.write(struct.pack('<I', directory))
        volume(path, [('data/video.txt', 'levels custom.txt\n')], 1)
        companion = Path(str(path) + '.001')
        volume(companion, [('data/custom.txt', 'hallfame_times 30\n')], 0)
        def result():
            return subprocess.run([str(self.binary), str(path)], capture_output=True,
                text=True, check=True, timeout=10).stdout
        self.assertEqual(result(), '4\n')
        companion.unlink()
        self.assertEqual(result(), '0\n')
        volume(companion, [('data/custom.txt', 'hallfame_times 30\n')], 1)
        self.assertEqual(result(), '0\n')
        volume(companion, [('data/custom.txt', 'hallfame_times 30\n'),
                           ('data/video.txt', 'levels custom.txt\n')], 0)
        self.assertEqual(result(), '0\n')  # ambiguous root aliases remain conservative

    def test_nonordinary_headers_and_malformed_directory_are_not_decoded(self):
        members = [('data/levels.txt', 'hallfame_times 30\n')]
        for header in (b'SPAK\0\0\0\0', b'PACK\0\1\1\0', b'BAD!\0\0\0\0'):
            with self.subTest(header=header):
                path = self.pak(members)
                with path.open('r+b') as stream:
                    stream.write(header)
                result = subprocess.run([str(self.binary), str(path)], capture_output=True,
                    text=True, check=True, timeout=10)
                self.assertEqual(result.stdout, '0\n')
        path = self.pak(members)
        with path.open('r+b') as stream:
            stream.seek(-4, 2)
            directory = struct.unpack('<I', stream.read(4))[0]
            stream.seek(directory)
            stream.write(struct.pack('<I', 0xffffffff))
        result = subprocess.run([str(self.binary), str(path)], capture_output=True,
            text=True, check=True, timeout=10)
        self.assertEqual(result.stdout, '0\n')


if __name__ == '__main__':
    unittest.main()
