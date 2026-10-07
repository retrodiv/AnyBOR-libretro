"""Cold fixed-capacity snapshots must include decoded resource growth.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import importlib.util
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
import zlib

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent if (HERE.parent / 'src').is_dir() else HERE.parents[2] / 'AnyBOR-libretro'
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', DEFAULT_SOURCE))
CORE = Path(os.environ.get('OBOR_TEST_CORE', SOURCE / '.build/dist/linux-x86_64/anybor_libretro.so'))


@unittest.skipUnless(CORE.is_file() and os.name == 'posix', 'requires a built Linux core')
class LoadingCapacityTests(unittest.TestCase):
    def test_compressed_background_grows_beyond_stored_pack_bytes(self):
        spec = importlib.util.spec_from_file_location('capacity_fixture', SOURCE / 'tools/make_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory(prefix='anybor-capacity-') as temporary:
            work = Path(temporary)
            host = work / 'host'
            subprocess.run(['cc', '-O2', '-pthread', '-I', str(SOURCE / 'src/third_party'),
                            '-I', str(SOURCE / 'src/glue'),
                            str(SOURCE / 'tests/host/libretro_host.c'), '-ldl', '-o', str(host)],
                           check=True, timeout=60)
            members = fixture.files()
            # Original authored pixels: both the background and panel expand
            # in memory, while the archive stores a short compressed PNG.
            width, height = 14336, 2048
            rows = (b'\0' + bytes((2, 3)) * (width // 2)) * height
            palette = bytes((0, 0, 0, 80, 230, 140, 240, 240, 240, 25, 45, 80)) + bytes(252 * 3)
            members['data/bgs/room.png'] = (b'\x89PNG\r\n\x1a\n' +
                fixture.chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0)) +
                fixture.chunk(b'PLTE', palette) + fixture.chunk(b'IDAT', zlib.compress(rows)) +
                fixture.chunk(b'IEND', b''))
            members['data/unused.bin'] = bytes(18 << 20)
            pak = work / 'authored.pak'
            fixture.write_pak(pak, members)
            system = work / 'system'
            system.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith('OBOR_')}
            env.update(OBOR_ENGINE='6391', OBOR_SKIP_LOADING='1', OBOR_FIXED_STATE_FRONTEND='1',
                       OBOR_STATE_CHECK='1', OBOR_STATE_CHECK_START='900', OBOR_STATE_CHECK_EVERY='60',
                       OBOR_INPUT='180-360:start,400-403:attack,600-603:start,900-903:attack',
                       OBOR_RAREWIND='1100,4', OBOR_RAREWIND_START='1092', OBOR_RAREWIND_BUFFERS='4')
            result = subprocess.run([str(host), str(CORE), str(pak), str(system), '1200'],
                                    env=env, capture_output=True, text=True, timeout=90)
            log = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, log)
            heaps = [int(size) for size in re.findall(r'state_contract[^\n]* heap=(\d+)', log)]
            self.assertTrue(heaps and max(heaps) > pak.stat().st_size, log)
            print('Authored compressed resources: PACK=%d heap=%d' %
                  (pak.stat().st_size, max(heaps)))
            self.assertIn('frames=1200', log)
            self.assertEqual(len(re.findall(r' MATCH\b', log)), 3, log)
            self.assertIn('cwd_restored=1', log)


if __name__ == '__main__':
    unittest.main()
