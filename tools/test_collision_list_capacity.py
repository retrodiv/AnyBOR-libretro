"""Check native collision pointer-table capacity and controlled allocation refusal.

The allocator records requests and supplies small real buffers. The INT_MAX
control observes only the request and clearing length, without allocating it.
Frame ownership, collision values and arena shutdown need separate controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from contract_fixtures import load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function


SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'fixtures/collision-list-capacity.json'
DECLARATION = re.compile(
    r'^s_collision_(attack|body|entity)\s*\*\*collision_alloc_\1_list\(\)', re.M)


def render(engine, code, kinds, counts, profiles):
    definitions = [function(code, 'collision_alloc_' + kind + '_list') for kind in kinds]
    stop = re.search(r'(?m)^void\s+(borShutdown|shutdown)\s*\(', code)
    if stop is None:
        raise ValueError('Native engine shutdown definition required')
    text = (HERE / 'collision_list_capacity_contract.c.in').read_text()
    replacements = {
        'COUNTS': ','.join(map(str, counts)),
        'FUNCTIONS': '\n\n'.join(definitions),
        'CHECKS': '\n    '.join('CHECK_CONSTRUCTOR(s_collision_' + kind +
            ', collision_alloc_' + kind + '_list);' for kind in kinds),
        'ENGINE': engine,
        'SHUTDOWN': stop[1],
        'PROFILES': ','.join(json.dumps(row['build']) for row in profiles),
        'REVISIONS': ','.join(str(int(row.get('revision',
            re.match(r'[0-9]+', row['build'])[0]))) for row in profiles),
    }
    for key, value in replacements.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unfilled collision constructor contract')
    return text


class CollisionListCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_contract_fixture(FIXTURE)
        cls.pin = json.loads((SOURCE / 'src/pin.json').read_text())
        temporary = tempfile.TemporaryDirectory(prefix='anybor-collision-list-')
        cls.addClassCleanup(temporary.cleanup)
        cls.work = Path(temporary.name)
        cls.programs = {}
        cls.profiles = {}
        cls.seen = {}
        for entry in cls.pin['engines']:
            engine = entry['build']
            code = (SOURCE / 'src/engines' / engine / 'openbor.c').read_text(encoding='latin1')
            kinds = DECLARATION.findall(code)
            if kinds:
                cls.seen[engine] = kinds
        if cls.seen != cls.data['families']:
            raise ValueError('Native collision-list family inventory changed')
        for engine, kinds in cls.data['families'].items():
            code = (SOURCE / 'src/engines' / engine / 'openbor.c').read_text(encoding='latin1')
            source = cls.work / (engine + '.c')
            target = source.with_suffix('')
            profiles = [row for row in cls.pin['profiles'] if row['engine'] == engine]
            if not profiles:
                raise ValueError('Collision family has no registered profiles')
            cls.profiles[engine] = profiles
            source.write_text(render(engine, code, kinds, cls.data['counts'], profiles))
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-g',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', str(source), '-o', str(target)],
                check=True, timeout=60)
            cls.programs[engine] = target

    def test_native_capacity_and_refusal_for_every_affected_profile(self):
        for engine, target in self.programs.items():
            profiles = self.profiles[engine]
            with self.subTest(engine=engine, profiles=[row['build'] for row in profiles]):
                result = subprocess.run([str(target)],
                    env=sanitizer_environment(), check=True, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                expected = ((len(self.data['counts']) + 2) *
                            len(self.data['families'][engine]) * len(profiles))
                self.assertEqual(json.loads(result.stdout), {
                    'status': 'PASS', 'engine': engine,
                    'profiles': [row['build'] for row in profiles], 'checks': expected})
                self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
