#!/usr/bin/env python3
"""Exercise 4432 and 4453 color, settings, routing and state behavior.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

import make_fixture
import release
import smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--host')
    args = parser.parse_args()
    core = Path(args.core).resolve()
    with tempfile.TemporaryDirectory(prefix='anybor-4453-') as temporary:
        work = Path(temporary)
        host = Path(args.host).resolve() if args.host else work / 'host'
        if not args.host:
            smoke.compile_host(release.ROOT, host)
        members = make_fixture.files()
        members['data/script.txt'] = b'alwaysupdate 1\n'
        members['data/scripts/updated.c'] = b'''void main() {
    if(getglobalvar("depth_logged") != 1) {
        void screen = allocscreen(2, 2);
        log("DEPTH " + openborvariant("pixelformat") + " " +
            getgfxproperty(screen, "pixelformat") + " " + rgbcolor(17, 69, 123) + "\\n");
        free(screen);
        setglobalvar("depth_logged", 1);
    }
}
'''

        def fixture(name, depth=None):
            files = dict(members)
            files['data/video.txt'] = b'video 0\n'
            if depth:
                files['data/video.txt'] += ('colourdepth ' + depth + '\n').encode('ascii')
            path = work / (name + '.pak')
            make_fixture.write_pak(path, files)
            return path

        def run(profile, pak, label, system=None, **options):
            system = system or work / label
            system.mkdir(exist_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith('OBOR_')}
            env.update(OBOR_ENGINE=profile, OBOR_GAMELOG='On', OBOR_CHECK_FDS='1')
            env.update({k: str(v) for k, v in options.items()})
            command = [str(host), str(core), str(pak), str(system), '180']
            result = subprocess.run(command, cwd=work, env=env, capture_output=True,
                                    text=True, timeout=60)
            log = result.stdout + result.stderr
            if result.returncode or 'frames=180' not in log or 'nonblack_max=0' in log:
                raise AssertionError(label + ': ' + log)
            if 'cwd_restored=1' not in log or 'file_descriptors_restored=1' not in log:
                raise AssertionError(label + ': resources not restored: ' + log)
            print('PASS ' + label, flush=True)
            return log, system

        def depths(log):
            return [tuple(map(int, match)) for match in
                    re.findall(r'DEPTH (\d+) (\d+) (\d+)', log)]

        baseline32 = None
        colors4453 = []
        for mode, expected in ((None, (0, 0)), ('8bit', (0, 0)),
                               ('16bit', (1, 2)), ('32bit', (1, 4))):
            pak = fixture('depth-' + str(mode), mode)
            log, system = run('4432', pak, '4432-' + str(mode))
            actual = depths(log)
            assert actual and actual[0][:2] == expected, log
            old_settings = next((system / 'saves').rglob(pak.stem + '.cfg')).read_bytes()
            if mode == '32bit':
                baseline32 = actual[0]
            log, system = run('4453', pak, '4453-' + str(mode))
            actual = depths(log)
            assert actual and actual[0][:2] == (1, 4), log
            colors4453.append(actual[0][2])
            if baseline32 is not None:
                assert actual[0] == baseline32, log
            settings = next((system / 'saves').rglob(pak.stem + '.cfg'))
            assert len(settings.read_bytes()) == len(old_settings) + 16
            # A sentinel after the key array proves that loading the native
            # configuration preserves the fields following it as well.
            data = bytearray(settings.read_bytes())
            data[260:264] = (1).to_bytes(4, 'little')  # showtitles, 13-key layout
            settings.write_bytes(data)
            run('4453', pak, '4453-' + str(mode) + '-existing', system=system)
            assert settings.read_bytes()[260:264] == (1).to_bytes(4, 'little')

        assert all(color == baseline32[2] for color in colors4453)

        pak = fixture('state')
        state = work / '4453.state'
        log, _ = run('4453', pak, '4453-save', OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state)
        assert state.is_file() and 'saved state' in log, log
        log, _ = run('4453', pak, '4453-load', OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
        assert 'load state at frame 120: ok' in log, log
        log, _ = run('4432', pak, '4432-reject-4453', OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
        assert 'load state at frame 120: FAILED' in log, log
        log, _ = run('4453', pak, '4453-to-4432', OBOR_SET_ENGINE_AT='60:4432', OBOR_RESET_AT=60)
        assert [value[:2] for value in depths(log)] == [(1, 4), (0, 0)], log
        log, _ = run('4432', pak, '4432-to-4453', OBOR_SET_ENGINE_AT='60:4453', OBOR_RESET_AT=60)
        assert [value[:2] for value in depths(log)] == [(0, 0), (1, 4)], log
        tagged = fixture('tagged [Build 4453]', '8bit')
        log, _ = run('auto', tagged, '4453-filename')
        assert 'profile 4453 -> engine 4432' in log, log
        assert depths(log)[0][:2] == (1, 4), log
        old_tagged = fixture('tagged [Build 4452]')
        log, _ = run('auto', old_tagged, '4452-routing')
        assert 'profile 6391 -> engine 6391' in log, log
        print('4432/4453 runtime checks: OK', flush=True)


if __name__ == '__main__':
    main()
