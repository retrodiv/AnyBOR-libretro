#!/usr/bin/env python3
"""Check CRT options, output frames and state/lifecycle integration.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
import make_fixture
import release
import crt_reference
from test_multiplayer import fixture as play_fixture
import re
from runtime_evidence import record_process

DEFAULT_CORE = release.ROOT / ("anybor_libretro.dylib" if sys.platform == "darwin"
                               else "anybor_libretro.so")


def read_ppm(path):
    with path.open("rb") as stream:
        assert stream.readline() == b"P6\n"
        width, height = map(int, stream.readline().split())
        assert stream.readline() == b"255\n"
        pixels = stream.read()
    assert len(pixels) == width * height * 3
    return width, height, pixels


def check_option_order(result, profile_count, capacity, version):
    """Check complete registration, including every manual build range."""
    assert profile_count > 0 and capacity >= 4
    expected = ["anybor_crt_tv", "anybor_crt_oversize_canvas_width", "anybor_crt_oversize_canvas_height",
                "anybor_os_screen_orientation",
                "anybor_image_rotation", "anybor_content_overrides", "anybor_analog", "anybor_rumble", "anybor_macros",
                "anybor_engine", "anybor_engine_3000_3499", "anybor_engine_3500_3749",
                "anybor_engine_3750_3999", "anybor_engine_4000_4999", "anybor_engine_5000_plus"]
    expected += ["anybor_state_content", "anybor_state_compression", "anybor_gamelog",
                 "anybor_clear_local_data", "anybor_clear_game_cache", "anybor_clear_all_caches"]
    orders = re.findall(r"^option_order=([^\r\n]*)$", result, re.M)
    assert orders and all(order.split("|") == expected for order in orders), result


def rotate(frame, turn):
    width, height, pixels = frame
    rows = [pixels[y * width * 3:(y + 1) * width * 3] for y in range(height)]
    matrix = [[row[x:x + 3] for x in range(0, len(row), 3)] for row in rows]
    if turn == "Left":
        return height, width, b"".join(pixel for col in reversed(list(zip(*matrix))) for pixel in col)
    if turn == "Right":
        return height, width, b"".join(pixel for col in zip(*matrix[::-1]) for pixel in col)
    return width, height, b"".join(pixel for row in matrix[::-1] for pixel in row[::-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=str(DEFAULT_CORE))
    args = parser.parse_args()
    root = release.ROOT
    core = Path(args.core).resolve()
    pin = release.read_json(root / "src/pin.json")
    capacity = re.search(r"^#define RETRO_NUM_CORE_OPTION_VALUES_MAX\s+(\d+)\s*$",
                         (root / "src/third_party/libretro.h").read_text(), re.M)
    assert capacity is not None
    capacity = int(capacity[1])
    with tempfile.TemporaryDirectory(prefix="anybor-crt-") as temp:
        work = Path(temp)
        host = work / "host"
        subprocess.check_call(shlex.split(os.environ.get("HOST_CC", "cc")) + [
            "-O2", "-I", str(root / "src/third_party"), "-I", str(root / "src/glue"),
            str(root / "tests/host/libretro_host.c"), "-ldl", "-o", str(host)])

        def run(engine, pak, label, expected, frames=180, **options):
            system = work / (engine + "-" + label)
            system.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=engine, OBOR_VIDEO_TRACE="1", OBOR_CHECK_FDS="1",
                       OBOR_CHECK_GEOMETRY="extent")
            env.update({key: str(value) for key, value in options.items()})
            if options.get("OBOR_SAVE_STATE"):
                Path(options["OBOR_SAVE_STATE"]).unlink(missing_ok=True)
            process = subprocess.run([
                str(host), str(core), str(pak), str(system), str(frames), str(system / "frame")],
                env=env, cwd=str(work), capture_output=True, text=True, timeout=60)
            record_process('crt', engine + '-' + label, process)
            result = process.stdout + process.stderr
            if process.returncode:
                raise RuntimeError(label + ': ' + result)
            for marker in (f"frames={frames} last={expected}", "cwd_restored=1",
                           "file_descriptors_restored=1"):
                assert marker in result, label + ": " + result
            assert "nonblack_max=0" not in result, result
            assert "FAILED" not in result, result
            check_option_order(result, len(pin["profiles"]), capacity,
                               int(options.get("OBOR_OPTIONS_VERSION", 0)))
            if options.get("OBOR_LOAD_AT"):
                assert "load state at frame 120: ok" in result, result
            if options.get("OBOR_SAVE_AT"):
                assert re.search(r"saved state \(\d+ bytes\) at frame " +
                                 str(options["OBOR_SAVE_AT"]) + r"\b", result), result
            if options.get("OBOR_OPTIONS_VERSION") == 2 and "category_order=" in result:
                assert "category_order=Video|Input|System|Development\n" in result, result
                assert "video_category=Video" in result, result
                assert "crt_option=Adjust for 4:3 CRT TV category=video default=Off" in result, result
            else:
                assert "crt_legacy=Adjust for 4:3 CRT TV; Off|On" in result, result
            print("PASS " + engine + " " + label, flush=True)
            return result, read_ppm(system / f"frame{frames:06d}.ppm")

        fixed_canvas = dict(OBOR_CRT_CANVAS_WIDTH="640px", OBOR_CRT_CANVAS_HEIGHT="480px")
        engines = [e["build"] for e in pin["engines"]]
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
                             OBOR_OPTIONS_VERSION=2, OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state, **fixed_canvas)
            width, height, pixels = adapted
            stride = width * 3
            assert (width, height) == (640, 480)
            assert not any(pixels[:59 * stride]) and not any(pixels[421 * stride:])
            assert any(pixels[59 * stride:421 * stride])
            # Check the complete fitted image against the native engine frame.
            crt_reference.assert_matches(pixels, crt_reference.compose(*native))
            result, _ = run(engine, pak, "toggle-on", "640x480", OBOR_CRT_TOGGLE_AT=100,
                            OBOR_RESET_AT=140, **fixed_canvas)
            assert "geometry=640x480 aspect=1.333333 frame=100" in result, result
            # Restore a real earlier CRT-on state in this process. A new
            # process may have a different module base and must refuse it;
            # independent-process refusal is covered by the state suites.
            result, _ = run(engine, pak, "toggle-off-load-crt-state", "480x272",
                            OBOR_CRT_TV="On", OBOR_CRT_TOGGLE_AT=100,
                            OBOR_SAVE_AT=90, OBOR_SAVE_STATE=state,
                            OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state, OBOR_RESET_AT=140, **fixed_canvas)
            assert "geometry=480x272 aspect=1.764706 frame=100" in result, result
            run(engine, pak, "load-crt-state", "640x480", OBOR_CRT_TV="On",
                OBOR_SAVE_AT=90, OBOR_SAVE_STATE=state,
                OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state, OBOR_RESET_AT=140, **fixed_canvas)
            members.pop("data/video.txt")
            make_fixture.write_pak(pak, members)
            _, native = run(engine, pak, "4-by-3-off", "320x240")
            _, adapted = run(engine, pak, "4-by-3-on", "320x240", OBOR_CRT_TV="On")
            assert native == adapted, "4:3 output must remain byte-identical"
        # Native output uses at most 244 lines and inclusive 4:3 +/-10%.
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
                                      OBOR_SAVE_AT=90, OBOR_SAVE_STATE=state,
                                      OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state, OBOR_RESET_AT=140)
                assert "geometry=320x180 aspect=1.777778 frame=100" in result, result
                assert toggled == native
                _, restored = run("6412", pak, label + "-load", output_size,
                                  OBOR_CRT_TV="On", OBOR_SAVE_AT=90, OBOR_SAVE_STATE=state,
                                  OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
                assert restored == adapted
        # Fitting samples the original raster when native padding or the original
        # height requires more than 244 scanlines.
        for width, height, left, top, fitted_width, fitted_height in (
                (360, 180, 0, 80, 640, 320),
                (328, 180, 0, 64, 640, 351),
                (320, 245, 7, 0, 626, 480),
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
            result, adapted = run("6412", pak, label + "-on", "640x480", OBOR_CRT_TV="On", **fixed_canvas)
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
                                 OBOR_CRT_TOGGLE_AT=100, **fixed_canvas)
                assert toggled == adapted, "Live toggle must use the same complete downscale"
                _, toggled = run("6412", pak, label + "-toggle-off", label,
                                 OBOR_CRT_TV="On", OBOR_CRT_TOGGLE_AT=100)
                assert toggled == native, "Disabling CRT must restore the complete native frame"

        def make_grid_pak(width, height):
            members = make_fixture.files()
            members["data/video.txt"] = ("video %dx%d\n" % (width, height)).encode("ascii")
            image = make_fixture.png(width, height, lambda x, y: 1 + ((x // 7 + y // 11) % 3))
            for name in members:
                if name.startswith("data/bgs/"):
                    members[name] = image
            pak = work / ("rotation-%dx%d.pak" % (width, height))
            make_fixture.write_pak(pak, members)
            return pak

        crt = dict(OBOR_CRT_TV="On", OBOR_HOST_ACCEPT_ROTATION=1, **fixed_canvas)
        portrait = make_grid_pak(224, 288)
        _, native = run("6412", portrait, "portrait-native", "224x288")
        _, horizontal = run("6412", portrait, "portrait-horizontal", "640x480", **crt)
        for turn, size in (("Left", "288x224"), ("Right", "288x224"), ("Upside Down", "224x288")):
            result, turned = run("6412", portrait, "crt-off-" + turn, size,
                                 OBOR_IMAGE_ROTATION=turn, OBOR_CRT_ORIENTATION="Vertical",
                                 OBOR_CRT_CANVAS_HEIGHT="240px", OBOR_HOST_ACCEPT_ROTATION=1)
            assert turned == rotate(native, turn) and "rotation=" not in result
        _, left = run("6412", portrait, "portrait-left", "288x224", OBOR_IMAGE_ROTATION="Left", **crt)
        assert left == rotate(native, "Left")
        result, vertical = run("6412", portrait, "portrait-vertical", "288x224",
                               OBOR_CRT_ORIENTATION="Vertical", **crt)
        assert vertical == rotate(native, "Right")
        assert rotate(vertical, "Left") == native
        assert "rotation=1 frame=0 accepted=1" in result and "aspect=0.777778" in result
        assert "rotation=0 " in result, "Unload must release the paired turn"
        _, inverted = run("6412", portrait, "portrait-vertical-inverted", "288x224",
                          OBOR_CRT_ORIENTATION="Vertical", OBOR_IMAGE_ROTATION="Upside Down", **crt)
        assert inverted == left
        result, cancelled = run("6412", portrait, "portrait-cancelled", "640x480",
                                OBOR_CRT_ORIENTATION="Vertical", OBOR_IMAGE_ROTATION="Right", **crt)
        assert cancelled == horizontal
        assert "rotation=3 frame=0 accepted=1" in result and "aspect=0.750000" in result
        result, refused = run("6412", portrait, "portrait-refused", "480x640",
                              OBOR_CRT_TV="On", OBOR_CRT_ORIENTATION="Vertical", OBOR_IMAGE_ROTATION="Right",
                              **fixed_canvas)
        assert refused == rotate(horizontal, "Right")
        assert "rotation=3 frame=0 accepted=0" in result and "rotation=0 frame=0 accepted=0" in result
        state = work / "rotation.state"
        for before, size, expected, request in (("Horizontal", "288x224", vertical, 1),
                                                 ("Vertical", "640x480", horizontal, 0)):
            result, changed = run("6412", portrait, "live-from-" + before, size,
                                  OBOR_CRT_ORIENTATION=before, OBOR_CRT_ORIENTATION_TOGGLE_AT=100,
                                  OBOR_SAVE_AT=90, OBOR_SAVE_STATE=state, OBOR_LOAD_AT=120,
                                  OBOR_LOAD_STATE=state, OBOR_RESET_AT=140, **crt)
            assert changed == expected
            assert f"rotation={request} frame=100 accepted=1" in result

        wide = make_grid_pak(1920, 1080)
        for canvas_w, canvas_h, width, height, border in (
                (None, None, 1920, 448, 56),
                ("640px", "480px", 640, 480, 60),
                ("512px", "360px", 512, 360, 45),
                ("320px", "224px", 320, 224, 28),
                ("Keep Game Width", "240px", 1920, 240, 30),
                ("Keep Game Width", "Keep Game Height", 1920, 1440, 180)):
            settings = {"OBOR_CRT_TV": "On"}
            if canvas_w:
                settings.update(OBOR_CRT_CANVAS_WIDTH=canvas_w, OBOR_CRT_CANVAS_HEIGHT=canvas_h)
            result, frame = run("6412", wide, f"wide-{width}x{height}", f"{width}x{height}", **settings)
            assert "aspect=1.333333" in result
            stride = width * 3
            pixels = frame[2]
            assert not any(pixels[:border * stride]) and not any(pixels[-border * stride:])
            assert any(pixels[border * stride:(border + 1) * stride])
            assert any(pixels[-(border + 1) * stride:-border * stride])
        tall = make_grid_pak(1080, 1920)
        result, frame = run("6412", tall, "vertical-keep", "1920x480",
                            OBOR_CRT_CANVAS_HEIGHT="480px", OBOR_CRT_TV="On",
                            OBOR_HOST_ACCEPT_ROTATION=1, OBOR_CRT_ORIENTATION="Vertical")
        assert "aspect=0.750000" in result
        stride = 1920 * 3
        assert not any(frame[2][:60 * stride]) and not any(frame[2][-60 * stride:])
        assert any(frame[2][60 * stride:61 * stride]) and any(frame[2][-61 * stride:-60 * stride])

        pak = make_grid_pak(240, 180)
        descriptor = work / "external.anybor"
        def declare(path, command):
            descriptor.write_text(f"[anybor]\npayload = {path.name}\n\n[overrides]\n?crt {command}\n",
                                  encoding="utf-8")
        declare(pak, "crtmode|256|192|window_fps")
        run("6412", descriptor, "descriptor-off", "240x180")
        result, fitted = run("6412", descriptor, "descriptor-fixed", "256x192",
                             OBOR_CRT_TV="On", OBOR_RESET_AT=140)
        assert not any(fitted[2][:6 * 256 * 3])
        declare(pak, "crtmode|window_w|window_h|60")
        run("6412", descriptor, "descriptor-native", "240x180", OBOR_CRT_TV="On")
        declare(pak, "crtmode|window_w|192|50")
        result, _ = run("6412", descriptor, "descriptor-mixed", "240x192",
                        OBOR_CRT_TV="On", OBOR_CRT_ORIENTATION="Vertical",
                        OBOR_IMAGE_ROTATION="Right", OBOR_HOST_ACCEPT_ROTATION=1,
                        OBOR_AUDIO_FRAME_TRACE=1)
        assert re.search(r"accepted=1 fps=50\.000000", result), result
        def samples(log):
            return sum(int(count) for count, frame in re.findall(r"audio_frames=(\d+) frame=(\d+)", log)
                       if 100 <= int(frame) < 150)
        assert samples(result) == 44100, result
        declare(pak, "crtmode|window_w|192|120")
        result, _ = run("6412", descriptor, "descriptor-repeat-frames", "240x192",
                        OBOR_CRT_TV="On", OBOR_AUDIO_FRAME_TRACE=1)
        assert re.search(r"accepted=1 fps=120\.000000", result), result
        assert samples(result) == 18375, result
        declare(pak, "crtmode|window_w|192|50")
        result, _ = run("6412", descriptor, "descriptor-refresh-rejected", "240x192",
                        OBOR_CRT_TV="On", OBOR_HOST_REJECT_AV_INFO=1, OBOR_AUDIO_FRAME_TRACE=1)
        assert re.search(r"accepted=0 fps=50\.000000", result), result
        assert samples(result) == 36750, result

        archive = work / "internal.zip"
        with zipfile.ZipFile(archive, "w") as container:
            container.write(pak, pak.name)
            container.write(descriptor, "internal.anybor")
        run("6412", archive, "descriptor-in-zip", "240x192", OBOR_CRT_TV="On")
        declare(archive, "crtmode|256|196|window_fps")
        run("6412", descriptor, "descriptor-external-priority", "256x196", OBOR_CRT_TV="On")
        declare(archive, "crtmode|window_w|window_h|60\n"
                         "?crt windowraster|304|228\n?crt=vertical windowraster|180|240")
        run("6412", descriptor, "window-horizontal", "304x228", OBOR_CRT_TV="On")
        run("6412", descriptor, "window-vertical", "180x240", OBOR_CRT_TV="On",
            OBOR_CRT_ORIENTATION="Vertical")
        run("6412", descriptor, "window-quarter-turn", "240x180", OBOR_CRT_TV="On",
            OBOR_IMAGE_ROTATION="Right")
        run("6412", descriptor, "window-off", "240x180", OBOR_CRT_TV="On",
            OBOR_CONTENT_OVERRIDES="Off")
        declare(archive, "crtmode|window_w|window_h|60\n"
                         "?gameres @present_crop_left=10\n?gameres @present_shift_x=-(1+3)/2")
        _, cropped = run("6412", descriptor, "native-raster-crop-shift", "230x180")
        assert cropped[0:2] == (230, 180) and not any(cropped[2][228 * 3:230 * 3])

        scoped = work / "scoped.pak"
        members = play_fixture()
        members["data/script.txt"] = b"alwaysupdate 1\n"
        members["data/scripts/update.c"] = b"""
