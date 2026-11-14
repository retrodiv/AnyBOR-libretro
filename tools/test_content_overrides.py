"""External engine choices and bounded .anybor routing, using synthetic media.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from content_key import selector
from content_selection_probe import compile_probe
from native_sanitizers import sanitizer_environment
from test_zip_content import build_probe, GLUE, THIRD
from make_fixture import write_pak, files as fixture_files

PROGRAM = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <strings.h>
#include <filesystem>
#define RETRO_LOG_ERROR 1
#define RETRO_LOG_WARN 2
#define RETRO_LOG_INFO 0
static void log_cb(int,const char *format,...) {
 va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);
}
static void mkdir_p(const char *path) { std::filesystem::create_directories(path); }
@TABLE@
#include "anybor_zip.h"
#include "anybor_content_override.h"
int main(int argc,char **argv) {
 if(argc==3&&!strcmp(argv[1],"--hash")) {
  FILE *f=fopen(argv[2],"rb");if(!f)return 2;
  fseek(f,0,SEEK_END);long size=ftell(f);unsigned char digest[16];
  bool ok=size>=0&&obor_imohash_read(obor_content_hash_read,f,(uint64_t)size,digest);
  fclose(f);if(!ok)return 3;
  printf("imohash:%ld:",size);for(unsigned i=0;i<16;++i)printf("%02x",digest[i]);puts("");return 0;
 }
 if(argc!=5)return 2;
 char out[4096]={0},engine[48]={0},evidence[4608]={0};
 obor_content_choice choice;
 obor_engine_identity identity={};
 bool ok=obor_storage_begin(argv[3],false,false);
 if(ok)ok=!strcmp(argv[1],"zip")?
  obor_zip_prepare(argv[2],argv[3],out,sizeof(out),argv[4],&identity,&choice):
  obor_content_loose(argv[2],out,sizeof(out),choice);
 if(ok)ok=obor_content_override(argv[4],choice,engine,evidence,sizeof(evidence));
 printf("ok=%d\npath=%s\nsource=%s\nengine=%s\nevidence=%s\n",ok,out,choice.source,engine,evidence);
 return 0;
}
'''


class ContentOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='anybor-content-overrides-')
        cls.directory = Path(cls.work.name)
        cls.route = build_probe(cls.directory, program=PROGRAM)
        cls.selection = cls.directory / 'selection'
        compile_probe(GLUE / 'libretro.cpp', GLUE / 'anybor_engines.h', GLUE,
                      THIRD, cls.selection, sanitizers=True)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.directory)
        self.folder = Path(self.case.name)
        self.system = self.folder / 'system'
        self.system.mkdir()
        self.pak = self.folder / 'authored [Build 8023].pak'
        write_pak(self.pak, {'data/models.txt': b'load Block data/chars/block.txt\n',
                            'data/chars/block.txt': b'name Block\ntype player\n'})
        self.key = self.process([self.route, '--hash', self.pak]).stdout.strip()

    def tearDown(self):
        self.case.cleanup()

    @staticmethod
    def process(command):
        return subprocess.run(list(map(str, command)), capture_output=True, text=True,
                              timeout=45, env=sanitizer_environment())

    def ini(self, engine='6330', key=None):
        text = f'[{key or self.key}.overrides]\nengine = {engine}\n'
        (self.system / 'AnyBOR.ini').write_text(text)
        return text

    def route_content(self, path=None, *, zip=False):
        run = self.process([self.route, 'zip' if zip else 'loose', path or self.pak,
                        self.folder / 'save', self.system])
        self.assertEqual(run.returncode, 0, run.stderr)
        return dict(line.split('=', 1) for line in run.stdout.splitlines()), run.stderr

    def select(self, engine='', manual='Auto', path=None):
        return self.process([self.selection, '--external', path or self.pak,
                         self.system, manual, engine])

    def descriptor(self, path=None, engine='6330', payload=None):
        path = path or self.folder / 'Alias.anybor'
        text = f'[anybor]\npayload = {payload or self.pak.name}\n'
        if engine is not None:
            text += f'\n[overrides]\nengine = {engine}\n'
        path.write_text(text)
        return path

    def archive(self, members):
        path = self.folder / 'authored.zip'
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
            for name, value in members.items():
                stream.writestr(name, value)
        return path

    def test_selector_tool_matches_core_at_sampling_boundaries(self):
        for size in (1, 3, 127, 128, 16384, 131071, 131072, 131073, 262144):
            raw = bytes((i * 37 + 11) % 256 for i in range(size))
            path = self.folder / 'sample.pak'
            path.write_bytes(raw)
            expected = self.process([self.route, '--hash', path]).stdout.strip()
            self.assertEqual(selector(io.BytesIO(raw), size), expected)
        with self.assertRaises(ValueError):
            selector(io.BytesIO(b''), 0)
        with self.assertRaises(ValueError):
            selector(io.BytesIO(b'x'), 2)
        class Bounded(io.BytesIO):
            def read(self, length):
                self.total = getattr(self, 'total', 0) + length
                return super().read(length)
        stream = Bounded(bytes(262144))
        selector(stream, 262144)
        self.assertEqual(stream.total, 3 * 16384)

    def test_ini_matches_original_payload_and_all_engine_notations(self):
        for value, profile in [('6330', '6330'), ('v3.0 6330', '6330'),
                               ('6391-mod', '6391-mod'), ('v3.0 6391-mod', '6391-mod'),
                               ('v4.0 7142-alpha', '7142'), ('3742-dev', '3742')]:
            with self.subTest(value=value):
                self.ini(value)
                result, _ = self.route_content()
                self.assertEqual(result['engine'], value)
                run = self.select()
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn('selection_profile=' + profile + ' ', run.stdout)
                self.assertIn('AnyBOR.ini ' + self.key, run.stdout)

    def test_precedence_manual_then_ini_then_descriptor_then_detection(self):
        self.ini('6330')
        self.assertIn('selection_profile=3400 ', self.select('6391', manual='3400').stdout)
        self.assertIn('selection_profile=6330 ', self.select('6391').stdout)
        (self.system / 'AnyBOR.ini').unlink()
        self.assertIn('selection_profile=6391 ', self.select('6391').stdout)
        run = self.select()
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertIn('selection_profile=8023 ', run.stdout)

    def test_exact_override_missing_or_wrong_version_is_rejected(self):
        for value in ('9999', 'v4.0 6330', '6391-dev'):
            with self.subTest(value=value):
                self.ini(value)
                run = self.select()
                self.assertEqual(run.returncode, 3, run.stdout)
                self.assertIn('unavailable', run.stdout)
                self.assertIn('selection_profile= selection_engine=', run.stdout)

    def test_unmatched_size_or_digest_preserves_detection(self):
        prefix, size, digest = self.key.split(':')
        for key in (f'{prefix}:{int(size)+1}:{digest}', f'{prefix}:{size}:'+'0'*32):
            self.ini(key=key)
            self.assertIn('selection_profile=8023 ', self.select().stdout)

    def test_digest_is_case_insensitive_and_configuration_is_reread(self):
        self.ini('6330', self.key[:-32] + self.key[-32:].upper())
        self.assertEqual(self.route_content()[0]['engine'], '6330')
        self.ini('6391')
        self.assertEqual(self.route_content()[0]['engine'], '6391')
        (self.system / 'AnyBOR.ini').unlink()
        self.assertEqual(self.route_content()[0]['engine'], '')

    def test_malformed_duplicate_and_unsupported_selectors_are_rejected(self):
        good = self.ini()
        for text in (good+good, good+'engine=6391\n', good.replace('engine', 'unknown'),
                     good.replace('imohash:', 'sha256:'), good.replace('.overrides]', ']'),
                     good.replace('engine = 6330', 'engine = Auto'),
                     f'[{self.key}.overrides]\n', good.replace(':', ':0', 1),
                     '[imohash:18446744073709551616:'+'a'*32+'.overrides]\nengine=6330\n',
                     good+'\0', 'x'*(524288+1)):
            with self.subTest(text=text[:100]):
                (self.system / 'AnyBOR.ini').write_text(text)
                self.assertEqual(self.route_content()[0]['ok'], '0')

    def test_transform_strings_cannot_introduce_an_override(self):
        text = '[transforms]\ninput = buffer unchanged() {\nparameters("['+self.key+'.overrides]");\nreturn slice(0,input_size);\n}\n'
        (self.system / 'AnyBOR.ini').write_text(text)
        result, log = self.route_content()
        self.assertEqual(result['ok'], '1', log)
        self.assertEqual(result['engine'], '')
        self.ini()
        with (self.system / 'AnyBOR.ini').open('a') as stream:
            stream.write(text)
        self.assertEqual(self.route_content()[0]['engine'], '6330')

    def test_direct_and_unique_sibling_descriptor_select_same_pak(self):
        descriptor = self.descriptor()
        for target in (descriptor, self.pak):
            result, log = self.route_content(target)
            self.assertEqual(result['ok'], '1', log)
            self.assertEqual(Path(result['path']), self.pak)
            self.assertEqual(Path(result['source']), self.pak)
            self.assertEqual(result['engine'], '6330')
        self.ini('6391')
        self.assertEqual(self.route_content(descriptor)[0]['engine'], '6391')
        self.descriptor(engine=None)
        (self.system / 'AnyBOR.ini').unlink()
        self.assertEqual(self.route_content()[0]['engine'], '')

    def test_unrelated_sibling_is_ignored_but_matching_siblings_are_ambiguous(self):
        self.descriptor(payload='missing.pak')
        self.assertEqual(self.route_content()[0]['engine'], '')
        self.descriptor()
        self.descriptor(self.folder / 'Second.anybor')
        self.assertEqual(self.route_content()[0]['ok'], '0')

    def test_descriptor_paths_formats_sizes_and_links_are_bounded(self):
        path = self.folder / 'Alias.anybor'
        for payload in ('../escape.pak', '/abs.pak', 'C:\\game.pak', './game.pak',
                        'nested/../game.pak', 'Alias.anybor', 'content.zip', 'data/models.txt', 'absent.pak'):
            self.descriptor(path, payload=payload)
            self.assertEqual(self.route_content(path)[0]['ok'], '0', payload)
        for text in ('[anybor]\n', '[anybor]\npayload=x.pak\nunknown=yes\n',
                     '[unknown]\npayload=x.pak\n', 'x'*65537, '[anybor]\n\0'):
            path.write_text(text)
            self.assertEqual(self.route_content(path)[0]['ok'], '0')
        link = self.folder / 'link.pak'
        link.symlink_to(self.pak)
        self.descriptor(path, payload=link.name)
        self.assertEqual(self.route_content(path)[0]['ok'], '0')
        nested = self.folder / 'nested'
        nested.symlink_to(self.folder, target_is_directory=True)
        self.descriptor(path, payload='nested/' + self.pak.name)
        self.assertEqual(self.route_content(path)[0]['ok'], '0')

    def test_zip_descriptor_selects_payload_among_multiple_games(self):
        path = self.archive({'bundle/Name.anybor': b'[anybor]\npayload=Paks/game.pak\n[overrides]\nengine=6330\n',
                             'bundle/Paks/game.pak': self.pak.read_bytes(),
                             'other.pak': self.pak.read_bytes(), 'helper.pak': b'unknown auxiliary'})
        result, log = self.route_content(path, zip=True)
        self.assertEqual(result['ok'], '1', log)
        self.assertTrue(result['path'].endswith('/bundle/Paks/game.pak'))
        self.assertEqual(result['engine'], '6330')
        self.ini('6391')
        self.assertEqual(self.route_content(path, zip=True)[0]['engine'], '6391')

    def test_zip_rule_survives_repacking_and_reads_original_before_repair(self):
        self.ini()
        for name in ('first.pak', 'nested/renamed.pak'):
            path = self.archive({name: self.pak.read_bytes(), 'notes.txt': b'auxiliary'})
            result, log = self.route_content(path, zip=True)
            self.assertEqual(result['ok'], '1', log)
            self.assertEqual(result['engine'], '6330')
        write_pak(self.pak, fixture_files())
        raw = b'BROK' + self.pak.read_bytes()[4:]
        self.pak.write_bytes(raw)
        self.key = self.process([self.route, '--hash', self.pak]).stdout.strip()
        self.ini()
        path = self.archive({'game.pak': raw})
        result, log = self.route_content(path, zip=True)
        self.assertEqual(result['ok'], '1', log)
        self.assertEqual(result['engine'], '6330')
        self.assertNotEqual(result['path'], result['source'])

    def test_zip_invalid_missing_ambiguous_descriptors_and_invalid_pak_reject(self):
        cases = [
            {'x.anybor': b'[anybor]\npayload=missing.pak\n'},
            {'x.anybor': b'[anybor]\npayload=../game.pak\n'},
            {'x.anybor': b'[anybor]\npayload=broken.pak\n', 'broken.pak': b'junk'},
            {'x.anybor': b'x'*65537},
            {'x.anybor': b'[anybor]\npayload=game.pak\n',
             'y.anybor': b'[anybor]\npayload=game.pak\n'},
        ]
        for members in cases:
            path = self.archive(dict({'game.pak': self.pak.read_bytes()}, **members))
            self.assertEqual(self.route_content(path, zip=True)[0]['ok'], '0')

    def test_warm_cache_uses_descriptor_in_original_zip(self):
        members = {'x.anybor': b'[anybor]\npayload=game.pak\n[overrides]\nengine=6330\n',
                   'game.pak': self.pak.read_bytes()}
        path = self.archive(members)
        first, _ = self.route_content(path, zip=True)
        cached_descriptor = Path(first['source']).parent / 'x.anybor'
        cached_descriptor.write_text('[anybor]\npayload=missing.pak\n')
        second, log = self.route_content(path, zip=True)
        self.assertIn('using imohash cache', log)
        self.assertEqual(second['ok'], '1', log)
        self.assertEqual(second['engine'], '6330')


@unittest.skipUnless(os.environ.get('OBOR_TEST_CORE'), 'set OBOR_TEST_CORE for linked-core loading controls')
class ContentOverrideRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from smoke import compile_host
        from test_zip_content import ROOT
        cls.work = tempfile.TemporaryDirectory(prefix='anybor-override-runtime-')
        cls.root = Path(cls.work.name)
        cls.host = cls.root / 'host'
        cls.core = Path(os.environ['OBOR_TEST_CORE']).resolve()
        compile_host(ROOT, cls.host)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.root)
        self.folder = Path(self.case.name)
        self.system = self.folder / 'system'
        self.system.mkdir()
        self.pak = self.folder / 'authored [Build 8023].pak'
        write_pak(self.pak, fixture_files())
        with self.pak.open('rb') as stream:
            self.key = selector(stream, self.pak.stat().st_size)

    def tearDown(self):
        self.case.cleanup()

    def boot(self, content=None, **settings):
        env = {k: v for k, v in os.environ.items() if not k.startswith('OBOR_')}
        env.update(OBOR_SKIP_LOADING='1', OBOR_CHECK_FDS='1', **settings)
        run = subprocess.run([str(self.host), str(self.core), str(content or self.pak),
                              str(self.system), '12'], capture_output=True, text=True,
                             timeout=60, env=env)
        log = run.stdout + run.stderr
        self.assertEqual(run.returncode, 0, log)
        self.assertIn('resource initialization complete', log)
        self.assertIn('cwd_restored=1', log)
        self.assertIn('file_descriptors_restored=1', log)
        return log

    def test_linked_core_ini_descriptor_manual_and_save_namespace(self):
        descriptor = self.folder / 'Different alias.anybor'
        descriptor.write_text('[anybor]\npayload=' + self.pak.name + '\n[overrides]\nengine=6391\n')
        (self.system / 'AnyBOR.ini').write_text('[' + self.key + '.overrides]\nengine=v3.0 6330\n')
        self.assertIn('-> profile 6330 -> engine 6391', self.boot(descriptor))
        self.assertTrue((self.system / 'saves/AnyBOR' / self.pak.stem / '6330').is_dir())
        self.assertFalse((self.system / 'saves/AnyBOR' / descriptor.stem).exists())
        self.assertIn('(core option) -> profile 3400', self.boot(descriptor, OBOR_ENGINE='3400'))
        (self.system / 'AnyBOR.ini').unlink()
        self.assertIn('-> profile 6391 -> engine 6391', self.boot(descriptor))

    def test_linked_core_zip_descriptor_and_restart(self):
        archive = self.folder / 'package.zip'
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.write(self.pak, 'Paks/game.pak')
            stream.write(self.pak, 'other.pak')
            stream.writestr('Name.anybor', '[anybor]\npayload=Paks/game.pak\n[overrides]\nengine=6330\n')
        log = self.boot(archive, OBOR_RESET_AT='3')
        self.assertGreaterEqual(log.count('descriptor Name.anybor -> profile 6330'), 2, log)
        self.assertTrue((self.system / 'saves/AnyBOR/package/6330').is_dir())

    def test_header_repair_keeps_ignoring_unrelated_invalid_transform(self):
        self.pak.write_bytes(b'BROK' + self.pak.read_bytes()[4:])
        (self.system / 'AnyBOR.ini').write_text('[transforms]\ninput=invalid\n')
        self.assertIn('-> profile 8023 -> engine 8023', self.boot())


if __name__ == '__main__':
    unittest.main()
