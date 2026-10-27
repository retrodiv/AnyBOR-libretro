"""Check legacy bitmap rows stay inside each profile's requested rectangle.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from historical_image_rows import render_image_rows
from make_fixture import png, indexed_bmp
from native_sanitizers import sanitizer_environment
from test_bitmap_dimensions import SOURCE, fixture_palette, native_context, compile_image_units, profile_program
from test_color_blends import compile_checked

FIXTURE = Path(__file__).parent / 'fixtures/image-row-contracts.json'


class ImageRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_contract_fixture(FIXTURE)
        cls.pin = json.loads((SOURCE/'src/pin.json').read_text())
        temporary = tempfile.TemporaryDirectory(prefix='anybor-image-rows-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        image, bitmap = work/'image.png', work/'image.bmp'
        image.write_bytes(png(4, 3, lambda x, y: (x+2*y)%3+1))
        width, height = cls.fixture['source_size']
        bitmap.write_bytes(indexed_bmp(width, height, lambda x, y: (x+2*y)%3+1))
        cases = [dict(path=str(image), width=4, height=3, expected_width=4, expected_height=3)]
        rows = [dict(path=str(bitmap), width=width, height=height, target_width=w, target_height=h)
                for w, h in cls.fixture['targets']]
        cls.executables = {}
        for engine, context in cls.fixture['engines'].items():
            compiler, flags, links = native_context(engine)
            objects = compile_image_units(engine, compiler, flags, work, include_loader=False)
            options = {key: context[key] for key in ('resource_hooks', 'magic_field',
                                                    'allocation_services', 'screen_format_variable')}
            code = render_image_rows(image_source=str(SOURCE/'src/engines'/engine/'source/gamelib/loadimg.c'),
                revision=int(engine), cases=cases, row_cases=rows,
                palette=fixture_palette(context['palette_bytes']), **options)
            source = work/(engine+'.c')
            source.write_text(profile_program(code))
            executable = source.with_suffix('')
            compile_checked(compiler+flags+[str(source), *objects, *links, '-o', str(executable)])
            cls.executables[engine] = executable

    def check_context(self, engine, revision):
        output = subprocess.check_output([str(self.executables[engine]), str(revision)],
                                        text=True, timeout=15, env=sanitizer_environment())
        self.assertEqual(json.loads(output), dict(status='PASS', cases=2+2*len(self.fixture['targets'])))

    def test_every_registered_engine_has_an_explicit_format_context(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            self.assertIn(profile['engine'], self.fixture['engines'] | self.fixture['exclusions'])
        for engine in self.fixture['exclusions']:
            source = (SOURCE/'src/engines'/engine/'source/gamelib/loadimg.c').read_text()
            self.assertNotRegex(source, r'\breadbmp\s*\(')

    def test_each_registered_legacy_bitmap_profile(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if profile['engine'] in self.fixture['engines']:
                with self.subTest(profile=profile['build']):
                    self.check_context(profile['engine'], int(profile.get('revision', profile['build'])))

    def test_each_declared_historical_context(self):
        for row in self.fixture['contexts']:
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row['engine'], row['revision'])


if __name__ == '__main__':
    unittest.main()
