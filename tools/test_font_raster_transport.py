"""Check bounded raster framing and fresh per-profile probe execution.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import font_raster_probe as probe


KEY = 'RASTER glyph 0 0 0 1 1 1 0 0'


class RasterTransportTests(unittest.TestCase):
    def test_binary_payload_preserves_whitespace_and_nul_bytes(self):
        raw = b'\x00\n \xff'
        binary = KEY.encode() + b' 4\n' + raw + b'\nWIDTHS 0 0 0 1 1 2,3,\n'
        old = KEY.encode() + b' ' + raw.hex().encode() + b'\nWIDTHS 0 0 0 1 1 2,3,\n'
        wanted = {KEY: {'bytes': 4, 'sha256': hashlib.sha256(raw).hexdigest()},
                  'WIDTHS 0 0 0 1 1': {'widths': [2, 3]}}
        self.assertEqual(probe.read_rows(io.BytesIO(binary), binary_pixels=True), wanted)
        self.assertEqual(probe.read_rows(io.BytesIO(old)), wanted)

    def test_refuses_unfinished_oversized_duplicate_and_wrong_profile_records(self):
        prefix = KEY.encode() + b' '
        invalid = [b'', prefix+b'1', prefix+b'1921\n', prefix+b'-1\n', prefix+b'2\nx',
                   prefix+b'1\nx!', b'UNEXPECTED 1\n', b'WIDTHS x 1,,\n',
                   prefix+b'1\nx\n'+prefix+b'1\nx\n', b'x'*65537+b'\n']
        for raw in invalid:
            with self.subTest(raw=raw[:60]), self.assertRaises(RuntimeError):
                probe.read_rows(io.BytesIO(raw), binary_pixels=True)
        for raw in (b'PROFILE 2\nWIDTHS p 1,\n', b'WIDTHS p 1,\n'):
            with self.assertRaises(RuntimeError):
                probe.read_rows(io.BytesIO(raw), profile=1)

    def test_profile_inventory_is_explicit_bounded_and_unique(self):
        for values in ([], [True], [0], [-1], [2**32], [1,1], ['1'], list(range(1,130))):
            with self.subTest(values=str(values)[:50]), self.assertRaises(ValueError):
                probe.profile_revisions(values)
        self.assertEqual(probe.profile_revisions([2,1]), (2,1))
        with self.assertRaises(ValueError):
            probe.run_profiles('/missing', '/missing', [1,2,3], retain_rows=True)
        for value in (True,-1,32,1):
            with self.subTest(inset=value), self.assertRaises(ValueError):
                probe.program('/missing',inset=value)

    def test_batch_compiles_once_and_observes_distinct_fresh_processes(self):
        generated = []
        def compile_stub(engine, port, work, code, cc, sanitizers, exception):
            generated.append(work)
            program = '#!'+sys.executable+'\nimport sys\n'
            program += ('n=int(sys.argv[1]);out=sys.stdout.buffer\n'
                        'out.write(("PROFILE %d\\n"%n).encode())\n'
                        'out.write('+repr(KEY.encode()+b' 3\n')+'+bytes([n,10,0])+b"\\n")\n')
            target=work/'probe';target.write_text(program);target.chmod(0o700)
            return []
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(probe, 'program', return_value='authored transport provider'), \
             patch.object(probe, 'compile_probe', side_effect=compile_stub) as compiler, \
             patch.object(probe, 'source_hashes', return_value={'fixture':'stable'}):
            result=probe.run_profiles(directory,directory,[1,2])
        self.assertEqual(compiler.call_count,1)
        self.assertEqual(list(result['profiles']),['1','2'])
        for value in (1,2):
            expected={KEY:{'bytes':3,'sha256':hashlib.sha256(bytes([value,10,0])).hexdigest()}}
            self.assertEqual(result['profiles'][str(value)]['matrix_sha256'],probe.matrix_digest(expected))
            self.assertEqual(result['profiles'][str(value)]['observations'],1)
        self.assertTrue(all(not path.exists() for path in generated))

    def test_wrong_native_marker_stops_and_reaps_the_child(self):
        children=[];real_popen=subprocess.Popen
        def compile_stub(engine, port, work, code, cc, sanitizers, exception):
            target=work/'probe'
            target.write_text('#!'+sys.executable+'\nimport time\nprint("PROFILE 9",flush=True)\ntime.sleep(30)\n')
            target.chmod(0o700);return []
        def observe(*args,**kwargs):
            child=real_popen(*args,**kwargs);children.append(child);return child
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(probe,'program',return_value='authored marker provider'), \
             patch.object(probe,'compile_probe',side_effect=compile_stub), \
             patch.object(probe,'source_hashes',return_value={}), \
             patch.object(probe.subprocess,'Popen',side_effect=observe):
            with self.assertRaisesRegex(RuntimeError,'different native profile'):
                probe.run_profiles(directory,directory,[1])
        self.assertEqual(len(children),1)
        self.assertIsNotNone(children[0].poll())


if __name__ == '__main__':
    unittest.main()
