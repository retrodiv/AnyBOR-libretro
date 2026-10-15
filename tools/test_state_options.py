#!/usr/bin/env python3
"""Check load-time state options and independent restoration across writers.

Only original geometric content is used. A relocated module image must be
refused in every mode, preserving the current video/PCM continuation.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

import make_fixture
import release
from smoke import compile_host
from test_rewind import DEFAULT_CORE, dedicated_wine
from runtime_evidence import record_process

MODES = (("Smart", "On"), ("Smart", "Off"), ("Full", "On"), ("Full", "Off"))


def lz4_block(data, expected):
    """Decode one bounded test record, without a host liblz4 dependency."""
    out = bytearray()
    at = 0
    def length(value):
        nonlocal at
        if value == 15:
            while True:
                if at >= len(data):
                    raise ValueError("truncated LZ4 length")
                extra = data[at]
                at += 1
                value += extra
                if extra != 255:
                    break
        return value
    while at < len(data):
        token = data[at]
        at += 1
        count = length(token >> 4)
        if count > len(data) - at or count > expected - len(out):
            raise ValueError("invalid LZ4 literals")
        out += data[at:at + count]
        at += count
        if at == len(data):
            break
        if at + 2 > len(data):
            raise ValueError("truncated LZ4 distance")
        distance, = struct.unpack_from("<H", data, at)
        at += 2
        count = length(token & 15) + 4
        if not 0 < distance <= len(out) or count > expected - len(out):
            raise ValueError("invalid LZ4 match")
        for _ in range(count):
            out.append(out[-distance])
    if len(out) != expected:
        raise ValueError("incorrect LZ4 size")
    return bytes(out)


def state_head(path):
    """Inspect the real writer's OBS header inside its optional OBC1 envelope."""
    with path.open("rb") as stream:
        capacity, = struct.unpack("<Q", stream.read(8))
        if capacity != path.stat().st_size - 8 or not 112 <= capacity <= 2 << 30:
            raise ValueError("invalid host state length")
        head = stream.read(112)
        codecs = None
        if head[:4] == b"OBC1":
            blocks, = struct.unpack_from("<I", head, 12)
            if not 0 < blocks <= (2 << 30) // 16384:
                raise ValueError("invalid block count")
            stream.seek(8 + 32)
            table = stream.read(blocks * 24)
            if len(table) != blocks * 24:
                raise ValueError("truncated block table")
            codecs = [0, 0, 0]
            for at in range(0, len(table), 24):
                codec, = struct.unpack_from("<I", table, at + 16)
                if codec > 2:
                    raise ValueError("invalid codec in table")
                codecs[codec] += 1
            offset, stored, slot, raw, codec, crc = struct.unpack_from("<6I", head, 32)
            if not 112 <= raw <= 16384 or not 0 < stored <= slot <= 16384 or offset + slot > capacity:
                raise ValueError("invalid first state block")
            stream.seek(8 + offset)
            block = stream.read(stored)
            if codec == 2:
                inflater = zlib.decompressobj()
                block = inflater.decompress(block, raw + 1)
                if not inflater.eof or inflater.unconsumed_tail or inflater.unused_data:
                    raise ValueError("invalid DEFLATE block")
            elif codec == 1:
                block = lz4_block(block, raw)
            elif codec != 0:
                raise ValueError("invalid codec")
            if len(block) != raw or zlib.crc32(block) != crc:
                raise ValueError("invalid decoded block")
            head = block[:112]
        if head[:4] != b"OBS1":
            raise ValueError("missing engine state")
        version, = struct.unpack_from("<I", head, 4)
        image_lo, image_hi = struct.unpack_from("<QQ", head, 24)
        return dict(version=version, image_lo=image_lo, image_hi=image_hi, capacity=capacity, codecs=codecs)


