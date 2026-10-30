"""Check source-owned screenshot formats, encoded PCX bytes and PNG pixels.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_bitmap_dimensions import native_context
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-screenshots.json'


def sample(x, y, plane, pattern):
    return 193 if not pattern and x % 143 < 66 else (x*17+y*29+plane*61) & 255


def pixels(width, pixel_format, pattern, legacy):
    rows = []
    for y in range(2):
        row = bytearray()
        for x in range(width):
            if pixel_format in (0, 1):
                index = sample(x, y, 0, pattern)
                row.extend(((index*3+p)*17+3) & 255 for p in range(3))
            elif pixel_format == 2:
                color = (x*13+y*17) & 65535
                r, g, b = color & 31, (color >> 5) & 63, (color >> 11) & 31
                row.extend((r*255//31, g*255//63, b*255//31) if legacy else (r << 3, g << 2, b << 3))
            else:
                row.extend(sample(x, y, p, pattern) for p in range(3))
        rows.append(bytes(row))
    return rows


def pcx_bytes(width, pixel_format, pattern):
    header = bytearray(128)
    header[:4] = bytes((10, 5, 1, 8))
    for offset, value in ((8, width-1), (10, 1), (12, width), (14, 2),
                          (66, (width+1) & 65534), (68, pixel_format != 0), (70, width), (72, 2)):
        struct.pack_into('<H', header, offset, int(value))
    header[65] = 1 if pixel_format == 0 else 3
    output = bytearray(header)
    rgb = pixels(width, pixel_format, pattern, True)
    for y in range(2):
        for plane in range(header[65]):
            row = (bytes(sample(x, y, 0, pattern) for x in range(width))
                   if pixel_format == 0 else rgb[y][plane::3])
            x = 0
            while x < len(row):
                end = x+1
                while end < len(row) and end-x < 63 and row[end] == row[x]:
                    end += 1
                count = end-x
                if count > 1 or row[x] >= 192:
                    output.append(192 | count)
                output.append(row[x])
                x = end
            if width & 1:
                output.append(0)
    if pixel_format == 0:
        output.append(12)
        output.extend((i*17+3) & 255 for i in range(768))
    return bytes(output)


class EarlyScreenshotTests(unittest.TestCase):
    def test_screenshot_format_and_pixels(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['format'], ('pcx', 'png'))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT/'src/engines'/fixture['engine']))
        screenshot = function((engine/'source/utils.c').read_text(), 'screenshot')
        program = (FIXTURE.parent/'early_screenshots.c').read_text().replace(
            '@SCREENSHOT@', screenshot).replace('@REVISIONS@', ','.join('{%d,%d}' % (row['revision'], row['format']=='pcx') for row in rows))
        compiler, flags, links = native_context(fixture['engine'])
        flags = ['-I'+str(engine/'source/gamelib'), '-I'+str(engine/'source'), '-I'+str(engine)] + flags
        with tempfile.TemporaryDirectory(prefix='early-screenshots-') as directory:
            work = Path(directory)
            source, binary = work/'probe.c', work/'probe'
            source.write_text(program)
            command = compiler + flags + [str(source), str(engine/'source/pnglib/savepng.c'),
                                         '-o', str(binary)] + links
            build = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout+build.stderr)
            run = subprocess.run([str(binary)], cwd=work, capture_output=True, text=True,
                                 timeout=90, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout[-1500:]+run.stderr)
            by_revision = {row['revision']: row for row in rows}
            observations = []
            bound_profiles = set()
            shot_count = 0
            for line in run.stdout.splitlines():
                if line.startswith('BOUNDS '):
                    _, revision, count = line.split()
                    self.assertEqual(int(count), 6)
                    bound_profiles.add(int(revision))
                    continue
                shot_count += 1
                kind, rev, case, fmt, width, pattern, collisions, ingame, exists, name = line.split(' ', 9)
                self.assertEqual(kind, 'SHOT')
                rev, case, fmt, width, pattern, collisions, ingame, exists = map(
                    int, (rev, case, fmt, width, pattern, collisions, ingame, exists))
                oracle = by_revision[rev]
                expected_name = './ScreenShots/case-%d-%d - %04d.%s' % (
                    rev, case, min(collisions, 99), oracle['format'])
                self.assertEqual(name, expected_name)
                self.assertEqual(bool(exists), oracle['format'] == 'png' or fmt != 1)
                path = work/name
                if not exists:
                    self.assertFalse(path.exists())
                    continue
                data = path.read_bytes()
                if oracle['format'] == 'pcx':
                    self.assertEqual(data, pcx_bytes(width, fmt, pattern), (rev, case, fmt, width))
                    pixel_digest = None
                else:
                    self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                    decoded = path.with_suffix(path.suffix+'.rgb').read_bytes()
                    self.assertEqual(decoded, b''.join(pixels(width, fmt, pattern, False)), (rev, case, fmt, width))
                    pixel_digest = hashlib.sha256(decoded).hexdigest()
                observations.append(dict(revision=rev, case=case, format=fmt, width=width,
                    file_sha256=hashlib.sha256(data).hexdigest(), pixels_sha256=pixel_digest))
            self.assertEqual(shot_count, len(rows)*30)
            self.assertEqual(bound_profiles, {row['revision'] for row in rows if row['format']=='pcx'})
            if os.environ.get('OBOR_SCREENSHOT_OBSERVATIONS'):
                Path(os.environ['OBOR_SCREENSHOT_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), cases=len(rows)*30, candidate_bound_cases=len(bound_profiles)*6, compiler=compiler,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    observations=observations, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source,binary,screenshot and decoded pixel files'), indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
