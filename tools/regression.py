#!/usr/bin/env python3
"""Exercise log states, save paths and WebM lifecycle with original content.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
import make_fixture
import release

DEFAULT_CORE = release.ROOT / ("anybor_libretro.dylib" if sys.platform == "darwin"
                               else "anybor_libretro.so")


def check_movie_restore(result, audio_path, restores=1):
    """A restored pre-movie continuation must match its original callbacks."""
    lines = [line for line in result.splitlines() if line.startswith("replay_frame ")]
    if not 1 <= restores <= 8 or len(lines) != 200 * (1 + restores) or any(
            lines[:200] != lines[at:at + 200] for at in range(200, len(lines), 200)):
        raise RuntimeError("Restored pre-movie video/audio continuation differs: " + result)
    if result.count("restore_joined_current_movie=1") != restores:
        raise RuntimeError("Movie workers were not joined before every restoration: " + result)
    if not audio_path.is_file() or not 0 < audio_path.stat().st_size <= 32 << 20:
        raise RuntimeError("Missing or excessive restored PCM evidence")
    data = audio_path.read_bytes()
    offset, records = 0, []
    while offset < len(data):
        if offset + 8 > len(data):
            raise RuntimeError("Truncated PCM header")
        source, count = struct.unpack_from("=II", data, offset)
        end = offset + 8 + count * 4
        if not 0 < count <= 32768 or end > len(data):
            raise RuntimeError("Invalid PCM record")
        records.append((source, data[offset + 8:end]))
        offset = end
    expected = list(range(121, 321))
    if ([r[0] for r in records] != expected * (1 + restores) or any(
            records[:200] != records[at:at + 200] for at in range(200, len(records), 200))):
        raise RuntimeError("Restored pre-movie full PCM differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=str(DEFAULT_CORE))
    parser.add_argument("--webm", action="store_true", help="also test WebM; needs host ffmpeg")
    parser.add_argument("--host", help="use a precompiled test host")
    parser.add_argument("--runner", default="", help="optional emulator command for the host")
    parser.add_argument("--windows", action="store_true", help="use Wine Z: paths with a Windows host")
    args = parser.parse_args()
    root = release.ROOT
    profiles = release.read_json(root / "src/pin.json")["profiles"]
    core = Path(args.core).resolve()
    cache = root / ".build"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="regression-", dir=str(cache)) as temp:
        work = Path(temp)
        host = Path(args.host).resolve() if args.host else work / "host"
        if not args.host:
            subprocess.check_call(shlex.split(os.environ.get("HOST_CC", "cc")) + [
                "-O2", "-I", str(root / "src/third_party"), "-I", str(root / "src/glue"),
                str(root / "tests/host/libretro_host.c"), "-ldl", "-o", str(host)])
        # A writable wrong directory makes a regression observable even when
        # the old code would otherwise silently fail to open its peak file.
        (work / "Saves").mkdir()
        members = make_fixture.files()
        pak = work / "diagnostic.pak"
        make_fixture.write_pak(pak, members)
        raw = work / "raw"
        for name, data in members.items():
            dest = raw / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

        def target_path(path):
            path = str(path)
            return "Z:" + path.replace("/", "\\") if args.windows else path

        def run(engine, content, label, frames=180, system_dir=None, **options):
            system = system_dir if system_dir is not None else work / engine
            system.mkdir(exist_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=engine, OBOR_POST_UNLOAD_MS="250")
            if not args.windows:
                env["OBOR_CHECK_FDS"] = "1"
            for key, value in options.items():
                env[key] = target_path(value) if isinstance(value, Path) else str(value)
            command = shlex.split(args.runner) + [str(host), target_path(core),
                       target_path(content), target_path(system), str(frames)]
            # Core diagnostics use stderr. Sharing its pipe with buffered
            # stdout can insert a diagnostic inside a replay-frame record.
            # Keep each stream intact; no cross-stream ordering is inferred.
            process = subprocess.run(command, cwd=str(work), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     universal_newlines=True, timeout=60)
            result = process.stdout + process.stderr
            if process.returncode:
                raise RuntimeError(label + ": " + result)
            if "cwd_restored=1" not in result or "nonblack_max=0" in result:
                raise RuntimeError(label + ": " + result)
            if not args.windows and "file_descriptors_restored=1" not in result:
                raise RuntimeError("Open files survived core unload: " + result)
            if options.get("OBOR_FD_PADDING") and "host_files_preserved=1" not in result:
                raise RuntimeError("Host files did not survive state restore: " + result)
            if list((work / "Saves").iterdir()):
                raise RuntimeError("Peak file escaped the frontend save directory")
            print("PASS " + engine + " " + label, flush=True)
            return result

        for engine in [e["build"] for e in profiles]:
            state = work / (engine + ".state")
            result = run(engine, pak, "save with game log", OBOR_GAMELOG="On",
                         OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state)
            if not state.is_file() or "saved state" not in result:
                raise RuntimeError("State was not saved: " + result)
            peak = work / engine / "saves/AnyBOR/diagnostic" / engine / "Saves/.obor_peak_sparse_v2_diagnostic.pak.txt"
            if not peak.is_file() or int(peak.read_text()) <= 0:
                raise RuntimeError("Missing peak in the frontend save directory")
            for option in ("On", "Off"):
                result = run(engine, pak, "cross-process load, game log " + option,
                             OBOR_GAMELOG=option, OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state,
                             OBOR_RESET_AT=150)
                if "load state at frame 120: ok" not in result:
                    raise RuntimeError("State did not load: " + result)
            result = run(engine, pak, "repeated state loads with shifted host descriptors",
                         OBOR_GAMELOG="On", OBOR_LOAD_AT=120, OBOR_LOAD_EVERY=10,
                         OBOR_LOAD_STATE=state, OBOR_FD_PADDING=12, OBOR_RESET_AT=150)
            if result.count("load state at frame") != 6 or ": FAILED" in result:
                raise RuntimeError("Repeated state loads did not complete: " + result)
            result = run(engine, pak, "nine restarts release all files", frames=1000,
                         OBOR_RESET_EVERY=100)
            if result.count("reset at frame") != 9:
                raise RuntimeError("Repeated restarts did not complete: " + result)
            state.unlink()

        peak = work / "6412/saves/AnyBOR/diagnostic/6412/Saves/.obor_peak_sparse_v2_diagnostic.pak.txt"
        peak.write_text(str(64 << 20) + "\n")
        run("6412", pak, "retain a previous larger peak", OBOR_SAVE_AT=120,
            OBOR_SAVE_STATE=work / "peak.state")
        if int(peak.read_text()) != (64 << 20):
            raise RuntimeError("A smaller session overwrote the learned peak")
        run("6412", raw / "data/models.txt", "unpacked mod save directory",
            OBOR_SAVE_AT=120, OBOR_SAVE_STATE=work / "raw.state")
        if not (work / "6412/saves/AnyBOR/raw/6412/Saves/.obor_peak_sparse_v2_raw.pak.txt").is_file():
            raise RuntimeError("Unpacked mod peak is missing")

        # Optional model entries must not index beyond the configured tables.
        # Each case has fresh files so an earlier warning cannot satisfy it.
        bounds_cases = (("defense", 11, None, True),
                        ("defense", 12, None, True),
                        ("offense", 11, None, True),
                        ("defense", 13, 12, True),
                        ("offense", 2147483647, None, True),
                        ("defense", 10, None, False),
                        ("defense", 12, 12, False),
                        ("offense", 12, 12, False))
        for index, (command, number, declared, warn) in enumerate(bounds_cases):
            model_members = make_fixture.files()
            if declared is not None:
                model_members["data/models.txt"] = (
                    "maxattacktypes {0}\n".format(declared).encode() +
                    model_members["data/models.txt"])
            directive = "{0} normal{1} 0 2000 1\n".format(command, number).encode()
            model_members["data/chars/block.txt"] = model_members["data/chars/block.txt"].replace(
                b"type player\n", b"type player\n" + directive)
            model_pak = work / ("model-attack-{0}.pak".format(index))
            make_fixture.write_pak(model_pak, model_members)
            for profile in profiles:
                engine = profile["build"]
                system = work / ("model-attack-{0}-{1}".format(index, engine))
                label = "model attack bounds {0} normal{1} max={2}".format(command, number, declared)
                result = run(engine, model_pak, label, frames=1000, system_dir=system,
                             OBOR_GAMELOG="On", OBOR_CRT_TV="Off")
                for log in system.rglob("OpenBorLog.txt"):
                    if log.stat().st_size > 1024 * 1024:
                        raise RuntimeError("Excessive model warning log")
                    result += log.read_text(errors="replace")
                diagnostic = "Ignoring out-of-range attack type"
                if ("resource initialization complete" not in result or
                        (not args.windows and "arena_released=1" not in result) or
                        "Allocator failed" in result or "invalid memory access" in result or
                        (warn and (diagnostic not in result or "normal{0}".format(number) not in result)) or
                        (not warn and diagnostic in result)):
                    raise RuntimeError(label + ": " + result)
        print("Model attack bounds: {0} conditions across {1} profiles: OK".format(
            len(bounds_cases) * len(profiles), len(profiles)), flush=True)

        if args.webm:
            for audio, width, height in ((False, 160, 120), (True, 160, 120), (True, 800, 450)):
                video = work / "green.webm"
                command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                           "color=c=green:s={0}x{1}:r=30:d=10".format(width, height)]
                if audio:
                    command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=10",
                                "-c:a", "libvorbis"]
                command += ["-c:v", "libvpx", "-b:v", "100k", "-threads", "2", "-y", str(video)]
                subprocess.check_call(command)
                video_members = dict(members)
                video_members["data/scenes/intro.txt"] = b"video data/scenes/green.webm 0 1\n"
                video_members["data/scenes/green.webm"] = video.read_bytes()
                video_pak = work / "video.pak"
                make_fixture.write_pak(video_pak, video_members)
                kind = ("WebM with audio" if audio else "WebM without audio") + " {0}x{1}".format(width, height)
                for engine in ("4432", "6412", "8023"):
                    physical = next(p["engine"] for p in profiles if p["build"] == engine)
                    movie_sources = root / "src/engines" / physical / "source/webmlib"
                    if not (movie_sources / "vidplay.c").is_file():
                        raise RuntimeError("Missing selected movie adapter")
                    asynchronous = (movie_sources / "movie_playback.c").is_file()
                    if width != 160 and not asynchronous:
                        continue  # Extra resolution exercises nested codec workers.
                    if width == 160:
                        result = run(engine, video_pak, kind + " unload", frames=1300, OBOR_STOP_WIDTH=160)
                        if "stop_width=160" not in result:
                            raise RuntimeError("Video did not start: " + result)
                        result = run(engine, video_pak, kind + " reset and complete", frames=1700,
                                     OBOR_RESET_WIDTH=160)
                        if "reset_width=160" not in result or "last=320x240" not in result:
                            raise RuntimeError("Video restart did not complete: " + result)
                        if audio and "audio_energy=0" in result:
                            raise RuntimeError("The video audio track produced no samples: " + result)
                    suffix = engine + "-" + str(int(audio)) + "-" + str(width)
                    state = work / ("pre-video-" + suffix + ".state")
                    options = dict(OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state,
                                   OBOR_LOAD_WIDTH=width, OBOR_LOAD_STATE=state,
                                   OBOR_LOAD_WIDTH_REPEAT=3, OBOR_STOP_AFTER_LOAD_FRAMES=200)
                    pcm = work / ("restored-" + suffix + ".pcm")
                    options.update(OBOR_REPLAY_TRACE="121,320", OBOR_REPLAY_AUDIO=pcm,
                                   OBOR_LOAD_SOURCE_FRAME=120, OBOR_STATE_TIMING=1)
                    if sys.platform == "linux" and not args.windows:
                        options["OBOR_CHECK_THREADS"] = 1
                    result = run(engine, video_pak, kind + " restore earlier state during playback",
                                 frames=4000, **options)
                    if result.count("load_width=" + str(width)) != 3 or ": FAILED" in result or "last=320x240" not in result:
                        raise RuntimeError("Movie restoration failed: " + result)
                    check_movie_restore(result, pcm, restores=3)
                    if "OBOR_CHECK_THREADS" in options:
                        native = re.findall(r"native_threads phase=restore before=(\d+) after=(\d+) baseline=(\d+)", result)
                        if len(native) != 3 or any(int(before) <= int(base) or after != base for before, after, base in native):
                            raise RuntimeError("Movie native workers did not return to baseline: " + result)
                        if width != 160 and any(int(before) < int(base) + 5 for before, _, base in native):
                            raise RuntimeError("Nested codec worker control was not active: " + result)
                    print("PASS " + engine + " " + kind +
                          " three restores; 200 video/audio callbacks and full PCM each", flush=True)
                    if not state.is_file() or "saved state" not in result:
                        raise RuntimeError("A fresh pre-video checkpoint was not saved: " + result)
        print("Runtime regressions: OK", flush=True)


if __name__ == "__main__":
    main()
