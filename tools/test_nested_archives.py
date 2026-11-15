"""Bounded nested ZIP/RAR5 extraction with authored containers and PE wrappers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

import test_zip_content as base
from native_sanitizers import sanitizer_environment


def vint(value):
    result=bytearray()
    while value>=128:result.append((value&127)|128);value>>=7
    result.append(value)
    return bytes(result)


def block(payload):
    header=vint(len(payload))+payload
    return struct.pack('<I',zlib.crc32(header))+header


def rar(members, *, declared=None, services=()):
    result=b'Rar!\x1a\x07\x01\0'+block(b'\x01\x00\x00')
    files=list(members.items() if isinstance(members,dict) else members)
    records=[(3,name,data) for name,data in services]+[(2,name,data) for name,data in files]
    for kind,name,data in records:
        name=name.encode()
        body=bytes((kind,2))+vint(len(data))+b'\x04'+vint(len(data) if declared is None else declared)+b'\x20'
        body+=struct.pack('<I',zlib.crc32(data))+b'\0\0'+vint(len(name))+name
        result+=block(body)+data
    return result+block(b'\x05\0\0')


def sfx(data):
    wrapper=bytearray(1024)
    wrapper[:2]=b'MZ';struct.pack_into('<I',wrapper,60,128)
    wrapper[128:132]=b'PE\0\0';struct.pack_into('<HH',wrapper,132,0x8664,1)
    struct.pack_into('<H',wrapper,148,240);struct.pack_into('<H',wrapper,152,0x20b)
    struct.pack_into('<I',wrapper,212,512)
    struct.pack_into('<II',wrapper,408,512,512)
    return bytes(wrapper)+data


def png():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\0\0'))+chunk(b'IEND',b'')


def zip_bytes(members):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as stream:
        for name,data in members.items():stream.writestr(name,data)
    return output.getvalue()


class NestedArchiveTests(base.ZipContentTests):
    @classmethod
    def setUpClass(cls):
        if sys.platform.startswith('linux'):
            from run_guarded import require_limits
            require_limits(1024)
        cls.work=tempfile.TemporaryDirectory(prefix='nested-archives-')
        cls.directory=Path(cls.work.name)
        # Build the same pinned standalone library with sanitizers. No host
        # archive package or external command-line decoder is needed.
        import build
        cls.old_build=build.BUILD_ROOT
        build.BUILD_ROOT=cls.directory/'build'
        flags='-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all'
        try:
            with patch.dict(os.environ,{'CC':os.environ.get('HOST_CC','cc'),'CXX':os.environ.get('HOST_CXX','c++'),'CFLAGS':flags,'CPPFLAGS':'','LDFLAGS':flags}):
                target,_=build.configure_target('auto','unix')
                reader=build.build_archive_reader(target)
        finally:build.BUILD_ROOT=cls.old_build
        cls.binary=base.build_probe(cls.directory,archive_reader=reader)
        from test_content_overrides import PROGRAM
        route=cls.directory/'route';route.mkdir()
        cls.route=base.build_probe(route,program=PROGRAM,archive_reader=reader)
        from content_selection_probe import compile_probe
        cls.selection=cls.directory/'selection'
        compile_probe(base.GLUE/'libretro.cpp',base.GLUE/'anybor_engines.h',base.GLUE,base.THIRD,cls.selection,sanitizers=True)

    def test_rar_and_sfx_packed_and_loose_cold_warm(self):
        for wrapper in (lambda x:x,sfx):
            for game in (self.game(),{'Paks/one.pak':self.pak()}):
                with self.subTest(sfx=wrapper==sfx,packed='Paks/one.pak' in game):
                    result,path,_=self.run_zip({'nested.bin':wrapper(rar(game))})
                    self.assertEqual(result,(1,0,0))
                    self.assertIn('.unpacked/',path)
                    command=[str(self.binary),str(self.folder/'content.zip'),str(self.folder/'save')]
                    warm=subprocess.run(command,capture_output=True,text=True,check=True,timeout=30,env=sanitizer_environment())
                    self.assertTrue(warm.stdout.startswith('1 '),warm.stderr)
                    self.assertIn('using imohash cache',warm.stderr)

    def test_nested_zip_shares_game_ambiguity_and_engine_rules(self):
        result,_,_=self.run_zip({'a.zip':zip_bytes({'b.rar':rar(dict(self.game(),**{'OpenBOR.exe':b'engine A'}))})})
        self.assertEqual(result,(1,1,4000))
        self.assertEqual(self.run_zip({'a.rar':rar(self.game()),'b.rar':rar(self.game())})[0][0],0)
        self.assertEqual(self.run_zip({'a.rar':rar(self.game()),'unknown.pak':b'not a game'})[0][0],0)

    def test_wrapper_never_enters_engine_identity(self):
        result,_,_=self.run_zip({'OpenBOR.exe':sfx(rar(dict(self.game(),**{'OpenBOR.exe':b'engine A'})))})
        self.assertEqual(result,(1,1,4000))

    def test_valid_auxiliary_media_and_scoped_model_text(self):
        model=b'name Resource\ntype none\nhealth 100\nanim idle\nframe data/chars/image.png\n'
        content=dict(self.game(),**{'data/chars/image.png':png(),'paks/resource.pak':model})
        self.assertEqual(self.run_zip({'picture.pak':png(),'setup.exe':sfx(rar(content))})[0][0],1)
        for invalid in (png()[:-1],png()+b'junk',png()[:-5]+b'bad!!'):
            self.assertEqual(self.run_zip(dict(self.game(),**{'picture.pak':invalid}))[0][0],0)
        for invalid in (model.replace(b'health 100',b'health garbage'),model+b'@script\n',model+b'\0'):
            self.assertEqual(self.run_zip({'setup.exe':sfx(rar(dict(content,**{'paks/resource.pak':invalid})))})[0][0],0)
        self.assertEqual(self.run_zip(dict(self.game(),**{'outside.pak':model}))[0][0],0)

    def test_truncation_crc_unsafe_names_links_and_quotas(self):
        payload=rar(self.game())
        wrong=bytearray(payload);wrong[25]^=1
        for value in (payload[:-1],payload[:-8],payload+b'junk',bytes(wrong),rar({'../escape':b'x'}),rar([('same',b'a'),('SAME',b'b')]),rar({'huge':b'x'},declared=(2<<30)+1)):
            with self.subTest(size=len(value)):
                result,_,_=self.run_zip({'archive.rar':value})
                self.assertEqual(result[0],0)
                self.assertFalse(list((self.folder/'save').rglob('*.partial-*')))
        nested=rar(self.game())
        for _ in range(5):nested=rar({'child':nested})
        self.assertEqual(self.run_zip({'nested':nested})[0][0],0)
        link=zipfile.ZipInfo('link');link.create_system=3;link.external_attr=0o120777<<16
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as stream:stream.writestr(link,'target')
        self.assertEqual(self.run_zip({'nested.zip':output.getvalue()})[0][0],0)

    def test_bounded_service_metadata_is_ignored(self):
        comment=b'Setup=unused-program.exe\n'
        result,path,_=self.run_zip({'setup.exe':sfx(rar(self.game(),services=[('CMT',comment),('QO',b'index')]))})
        self.assertEqual(result[0],1)
        root=Path(path).parents[1]
        self.assertFalse((root/'CMT').exists());self.assertFalse((root/'QO').exists())
        oversized=rar({},services=[('CMT',b'x')],declared=(16<<20)+1)
        self.assertEqual(self.run_zip({'setup.rar':oversized})[0][0],0)

    def test_cancellation_and_reserved_cache_marker(self):
        self.assertEqual(self.run_zip(dict(self.game(),**{'.complete':b'not a marker'}))[0][0],0)
        members=dict(self.game(),**{'padding.bin':bytes(range(256))*4096})
        archive=self.folder/'cancel.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as stream:stream.writestr('nested.rar',rar(members))
        for after in (2,20,50):
            save=self.folder/('save-'+str(after))
            run=subprocess.run([str(self.binary),str(archive),str(save)],capture_output=True,text=True,check=True,timeout=30,env=sanitizer_environment(dict(os.environ,OBOR_TEST_CANCEL_AFTER=str(after))))
            self.assertTrue(run.stdout.startswith('0 '),run.stderr)
            self.assertFalse(list(save.rglob('*.partial-*')))
            self.assertFalse(list(save.rglob('.complete')))

    def test_original_pak_identity_and_profile_precedence(self):
        from content_key import selector
        payload=self.pak()
        archive=self.folder/'content.zip'
        members={'game.pak':payload,'inside.anybor':b'[anybor]\npayload=game.pak\n[overrides]\nengine=6391\n'}
        with zipfile.ZipFile(archive,'w') as stream:stream.writestr('nested',rar(members))
        system=self.folder/'system';system.mkdir()
        outer=self.folder/'outside.anybor'
        outer.write_text('[anybor]\npayload=content.zip\n[overrides]\nengine=3400\n')
        pak_key=selector(io.BytesIO(payload),len(payload))
        data=archive.read_bytes();zip_key=selector(io.BytesIO(data),len(data)).replace('pak-imohash:','zip-imohash:')
        pak_rule=f'[{pak_key}.overrides]\nengine=6330\n'
        zip_rule=f'[{zip_key}.overrides]\nengine=3740\n'
        for rules,expected in ((pak_rule+zip_rule,'3740'),(pak_rule,'6330'),('','3400')):
            (system/'AnyBOR.ini').write_text(rules)
            run=subprocess.run([str(self.route),'zip',str(outer),str(self.folder/'save'),str(system)],capture_output=True,text=True,check=True,timeout=30,env=sanitizer_environment())
            result=dict(line.split('=',1) for line in run.stdout.splitlines())
            self.assertEqual(result['ok'],'1',run.stderr);self.assertEqual(result['engine'],expected)
            chosen=Path(result['source']);self.assertEqual(chosen.read_bytes(),payload)
            selected=subprocess.run([str(self.selection),'--external',str(chosen),str(system),'Auto','3400',str(archive),'6391'],capture_output=True,text=True,check=True,timeout=30,env=sanitizer_environment())
            self.assertIn('selection_profile='+expected+' ',selected.stdout)
            manual=subprocess.run([str(self.selection),'--external',str(chosen),str(system),'4432','3400',str(archive),'6391'],capture_output=True,text=True,check=True,timeout=30,env=sanitizer_environment())
            self.assertIn('selection_profile=4432 ',manual.stdout)

    def test_warm_routing_and_payload_mutation_are_rejected(self):
        content={'one.pak':self.pak(),'choice.anybor':b'[anybor]\npayload=one.pak\n'}
        result,path,_=self.run_zip({'archive.rar':rar(content)})
        self.assertEqual(result[0],1)
        payload=Path(path);payload.write_bytes(payload.read_bytes()+b'bad')
        command=[str(self.binary),str(self.folder/'content.zip'),str(self.folder/'save')]
        warm=subprocess.run(command,capture_output=True,text=True,check=True,timeout=30,env=sanitizer_environment())
        self.assertTrue(warm.stdout.startswith('0 '),warm.stderr)


if __name__=='__main__':unittest.main()
