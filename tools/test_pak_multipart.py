"""Exercise PACK 1.1 volume metadata and the native read-only backend.

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

ROOT = Path(__file__).resolve().parents[1]
GLUE = ROOT / 'src/glue'
PORT = ROOT / 'src/port/libretro'


class PakMultipartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='anybor-pak-volumes-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        source = cls.root / 'probe.c'
        source.write_text(r'''
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "anybor_pak_volumes.h"
#include "anybor_pak_validate.h"
#include "anybor_video_config.h"
#include "anybor_pak_multipart.h"
int main(int argc, char **argv) {
    assert(argc >= 2);
    obor_pak_volumes pak;
    const char *error = obor_pak_volumes_open(&pak, argv[1]);
    const char *validation = obor_pak_validate(argv[1]);
    assert((error != NULL) == (validation != NULL));
    if(error) { puts("invalid"); return 0; }
    if(argc == 3 && !strcmp(argv[2],"--video")) {
        int width=0,height=0;
        obor_pak_volumes_close(&pak);
        assert(obor_video_resolution(argv[1],&width,&height));
        printf("%d %d\n",width,height);
        return 0;
    }
    if(argc == 2) { printf("%u %u\n",pak.count,pak.entries); obor_pak_volumes_close(&pak); return 0; }
    obor_pak_volumes_close(&pak);
    assert(obor_multipart_init(argv[1]) == 1);
    char alias[4096];
    assert(strlen(argv[1]) < sizeof(alias));
    for(size_t i=0;i<=strlen(argv[1]);++i) {
        unsigned char c=(unsigned char)argv[1][i];
        alias[i]=c=='/'?'\\':c>='a'&&c<='z'?(char)(c-'a'+'A'):(char)c;
    }
    assert(obor_multipart_init(alias) == 1);
    assert(obor_multipart_init("different-container.pak") == -1);
    if(!strcmp(argv[2],"--stream")) {
        int h=obor_multipart_open("data/pattern");
        assert(h>=0);
        unsigned char *buffer=(unsigned char *)malloc(65537);
        assert(buffer);
        const int requests[]={1,3,17,65535,65536,65537,5};
        unsigned position=0,call=0;
        while(position<300003) {
            int read_bytes=obor_multipart_read(h,buffer,requests[call++%7]);
            assert(read_bytes>0);
            for(int i=0;i<read_bytes;++i) assert(buffer[i]==((position+(unsigned)i)*7)%251);
            position+=(unsigned)read_bytes;
        }
        assert(position==300003 && obor_multipart_read(h,buffer,1)==0);
        const int offsets[]={31,65531,131073,299999,0};
        for(unsigned n=0;n<sizeof(offsets)/sizeof(offsets[0]);++n) {
            assert(obor_multipart_seek(h,offsets[n],SEEK_SET)==offsets[n]);
            int read_bytes=obor_multipart_read(h,buffer,19);
            assert(read_bytes==(offsets[n]==299999?4:19));
            for(int i=0;i<read_bytes;++i) assert(buffer[i]==((unsigned)(offsets[n]+i)*7)%251);
        }
        assert(obor_multipart_read(h,NULL,0)==0);
        assert(obor_multipart_read(h,buffer,-1)==-1);
        assert(obor_multipart_close(h)==0);
        obor_multipart_term(); free(buffer); puts("stream-ok"); return 0;
    }
    int h = obor_multipart_open(argv[2]);
    assert(h >= 0);
    int second = obor_multipart_open(argv[2]);
    assert(second >= 0 && second != h);
    char data[128] = {0};
    int bytes = obor_multipart_read(h,data,127);
    assert(bytes >= 0);
    fwrite(data,1,bytes,stdout); putchar('\n');
    assert(obor_multipart_read(h,data,127) == 0);
    assert(obor_multipart_read(second,data,1) == 1);
    assert(obor_multipart_seek(h,0,SEEK_SET) == 0);
    assert(obor_multipart_read(h,data,1) == 1);
    assert(obor_multipart_seek(h,INT_MIN,SEEK_CUR) == 0);
    assert(obor_multipart_seek(h,INT_MAX,SEEK_END) == bytes);
    assert(obor_multipart_seek(h,0,12345) == -1);
    assert(obor_multipart_close(h) == 0);
    assert(obor_multipart_read(h,data,1) == -1);
    if(argc > 3) {
        assert(obor_multipart_seek(second,1,SEEK_SET) == 1);
        obor_multipart_rebind(argv[3]);
        memset(data,0,sizeof(data));
        int rebound = obor_multipart_read(second,data,127);
        assert(rebound == bytes - 1);
        printf("rebound=%s\n",data);
    }
    obor_multipart_closeall();
    assert(obor_multipart_read(second,data,1) == -1);
    for(int i=0;i<8;++i) assert(obor_multipart_open(argv[2]) >= 0);
    assert(obor_multipart_open(argv[2]) == -1);
    obor_multipart_term();
    assert(!obor_multipart_active());
    assert(obor_multipart_init(argv[1]) == 1);
    obor_multipart_term();
    return 0;
}
''')
        cls.binary = cls.root / 'probe'
        subprocess.run([*shlex.split(os.environ.get('HOST_CC', 'cc')), '-std=c11',
            '-D_POSIX_C_SOURCE=200809L', '-D_FILE_OFFSET_BITS=64', '-DOBOR_ENGINE_BUILD=6391',
            '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-g', '-fsanitize=address,undefined',
            '-I', str(GLUE), '-I', str(PORT), str(source),
            str(PORT / 'anybor_pak_multipart.c'), '-o', str(cls.binary)], check=True, timeout=60)

    def volume(self, path, members, *, following=0, offset=16, version=0x10100):
        with path.open('wb') as stream:
            stream.write(b'PACK' + struct.pack('<III', version, following, 0))
            stream.seek(offset)
            entries = []
            for name, data in members:
                entries.append((name.encode() + b'\0', stream.tell(), len(data)))
                stream.write(data)
            directory = stream.tell()
            for name, start, size in entries:
                stream.write(struct.pack('<III', len(name) + 12, start, size) + name)
            stream.write(struct.pack('<I', directory))

    def probe(self, path, *args):
        return subprocess.run([str(self.binary), str(path), *args], capture_output=True,
            text=True, check=True, timeout=10).stdout

    def test_volume_reads_case_slashes_precedence_positions_and_reset(self):
        path = self.root / 'multiple.pak'
        self.volume(path, [('data/first', b'first'), ('data/alias', b'base')], following=1)
        self.volume(Path(str(path) + '.001'), [('data/second', b'second'), ('DATA\\ALIAS', b'companion')])
        self.assertEqual(self.probe(path), '2 4\n')
        for name, expected in [('DATA\\FIRST', 'first'), ('data/second', 'second'), ('data/alias', 'base')]:
            self.assertEqual(self.probe(path, name), expected + '\n')

    def test_offsets_on_both_sides_of_int_max(self):
        for offset in ((1 << 31) - 32, (1 << 31) + 32, (1 << 32) - 256):
            path = self.root / 'large.pak'
            self.volume(path, [('data/high', b'offset')], offset=offset)
            self.assertEqual(self.probe(path, 'data/high'), 'offset\n')

    def test_current_session_volume_paths_replace_restored_paths(self):
        old = self.root / 'old-path.pak'
        current = self.root / 'current-path.pak'
        self.volume(old, [('data/file', b'first')])
        self.volume(current, [('data/file', b'other')])
        self.assertEqual(self.probe(old, 'data/file', str(current)), 'first\nrebound=ther\n')

    def test_video_binding_across_volumes_and_large_offsets(self):
        path = self.root / 'video.pak'
        companion = Path(str(path) + '.001')
        self.volume(path, [('data/video.txt', b'video 640x480\n')], following=1)
        for offset in (16, (1 << 31) + 64):
            self.volume(companion, [('DATA\\VIDEOPC.TXT', b'video 480x360\n')], offset=offset)
            self.assertEqual(self.probe(path, '--video'), '480 360\n')

    def test_streaming_small_and_large_reads_seeks_and_cache_boundaries(self):
        path = self.root / 'stream.pak'
        payload = bytes((i * 7) % 251 for i in range(300003))
        for offset in (16, (1 << 31) + 64):
            self.volume(path, [('data/pattern', payload)], offset=offset)
            self.assertEqual(self.probe(path, '--stream'), 'stream-ok\n')

    def test_missing_inconsistent_and_truncated_companions(self):
        path = self.root / 'incomplete.pak'
        companion = Path(str(path) + '.001')
        self.volume(path, [('data/first', b'first')], following=1)
        self.assertEqual(self.probe(path), 'invalid\n')
        for kwargs in ({'following': 1}, {'version': 0}, {}):
            self.volume(companion, [('data/second', b'second')], **kwargs)
            if not kwargs:
                with companion.open('r+b') as stream:
                    stream.seek(-4, 2)
                    stream.write(struct.pack('<I', 1))
            self.assertEqual(self.probe(path), 'invalid\n')
        self.volume(path, [], following=16)
        self.assertEqual(self.probe(path), 'invalid\n')

    def test_corrupt_records_and_protected_signatures_refused(self):
        path = self.root / 'bad.pak'
        for field, value in ((0, 0xffffffff), (4, 0), (8, 0xffffffff)):
            self.volume(path, [('data/file', b'data')])
            with path.open('r+b') as stream:
                stream.seek(-4, 2)
                directory = struct.unpack('<I', stream.read(4))[0]
                stream.seek(directory + field)
                stream.write(struct.pack('<I', value))
            self.assertEqual(self.probe(path), 'invalid\n')
        path.write_bytes(b'SPAK' + bytes(32))
        self.assertEqual(self.probe(path), 'invalid\n')


if __name__ == '__main__':
    unittest.main()
