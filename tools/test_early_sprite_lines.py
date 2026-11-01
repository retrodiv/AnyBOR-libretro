"""Check source-owned early sprite line/rotation contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles,load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURES=Path(__file__).parent/'fixtures'


class EarlySpriteLineTests(unittest.TestCase):
    def test_native_scaled_line_pixels_and_bounds(self):
        fixture=load_contract_fixture(FIXTURES/'profile-early-sprite-lines.json')
        rows=fixture['sources'];revisions={r['revision']for r in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for p in contract_profiles(fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(p.get('revision',p['build']))
            if p['engine']==fixture['engine'] and fixture['range'][0]<=revision<=fixture['range'][1]:
                self.assertIn(revision,revisions)
        cases=fixture['cases'];packets=fixture['packets'];oracles=fixture['oracles']
        self.assertTrue(0<len(cases)<=256)
        self.assertTrue(0<len(packets)<=16)
        self.assertTrue(all(0<len(p)<=32 and p[-1]==255 and all(type(v)is int and 0<=v<=255 for v in p)for p in packets))
        for p,x,cx,scale,flip,mode in cases:
            self.assertTrue(0<=p<len(packets) and -16<=x<=16 and -8<=cx<=8)
            self.assertTrue(1<=scale<=512 and flip in (0,1) and 0<=mode<=3)
        self.assertEqual(len(oracles),3)
        for era in oracles:
            self.assertEqual(len(era),3)
            for unit in era:
                self.assertEqual(len(unit),len(cases))
                self.assertTrue(all(re.fullmatch('[0-9a-f]{576}',image)for image in unit))
        engine=Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',ROOT/'src/engines'/fixture['engine']))
        main=(FIXTURES/'early_sprite_line_main.c').read_text()
        main=main.replace('@PROTOTYPES@','\n'.join('void render_%d(int,int,int,int,int,int,int,int*,uint32_t*);'%u for u in range(3)))
        main=main.replace('@PACKETS@',','.join('{'+','.join(map(str,p))+'}'for p in packets))
        main=main.replace('@CASES@',','.join('{'+','.join(map(str,c))+'}'for c in cases))
        def words(image):return '{'+','.join('0x'+image[i:i+8]+'U'for i in range(0,len(image),8))+'}'
        values=','.join('{'+','.join('{'+','.join(words(image)for image in unit)+'}'for unit in era)+'}'for era in oracles)
        main=main.replace('@ORACLES@','static const uint32_t oracles[3][3][%d][72]={%s};'%(len(cases),values))
        main=main.replace('@CHECKS@','\n'.join('check(%d,%d);'%(r['revision'],r['epoch'])for r in rows))
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        flags=['-std=gnu11','-O0','-g','-UNDEBUG','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+fixture['engine'],
            '-fcommon','-fsigned-char','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
            '-fno-sanitize-recover=all','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror',
            '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-unused-but-set-variable',
            '-Wno-error=sign-compare','-Wno-error=misleading-indentation','-Wno-error=deprecated-declarations']
        flags+=['-I'+str(p)for p in [engine/'source/gamelib',engine/'source',engine,ROOT/'src/port/libretro',ROOT/'src/glue']]
        with tempfile.TemporaryDirectory(prefix='early-sprite-lines-')as temporary:
            work=Path(temporary);objects=[];source_hashes=[]
            for unit,(filename,pixel)in enumerate([('spritef.c','unsigned char'),('spritex8p16.c','unsigned short'),('spritex8p32.c','unsigned')]):
                renderer=engine/'source/gamelib'/filename
                args='x,cx,16,line,'+('image+row*8,table,mode?probe_mix:NULL,scale'if unit==0 else'palette,image+row*8,(mode==1||mode==3)?probe_mix:NULL,scale')
                values=dict(UNIT=str(unit),PIXEL=pixel,RENDERER=json.dumps(str(renderer)),
                    MIX_ARGS='unsigned char *table, unsigned char source, unsigned char destination'if unit==0 else pixel+' source, '+pixel+' destination',
                    MIX_UNUSED='(void)table;'if unit==0 else'',PALETTE='(i*257+31)'if unit==1 else'(i*0x010203+0x102030)',FILL='(mode>=2?37:0)',
                    CALL='(flip?scaleline_flip:scaleline)('+args+',image,72);')
                code=(FIXTURES/'early_sprite_line_unit.c').read_text()
                for key,value in values.items():code=code.replace('@'+key+'@',value)
                code=code.replace('    (void)epoch;','    (void)epoch; (void)palette; (void)table;')
                source=work/('unit%d.c'%unit);obj=source.with_suffix('.o');source.write_text(code)
                source_hashes.append(hashlib.sha256(code.encode()).hexdigest())
                built=subprocess.run(compiler+flags+['-c',str(source),'-o',str(obj)],capture_output=True,text=True,timeout=60)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr);objects.append(str(obj))
            source=work/'main.c';binary=work/'probe';source.write_text(main)
            links=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
            built=subprocess.run(compiler+flags+[str(source),*objects,*links,'-lm','-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=sanitizer_environment())
            self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn('early_sprite_lines=1',run.stdout)
            if os.environ.get('OBOR_SPRITE_LINE_OBSERVATIONS'):
                Path(os.environ['OBOR_SPRITE_LINE_OBSERVATIONS']).write_text(json.dumps(dict(compiler=compiler,contexts=len(rows),
                    cases=len(cases),stdout=run.stdout,wrapper_sha256=source_hashes,main_sha256=hashlib.sha256(main.encode()).hexdigest(),scope=fixture['scope']),indent=2)+'\n')

    def test_native_trig_vectors_and_projection_boundary(self):
        fixture=load_contract_fixture(FIXTURES/'profile-early-sprite-trig.json')
        rows=fixture['sources'];revisions={r['revision']for r in rows}
        self.assertEqual(len(rows),len(revisions));self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for p in contract_profiles(fixture,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision=int(p.get('revision',p['build']))
            if p['engine']==fixture['engine'] and fixture['range'][0]<=revision<=fixture['range'][1]:self.assertIn(revision,revisions)
        engine=Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',ROOT/'src/engines'/fixture['engine']))
        vectors=[]
        self.assertEqual(len(fixture['vectors']),3)
        for vector in fixture['vectors']:
            self.assertEqual(len(vector),720)
            self.assertTrue(all(re.fullmatch(r'[0-9a-f]{16}',s)for s in vector))
            vectors.append('{'+','.join('0x'+s+'ULL'for s in vector)+'}')
        points=[]
        for p in fixture['projections']:
            self.assertTrue(0<=p['angle']<360)
            # Source-reachable substeps stay away from integer boundaries,
            # so small contraction/rounding differences cannot change pixels.
            self.assertTrue(abs(p['dx'])<=128 and abs(p['dy'])<=9)
            self.assertEqual(p['dx'],int(p['dx']))
            self.assertGreaterEqual(p['minimum_integer_margin'],1e-7)
            expected='{'+','.join('{%d,%d}'%tuple(r)for r in p['expected'])+'}'
            points.append('{%d,%d,%d,%s,%s,%s}'%(p['angle'],p['x'],p['y'],p['dx'],p['dy'],expected))
        main=(FIXTURES/'early_sprite_trig_main.c').read_text().replace('@VECTORS@',','.join(vectors)).replace('@POINTS@',','.join(points))
        main=main.replace('@CHECKS@','\n'.join('check(%d,%s);'%(r['revision'],','.join(map(str,r['tables'])))for r in rows))
        compiler=shlex.split(os.environ.get('HOST_CC','cc'));flags=['-std=gnu11','-O0','-g','-UNDEBUG','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+fixture['engine'],
            '-fcommon','-fsigned-char','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
            '-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
            '-Wno-error=sign-compare','-Wno-error=misleading-indentation','-Wno-error=deprecated-declarations']
        includes=[engine/'source/gamelib',engine/'source',engine,ROOT/'src/port/libretro',ROOT/'src/glue']
        flags+=['-I'+str(p)for p in includes]
        with tempfile.TemporaryDirectory(prefix='early-sprite-trig-')as temporary:
            work=Path(temporary);objects=[];source_hashes=[]
            for index,file in enumerate(['spritef.c','spritex8p16.c','spritex8p32.c']):
                renderer=engine/'source/gamelib'/file;text=renderer.read_text();values=dict(UNIT=str(index),RENDERER=json.dumps(str(renderer)))
                for mode,name in [('ROT','scaleline_rot'),('FLIP','scaleline_rotflip')]:
                    body=function(text,name)
                    if index:
                        pointers=re.findall(r'(?m)^\s*const double \*obor_(?:sin|cos) = [^;]+;',body)
                        self.assertEqual(len(pointers),2);values[mode+'_POINTERS']='\n'.join(pointers)
                    else:values[mode+'_POINTERS']='const double *obor_sin=sin_table,*obor_cos=cos_table;'
                    statements=sorted(set(re.findall(r'\br[xy]\s*=\s*[^;]+;',body)))
                    self.assertEqual(len(statements),2);values[mode+'_PROJECT']='\n'.join(statements)
                code=(FIXTURES/'early_sprite_trig_unit.c').read_text()
                for key,value in values.items():code=code.replace('@'+key+'@',value)
                source=work/('unit%d.c'%index);obj=source.with_suffix('.o');source.write_text(code);source_hashes.append(hashlib.sha256(code.encode()).hexdigest())
                built=subprocess.run(compiler+flags+['-c',str(source),'-o',str(obj)],capture_output=True,text=True,timeout=60)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr);objects.append(str(obj))
            source=work/'main.c';binary=work/'probe';source.write_text(main)
            links=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
            built=subprocess.run(compiler+flags+[str(source),*objects,*links,'-lm','-o',str(binary)],capture_output=True,text=True,timeout=60)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=sanitizer_environment())
            self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertIn('early_sprite_trig=1',run.stdout)
            if os.environ.get('OBOR_SPRITE_TRIG_OBSERVATIONS'):
                Path(os.environ['OBOR_SPRITE_TRIG_OBSERVATIONS']).write_text(json.dumps(dict(compiler=compiler,contexts=len(rows),stdout=run.stdout,
                    wrapper_sha256=source_hashes,main_sha256=hashlib.sha256(main.encode()).hexdigest(),scope=fixture['scope']),indent=2)+'\n')


if __name__=='__main__':unittest.main()
