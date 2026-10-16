#!/usr/bin/env python3
"""Check allocation growth, live CRT geometry and exact state/rewind output.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import tempfile

import make_fixture
import release
import smoke
from runtime_evidence import record_process
from test_crt import read_ppm


SCRIPT = b'''void main() {
    if(getglobalvar("geometry_tick") == NULL()) setglobalvar("geometry_tick", 0);
    int tick = getglobalvar("geometry_tick") + 1;
    setglobalvar("geometry_tick", tick);
    if(tick == 1) {
        setglobalvar("geometry_native", openborvariant("vscreen"));
        setglobalvar("geometry_high", allocscreen(2048, 1152));
        setglobalvar("geometry_sound", loadsample("data/sounds/beep.wav"));
    }
    if(tick == 50 || tick == 130)
        changeopenborvariant("vscreen", getglobalvar("geometry_high"));
    if(tick == 90 || tick == 170)
        changeopenborvariant("vscreen", getglobalvar("geometry_native"));
    drawboxtoscreen(openborvariant("vscreen"), 1800, 900, 248, 252,
                    rgbcolor(200, 40, 80), 0);
    if(tick % 10 == 0) playsample(getglobalvar("geometry_sound"), 0, 255, 255, 100, 0);
}'''


def pcm_records(path):
    raw, offset, result = path.read_bytes(), 0, []
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise AssertionError("Truncated PCM header")
        frame, count = struct.unpack_from("=II", raw, offset)
        end = offset + 8 + count * 4
        assert 0 < count <= 32768 and end <= len(raw), "Invalid PCM extent"
        result.append((frame, raw[offset + 8:end]))
        offset = end
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--host')
    parser.add_argument('--runner', default='')
    parser.add_argument('--windows', action='store_true')
    args = parser.parse_args()
    core = Path(args.core).resolve()
    with tempfile.TemporaryDirectory(prefix='anybor-geometry-') as folder:
        work = Path(folder)
        host = Path(args.host).resolve() if args.host else work / ('host.exe' if args.windows else 'host')
        if not args.host:
            smoke.compile_host(release.ROOT, host, windows=args.windows)
        members = make_fixture.files()
        members.update({'data/video.txt': b'video 320x200\n',
                        'data/script.txt': b'alwaysupdate 1\n',
                        'data/scripts/updated.c': SCRIPT})
        pak = work / 'geometry.pak'
        make_fixture.write_pak(pak, members)

        def target(path):
            value = str(path)
            return 'Z:' + value.replace('/', '\\') if args.windows else value

        def run(label, frames=400, content=pak, initial_max='320x240', **options):
            system = work / label
            system.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith('OBOR_')}
            env.update(OBOR_ENGINE='6412', OBOR_VIDEO_TRACE='1', OBOR_CHECK_GEOMETRY='1')
            env.update({k: target(v) if isinstance(v, Path) else str(v) for k, v in options.items()})
            process = subprocess.run(shlex.split(args.runner) + [str(host), target(core),
                target(content), target(system), str(frames), target(system / 'frame')],
                env=env, cwd=work, capture_output=True, text=True, timeout=120)
            record_process('geometry', label, process)
            log = process.stdout + process.stderr
            assert process.returncode == 0, log
            assert 'cwd_restored=1' in log and 'arena_released=1' in log, log
            assert 'FAILED' not in log and 'MISMATCH' not in log, log
            assert 'initial_maximum=' + initial_max in log, log
            assert 'final_maximum=2048x1152' in log, log
            growth = re.findall(r'^av_info=.*$', log, re.M)
            assert len(growth) == 1 and 'max=2048x1152' in growth[0], log
            # CRT can fit a large native screen into 640x480 while still
            # reserving its complete native bounds for a later live toggle.
            native_crossings = (0 if options.get('OBOR_CRT_TV') == 'On' else
                                1 if options.get('OBOR_CRT_TOGGLE_AT') else 2)
            assert log.count('video=2048x1152') >= native_crossings, log
            print('PASS geometry ' + label, flush=True)
            return log, system

        for crt in ('Off', 'On'):
            log, _ = run('crt-' + crt, OBOR_CRT_TV=crt)
            if crt == 'On':
                assert 'video=640x480' in log and 'video=320x240' in log, log
            else:
                assert 'video=320x200' in log, log
        run('live-toggles', OBOR_CRT_TOGGLE_AT='30,110,160,210')
        run('av-info-refused-fallback', OBOR_HOST_REJECT_AV_INFO=1)
        _, system = run('high-resolution-pixels', OBOR_DUMP_EVERY=60)
        width, height, pixels = read_ppm(system / 'frame000060.ppm')
        assert (width, height) == (2048, 1152)
        assert pixels[-3:] == bytes((200, 40, 80)), 'High-resolution edge was cropped'
        for crt in ('Off', 'On'):
            state, audio = work / ('save-' + crt), work / ('audio-' + crt)
            log, _ = run('load-' + crt, frames=510, OBOR_CRT_TV=crt,
                OBOR_SAVE_AT=65, OBOR_SAVE_STATE=state, OBOR_LOAD_AT=300,
                OBOR_LOAD_STATE=state, OBOR_LOAD_SOURCE_FRAME=65,
                OBOR_REPLAY_TRACE='66,265', OBOR_REPLAY_AUDIO=audio)
            replay = [line for line in log.splitlines() if line.startswith('replay_frame ')]
            assert len(replay) == 400 and replay[:200] == replay[200:], log
            pcm = pcm_records(audio)
            assert len(pcm) == 400 and pcm[:200] == pcm[200:], 'Restored PCM differs'
            assert any(any(data) for _, data in pcm), 'Audio control was silent'
            assert 'load state at frame 300: ok' in log, log
        state = work / 'crt-before-toggle.state'
        log, _ = run('load-after-crt-toggle', frames=450, OBOR_CRT_TV='On',
            OBOR_CRT_TOGGLE_AT=110, OBOR_SAVE_AT=65, OBOR_SAVE_STATE=state,
            OBOR_LOAD_AT=200, OBOR_LOAD_STATE=state)
        assert 'video=2048x1152 frame=201' in log, log
        for crt in ('Off', 'On'):
            log, _ = run('rewind-' + crt, OBOR_CRT_TV=crt, OBOR_RAREWIND='151,4',
                OBOR_RAREWIND_START=60, OBOR_RAREWIND_EVERY=30, OBOR_RAREWIND_BUFFERS=4,
                OBOR_HOST_THROTTLE='rewind', OBOR_EXPECT_REVERSE_PRESENTATION=1,
                OBOR_EXPECT_AUDIO_REPLAY=1,
                OBOR_CRT_TOGGLE_AT='30,40' if crt == 'Off' else '')
            assert len(re.findall(r'^rewind step .* MATCH$', log, re.M)) == 4, log
            assert len(re.findall(r'^rewind audio step .* MATCH$', log, re.M)) == 4, log
        # No mode can be inferred from a ZIP before extraction has run.
        import zipfile
        archive = work / 'unknown.zip'
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.write(pak, 'geometry.pak')
        # The fallback's loading transition is checked separately from the
        # deterministic native-mode fixture; it is not an extra rewind ring.
        run('unknown-initial-mode', content=archive, initial_max='1920x1080')
        raw = work / 'raw'
        for name, data in members.items():
            path = raw / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        run('known-loose-mode', content=raw / 'data/models.txt')
        for width, height, bounds in ((480, 272, '640x480'), (800, 450, '800x480')):
            wide_members = dict(members)
            wide_members['data/video.txt'] = ('video %dx%d\n' % (width, height)).encode('ascii')
            wide = work / ('wide-%d.pak' % width)
            make_fixture.write_pak(wide, wide_members)
            run('crt-reserve-%d' % width, content=wide, initial_max=bounds)
        print('Geometry: CRT, monotonic bounds, exact load/rewind and >1080p: OK', flush=True)


if __name__ == '__main__':
    main()
