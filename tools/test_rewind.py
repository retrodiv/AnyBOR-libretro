#!/usr/bin/env python3
"""Exercise fixed-capacity rewind, reset and independent state restoration.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
from contextlib import contextmanager
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


@contextmanager
def dedicated_wine(enabled, parent=None):
    """Keep one owned Wine server alive, with services outside host output pipes."""
    if not enabled:
        yield
        return
    previous = os.environ.get('WINEPREFIX')
    with tempfile.TemporaryDirectory(prefix='anybor-rewind-wine-', dir=parent) as prefix:
        os.environ['WINEPREFIX'] = prefix
        try:
            subprocess.run(['wineserver', '-p'], check=True, timeout=15)
            subprocess.run(['wineboot', '--init'], check=True, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print('wine_server=dedicated_persistent', flush=True)
            yield
        finally:
            try:
                subprocess.run(['wineserver', '-k'], check=True, timeout=15)
                subprocess.run(['wineserver', '-w'], check=True, timeout=15)
            finally:
                if previous is None:
                    os.environ.pop('WINEPREFIX', None)
                else:
                    os.environ['WINEPREFIX'] = previous


def main():
    from test_state_options import state_head
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=str(DEFAULT_CORE))
    parser.add_argument("--host", help="use a precompiled test host")
    parser.add_argument("--runner", default="", help="optional emulator command")
    parser.add_argument("--windows", action="store_true", help="use Wine Z: paths")
    parser.add_argument("--keep-wine-server", action="store_true",
                        help="use a dedicated persistent Wine prefix for this bounded test batch")
    parser.add_argument("--windows-native", action="store_true",
                        help="run a Windows host natively (also supports WSL interop)")
    parser.add_argument("--work-parent", help="parent for temporary test files; use a Windows drive under WSL")
    args = parser.parse_args()
    if args.keep_wine_server and (not args.windows or args.runner != 'wine' or not args.work_parent):
        parser.error('--keep-wine-server requires --windows --runner wine and an explicit --work-parent')
    if args.windows_native and (args.windows or args.runner or not args.host):
        parser.error("--windows-native requires --host and cannot use --windows or --runner")
    windows = args.windows or args.windows_native
    core = Path(args.core).resolve()
    with dedicated_wine(args.keep_wine_server, args.work_parent), tempfile.TemporaryDirectory(prefix="anybor-rewind-", dir=args.work_parent) as temp:
        work = Path(temp)
        host = Path(args.host).resolve() if args.host else work / ("host.exe" if windows else "host")
        if not args.host:
            from smoke import compile_host
            compile_host(release.ROOT, host, windows)
        members = make_fixture.files()
        members["data/video.txt"] = b"video 1\n"
        pak = work / "diagnostic.pak"
        make_fixture.write_pak(pak, members)

        def target_path(path):
            if args.windows_native and os.name != "nt":
                return subprocess.check_output(["wslpath", "-w", str(path)], universal_newlines=True).strip()
            return "Z:" + str(path).replace("/", "\\") if args.windows else str(path)

        mode = "default"
        def run(engine, name, **options):
            root = work / (mode + "-" + engine + "-" + name)
            root.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=engine, OBOR_STATE_CHECK="1",
                       OBOR_FIXED_STATE_FRONTEND="1", OBOR_SKIP_LOADING="1",
                       OBOR_SAVE_AT="179", OBOR_SAVE_STATE=target_path(root / "current.state"))
            if mode == "raw":
                env["OBOR_COMPRESSED_STATES"] = "0"
            if not windows:
                env["OBOR_CHECK_FDS"] = "1"
            else:
                env["OBOR_CHECK_UNLOAD_EXCEPTIONS"] = "1"
                if "OBOR_LOAD_AT" in options:
                    env["OBOR_PROCESS_RUNTIME_PADDING"] = "5"
            env.update({k: target_path(v) if isinstance(v, Path) else str(v)
                        for k, v in options.items()})
            if args.windows_native and os.name != "nt":
                # WSL does not forward arbitrary variables to native Windows
                # processes unless named in WSLENV. Paths are converted above.
                env["WSLENV"] = ":".join(filter(None, [env.get("WSLENV", "")] +
                                                 [k for k in env if k.startswith("OBOR_")]))
            command = shlex.split(args.runner) + [
                str(host), target_path(core), target_path(pak), target_path(root),
                "180", target_path(root / "frame")]
            result = subprocess.run(command, env=env, cwd=str(work),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=90)
            log = result.stdout + result.stderr
            if result.returncode:
                raise RuntimeError("%s %s host exited %d:\n%s" %
                                   (engine, name, result.returncode, log))
            assert "invalid_version_and_truncation_rejected=1" in log, log
            assert "frames=180" in log, log
            initial = re.search(r"loading_frames=\d+ initial_capacity=(\d+)", log)
            assert initial, log
            if not windows:
                assert "file_descriptors_restored=1" in log, log
            else:
                assert "post_unload_exception_safe=1" in log, log
                if "OBOR_LOAD_AT" in options:
                    assert "host_process_runtime_preserved=1" in log, log
            checked_log = log
            if "OBOR_LOAD_AT" in options:
                saved = state_head(options["OBOR_LOAD_STATE"])
                current = state_head(root / "current.state")
                if saved["image_lo"] != current["image_lo"]:
                    # The current process must remain intact when ASLR moves
                    # the module. Refusal is required for both state writers.
                    marker = "load state at frame 120: FAILED"
                    assert log.count(marker) == 1 and "state module address differs" in log, log
                    checked_log = log.replace(marker, "expected displaced-module refusal")
                    print("LIMIT", mode, engine, "cross-session module displaced; load refused", flush=True)
                else:
                    assert "load state at frame 120: ok" in log, log
            assert "FAILED" not in checked_log and "MISMATCH" not in checked_log, log
            version = 1 if mode == "default" and (windows or sys.platform == "linux") else 7
            sizes = re.findall(r"state_contract version=" + str(version) + r" capacity=(\d+)", log)
            assert len(sizes) == 2 and sizes[0] == sizes[1] == initial.group(1), log
            if "OBOR_RAREWIND" in options:
                assert log.count(" MATCH") == 7 and log.count(" NOREF") == 1, log
            print("PASS", mode, engine, name, "capacity=" + sizes[0], flush=True)
            return (root / "frame000180.ppm").read_bytes(), log

        for mode in ("default", "raw"):
            for entry in release.read_json(release.ROOT / "src/pin.json")["profiles"]:
                engine = entry["build"]
                state = work / (mode + "-" + engine + ".state")
                # Both current transport and raw fallback retain all fixed
                # capacity, reverse-playback, reset and independent-load checks.
                run(engine, "reverse", OBOR_CRT_TV="On", OBOR_RAREWIND="150,8")
                run(engine, "toggle-reset", OBOR_CRT_TOGGLE_AT=60, OBOR_RESET_AT=100)
                image, _ = run(engine, "save", OBOR_CRT_TV="On", OBOR_SAVE_AT=120,
                               OBOR_SAVE_STATE=state)
                restored, _ = run(engine, "cross-session", OBOR_CRT_TV="On", OBOR_LOAD_AT=120,
                                  OBOR_LOAD_STATE=state)
                assert image == restored, engine + " cross-session presentation diverged"
            # Reset may select another engine without changing capacity.
            run("6412", "engine-reset", OBOR_SET_ENGINE_AT="60:3400", OBOR_RESET_AT=60)
    print("Fixed-capacity rewind contracts: OK", flush=True)


if __name__ == "__main__":
    main()
