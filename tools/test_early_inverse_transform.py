"""Check historical inverse geometry against source-owned native controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from historical_water_phase import water_sines
from native_c_fragments import split_macro_functions
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURES = Path(__file__).parent / 'fixtures'
GEOMETRY = ('x','y','scalex','scaley','flipx','flipy','shiftx','angle','cx','cy','ox','oy')


def validate(fixture):
    if not re.fullmatch(r'[1-9][0-9]{3,4}',fixture['engine']):
        raise ValueError('Numeric engine identifier required')
    for key in ('sources','parents'):
        rows = fixture[key]
        if not 1 <= len(rows) <= 128 or len({r['revision'] for r in rows}) != len(rows):
            raise ValueError('Unique bounded source contexts required')
        for row in rows:
            if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                    row['engine'] != fixture['engine'] or type(row['epoch']) is not int or row['epoch'] not in (0,1)):
                raise ValueError('Explicit source context and epoch required')
            if key == 'sources' and (type(row['bitmap']) is not bool or type(row['assert_line']) is not int or
                                      row['assert_line'] < 0):
                raise ValueError('Source-owned bitmap availability and diagnostic required')
            if key == 'parents' and type(row['inverse']) is not bool:
                raise ValueError('Explicit parent route required')
    if not 1 <= len(fixture['geometries']) <= 128 or not 1 <= len(fixture['triangles']) <= 16:
        raise ValueError('Bounded geometry inventory required')
    for row in fixture['geometries']:
        if (set(row) != set(GEOMETRY) or any(type(v) is not int for v in row.values()) or
                not all(-32 <= row[k] <= 32 for k in ('x','y','cx','cy','ox','oy')) or
                not 1 <= row['scalex'] <= 512 or not 1 <= row['scaley'] <= 512 or
                row['flipx'] not in (0,1) or row['flipy'] not in (0,1) or
                not -512 <= row['shiftx'] <= 512 or not 0 <= row['angle'] < 360):
            raise ValueError('Finite source geometry required')
    for row in fixture['triangles']:
        vertices = row['vertices']
        if (type(row['count']) is not int or not 1 <= row['count'] <= 4 or
                len(vertices) != row['count'] + 2 or
                any(len(v) != 4 or any(type(n) is not int for n in v) or
                    not all(-32 <= n <= 32 for n in v[:2]) or not all(0 <= n <= 1 for n in v[2:])
                    for v in vertices)):
            raise ValueError('Bounded triangle and source texture coordinates required')
    units = fixture['units'] + [fixture['colour_unit']]
    if not 1 <= len(units) <= 16 or len(set(units)) != len(units):
        raise ValueError('Unique bounded compilation units required')
    for name in units:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or path.suffix != '.c':
            raise ValueError('Relative C compilation units required')
    names = fixture['copy_functions']
    if not 1 <= len(names) <= 16 or len(set(names)) != len(names) or any(
            not re.fullmatch(r'[A-Za-z_]\w*', n) for n in names):
        raise ValueError('Bounded exact copy function inventory required')


class EarlyInverseTransformTests(unittest.TestCase):
    def test_fixture_rejects_unbounded_or_missing_contexts(self):
        import copy
        fixture = load_contract_fixture(FIXTURES/'profile-early-inverse-transform.json')
        for kind in ('duplicate','empty','epoch','scale','angle','triangle','unit','copy'):
            invalid = copy.deepcopy(fixture)
            if kind == 'duplicate': invalid['sources'].append(dict(invalid['sources'][0]))
            elif kind == 'empty': invalid['parents'] = []
            elif kind == 'epoch': invalid['sources'][0]['epoch'] = True
            elif kind == 'scale': invalid['geometries'][0]['scalex'] = 0
            elif kind == 'angle': invalid['geometries'][0]['angle'] = 360
            elif kind == 'triangle': invalid['triangles'][0]['count'] = 1000000
            elif kind == 'unit': invalid['units'][0] = '../outside.c'
            else: invalid['copy_functions'].append(invalid['copy_functions'][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError): validate(invalid)

    def test_exact_macro_split_preserves_code_and_refuses_ambiguous_inputs(self):
        source = 'int prefix;\n#define COPY(x) (x)\n#define END 1\nint first(int x){return COPY(x); }\n'
        units = split_macro_functions(source,'#define COPY','#define END',['first'])
        self.assertEqual(units,[('prefix','int prefix;\n'),
            ('first','#define COPY(x) (x)\n\n'+function(source,'first'))])
        for start,end,names in [('#define missing','#define END',['first']),
                ('#define END','#define COPY',['first']),('#define COPY','#define END',[]),
                ('#define COPY','#define END',['first','first']),
                ('#define COPY','#define END',['not a C name'])]:
            with self.subTest(start=start,end=end,names=names),self.assertRaises(ValueError):
                split_macro_functions(source,start,end,names)
        with self.assertRaises(ValueError):
            split_macro_functions(source+'\n#define COPY(y) (y)','#define COPY','#define END',['first'])

    def test_native_common_services_and_actual_sprite_parent(self):
        fixture = load_contract_fixture(FIXTURES/'profile-early-inverse-transform.json')
        validate(fixture)
        sources, parents = fixture['sources'], fixture['parents']
        self.assertTrue(set(fixture['source_boundary_controls']) <= {r['revision'] for r in sources})
        self.assertTrue(set(fixture['parent_boundary_controls']) <= {r['revision'] for r in parents})
        for p in contract_profiles(fixture, json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(p.get('revision', p['build']))
            if p['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, {r['revision'] for r in parents})
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT/'src/engines'/fixture['engine']))
        for name in fixture['units'] + [fixture['colour_unit']]:
            self.assertTrue((engine/name).resolve().is_relative_to(engine.resolve()))
        half = (FIXTURES/'early_inverse_transform.c').read_text()
        half = half.replace('@VECTORS@', 'extern const double sin_table[],cos_table[];')
        half = half.replace('int pixelbytes[]={1,1,2,3,4};', '')
        helpers = half.split('static void check(', 1)[0]
        for name in ('pixels','clear'):
            helpers = helpers.replace(function(helpers, name).removesuffix('\n'), '', 1)
        half = half.replace('uint32_t obor_profile_build;','uint32_t obor_profile_build;\nint screenformat;')
        reference = (FIXTURES/'early_inverse_reference.c').read_text().replace(
            '@MATH_BODIES@', (FIXTURES/'early_inverse_math.c').read_text())
        paired = (FIXTURES/'early_inverse_paired.c').read_text()
        paired = paired.replace('@HELPERS@', helpers).replace('@REFERENCE@', reference)
        paired = paired.replace('@PARENTS@', (FIXTURES/'early_inverse_parent.c').read_text())
        paired = paired.replace('@GEOMETRIES@', ','.join('{' + ','.join(str(g[k]) for k in GEOMETRY) + '}'
                                                       for g in fixture['geometries']))
        paired = paired.replace('@TRIANGLES@', ','.join('{' + str(g['count']) + ',{' + ','.join(
            '{' + ','.join(map(str, v)) + '}' for v in g['vertices'] + [[0,0,0,0]] * (6-len(g['vertices'])))
            + '}}' for g in fixture['triangles']))
        paired = paired.replace('@CHECKS@', '\n'.join('paired(%d,%d);' % (r['revision'],r['epoch']) for r in sources))
        paired = paired.replace('@PARENT_CHECKS@', '\n'.join('parent(%d,%d,%d);' %
            (r['revision'],r['inverse'],r['epoch']) for r in parents))
        half = half.replace('@CHECKS@', '\n'.join('check(%d,%d,%d,%d);' %
            (r['revision'],r['epoch'],r['bitmap'],r['assert_line']) for r in sources))
        water_fixture = load_contract_fixture(FIXTURES/'profile-early-water-geometry.json')
        water_rows = water_fixture['sources']
        self.assertTrue(1 <= len(water_rows) <= 128)
        self.assertEqual(len(water_rows),len({r['revision'] for r in water_rows}))
        self.assertTrue(set(water_fixture['boundary_controls']) <= {r['revision'] for r in water_rows})
        for row in water_rows:
            self.assertIs(type(row['revision']),int)
            self.assertIs(type(row['available']),bool)
            self.assertIs(type(row['plane_epoch']),int)
            self.assertTrue(0 <= row['plane_epoch'] <= 6 if row['available'] else row['plane_epoch']==-1)
        for profile in contract_profiles(water_fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine']==water_fixture['engine'] and water_fixture['range'][0]<=revision<=water_fixture['range'][1]:
                self.assertIn(revision,{r['revision'] for r in water_rows})
        paired_template = (FIXTURES/'early_inverse_paired.c').read_text()
        provider_start = paired_template.index('static unsigned char map8')
        provider_end = paired_template.index('static void paired(')
        providers = paired_template[provider_start:provider_end]
        screen_fixture = load_contract_fixture(FIXTURES/'profile-early-screen-parent.json')
        screen_rows = screen_fixture['sources']
        self.assertTrue(1 <= len(screen_rows) <= 128)
        self.assertEqual(len(screen_rows),len({r['revision'] for r in screen_rows}))
        self.assertTrue(set(screen_fixture['boundary_controls']) <= {r['revision'] for r in screen_rows})
        for row in screen_rows:
            self.assertIs(type(row['revision']),int)
            self.assertIs(type(row['water']),bool)
        for profile in contract_profiles(screen_fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine']==screen_fixture['engine'] and screen_fixture['range'][0]<=revision<=screen_fixture['range'][1]:
                self.assertIn(revision,{r['revision'] for r in screen_rows})
        water = (FIXTURES/'early_water_geometry.c').read_text()
        plain = re.findall(r'(?ms)^const s_drawmethod plainmethod\s*=\s*\{.*?^};',
                           (engine/'openbor.c').read_text())
        self.assertEqual(len(plain),1)
        for key,value in dict(HELPERS=helpers,REFERENCE=reference,PLAIN_METHOD=plain[0],
                GEOMETRIES=','.join('{' + ','.join(str(g[k]) for k in GEOMETRY) + '}' for g in fixture['geometries']),
                TRIANGLES='{{0}}',PROVIDERS=providers,
                SCREEN_PARENT=(FIXTURES/'early_screen_parent.c').read_text(),
                SCREEN_CHECKS='\n'.join('screen_parent_normal(%d,%d);' %
                    (r['revision'],r['water']) for r in screen_rows),
                WATER_MATH=(FIXTURES/'early_water_geometry_math.c').read_text(),
                WATER_CHECKS='\n'.join('water_geometry(%d,%d,%d);range_controls(%d,%d);' %
                    (r['revision'],r['available'],r['plane_epoch'],r['revision'],r['plane_epoch']>=4) for r in water_rows)).items():
            water = water.replace('@'+key+'@',value)
        queue_fixture = load_contract_fixture(FIXTURES/'profile-early-queue-flags.json')
        queue_rows = queue_fixture['sources']
        self.assertTrue(1 <= len(queue_rows) <= 128)
        self.assertEqual(len(queue_rows),len({r['revision'] for r in queue_rows}))
        self.assertTrue(set(queue_fixture['boundary_controls']) <= {r['revision'] for r in queue_rows})
        for row in queue_rows:
            self.assertIs(type(row['revision']),int)
            self.assertIs(type(row['preserve']),bool)
        for profile in contract_profiles(queue_fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine']==queue_fixture['engine'] and queue_fixture['range'][0]<=revision<=queue_fixture['range'][1]:
                self.assertIn(revision,{r['revision'] for r in queue_rows})
        source = (engine/'source/gamelib/spriteq.c').read_text()
        start = source.index(function(source,'spriteq_add_frame').rstrip('\n'))
        queue_source = source[:start] + '\n'.join(function(source,name) for name in (
            'spriteq_add_frame','spriteq_add_sprite','spriteq_add_screen'))
        queued = (FIXTURES/'early_queue_flags.c').read_text().replace('@HELPERS@',helpers)
        queued = queued.replace('@QUEUE_SOURCE@',queue_source).replace('@QUEUE_CHECKS@',
            '\n'.join('check(%d,%d);' % (r['revision'],r['preserve']) for r in queue_rows))
        compiler = shlex.split(os.environ.get('HOST_CC','cc'))
        flags = ['-std=gnu99','-O0','-g0','-UNDEBUG','-DLIBRETRO=1','-DOBOR_CONTROLLED_ASSERTIONS=1',
                 '-DOBOR_ENGINE_BUILD='+fixture['engine'],'-fcommon','-fsigned-char',
                 '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                 '-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-Wno-unused-variable',
                 '-Wno-unused-function','-Wno-unused-parameter','-Wno-unused-but-set-variable',
                 '-Wno-implicit-fallthrough','-Wno-error=sign-compare','-Wno-error=misleading-indentation',
                 '-Wno-error=deprecated-declarations']
        flags += ['-I'+str(p) for p in [engine,engine/'source',engine/'source/gamelib',
                                      ROOT/'src/port/libretro',ROOT/'src/glue']]
        colour = (engine/fixture['colour_unit']).read_text()
        units = split_macro_functions(colour,fixture['macro_start'],fixture['macro_end'],
                                      fixture['copy_functions'])
        units.append(('water-sines',water_sines(engine)))
        with tempfile.TemporaryDirectory(prefix='early-inverse-transform-') as temporary:
            work = Path(temporary); objects = []; identities = []
            for i,(label,code) in enumerate([(name,None) for name in fixture['units']] + units):
                source = engine/label if code is None else work/(label+'.c')
                if code is not None: source.write_text(code)
                obj = work/('unit%d.o'%i)
                built = subprocess.run(compiler+flags+['-c',str(source),'-o',str(obj)],
                                       capture_output=True,text=True,timeout=60)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr)
                objects.append(str(obj)); identities.append([label,hashlib.sha256(source.read_bytes()).hexdigest()])
            for label,code in [('half',half),('paired',paired),('water',water),('queue',queued)]:
                source = work/(label+'.c'); binary = work/label; source.write_text(code)
                links = [] if sys.platform=='darwin' else ['-no-pie']
                built = subprocess.run(compiler+flags+[str(source),*objects,*links,'-lm','-o',str(binary)],
                                       capture_output=True,text=True,timeout=60)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr)
                run = subprocess.run([str(binary)],capture_output=True,text=True,timeout=60,
                                     env=sanitizer_environment())
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                self.assertIn('inverse_transform_'+('halfsteps' if label=='half' else label)+'=1',run.stdout)
            # Check the literal source assertion in both build modes. Only the
            # common unit differs; the half-step control calls it directly.
            common = fixture['units'].index('source/gamelib/transform.c')
            release_obj = work/'common-release.o'
            built = subprocess.run(compiler+flags+['-DNDEBUG', '-c',
                str(engine/fixture['units'][common]), '-o', str(release_obj)],
                capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            release_objects = list(objects);release_objects[common] = str(release_obj)
            source = work/'half-release.c';source.write_text(half)
            binary = work/'half-release'
            built = subprocess.run(compiler+flags+['-DNDEBUG',str(source),
                *release_objects,*links,'-lm','-o',str(binary)],
                capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run = subprocess.run([str(binary)],capture_output=True,text=True,
                                 timeout=60,env=sanitizer_environment())
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn('inverse_transform_halfsteps=1',run.stdout)
            if os.environ.get('OBOR_INVERSE_OBSERVATIONS'):
                Path(os.environ['OBOR_INVERSE_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=compiler,sources=len(sources),parents=len(parents),screen_sources=len(screen_rows),water_sources=len(water_rows),queue_sources=len(queue_rows),units=identities,
                    geometries=len(fixture['geometries']),triangles=len(fixture['triangles']),
                    bitmap_assertions_modes=['enabled','NDEBUG'],scope=fixture['scope']),indent=2)+'\n')


if __name__ == '__main__': unittest.main()
