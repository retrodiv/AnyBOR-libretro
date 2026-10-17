# Testing

`make check` validates the exported file inventory, engine/dependency
provenance and license dossier, then tests circle rasterization and IMA
ADPCM format vectors, fixed-width endian conversions and portable ZIP path
validation and CRT framing using a host C compiler. It does not require games.
It also validates the core-info capability/version contract and the required
publication entry points. `make release` includes an exact source tar.gz in
each platform ZIP and reopens both archives to verify their contents.
`make source-release` produces the same source archive on explicit request.
Binary checks fail if the inspection tool is missing, fails, or finds an
incorrect format, architecture, dependency or exported interface.

`make release` checks source integrity before compiling. CI checks the committed
source inventory before starting any platform build. Enable the local push check
with `git config core.hooksPath .githooks`; it checks the exact outgoing revisions,
including tags and branches other than the current checkout. It catches stale
manifests even when the working copy has already been repaired. Run it explicitly
with `python3 tools/check_revision.py HEAD`.

After a native Linux build, run:

```sh
python3 tools/smoke.py
python3 tools/regression.py
python3 tools/regression.py --webm  # also requires host ffmpeg
python3 tools/test_crt.py
python3 tools/test_geometry.py --core anybor_libretro.so
python3 tools/test_rewind.py
python3 tools/test_state_options.py
python3 tools/test_multiplayer.py
python3 tools/test_6330_6510.py --core anybor_libretro.so
python3 tools/test_animation_scripts.py --core anybor_libretro.so
python3 tools/test_script_timestamps.py
```

The state-option suite checks all published profiles, four writers and four readers,
with 200-frame video and complete PCM comparisons. A valid snapshot whose
declared module and segment addresses have moved must be refused in every
mode without changing playback. Native cross-process tests read both snapshot
headers: loads must succeed when the bases match and must explicitly refuse
when they differ. This includes the temporary macOS ASLR limitation; an
unexplained load failure never counts as success.
Each writer must also restore successfully in the same process after 200
frames of forward play and reproduce that continuation exactly.

Linux CI runs the shared-profile checks automatically. The inline-script
fixture allocates 260 padding animations, then requires a countdown to finish
and load the next level under 6330, 6391, 6412 and 6510. The timestamp check
compiles the actual getter and setter branches and checks each against the
engine field independently, so inverse conversion mistakes cannot cancel out.

The smoke test generates a tiny diagnostic PAK from original scripts and
geometric graphics in `tools/make_fixture.py`, under the project's BSD
license. The synthetic font consists of simple rectangular markers. No
existing game or font artwork is copied. It loads the content with all published
profiles and checks frame output, working-directory restoration and the
runtime license document, signal-handler restoration and arena release on
module unload. This checks basic engine boot/rendering; it does
not claim compatibility with every game.

Each engine boots in a new process with fresh saves and then again with existing
saves; a user-data marker must survive the second run. Windows CI executes the
same cases under Wine using a MinGW-built host:

```sh
python3 tools/smoke.py --core anybor_libretro.dll --windows --runner wine
```

`--host` accepts a precompiled host. Native macOS CI runs on both Intel and Apple
Silicon. On Linux, `tools/run_guarded.py --memory-mib 2048 --seconds 900 -- COMMAND`
bounds a runtime process tree using cgroup memory, with swap disabled. Use 1024 MiB
for small regression suites and 6144 MiB / 1800 seconds with at most four compiler
jobs for builds. The guard requires a working systemd user manager and refuses an
unlimited fallback.

The regression suite saves with Forward game log enabled and loads in new
processes with that option both on and off, then restarts the content. It
also repeats state loads with extra frontend files open and runs nine
consecutive restarts. Linux hosts check that all file descriptors are
released after module unload; the frontend's own files must remain usable.
It also checks the memory-peak files for packed and unpacked games. The WebM
cases generate original solid-color VP8 video, with and without a sine tone,
and exercise content unload, restart and restoration of a valid pre-movie
state during threaded playback. Every decoder worker must join before live
memory is restored. The host remains alive after unload so abandoned workers
cannot escape detection merely because the test process exits immediately.
Capturing an active threaded movie remains unavailable. Invalid loads must
leave the current playback intact.

The native host in `tests/host/` can also load a user-supplied PAK. Its header
documents scripted input, save-state and capture controls. Keep third-party
games, captures and diagnostic output out of source commits. Inspect captures
before sharing them, as described in `DEBUGGING.md`.

The geometry suite uses original scripted 320x200 and 2048x1152 screens. It
checks the union of native and CRT bounds before the first frame, one-time
growth, smaller modes, live toggles, AV-info refusal with geometry fallback,
uncropped pixels and exact video/PCM after load and reverse playback. A ZIP
checks the 1920x1080 initial fallback before the raster is known.

