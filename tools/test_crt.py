#!/usr/bin/env python3
"""Check CRT options, output frames and state/lifecycle integration.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
import make_fixture
import release
import crt_reference


def read_ppm(path):
    with path.open("rb") as stream:
        assert stream.readline() == b"P6\n"
        width, height = map(int, stream.readline().split())
        assert stream.readline() == b"255\n"
        pixels = stream.read()
    assert len(pixels) == width * height * 3
    return width, height, pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=str(release.ROOT / "anybor_libretro.so"))
    args = parser.parse_args()
    root = release.ROOT
    core = Path(args.core).resolve()
    with tempfile.TemporaryDirectory(prefix="anybor-crt-") as temp:
        work = Path(temp)
        host = work / "host"
        subprocess.check_call(shlex.split(os.environ.get("HOST_CC", "cc")) + [
            "-O2", "-I", str(root / "src/third_party"), "-I", str(root / "src/glue"),
            str(root / "tests/host/libretro_host.c"), "-ldl", "-o", str(host)])

        def run(engine, pak, label, expected, **options):
            system = work / (engine + "-" + label)
            system.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=engine, OBOR_VIDEO_TRACE="1", OBOR_CHECK_FDS="1")
            env.update({key: str(value) for key, value in options.items()})
            result = subprocess.check_output([
                str(host), str(core), str(pak), str(system), "180", str(system / "frame")],
                env=env, cwd=str(work), stderr=subprocess.STDOUT,
                universal_newlines=True, timeout=60)
            for marker in ("frames=180 last=" + expected, "cwd_restored=1",
                           "file_descriptors_restored=1"):
                assert marker in result, label + ": " + result
            assert "nonblack_max=0" not in result, result
            assert "FAILED" not in result, result
            assert ("option_order=obor_crt_tv|obor_analog|obor_rumble|obor_macros|"
                    "obor_engine|obor_gamelog") in result, result
            if options.get("OBOR_LOAD_AT"):
                assert "load state at frame 120: ok" in result, result
            if options.get("OBOR_SAVE_AT"):
                assert "saved state" in result, result
            if options.get("OBOR_OPTIONS_VERSION") == 2:
                assert "category_order=Video|Input|System" in result, result
                assert "video_category=Video" in result, result
                assert "crt_option=Adjust for 4:3 CRT TV category=video default=Off" in result, result
            else:
                assert "crt_legacy=Adjust for 4:3 CRT TV; Off|On" in result, result
            print("PASS " + engine + " " + label, flush=True)
            return result, read_ppm(system / "frame000180.ppm")

        engines = [e["build"] for e in release.read_json(root / "src/pin.json")["engines"]]
        for engine in engines:
            members = make_fixture.files()
            members["data/video.txt"] = b"video 1\n"
            pak = work / (engine + ".pak")
            make_fixture.write_pak(pak, members)
            _, native = run(engine, pak, "default-off", "480x272")
            _, explicit = run(engine, pak, "explicit-off", "480x272", OBOR_CRT_TV="Off")
            assert native == explicit, "Default must preserve native output"
            state = work / (engine + ".state")
            _, adapted = run(engine, pak, "crt-on", "640x480", OBOR_CRT_TV="On",
                             OBOR_OPTIONS_VERSION=2, OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state)
            width, height, pixels = adapted
            stride = width * 3
            assert (width, height) == (640, 480)
            assert not any(pixels[:59 * stride]) and not any(pixels[421 * stride:])
            assert any(pixels[59 * stride:421 * stride])
            # Check the complete fitted image against the native engine frame.
            crt_reference.assert_matches(pixels, crt_reference.compose(*native))
            result, _ = run(engine, pak, "toggle-on", "640x480", OBOR_CRT_TOGGLE_AT=100,
                            OBOR_RESET_AT=140)
            assert "geometry=640x480 aspect=1.333333 frame=100" in result, result
            result, _ = run(engine, pak, "toggle-off-load-crt-state", "480x272",
                            OBOR_CRT_TV="On", OBOR_CRT_TOGGLE_AT=100,
                            OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state, OBOR_RESET_AT=140)
            assert "geometry=480x272 aspect=1.764706 frame=100" in result, result
            run(engine, pak, "load-crt-state", "640x480", OBOR_CRT_TV="On",
                OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state, OBOR_RESET_AT=140)
            members.pop("data/video.txt")
            make_fixture.write_pak(pak, members)
            _, native = run(engine, pak, "4-by-3-off", "320x240")
            _, adapted = run(engine, pak, "4-by-3-on", "320x240", OBOR_CRT_TV="On")
            assert native == adapted, "4:3 output must remain byte-identical"
        # Native output requires both size limits and inclusive 4:3 +/-10%.
        for width, height in ((320, 240), (240, 200), (244, 200), (216, 150), (220, 150)):
            members = make_fixture.files()
            label = "native-%dx%d" % (width, height)
            native_size = "%dx%d" % (width, height)
            members["data/video.txt"] = ("video %s\n" % native_size).encode("ascii")
            pak = work / (label + ".pak")
            make_fixture.write_pak(pak, members)
            _, native = run("6412", pak, label + "-off", native_size)
            _, adapted = run("6412", pak, label + "-on", native_size, OBOR_CRT_TV="On")
            assert native == adapted, "Frames within size and aspect limits must stay native"
        # Native padding copies every source pixel and respects packed output
        # pitch, including fractional extents and unequal integer margins.
        for width, height, out_w, out_h, left, top in (
                (320, 180, 320, 240, 0, 30),
                (320, 200, 320, 240, 0, 20),
                (240, 240, 320, 240, 40, 0),
                (240, 244, 326, 244, 43, 0),
                (240, 241, 322, 241, 41, 0),
                (320, 181, 320, 240, 0, 29),
                (324, 180, 324, 243, 0, 31),
                (236, 200, 267, 200, 15, 0),
                (224, 150, 224, 168, 0, 9)):
            members = make_fixture.files()
            label = "padding-%dx%d" % (width, height)
            native_size, output_size = "%dx%d" % (width, height), "%dx%d" % (out_w, out_h)
            members["data/video.txt"] = ("video %s\n" % native_size).encode("ascii")
            grid = make_fixture.png(width, height, lambda x, y: 1 + ((x // 7 + y // 11) % 3))
            for name in list(members):
                if name.startswith("data/bgs/"):
                    members[name] = grid
            pak = work / (label + ".pak")
            make_fixture.write_pak(pak, members)
            _, native = run("6412", pak, label + "-off", native_size)
            _, adapted = run("6412", pak, label + "-on", output_size, OBOR_CRT_TV="On")
            expected = bytearray(out_w * out_h * 3)
            for y in range(height):
                dest = ((top + y) * out_w + left) * 3
                expected[dest:dest + width * 3] = native[2][y * width * 3:(y + 1) * width * 3]
            assert adapted == (out_w, out_h, expected), "Native padding changed source pixels or borders"
            if (width, height) == (320, 180):
                state = work / "padding.state"
                result, toggled = run("6412", pak, label + "-toggle-on", output_size,
                                      OBOR_CRT_TOGGLE_AT=100, OBOR_SAVE_AT=120,
                                      OBOR_SAVE_STATE=state, OBOR_RESET_AT=140)
                assert "geometry=320x240 aspect=1.333333 frame=100" in result, result
                assert toggled == adapted
                result, toggled = run("6412", pak, label + "-toggle-off-load", native_size,
                                      OBOR_CRT_TV="On", OBOR_CRT_TOGGLE_AT=100,
                                      OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state, OBOR_RESET_AT=140)
                assert "geometry=320x180 aspect=1.777778 frame=100" in result, result
                assert toggled == native
                _, restored = run("6412", pak, label + "-load", output_size,
                                  OBOR_CRT_TV="On", OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
                assert restored == adapted
        # Explicit fitted rectangles exercise either size limit independently,
        # the exact boundary, and wide/square/portrait output without cropping.
        # Engine screens round widths down to a multiple of four; the primitive
        # tests exercise the exact 365-pixel crossing directly.
        for width, height, left, top, fitted_width, fitted_height in (
                (360, 180, 0, 80, 640, 320),
                (328, 180, 0, 64, 640, 351),
                (364, 244, 0, 25, 640, 429),
                (364, 240, 0, 29, 640, 421),
                (368, 240, 0, 31, 640, 417),
                (320, 245, 7, 0, 626, 480),
                (364, 245, 0, 25, 640, 430),
                (368, 245, 0, 27, 640, 426),
                (320, 256, 20, 0, 600, 480),
                (640, 480, 0, 0, 640, 480),
                (644, 480, 0, 1, 640, 477),
                (640, 481, 1, 0, 638, 480),
                (672, 480, 0, 11, 640, 457),
                (640, 512, 20, 0, 600, 480),
                (800, 600, 0, 0, 640, 480),
                (800, 601, 1, 0, 638, 480),
                (800, 800, 80, 0, 480, 480),
                (600, 800, 140, 0, 360, 480),
                (1280, 720, 0, 60, 640, 360)):
            members = make_fixture.files()
            members["data/video.txt"] = ("video %dx%d\n" % (width, height)).encode("ascii")
            # A coloured grid exposes missing content and incorrect filtering.
            grid = make_fixture.png(width, height, lambda x, y: 1 + ((x // 7 + y // 11) % 3))
            for name in list(members):
                if name.startswith("data/bgs/"):
                    members[name] = grid
            pak = work / ("size-%dx%d.pak" % (width, height))
            make_fixture.write_pak(pak, members)
            label = "%dx%d" % (width, height)
            _, native = run("6412", pak, label + "-off", label)
            result, adapted = run("6412", pak, label + "-on", "640x480", OBOR_CRT_TV="On")
            assert "geometry=640x480 aspect=1.333333" in result, result
            pixels = adapted[2]
            stride = 640 * 3
            assert not any(pixels[:top * stride])
            assert not any(pixels[(top + fitted_height) * stride:])
            for y in range(top, top + fitted_height):
                row = pixels[y * stride:(y + 1) * stride]
                assert not any(row[:left * 3])
                assert not any(row[(left + fitted_width) * 3:])
                assert any(row[left * 3:(left + fitted_width) * 3])
            crt_reference.assert_matches(pixels, crt_reference.compose(*native))
            if (width, height) == (640, 480):
                assert native == adapted, "640x480 output must remain byte-identical"
            if (width, height) == (800, 600):
                _, toggled = run("6412", pak, label + "-toggle-on", "640x480",
                                 OBOR_CRT_TOGGLE_AT=100)
                assert toggled == adapted, "Live toggle must use the same complete downscale"
                _, toggled = run("6412", pak, label + "-toggle-off", label,
                                 OBOR_CRT_TV="On", OBOR_CRT_TOGGLE_AT=100)
                assert toggled == native, "Disabling CRT must restore the complete native frame"
        print("CRT runtime regressions: OK", flush=True)


if __name__ == "__main__":
    main()
