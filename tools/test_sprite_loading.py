"""Observe native image-to-sprite metadata and encoded pixels by profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from historical_sprite_loading import render_sprite_loading
from make_fixture import png
from native_sanitizers import sanitizer_environment
from test_bitmap_dimensions import SOURCE, fixture_palette, native_context, profile_program
from test_color_blends import compile_checked

FIXTURE = Path(__file__).parent / 'fixtures/sprite-loading-contracts.json'


class SpriteLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_contract_fixture(FIXTURE)
        cls.pin = json.loads((SOURCE/'src/pin.json').read_text())
        cls.contexts = {(row['engine'], row['revision']): row for row in cls.fixture['contexts']}
        temporary = tempfile.TemporaryDirectory(prefix='anybor-sprite-loading-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        images = []
        for entry in cls.fixture['images']:
            path = work/(entry['id']+'.png')
            def sample(x, y):
                visible = any(left <= x < right and top <= y < bottom
                              for left, top, right, bottom in entry['regions'])
                return (x+2*y)%3+1 if visible else 0
            path.write_bytes(png(entry['width'], entry['height'], sample))
            images.append(path)
        control = work/'dimension-control.png'
        control.write_bytes(png(4, 3, lambda x,y: (x+2*y)%3+1))
        cls.executables = {}
        for engine, context in cls.fixture['engines'].items():
            compiler, flags, links = native_context(engine)
            root = SOURCE/'src/engines'/engine
            flags += ['-DOV_EXCLUDE_STATIC_CALLBACKS']
            flags += ['-I'+str(root/'source'/name) for name in (
                'adpcmlib', 'gfxlib', 'preprocessorlib', 'ramlib', 'randlib', 'scriptlib')]
            objects = []
            units = [root/'openbor.c'] + [root/'source/gamelib'/(name+'.c')
                for name in ('loadimg', 'bitmap', 'sprite', 'pixelformat', 'palette')]
            for index, unit in enumerate(units):
                target = work/(engine+'-unit-'+str(index)+'.o')
                context_flags = (['-Wno-error', '-Wno-unused-but-set-variable',
                                  '-finstrument-functions'] if index == 0 else
                                 ['-O1'] if unit.stem == 'pixelformat' else
                                 ['-finstrument-functions'])
                compile_checked(compiler+flags+context_flags+['-c',str(unit),'-o',str(target)])
                objects.append(str(target))
            caps = {row['axis_limit'] for row in cls.fixture['contexts'] if row['engine']==engine}
            for cap in sorted(caps):
                cases = [entry['expected'][str(cap)] | dict(path=str(path))
                         for entry,path in zip(cls.fixture['images'], images)]
                code = render_sprite_loading(revision=int(engine), sprite_cases=cases,
                    cases=[dict(path=str(control),width=4,height=3,expected_width=4,expected_height=3)],
                    palette=fixture_palette(context['palette_bytes']), resource_hooks=True)
                source = work/(engine+'-'+str(cap)+'.c')
                source.write_text(profile_program(code))
                executable = source.with_suffix('')
                compile_checked(compiler+flags+[str(source),*objects,*links,'-o',str(executable)])
                cls.executables[engine,cap] = executable

    def check_context(self, engine, revision):
        row = self.contexts[engine,revision]
        output = subprocess.check_output([str(self.executables[engine,row['axis_limit']]),str(revision)],
            text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(output),dict(status='PASS',cases=2+8*len(self.fixture['images'])))

    def test_registered_profiles_have_own_source_contexts(self):
        self.assertEqual(len(self.contexts),len(self.fixture['contexts']))
        for row in self.fixture['contexts']:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_function_sha256'],r'^[0-9a-f]{64}$')
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if profile['engine'] in self.fixture['engines']:
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)

    def test_each_registered_historical_profile(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if profile['engine'] in self.fixture['engines']:
                with self.subTest(profile=profile['build']):
                    self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_each_own_source_context(self):
        for row in self.fixture['contexts']:
            with self.subTest(engine=row['engine'],revision=row['revision']):
                self.check_context(row['engine'],row['revision'])


if __name__=='__main__':
    unittest.main()