For the RISC-V GNU toolchain and user emulator, run the guarded
`tools/test_riscv64.py` with an explicit `--runner` if its sysroot is elsewhere.
Adding `--core anybor_libretro.so` also checks cold state loads at the fixed
Sv39-compatible base and real reverse-frame output. The context fixture covers
all preserved integer and floating-point registers, FCSR and a restored stack.
Protected-page fixtures use the production RISC-V enablement and fixed arena,
cover CPU and kernel-I/O writes, unchanged-page proofs, registered workers,
hot-page learning and foreign-signal forwarding. Execution faults, including
an instruction straddling an executable/NX boundary, must not dirty the data.
These tests do not constitute validation on physical RISC-V hardware.

The CRT suite checks the Video / Input / System category order, matching flat
option order on legacy frontends, disabled default,
black borders and pixel output against the captured native frames.
Output must remain byte-identical to disabled output when its width is at
most 364, its height is at most 244, and its aspect is within inclusive
4:3 +/-10%. Smaller images outside that tolerance receive native-pixel black
padding on one axis, with fractional extents rounded up, followed by another
size-limit check. Exceeding either limit requires fitting the complete image inside 640x480, preserving
its aspect with centred black borders and a 4:3 output aspect. Cases cover
the 364x244 boundary after padding, both exact tolerance endpoints and their
pixel neighbours, wide and narrow native padding, unequal borders, independent
width-only and height-only crossings, both limits exceeded, 800x600, 800x601,
square 800x800, portrait 600x800 and widescreen 1280x720 frames. Primitive
tests exercise the exact 365-pixel crossing; runtime tests use 368 pixels
because engine screens round widths down to a multiple of four. Their full
pixel output is compared against independently filtered native frames.
Native padding must preserve every source pixel exactly and clear all borders;
320x180 remains 320x240, while 360x180 crosses the padded height limit and
uses 640x480. Live toggles, resets and state loads also exercise native padding.
The suite also
toggles adaptation during play, restarts, and loads states from a
separate process while keeping the current video option. The primitive tests
include exact 16:9, near-16:9, 4:3, narrow and portrait frames, padded source
rows, and consecutive frames whose borders differ.
Sharp-bilinear filtering is checked against an independent floating-point
texture-sampling reference, allowing at most one 8-bit channel level for Q16
and separable rounding. Coverage includes fractional enlargement, reduction,
integer/identity sampling, clamped edges, very narrow/tall images, and six
horizontal-scroll phases of one-pixel strokes at 480x272. Runtime frames from
the tested engines are compared against the same independent reference.

On the Linux and macOS hosts, `OBOR_CHECK_FDS=1` checks that the number of open
file descriptors returns to its baseline after unloading the core. Linux uses
procfs; macOS queries descriptor validity through POSIX `fcntl`. Both hosts
check arena reservations without replacing existing memory mappings.

`OBOR_OCCUPIED_ARENA=1` checks that a pre-existing mapping
is preserved when content loading is refused. `OBOR_LIFECYCLE=1` unloads and
reloads the module; combine it with `OBOR_DEBUG=1` and `OBOR_RESET_AT=180` to
exercise diagnostic cleanup across restarts. `OBOR_FASTCHECK=120,30` compares
the incremental heap/stack payload against a fresh full snapshot. Module
bookkeeping and unused buffer tails are intentionally outside that comparison.

The rewind suite checks all published profiles using a capacity obtained before
the first frame. It compares complete frame hashes while stepping backwards,
restores a state in a fresh process, toggles CRT adaptation, resets and
switches engines through Reset. Capacity must remain constant and every
capture/restore must succeed. Deliberately dirty, guarded buffers check OBS v3
layout, active-engine segment size and zeroed padding; invalid-version and
truncated snapshots must be rejected. Optional `--host`, `--runner` and
`--windows` arguments allow the same cases to run under an emulator or Wine.
Primitive tests compare padding cleanup against `memset` for all lengths
through 2048, sixteen alignments, zero, dirty and sparse patterns.
These short synthetic cases are contract tests, not full game playthroughs.

The multiplayer suite joins four players in an original diagnostic game.
Game scripts report held buttons and press/release edges
for each player. The suite checks isolated and simultaneous buttons, left
sticks, combined stick/D-pad directions and saved configurations. Engine 8023
also checks independent saved device mappings and recovery from a truncated
controls file. The host accepts independent `OBOR_INPUT_P1` through
`OBOR_INPUT_P4` timelines; `OBOR_INPUT` remains available for player one.
Optional `--host`, `--runner` and `--windows` arguments support the same
checks under emulation or Wine. These tests inject virtual RetroPad inputs;
physical controller pairing remains the frontend's responsibility.

The native runtime regression also compiles authored historical player-property
calls in every profile using engine 3842, on both sides of the rejected-value
contract boundary. It separately checks complete script variable names across the former 24-byte
boundary for every published profile. Names with the same prefix must remain
distinct, and the script must continue with the exact values stored in each
name across LOAD, reset and a fresh host process. Native unit tests also check
allocation failure, slot reuse and cleanup. Ordered level spawn scripts use
compiled fixtures on both sides of the 3805 boundary, checking declaration order
and shared versus per-entry locals.
