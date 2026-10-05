#!/usr/bin/env python3
"""Exercise native IDs, binding, settings, routing and state isolation.

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

PROFILES = ('6330', '6391', '6412', '6510')
# Native values from the four upstream headers, independently of runtime maps.
NATIVE = {'6330': (0, 239, 5, 20), '6391': (0, 237, 4, 20),
          '6412': (0, 237, 4, 20), '6510': (1, 238, 4, 21)}
SCRIPT = b'''void main() {
    if(getglobalvar("profile_logged") != 1) {
        log("NATIVE " + openborconstant("ANI_IDLE") + " " +
            openborconstant("ANI_EDGE") + " " + openborconstant("SUBTYPE_TOUCH") + " " +
            openborconstant("ATK_TIMEOVER") + "\\n");
        clearspawnentry();
        setspawnentry("name", "TestBlock");
        setspawnentry("coords", 150, 100, 0);
        void target = spawn();
        clearspawnentry();
        setspawnentry("name", "TestBlock");
        setspawnentry("coords", 50, 60, 0);
        void child = spawn();
        changeentityproperty(target, "direction", 0);
        bindentity(child, target, 10, 5, 7, 2, 0, 3);
        log("BIND " + getentityproperty(child, "x") + " " +
            getentityproperty(child, "z") + " " + getentityproperty(child, "a") + " " +
            getentityproperty(child, "direction") + "\\n");
        log("ANIM " + getentityproperty(child, "animnum") + "\\n");
        log("ATTACK " + openborconstant("ATK_NORMAL1") + " " +
            getentityproperty(child, "defense", openborconstant("ATK_NORMAL1")) + " " +
            getentityproperty(child, "offense", openborconstant("ATK_NORMAL1")) + " " +
            getentityproperty(child, "defense", openborconstant("ATK_NORMAL11")) + " " +
            getentityproperty(child, "offense", openborconstant("ATK_NORMAL11")) + " " +
            openborvariant("maxattacktypes") + "\\n");
        setglobalvar("profile_logged", 1);
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--host')
    args = parser.parse_args()
    core = Path(args.core).resolve()
    with tempfile.TemporaryDirectory(prefix='anybor-6330-6510-') as temporary:
        work = Path(temporary)
        host = Path(args.host).resolve() if args.host else work / 'host'
        if not args.host:
            smoke.compile_host(release.ROOT, host)
        members = make_fixture.files()
        members['data/models.txt'] += b'maxattacktypes 13\n'
        members['data/chars/block.txt'] = (b'defense normal1 2\noffense normal1 3\n'
                                          b'defense normal11 4\noffense normal11 5\n'
                                          + members['data/chars/block.txt'])
        members['data/script.txt'] = b'alwaysupdate 1\n'
        members['data/scripts/updated.c'] = SCRIPT

        def fixture(name):
            path = work / (name + '.pak')
            make_fixture.write_pak(path, members)
            return path

        def run(profile, pak, label, system=None, **options):
            system = system or work / label
            system.mkdir(exist_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith('OBOR_')}
            env.update(OBOR_ENGINE=profile, OBOR_GAMELOG='On', OBOR_CHECK_FDS='1')
            env.update({k: str(v) for k, v in options.items()})
            result = subprocess.run([str(host), str(core), str(pak), str(system), '180'],
                                    cwd=work, env=env, capture_output=True, text=True, timeout=60)
            log = result.stdout + result.stderr
            if result.returncode or 'frames=180' not in log or 'nonblack_max=0' in log:
                raise AssertionError(label + ': ' + log)
            assert 'cwd_restored=1' in log and 'file_descriptors_restored=1' in log, log
            print('PASS ' + label, flush=True)
            return log, system

        def values(log, name):
            return [tuple(map(float, m.split())) for m in
                    re.findall(name + r' ([0-9. -]+)\n', log)]

        pak = fixture('native-profiles')
        settings_sizes = {}
        for profile in PROFILES:
            log, system = run(profile, pak, profile)
            assert values(log, 'NATIVE') == [NATIVE[profile]], log
            expected_x = 140 if profile == '6510' else 160
            assert values(log, 'BIND') == [(expected_x, 105, 7, 1)], log
            assert values(log, 'ANIM') == [(NATIVE[profile][0],)], log
            assert values(log, 'ATTACK') == [(12 if profile == '6510' else 11, 2, 3, 4, 5,
                                               25 if profile == '6510' else 24)], log
            settings_sizes[profile] = len(next((system / 'saves').rglob(pak.stem + '.cfg')).read_bytes())
            run(profile, pak, profile + '-existing', system=system)
            state = work / (profile + '.state')
            log, _ = run(profile, pak, profile + '-save', OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state)
            assert state.is_file() and 'saved state' in log, log
            log, _ = run(profile, pak, profile + '-load', OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
            assert 'load state at frame 120: ok' in log, log
            for other in PROFILES:
                if other != profile:
                    log, _ = run(other, pak, other + '-reject-' + profile,
                                 OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
                    assert 'load state at frame 120: FAILED' in log, log
        assert settings_sizes['6330'] + 4 == settings_sizes['6391']
        assert settings_sizes['6391'] == settings_sizes['6412'] == settings_sizes['6510']
        for profile in ('6330', '6510'):
            tagged = fixture('tagged [Build ' + profile + ']')
            log, _ = run('auto', tagged, profile + '-filename')
            assert 'profile ' + profile + ' -> engine 6391' in log, log
            assert values(log, 'NATIVE') == [NATIVE[profile]], log
            log, _ = run('6391', pak, 'reset-to-' + profile,
                         OBOR_SET_ENGINE_AT='60:' + profile, OBOR_RESET_AT=60)
            assert values(log, 'NATIVE') == [NATIVE['6391'], NATIVE[profile]], log
            log, _ = run(profile, pak, 'reset-from-' + profile,
                         OBOR_SET_ENGINE_AT='60:6391', OBOR_RESET_AT=60)
            assert values(log, 'NATIVE') == [NATIVE[profile], NATIVE['6391']], log
        print('6330/6391/6412/6510 runtime checks: OK', flush=True)


if __name__ == '__main__':
    main()
