"""Inherited flags retain native isolation and actual file ABI bindings.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
SCRIPT=Path(os.environ.get('OBOR_FLAG_BUILDER',ROOT/'tools/build.py'))
sys.path.insert(0,str(SCRIPT.parent))
spec=importlib.util.spec_from_file_location('external_build_policy',SCRIPT)
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class ExternalFlagTests(unittest.TestCase):
    def test_argument_forms_and_platform_scope(self):
        environment={'CPPFLAGS':'-D _FILE_OFFSET_BITS=64 -DOTHER=64 -I "include space" -U_FILE_OFFSET_BITS -D_FILE_OFFSET_BITS_EXTRA=7 -flto=auto'}
        with patch.dict(os.environ,environment):
            flags=build.external_flag_args('CPPFLAGS',{'plat':'linux'},isolated=True)
            self.assertEqual(flags,['-DOTHER=64','-I','include space','-D_FILE_OFFSET_BITS_EXTRA=7','-flto=auto','-U_FILE_OFFSET_BITS','-fno-lto'])
            for platform in ('windows','darwin'):
                flags=build.external_flag_args('CPPFLAGS',{'plat':platform},isolated=True)
                self.assertIn('_FILE_OFFSET_BITS=64',flags)
                self.assertEqual(flags[-1],'-fno-lto')
            independent=build.external_flag_args('CPPFLAGS',{'plat':'linux'})
            self.assertIn('-flto=auto',independent);self.assertNotIn('-fno-lto',independent)

    @unittest.skipUnless(sys.platform=="linux","native Linux file ABI probe")
    def test_real_native_objects_in_normal_lto_offsets_and_combined_cases(self):
        for lto,offsets in ((False,False),(True,False),(False,True),(True,True)):
            flags='-fPIC -O2 -fstack-protector-strong -DKEEP_VALUE=37'
            if lto:flags+=' -flto=auto -fno-lto -flto'
            defines='-D _FILE_OFFSET_BITS=64' if offsets else ''
            with self.subTest(lto=lto,offsets=offsets),tempfile.TemporaryDirectory(prefix='external-flags-') as directory,patch.dict(os.environ,{'CFLAGS':flags,'CPPFLAGS':defines}):
                build.verify_external_file_abi({'plat':'linux','cc':'cc','nm':'nm'},Path(directory))
                receipt=json.loads((Path(directory)/'native-file-abi/receipt.json').read_text())
                self.assertIn('fopen',receipt['imports']);self.assertIn('stat',receipt['imports'])
                sections=subprocess.check_output(['objdump','-h',str(Path(directory)/'native-file-abi/probe.o')],text=True)
                self.assertNotIn('.gnu.lto_',sections)
                self.assertEqual(receipt['flags'][-1],'-fno-lto')

    @unittest.skipUnless(sys.platform=="linux","native Linux file ABI probe")
    def test_forced_header_alias_is_refused_before_long_build(self):
        with tempfile.TemporaryDirectory(prefix='external-header-') as directory:
            root=Path(directory);header=root/'forced.h';header.write_text('#define _FILE_OFFSET_BITS 64\n')
            with patch.dict(os.environ,{'CFLAGS':'-include '+str(header),'CPPFLAGS':''}):
                with self.assertRaisesRegex(RuntimeError,'bypasses native engine wrappers'):
                    build.verify_external_file_abi({'plat':'linux','cc':'cc','nm':'nm'},root)

    def test_real_large_file_position_and_preserved_define(self):
        code=r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <sys/types.h>
_Static_assert(sizeof(off_t)>=8,"wide native offsets required");
_Static_assert(KEEP_VALUE==37,"integrator define must survive");
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"w+b");assert(f);
off_t offset=((off_t)4<<30)+3;assert(!fseeko(f,offset,SEEK_SET));assert(fputc(42,f)==42);
assert(ftello(f)==offset+1);assert(!fseeko(f,offset,SEEK_SET));assert(fgetc(f)==42);assert(!fclose(f));return 0;}
'''
        with tempfile.TemporaryDirectory(prefix='external-large-file-') as directory,patch.dict(os.environ,{'CFLAGS':'-flto=auto -D_FILE_OFFSET_BITS=64 -DKEEP_VALUE=37','CPPFLAGS':''}):
            root=Path(directory);source=root/'probe.c';exe=root/'probe';source.write_text(code)
            flags=build.external_flag_args('CFLAGS',{'plat':'linux'},isolated=True)
            subprocess.run(['cc','-O2',*flags,str(source),'-o',str(exe)],check=True,timeout=30)
            subprocess.run([str(exe),str(root/'sparse.bin')],check=True,timeout=5)
            self.assertEqual((root/'sparse.bin').stat().st_size,(4<<30)+4)

    @unittest.skipUnless(shutil.which('x86_64-w64-mingw32-gcc'),'Windows cross compiler unavailable')
    def test_windows_object_retains_native_import_contract(self):
        with tempfile.TemporaryDirectory(prefix='external-pe-') as directory,patch.dict(os.environ,{'CFLAGS':'-flto=auto -D_FILE_OFFSET_BITS=64','CPPFLAGS':''}):
            root=Path(directory);source=root/'probe.c';obj=root/'probe.o'
            source.write_text('#include <stdio.h>\nFILE *probe(const char *s){return fopen(s,"rb");}\n')
            target={'plat':'windows'}
            flags=[*build.native_io_flags(target),*build.external_flag_args('CFLAGS',target,isolated=True)]
            subprocess.run(['x86_64-w64-mingw32-gcc',*flags,'-c',str(source),'-o',str(obj)],check=True,timeout=30)
            _,undefined=build.symbol_sets(obj,'x86_64-w64-mingw32-nm')
            self.assertIn('fopen',undefined);self.assertNotIn('__imp_fopen',undefined)
            sections=subprocess.check_output(['x86_64-w64-mingw32-objdump','-h',str(obj)],text=True)
            self.assertNotIn('.gnu.lto_',sections)


if __name__=='__main__':unittest.main()