void main() {
    if (getglobalvar("paint") == NULL()) {
        setglobalvar("paint", 1);
        setglobalvar("locked", 4);
        setglobalvar("enabled", 1);
        setglobalvar("hold_value", 2);
    }
    setglobalvar("before_draw", getglobalvar("paint"));
}
"""
        members["data/scripts/updated.c"] = b"""
void main() {
    if (openborvariant("in_level")) {
        log("POLICY "+getglobalvar("before_draw")+" "+getglobalvar("paint")+" "+
            getglobalvar("locked")+" "+openborvariant("elapsed_time")+"\\n");
    }
}
"""
        make_fixture.write_pak(scoped, members)
        # The set starts with a skipselect entry. Its first playable level has index 1.
        declare(scoped, "roomspeed|1|50\n?crt crtmode|window_w|window_h|window_fps\n"
                        "?gameres ?global.enabled drawhold|paint|($global.hold_value+2)/2\n?crt $locked=7")
        result, _ = run("6412", descriptor, "scoped-gameplay", "320x240", frames=720,
                        OBOR_CRT_TV="On", OBOR_CRT_TOGGLE_AT=600, OBOR_GAMELOG="On",
                        OBOR_INPUT="150-500:start:pulse")
        assert re.search(r"accepted=1 fps=50\.000000", result), result
        assert re.search(r"accepted=1 fps=60\.000000", result), result
        observations = [tuple(map(int, row)) for row in
                        re.findall(r"POLICY (\d+) (\d+) (\d+) (\d+)", result)]
        held_ticks = [ticks for before, draw, locked, ticks in observations
                      if (before, draw, locked) == (1, 2, 7)]
        assert len(held_ticks) >= 65, result
        assert 48 <= held_ticks[64] - held_ticks[4] <= 52, result
        assert len(observations) >= 60 and all(row[:3] == (1, 2, 4) for row in observations[-20:]), result
        assert 62 <= observations[-1][3] - observations[-20][3] <= 65, result

        print("CRT runtime regressions: OK", flush=True)


if __name__ == "__main__":
    main()
