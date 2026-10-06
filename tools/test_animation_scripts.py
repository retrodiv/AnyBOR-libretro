#!/usr/bin/env python3
"""Verify that inline animation scripts can finish a cutscene in every shared profile.

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


def files():
    members = make_fixture.files()
    # Allocate more animations than the fixed selector enumeration contains.
    # Allocation handles and profile-native selector IDs are separate domains.
    members['data/models.txt'] = (
        b'maxidles 260\nload TestBlock data/chars/block.txt\n'
        b'load Padding data/chars/padding.txt\n'
        b'load Countdown data/chars/countdown.txt\n'
        b'load Sentry data/chars/sentry.txt\n')
    members['data/chars/padding.txt'] = b'name Padding\ntype none\n' + b''.join(
        ('anim idle%d\nloop 1\ndelay 1\noffset 8 31\n'
         'frame data/chars/block.png\n' % i).encode('ascii') for i in range(1, 261))
    members['data/chars/countdown.txt'] = b'''name Countdown
type enemy
health 3
nomove 1 1
antigravity 100
anim idle
loop 1
@script
void subject = getlocalvar("self");
int remaining = getentityproperty(subject, "health");
if(frame == 1) {
    log("COUNTDOWN " + remaining + "\\n");
    changeentityproperty(subject, "health", remaining - 1);
    if(remaining <= 0) { killentity(subject); }
}
@end_script
delay 1
offset 8 31
frame data/chars/block.png
frame data/chars/block.png
anim spawn
delay 1
offset 8 31
frame data/chars/block.png
'''
    members['data/chars/sentry.txt'] = (members['data/chars/block.txt']
        .replace(b'name TestBlock', b'name Sentry').replace(b'type player', b'type enemy')
        .replace(b'health 100', b'health 100000').replace(b'speed 2', b'speed 0'))
    members['data/levels.txt'] = (b'set Diagnostics\nskipselect TestBlock\n'
        b'file data/levels/countdown.txt\nfile data/levels/after.txt\n')
    room = members.pop('data/levels/room.txt')
    members['data/levels/countdown.txt'] = room + (
        b'nopause 1\nwait\nat 0\ngroup 1 1\nat 0\n'
        b'spawn Countdown\ncoords 160 200 0\nat 0\n')
    members['data/levels/after.txt'] = room.replace(
        b'order a\n', b'order aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n') + (
        b'nopause 1\ngroup 1 1\nat 0\nspawn Sentry\ncoords 600 200 0\nat 0\n')
    return members


def check(log):
    values = [int(value) for value in re.findall(r'COUNTDOWN (-?\d+)\n', log)]
    if values != [3, 2, 1, 0]:
        raise AssertionError('Inline countdown did not execute exactly once: ' + log)
    stages = re.findall(r"Level Loaded:\s+'([^']+)'", log)
    if stages != ['data/levels/countdown.txt', 'data/levels/after.txt']:
        raise AssertionError('Cutscene did not advance to the next level: ' + log)
    if ('frames=1000' not in log or 'nonblack_max=0' in log
            or 'cwd_restored=1' not in log or 'file_descriptors_restored=1' not in log):
        raise AssertionError('Runtime or unload check failed: ' + log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--host')
    parser.add_argument('--profile', choices=PROFILES)
    args = parser.parse_args()
    core = Path(args.core).resolve()
    with tempfile.TemporaryDirectory(prefix='anybor-animation-scripts-') as temporary:
        work = Path(temporary)
        host = Path(args.host).resolve() if args.host else work / 'host'
        if not args.host:
            smoke.compile_host(release.ROOT, host)
        pak = work / 'inline-countdown.pak'
        make_fixture.write_pak(pak, files())
        for profile in (args.profile,) if args.profile else PROFILES:
            system = work / profile
            system.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith('OBOR_')}
            env.update(OBOR_ENGINE=profile, OBOR_GAMELOG='On', OBOR_CHECK_FDS='1',
                       OBOR_INPUT='150-650:start:pulse')
            result = subprocess.run([str(host), str(core), str(pak), str(system), '1000'],
                                    cwd=work, env=env, capture_output=True, text=True, timeout=60)
            log = result.stdout + result.stderr
            if result.returncode:
                raise AssertionError(profile + ': ' + log)
            check(log)
            print('PASS ' + profile + ' inline animation countdown and level transition', flush=True)


if __name__ == '__main__':
    main()
