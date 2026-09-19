#!/usr/bin/env python3
"""Exercise fixed-capacity rewind, reset and independent state restoration.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import re
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
    parser.add_argument("--host", help="use a precompiled test host")
    parser.add_argument("--runner", default="", help="optional emulator command")
    parser.add_argument("--windows", action="store_true", help="use Wine Z: paths")
    parser.add_argument("--windows-native", action="store_true",
                        help="run a Windows host natively (also supports WSL interop)")
    parser.add_argument("--work-parent", help="parent for temporary test files; use a Windows drive under WSL")
    args = parser.parse_args()
    if args.windows_native and (args.windows or args.runner or not args.host):
        parser.error("--windows-native requires --host and cannot use --windows or --runner")
    windows = args.windows or args.windows_native
    core = Path(args.core).resolve()
    with tempfile.TemporaryDirectory(prefix="anybor-rewind-", dir=args.work_parent) as temp:
        work = Path(temp)
        host = Path(args.host).resolve() if args.host else work / "host"
        if not args.host:
            subprocess.check_call(shlex.split(os.environ.get("HOST_CC", "cc")) + [
                "-O2", "-I", str(release.ROOT / "src/third_party"),
                "-I", str(release.ROOT / "src/glue"),
                str(release.ROOT / "tests/host/libretro_host.c"), "-ldl", "-o", str(host)])
        members = make_fixture.files()
        members["data/video.txt"] = b"video 1\n"
        pak = work / "diagnostic.pak"
        make_fixture.write_pak(pak, members)

        def target_path(path):
            if args.windows_native and os.name != "nt":
                return subprocess.check_output(["wslpath", "-w", str(path)], universal_newlines=True).strip()
            return "Z:" + str(path).replace("/", "\\") if args.windows else str(path)

        def run(engine, name, **options):
            root = work / (engine + "-" + name)
            root.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=engine, OBOR_STATE_CHECK="1",
                       OBOR_FIXED_STATE_FRONTEND="1")
            if not windows:
                env["OBOR_CHECK_FDS"] = "1"
            env.update({k: target_path(v) if isinstance(v, Path) else str(v)
                        for k, v in options.items()})
            if args.windows_native and os.name != "nt":
                # WSL does not forward arbitrary variables to native Windows
                # processes unless named in WSLENV. Paths are converted above.
                env["WSLENV"] = ":".join(filter(None, [env.get("WSLENV", "")] +
                                                 [k for k in env if k.startswith("OBOR_")]))
            log = subprocess.check_output(shlex.split(args.runner) + [
                                           str(host), target_path(core), target_path(pak),
                                           target_path(root), "180", target_path(root / "frame")],
                                          env=env, cwd=str(work), stderr=subprocess.STDOUT,
                                          universal_newlines=True, timeout=90)
            assert "invalid_version_and_truncation_rejected=1" in log, log
            assert "frames=180" in log, log
            if not windows:
                assert "file_descriptors_restored=1" in log, log
            assert "FAILED" not in log and "MISMATCH" not in log, log
            sizes = re.findall(r"state_contract version=2 capacity=(\d+)", log)
            assert len(sizes) == 2 and sizes[0] == sizes[1], log
            if "OBOR_RAREWIND" in options:
                assert log.count(" MATCH") == 7 and log.count(" NOREF") == 1, log
            if "OBOR_LOAD_AT" in options:
                assert "load state at frame 120: ok" in log, log
            print("PASS", engine, name, "capacity=" + sizes[0], flush=True)
            return (root / "frame000180.ppm").read_bytes(), log

        for entry in release.read_json(release.ROOT / "src/pin.json")["engines"]:
            engine = entry["build"]
            state = work / (engine + ".state")
            # An allocation is fixed before frame zero and then used for
            # every snapshot, including after a geometry toggle or Reset.
            run(engine, "reverse", OBOR_CRT_TV="On", OBOR_RAREWIND="150,8")
            run(engine, "toggle-reset", OBOR_CRT_TOGGLE_AT=60, OBOR_RESET_AT=100)
            image, _ = run(engine, "save", OBOR_CRT_TV="On", OBOR_SAVE_AT=120,
                           OBOR_SAVE_STATE=state)
            restored, _ = run(engine, "cross-session", OBOR_CRT_TV="On", OBOR_LOAD_AT=120,
                              OBOR_LOAD_STATE=state)
            assert image == restored, engine + " cross-session presentation diverged"
        # Reset may also select another engine, but the frontend's capacity
        # must not change. The new engine still gets its own BSS in the state.
        run("6412", "engine-reset", OBOR_SET_ENGINE_AT="60:3400", OBOR_RESET_AT=60)
    print("Fixed-capacity rewind contracts: OK", flush=True)


if __name__ == "__main__":
    main()