def relocated_state(source, destination):
    """Preserve a valid envelope but declare an impossible zero-based module.

    This specifically exercises the address preflight, not CRC rejection.
    A small displacement could coincide with a new process's ASLR base: its
    unchanged pointers would then be accepted under a false module identity.
    A running shared core cannot occupy address zero. Keep relative segment
    offsets and the image extent valid, and never change the original file.
    """
    header = state_head(source)
    if header["version"] not in (7, 9):
        raise ValueError("expected Full or Smart state")
    if not 0 < header["image_lo"] < header["image_hi"]:
        raise ValueError("expected a nonzero source module")
    shutil.copyfile(source, destination)
    with destination.open("r+b") as stream:
        stream.seek(8)
        head = bytearray(stream.read(56))
        compressed = head[:4] == b"OBC1"
        if compressed:
            offset, stored, slot, raw, codec, crc = struct.unpack_from("<6I", head, 32)
            stream.seek(8 + offset)
            block = stream.read(stored)
            if codec == 2:
                inflater = zlib.decompressobj()
                block = inflater.decompress(block, raw + 1)
                if not inflater.eof or inflater.unconsumed_tail or inflater.unused_data:
                    raise ValueError("invalid relocation source block")
            elif codec == 1:
                block = lz4_block(block, raw)
            elif codec != 0:
                raise ValueError("invalid relocation source codec")
            if len(block) != raw or zlib.crc32(block) != crc:
                raise ValueError("invalid relocation source CRC")
        else:
            stream.seek(8)
            block = stream.read(min(header["capacity"], 16384))
        block = bytearray(block)
        segments, = struct.unpack_from("<I", block, 16)
        if not 0 < segments <= 16 or 112 + segments * 16 > len(block):
            raise ValueError("invalid relocation source table")
        for field in (24, 32, *(112 + n * 16 for n in range(segments))):
            value, = struct.unpack_from("<Q", block, field)
            if not header["image_lo"] <= value <= header["image_hi"]:
                raise ValueError("invalid relocation source address")
            struct.pack_into("<Q", block, field, value - header["image_lo"])
        if not compressed:
            stream.seek(8)
            stream.write(block)
            return
        used, = struct.unpack_from("<I", head, 20)
        end = used + ((raw + 255) // 256) * 256
        if end > header["capacity"]:
            raise ValueError("no bounded space for relocation probe")
        stream.seek(8 + offset)
        stream.write(bytes(slot))
        stream.seek(8 + used)
        stream.write(block)
        stream.write(bytes(end - used - raw))
        struct.pack_into("<I", head, 20, end)
        struct.pack_into("<6I", head, 32, used, raw, end - used, raw, 0, zlib.crc32(block))
        stream.seek(8)
        stream.write(head)


def pcm_records(path, repetitions=1):
    data = path.read_bytes()
    if not 0 < len(data) <= 32 << 20:
        raise ValueError("missing or excessive PCM")
    offset, records = 0, []
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError("truncated PCM")
        frame, count = struct.unpack_from("=II", data, offset)
        end = offset + 8 + count * 4
        if not 0 < count <= 32768 or end > len(data):
            raise ValueError("invalid PCM record")
        records.append((frame, data[offset + 8:end]))
        offset = end
    if [r[0] for r in records] != list(range(121, 321)) * repetitions:
        raise ValueError("incomplete 200-frame PCM continuation")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default=str(DEFAULT_CORE))
    parser.add_argument("--host")
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--runner", default="")
    parser.add_argument("--keep-wine-server", action="store_true")
    parser.add_argument("--work-parent")
    args = parser.parse_args()
    if args.keep_wine_server and (not args.windows or args.runner != "wine" or not args.work_parent):
        parser.error("--keep-wine-server requires --windows --runner wine --work-parent")
    core = Path(args.core).resolve()
    with dedicated_wine(args.keep_wine_server, args.work_parent), tempfile.TemporaryDirectory(
            prefix="anybor-state-options-", dir=args.work_parent) as directory:
        work = Path(directory)
        host = Path(args.host).resolve() if args.host else work / ("host.exe" if args.windows else "host")
        if not args.host:
            compile_host(release.ROOT, host, args.windows)
        pak = work / "diagnostic.pak"
        make_fixture.write_pak(pak, make_fixture.files())
        default = MODES[0] if args.windows or sys.platform == "linux" else MODES[3]

        def target(path):
            return "Z:" + str(path).replace("/", "\\") if args.windows else str(path)

        def run(profile, label, mode, same_session=False, **options):
            root = work / (profile + "-" + label)
            root.mkdir()
            # Save a late snapshot too: restoration must not change the writer
            # selected for this session, including its resource-content policy.
            output = root / "current.state"
            env = {k: v for k, v in os.environ.items() if not k.startswith("OBOR_")}
            env.update(OBOR_ENGINE=profile, OBOR_SKIP_LOADING="1", OBOR_OPTIONS_VERSION="2",
                       OBOR_FIXED_STATE_FRONTEND="1", OBOR_VIDEO_TRACE="1",
                       OBOR_STATE_CHECK="1", OBOR_STATE_CHECK_EVERY="1000000",
                       OBOR_REPLAY_TRACE="121,320", OBOR_REPLAY_AUDIO=target(root / "audio.pcm"),
                       OBOR_SAVE_AT="320", OBOR_SAVE_STATE=target(output))
            if mode is not None:
                env.update(OBOR_HOST_STATE_CONTENT=mode[0], OBOR_HOST_STATE_COMPRESSION=mode[1])
            if args.windows:
                env.update(OBOR_CHECK_UNLOAD_EXCEPTIONS="1", OBOR_PROCESS_RUNTIME_PADDING="5")
            else:
                env["OBOR_CHECK_FDS"] = "1"
            env.update({k: target(v) if isinstance(v, Path) else str(v) for k, v in options.items()})
            nframes = 521 if same_session else 321
            source = options.get('OBOR_LOAD_STATE')
            input_header = state_head(Path(source)) if source and Path(source).exists() else None
            result = subprocess.run(shlex.split(args.runner) + [str(host), target(core), target(pak),
                target(root), str(nframes)], env=env, cwd=work, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=90)
            record_process('state-options', profile + '-' + label, result,
                           dict(mode=mode, input_header=input_header))
            log = result.stdout + result.stderr
            if result.returncode or "frames=" + str(nframes) + " " not in log or "invalid_version_and_truncation_rejected=1" not in log:
                raise RuntimeError(label + ": " + log)
            required = "post_unload_exception_safe=1" if args.windows else "file_descriptors_restored=1"
            if required not in log:
                raise RuntimeError(label + ": " + log)
            for key, title, values, chosen in (
                    ("content", "Save state content", "Smart|Full", default[0]),
                    ("compression", "Save state compression", "On|Off", default[1])):
                marker = "state_option=obor_state_" + key + " label=" + title + " category=system default=" + chosen + " values=" + values
                if marker not in log:
                    raise RuntimeError("state option metadata: " + log)
            frames = re.findall(r"^replay_frame source=.*$", result.stdout, re.M)
            repetitions = 2 if same_session else 1
            if len(frames) != 200 * repetitions:
                raise RuntimeError("incomplete video continuation: " + log)
            pcm = pcm_records(root / "audio.pcm", repetitions)
            if same_session and (frames[:200] != frames[200:] or pcm[:200] != pcm[200:]):
                raise RuntimeError("same-session restoration changed video or complete PCM: " + label)
            saved = Path(options.get("OBOR_SAVE_STATE", output))
            header = state_head(saved)
            expected = mode or default
            if header["version"] != (9 if expected[0] == "Smart" else 7):
                raise RuntimeError("writer selection changed: " + label + " " + str(header))
            if (header['codecs'] is None) != (expected == MODES[3]):
                raise RuntimeError("compression transport selection changed: " + label)
            if 'OBOR_LOAD_AT' not in options and header['codecs'] is not None:
                # Off retains compact initial slots (LZ4) and writes changed
                # blocks raw. Unchanged slots must not be required to expand.
                codec = 1 if expected[1] == 'On' else 0
                if not header['codecs'][codec]:
                    raise RuntimeError("mutable codec selection changed: " + label + " " + str(header))
            print("PASS", profile, label, "writer=" + str(header["version"]), flush=True)
            return dict(frames=frames[-200:], pcm=pcm[-200:], log=log,
                        state=saved, header=header)

        def equal(left, right, label):
            if left["frames"] != right["frames"] or left["pcm"] != right["pcm"]:
                raise RuntimeError(label + ": video or complete PCM continuation differs")

        profiles = release.read_json(release.ROOT / "src/pin.json")["profiles"]
        for entry in profiles:
            profile = entry["build"]
            reference = run(profile, "default", None)
            explicit = run(profile, "explicit-default", default)
            equal(reference, explicit, profile + " default options")
            for content, compression in MODES:
                mode = (content, compression)
                label = content + "-" + compression
                state = work / (profile + "-" + label + ".state")
                original = run(profile, label + "-save", mode, OBOR_SAVE_AT=120, OBOR_SAVE_STATE=state)
                # Always exercise actual restoration in every writer, including
                # ASLR hosts where independent-process loads may all be refused.
                # Advance 200 frames before loading, then replay the same input
                # timeline; a reader that merely returns success cannot pass.
                session_state = work / (profile + "-" + label + "-same-session.state")
                session = run(profile, label + "-same-session", mode, same_session=True,
                              OBOR_SAVE_AT=120, OBOR_SAVE_STATE=session_state,
                              OBOR_LOAD_AT=320, OBOR_LOAD_STATE=session_state,
                              OBOR_LOAD_SOURCE_FRAME=120)
                if "load state at frame 320: ok" not in session["log"] or not \
                        re.search(r"saved state \(\d+ bytes\) at frame 120", session["log"]):
                    raise RuntimeError("same-session load failed: " + session["log"])
                equal(original, session, profile + " " + label + " same-session load")
                session_state.unlink()
                for reader in MODES:
                    restored = run(profile, label + "-to-" + "-".join(reader), reader,
                                   OBOR_LOAD_AT=120, OBOR_LOAD_STATE=state)
                    displaced = original["header"]["image_lo"] != restored["header"]["image_lo"]
                    if displaced:
                        # Neither writer carries exact pointer relocation data.
                        # Do not relabel refusal as successful restoration.
                        if "load state at frame 120: FAILED" not in restored["log"] or \
                                "state module address differs" not in restored["log"]:
                            raise RuntimeError("unsafe relocated restoration: " + restored["log"])
                        equal(reference, restored, profile + " rejected state changed playback")
                        print("LIMIT", profile, label, "relocated module refused; current continuation intact", flush=True)
                    else:
                        if "load state at frame 120: ok" not in restored["log"]:
                            raise RuntimeError("cross-writer load refused: " + restored["log"])
                        equal(original, restored, profile + " " + label + " cross-writer load")
                    restored["state"].unlink()
                rejected_state = work / (profile + "-displaced.state")
                relocated_state(state, rejected_state)
                rejected = run(profile, label + "-displaced-rejected", mode,
                               OBOR_LOAD_AT=120, OBOR_LOAD_STATE=rejected_state)
                if "load state at frame 120: FAILED" not in rejected["log"] or \
                        "state module address differs" not in rejected["log"]:
                    raise RuntimeError("missing address refusal: " + rejected["log"])
                equal(reference, rejected, profile + " displaced state refusal changed playback")
                rejected_state.unlink()
                rejected["state"].unlink()
                if profile == "4432" and mode == MODES[3]:
                    padded = work / "full-larger-than-smart.state"
                    shutil.copyfile(state, padded)
                    capacity = max((65 << 20), original["header"]["capacity"])
                    with padded.open("r+b") as stream:
                        stream.write(struct.pack("<Q", capacity))
                        stream.truncate(8 + capacity)
                    loaded = run(profile, "large-full-to-smart", MODES[0],
                                 OBOR_LOAD_AT=120, OBOR_LOAD_STATE=padded)
                    if original["header"]["image_lo"] != loaded["header"]["image_lo"]:
                        if "load state at frame 120: FAILED" not in loaded["log"] or \
                                "state module address differs" not in loaded["log"]:
                            raise RuntimeError("unsafe relocated larger state: " + loaded["log"])
                        equal(reference, loaded, "rejected large Full state changed playback")
                    else:
                        if "load state at frame 120: ok" not in loaded["log"]:
                            raise RuntimeError("writer capacity rejected a valid larger state: " + loaded["log"])
                        equal(original, loaded, "large Full state into Smart")
                    padded.unlink()
                    loaded["state"].unlink()
                other = ("Full" if content == "Smart" else "Smart", "Off" if compression == "On" else "On")
                latched = run(profile, label + "-latched-reset", mode,
                              OBOR_SET_STATE_OPTIONS_AT="60:" + ":".join(other), OBOR_RESET_AT=80,
                              OBOR_STATE_CHECK_EVERY=80)
                if "frontend_state_options=" + "+".join(other) not in latched["log"]:
                    raise RuntimeError("missing frontend option change")
                latched["state"].unlink()
                state.unlink()
            reference["state"].unlink()
            explicit["state"].unlink()
        print("State options:", len(profiles), "profiles, four writers, independent cross-mode video/PCM and load-time latch: OK", flush=True)


if __name__ == "__main__":
    main()
