#!/usr/bin/env python3
"""Boot every engine with fresh and existing saves using original content.

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
    parser.add_argument("--frames", type=int, default=400)
    parser.add_argument("--engine", action="append")
    parser.add_argument("--host", help="use a precompiled test host")
    parser.add_argument("--runner", default="", help="optional emulator command, such as wine")
    parser.add_argument("--windows", action="store_true", help="use Windows host and Wine Z: paths")
    args = parser.parse_args()
    root = release.ROOT
    pin = release.read_json(root / "src/pin.json")
    cache = root / ".build"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smoke-", dir=str(cache)) as temporary:
        exercise(args, root, pin, Path(temporary))


def compile_host(root, host, windows=False):
    compiler = "x86_64-w64-mingw32-gcc" if windows else "cc"
    command = shlex.split(os.environ.get("HOST_CC", compiler)) + [
        "-O2", "-I", str(root / "src/third_party"),
        "-I", str(root / "src/glue"), str(root / "tests/host/libretro_host.c"),
        "-o", str(host)]
    if windows:
        # The host times state operations through clock_gettime. MinGW
        # supplies it in winpthreads; keep the test executable standalone.
        command += ["-static", "-lwinpthread"]
    else:
        command.append("-ldl")
    subprocess.check_call(command)


def exercise(args, root, pin, work):
    fixture = work / "diagnostic.pak"
    make_fixture.write_pak(fixture, make_fixture.files())
    host = Path(args.host).resolve() if args.host else work / ("host.exe" if args.windows else "host")
    if not args.host:
        compile_host(root, host, args.windows)

    def target_path(path):
        path = str(Path(path).resolve())
        return "Z:" + path.replace("/", "\\") if args.windows and os.name != "nt" else path

    selected = args.engine or [e["build"] for e in pin["engines"]]
    if set(selected) - set(e["build"] for e in pin["engines"]):
        raise RuntimeError("Unknown engine requested")
    for engine in selected:
        system = work / engine
        system.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
        env["OBOR_ENGINE"] = engine
        command = shlex.split(args.runner) + [str(host), target_path(args.core),
                                             target_path(fixture), target_path(system), str(args.frames)]
        saves = system / "saves" / pin["core_name"] / fixture.stem / engine / "Saves"
        for label in ("fresh saves", "existing saves"):
            print("Engine " + engine + " / " + label, flush=True)
            try:
                result = subprocess.check_output(command, cwd=str(work), env=env,
                    stderr=subprocess.STDOUT, universal_newlines=True, timeout=90)
            except subprocess.CalledProcessError as error:
                raise RuntimeError("Engine " + engine + " / " + label + ": " + error.output)
            if "frames=" not in result or "nonblack_max=0" in result or "cwd_restored=1" not in result:
                raise RuntimeError("Smoke check failed for engine " + engine + ": " + result)
            if "library_name=" + pin["core_name"] not in result.splitlines():
                raise RuntimeError("Frontend core identity mismatch: " + result)
            if not saves.is_dir():
                raise RuntimeError("Runtime save directory missing for engine " + engine)
            document = system / "saves/anybor-license-notices.txt"
            if not document.is_file() or (root / "NOTICE.txt").read_bytes() not in document.read_bytes():
                raise RuntimeError("Runtime notice documentation missing for engine " + engine)
            marker = saves / "frontend-preserved.txt"
            if label == "fresh saves":
                marker.write_bytes(b"existing user data\n")
            elif marker.read_bytes() != b"existing user data\n":
                raise RuntimeError("Existing saves were changed")
            print("PASS " + engine + " / " + label, flush=True)


if __name__ == "__main__":
    main()
