#!/usr/bin/env python3
"""Check four independent RetroPads through game scripts in every engine.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import re
import shlex
import struct
import subprocess
import tempfile
from pathlib import Path
import make_fixture
import release

BUTTONS = ('up', 'down', 'left', 'right', 'attack', 'attack2', 'attack3',
           'attack4', 'jump', 'special', 'start')
SCRIPT_KEYS = ('moveup', 'movedown', 'moveleft', 'moveright') + BUTTONS[4:]
NONE = 6937  # CONTROL_NONE in libretro virtual keyboard profiles.


def fixture():
    members = make_fixture.files()
    # Exercise action buttons with valid minimal animations in every engine.
    # Disable grabs between the four geometric actors; they are input probes.
    members['data/chars/block.txt'] = members['data/chars/block.txt'].replace(
        b'shadow 0\n', b'shadow 0\nantigrab 100\natchain 1\n')
    for animation in ('jump', 'fall', 'rise', 'pain', 'attack1', 'land'):
        members['data/chars/block.txt'] += (
            ('anim ' + animation + '\nloop 0\ndelay 10\noffset 8 31\n').encode('ascii') +
            b'bbox 0 0 16 32\nframe data/chars/block.png\n')
    members['data/models.txt'] += b'load Target data/chars/target.txt\n'
    members['data/chars/target.txt'] = (members['data/chars/block.txt']
        .replace(b'name TestBlock', b'name Target').replace(b'type player', b'type enemy')
        .replace(b'health 100', b'health 100000').replace(b'speed 2', b'speed 0'))
    members['data/levels.txt'] = (b'set Diagnostics\nmaxplayers 4\n'
        b'skipselect TestBlock TestBlock TestBlock TestBlock\nfile data/levels/room.txt\n')
    # A stationary off-screen target keeps the original diagnostic level open.
    members['data/levels/room.txt'] = (members['data/levels/room.txt']
        .replace(b'order a\n', b'order aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n') +
        b'nopause 1\ngroup 1 1\nspawn Target\ncoords 600 200\nat 0\n')
    script = 'void main() { int p; for(p=0;p<4;p++) { int h=0; int n=0; int r=0;\n'
    for bit, key in enumerate(SCRIPT_KEYS):
        for var, mode in (('h', 0), ('n', 1), ('r', 2)):
            script += 'if(playerkeys(p,%d,"%s")) %s=%s+%d;\n' % (mode, key, var, var, 1 << bit)
    script += ('log("PAD "+p+" "+h+" "+n+" "+r+" "+'
               '(getplayerproperty(p,"entity")!=NULL())+"\\n"); }}\n')
    members['data/scripts/updated.c'] = script.encode('ascii')
    return members


def schedule():
    timelines = [['150-650:start:pulse']] + [['700-705:start:hold'] for _ in range(3)]
    # Synchronization vector, single-player isolation, simultaneous distinct
    # buttons, and four full-stick directions on each player's analog device.
    phases = [[('up',), ('down',), ('left',), ('right',)]]
    for player in range(4):
        for button in BUTTONS:
            phases.append([(button,) if p == player else () for p in range(4)])
    for button in range(len(BUTTONS)):
        phases.append([(BUTTONS[(button + p) % len(BUTTONS)],) for p in range(4)])
    analog = ('analog_up', 'analog_down', 'analog_left', 'analog_right')
    for direction in range(4):
        phases.append([(analog[(direction + p) % 4],) for p in range(4)])
    phases.append([('analog_up', 'right'), ('analog_down', 'left'),
                   ('analog_left', 'down'), ('analog_right', 'up')])
    vectors = []
    for i, phase in enumerate(phases):
        start = 900 + i * 16
        masks = []
        for p, buttons in enumerate(phase):
            mask = 0
            for button in buttons:
                timelines[p].append('%d-%d:%s:hold' % (start, start + 7, button))
                mask |= 1 << BUTTONS.index(button.replace('analog_', ''))
            masks.append(mask)
        vectors.extend([tuple(masks), (0, 0, 0, 0)])
    return [','.join(t) for t in timelines], vectors, 900 + len(phases) * 16 + 30


def remap(vectors, rows):
    result = []
    for vector in vectors:
        translated = []
        for p, mask in enumerate(vector):
            out = 0
            for logical in range(len(BUTTONS)):
                physical = rows[p][logical] - (100 + p * 32)
                if 0 <= physical < len(BUTTONS) and mask & (1 << physical):
                    out |= 1 << logical
            translated.append(out)
        item = tuple(translated)
        if not result or result[-1] != item:
            result.append(item)
    return result


def check_inputs(text, expected):
    if 'exception' in text.lower() or 'Script compile error' in text:
        raise AssertionError('Diagnostic game script failed: ' + text[-2000:])
    rows = [tuple(map(int, r)) for r in re.findall(r'PAD (\d+) (\d+) (\d+) (\d+) (\d+)', text)]
    assert rows and len(rows) % 4 == 0, 'Missing four-player game reports'
    snapshots = []
    for offset in range(0, len(rows), 4):
        group = rows[offset:offset + 4]
        assert [r[0] for r in group] == list(range(4)), group
        snapshots.append(tuple(tuple(r[column] for r in group) for column in range(1, 5)))
    # Ignore only the title/join sequence. Swapped ports cannot pass: the full
    # ordered sequence and every press/release edge must match afterwards.
    start = next((i for i, s in enumerate(snapshots) if s[0] == expected[0]), None)
    assert start is not None, 'Four-player synchronization vector never reached the game'
    actual, previous = [], (0, 0, 0, 0)
    for held, pressed, released, active in snapshots[start:]:
        assert active == (1, 1, 1, 1), ('Four players did not join/stay in the game', active)
        assert pressed == tuple(h & ~p for h, p in zip(held, previous)), ('press edge', held, pressed, previous)
        assert released == tuple(p & ~h for h, p in zip(held, previous)), ('release edge', held, released, previous)
        if not actual or actual[-1] != held:
            actual.append(held)
        previous = held
    assert actual == expected, ('Game-visible input sequence differs', actual, expected)


def config_rows(data):
    # Persisted 8020 libretro s_savedata: ten 32-bit header fields followed by
    # four rows of thirteen keys. Keep this legacy on-disk fixture explicit;
    # a future format change needs a deliberate migration-test update.
    assert len(data) == 308, 'Unexpected 8020 saved configuration format'
    keys = struct.unpack_from('<52i', data, 40)
    return [list(keys[p * 13:(p + 1) * 13]) for p in range(4)]


def write_rows(data, rows):
    result = bytearray(data)
    struct.pack_into('<52i', result, 40, *[k for row in rows for k in row])
    return bytes(result)


def after_launch(data):
    # Upstream cycles savedata.logo at each launch; every other byte must stay
    # intact apart from the control rows explicitly repaired by this test.
    result = bytearray(data)
    logo = struct.unpack_from('<i', data, 276)[0]
    struct.pack_into('<i', result, 276, 0 if logo > 10 else logo + 1)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', default=str(release.ROOT / 'anybor_libretro.so'))
    parser.add_argument('--host', help='precompiled test host')
    parser.add_argument('--runner', default='', help='optional emulator command')
    parser.add_argument('--windows', action='store_true', help='Wine Z: paths')
    parser.add_argument('--engine', action='append', help='limit engine selection')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='anybor-multiplayer-') as temp:
        work = Path(temp)
        host = Path(args.host).resolve() if args.host else work / 'host'
        if not args.host:
            subprocess.check_call(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-O2', '-I', str(release.ROOT / 'src/third_party'), '-I', str(release.ROOT / 'src/glue'),
                str(release.ROOT / 'tests/host/libretro_host.c'), '-ldl', '-o', str(host)])
        pak = work / 'fourpads.pak'
        make_fixture.write_pak(pak, fixture())
        timelines, vectors, frames = schedule()

        def target(path):
            return 'Z:' + str(path).replace('/', '\\') if args.windows else str(path)

        def run(engine, label, system, expected=vectors):
            system.mkdir(exist_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith('OBOR_')}
            env['OBOR_ENGINE'] = engine
            for p, timeline in enumerate(timelines):
                env['OBOR_INPUT_P%d' % (p + 1)] = timeline
            process = subprocess.Popen(shlex.split(args.runner) + [str(host),
                target(Path(args.core).resolve()), target(pak), target(system), str(frames)],
                env=env, cwd=str(work), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            try:
                output, _ = process.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate()
                raise AssertionError(engine + ' ' + label + ' timed out:\n' + output[-6000:])
            assert process.returncode == 0, engine + ' ' + label + ':\n' + output[-6000:]
            assert 'frames=%d' % frames in output and 'cwd_restored=1' in output, output
            logs = system / 'saves/AnyBOR' / engine / 'Logs'
            text = '\n'.join(p.read_text(errors='replace') for p in logs.glob('*Log.txt'))
            check_inputs(text, expected)
            print('PASS ' + engine + ' ' + label + ': four players, ordered buttons/sticks and press/release edges', flush=True)
            return system / 'saves/AnyBOR' / engine / 'Saves/fourpads.cfg'

        for engine in args.engine or [e['build'] for e in release.read_json(release.ROOT / 'src/pin.json')['engines']]:
            system = work / engine
            config = run(engine, 'fresh defaults', system)
            run(engine, 'saved configuration', system)
            if engine != '8020':
                continue
            original = config.read_bytes()
            defaults = config_rows(original)
            empty = [row[:] for row in defaults]
            for p in range(1, 4):
                empty[p][:12] = [NONE] * 12
            legacy = write_rows(original, empty)
            config.write_bytes(legacy)
            run(engine, 'legacy empty P2-P4 migration', system)
            assert config.read_bytes() == after_launch(original), 'Migration changed unrelated saved settings'
            config.unlink()
            default_file = config.parent / 'default.cfg'
            default_file.write_bytes(legacy)
            run(engine, 'legacy default.cfg import', system)
            assert config.read_bytes() == after_launch(original) and default_file.read_bytes() == legacy
            default_file.unlink()
            custom = [row[:] for row in defaults]
            for p in range(4):
                custom[p][4], custom[p][8] = custom[p][8], custom[p][4]
            custom[2][7] = NONE  # A deliberately unbound action in a custom row.
            custom_data = write_rows(original, custom)
            config.write_bytes(custom_data)
            run(engine, 'custom mappings retained', system, remap(vectors, custom))
            assert config.read_bytes() == after_launch(custom_data), 'Custom controls were replaced'
    print('Four-player runtime regressions: OK', flush=True)


if __name__ == '__main__':
    main()
