#!/usr/bin/env python3
"""Exercise UTF-8 content, system and save paths through the Windows core.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import zipfile

from content_key import selector
import make_fixture
import release
from smoke import compile_host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--runner', default='')
    args = parser.parse_args()
    core = args.core.resolve()

    def target(path):
        return str(path) if os.name == 'nt' else 'Z:' + str(path).replace('/', '\\')

    with tempfile.TemporaryDirectory(prefix='anybor-unicode-') as directory:
        work = Path(directory).resolve()
        host = work / 'host.exe'
        compile_host(release.ROOT, host, windows=True)
        content = work / 'niño 日本 🎮'
        system = work / 'système 設定 🚀'
        frontend = work / 'exécution 起動'
        content.mkdir()
        system.mkdir()
        frontend.mkdir()
        pak = content / 'niño.pak'
        members = make_fixture.files()
        make_fixture.write_pak(pak, members)
        descriptor = content / 'sélection.anybor'
        descriptor.write_text('[anybor]\npayload = niño.pak\n', encoding='utf-8')
        loose = content / 'juego 展開'
        for name, data in members.items():
            entry = loose / name
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_bytes(data)
        archive = content / '日本 🎮.zip'
        # The extracted path exceeds 260 UTF-8 bytes while each component still
        # fits under the filesystem limit on the Linux host used by Wine.
        archive_member = '画' * 76 + '.pak'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
            stream.write(pak, '束/' + archive_member)
        with pak.open('rb') as stream:
            key = selector(stream, pak.stat().st_size)
        (system / 'AnyBOR.ini').write_text(
            '[' + key + '.overrides]\nengine = 6412\n', encoding='utf-8')
        save = system / 'saves'

        def run(path, game=None, **options):
            env = {key: val for key, val in os.environ.items() if not key.startswith('OBOR_')}
            env.update(options)
            proc = subprocess.run(shlex.split(args.runner) + [
                str(host), target(core), target(path), target(system), '90'],
                cwd=frontend, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors='replace', timeout=60)
            log = proc.stdout
            assert proc.returncode == 0, log
            assert re.search(r'frames=90 .*\bnonblack_max=[1-9][0-9]*', log), log
            assert 'resource initialization complete' in log, log
            assert 'cwd_restored=1' in log, log
            profile = save / 'AnyBOR' / (game or path.stem) / '6412'
            assert (profile / 'Saves').is_dir(), log
            assert (profile / 'Logs' / 'OpenBorLog.txt').is_file(), log
            assert (save / 'anybor-license-notices.txt').is_file(), log
            return log

        run(pak)
        run(descriptor, game=pak.stem)
        damaged = content / 'réparation 補修.pak'
        damaged.write_bytes(b'BROK' + pak.read_bytes()[4:])
        assert 'structural header repair' in run(damaged, OBOR_ENGINE='6412')
        run(loose / 'data' / 'models.txt', game=loose.name, OBOR_ENGINE='6412')
        keep_cache = dict(OBOR_CLEAR_ALL_CACHES='Off', OBOR_CLEAR_GAME_CACHE='Off')
        assert 'zip: extracted' in run(archive, **keep_cache)
        extracted = list((save / 'AnyBOR-cache' / 'zipcache').rglob(archive_member))
        assert len(extracted) == 1, extracted
        assert len(target(extracted[0]).encode('utf-8')) > 260
        assert extracted[0].read_bytes() == pak.read_bytes()
        assert 'using imohash cache' in run(archive, **keep_cache)
        assert 'zip: extracted' in run(archive)
        assert not extracted[0].exists()
    print('Windows UTF-8 content, system directory, saves and ZIP cache: OK')


if __name__ == '__main__':
    main()
