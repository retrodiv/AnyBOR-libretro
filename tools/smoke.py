#!/usr/bin/env python3
"""Exercise the native Linux core using original generated diagnostic content.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import shlex
import subprocess
import sys
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
    args = parser.parse_args()
    root = release.ROOT
    pin = release.read_json(root / "src/pin.json")
    work = root / ".build/smoke"
    work.mkdir(parents=True, exist_ok=True)
    fixture = work / "diagnostic.pak"
    make_fixture.write_pak(fixture, make_fixture.files())
    host = work / "host"
    subprocess.check_call(shlex.split(os.environ.get("HOST_CC", "cc")) + [
        "-O2", "-I", str(root / "src/third_party"),
        "-I", str(root / "src/glue"), str(root / "tests/host/libretro_host.c"),
        "-ldl", "-o", str(host)])
    for engine in args.engine or [e["build"] for e in pin["engines"]]:
        system = work / engine
        system.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["OBOR_ENGINE"] = engine
        result = subprocess.check_output([str(host), str(Path(args.core).resolve()),
                                          str(fixture), str(system), str(args.frames)],
                                         env=env, universal_newlines=True)
        if "frames=" not in result or "nonblack_max=0" in result or "cwd_restored=1" not in result:
            raise RuntimeError("Smoke check failed for engine " + engine + ": " + result)
        if "library_name=" + pin["core_name"] not in result.splitlines():
            raise RuntimeError("Frontend core identity mismatch: " + result)
        if not (system / "saves" / pin["core_name"] / fixture.stem / engine).is_dir():
            raise RuntimeError("Runtime save directory missing for engine " + engine)
        document = system / "saves/anybor-license-notices.txt"
        if not document.is_file() or (root / "NOTICE.txt").read_bytes() not in document.read_bytes():
            raise RuntimeError("Runtime notice documentation missing for engine " + engine)
        print("Engine " + engine + ": " + result.strip())


if __name__ == "__main__":
    main()
