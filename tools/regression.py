#!/usr/bin/env python3
"""Exercise log states, save paths and WebM lifecycle with original content.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
import make_fixture
import release

DEFAULT_CORE = release.ROOT / ("anybor_libretro.dylib" if sys.platform == "darwin"
                               else "anybor_libretro.so")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=str(DEFAULT_CORE))
    parser.add_argument("--webm", action="store_true", help="also test WebM; needs host ffmpeg")
    parser.add_argument("--host", help="use a precompiled test host")
    parser.add_argument("--runner", default="", help="optional emulator command for the host")
    parser.add_argument("--windows", action="store_true", help="use Wine Z: paths with a Windows host")
    args = parser.parse_args()
    root = release.ROOT
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

        def run(engine, content, label, frames=180, **options):
            system = work / engine
            system.mkdir(exist_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=engine, OBOR_POST_UNLOAD_MS="250")
            if not args.windows:
                env["OBOR_CHECK_FDS"] = "1"
            for key, value in options.items():
                env[key] = target_path(value) if isinstance(value, Path) else str(value)
            command = shlex.split(args.runner) + [str(host), target_path(core),
                       target_path(content), target_path(system), str(frames)]
            try:
                result = subprocess.check_output(command, cwd=str(work), env=env,
                                                 stderr=subprocess.STDOUT,
                                                 universal_newlines=True, timeout=60)
            except subprocess.CalledProcessError as error:
                raise RuntimeError(label + ": " + error.output)
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

        for engine in [e["build"] for e in release.read_json(root / "src/pin.json")["engines"]]:
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

        if args.webm:
            for audio in (False, True):
                video = work / "green.webm"
                command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                           "color=c=green:s=160x120:r=30:d=10"]
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
                kind = "WebM with audio" if audio else "WebM without audio"
                for engine in ("4432", "6412", "8020"):
                    result = run(engine, video_pak, kind + " unload", frames=1300, OBOR_STOP_WIDTH=160)
                    if "stop_width=160" not in result:
                        raise RuntimeError("Video did not start: " + result)
                    result = run(engine, video_pak, kind + " reset and complete", frames=1700,
                                 OBOR_RESET_WIDTH=160)
                    if "reset_width=160" not in result or "last=320x240" not in result:
                        raise RuntimeError("Video restart did not complete: " + result)
                    if audio and "audio_energy=0" in result:
                        raise RuntimeError("The video audio track produced no samples: " + result)
                    state = work / "pre-video.state"
                    result = run(engine, video_pak, kind + " refuse load during playback", frames=1300,
                                 OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state,
                                 OBOR_LOAD_WIDTH=160, OBOR_LOAD_STATE=state)
                    if "load_width=160" not in result or ": FAILED" not in result or "last=320x240" not in result:
                        raise RuntimeError("Load must be refused without interrupting playback: " + result)
        print("Runtime regressions: OK", flush=True)


if __name__ == "__main__":
    main()
