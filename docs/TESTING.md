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
python3 tools/test_rewind.py
python3 tools/test_multiplayer.py
```

The smoke test generates a tiny diagnostic PAK from original scripts and
geometric graphics in `tools/make_fixture.py`, under the project's BSD
license. The synthetic font consists of simple rectangular markers. No
existing game or font artwork is copied. It loads the content with all six
engines and checks frame output, working-directory restoration and the
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
and exercise content unload, restart and a refused state load during threaded
playback. The host remains alive after unload so abandoned workers cannot
escape detection merely because the test process exits immediately.
Saving and loading states are unavailable while threaded playback is active;
a refused load leaves the current playback intact.

The native host in `tests/host/` can also load a user-supplied PAK. Its header
documents scripted input, save-state and capture controls. Keep third-party
games, captures and diagnostic output out of source commits. Inspect captures
before sharing them, as described in `DEBUGGING.md`.

The CRT suite checks the Video / Input / System category order, matching flat
option order on legacy frontends, disabled default,
black borders and pixel output against native frames in all six engines.
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
all six engines are compared against the same independent reference.

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

The rewind suite checks all six engines using a capacity obtained before
the first frame. It compares complete frame hashes while stepping backwards,
restores a state in a fresh process, toggles CRT adaptation, resets and
switches engines through Reset. Capacity must remain constant and every
capture/restore must succeed. Deliberately dirty, guarded buffers check OBS v1
layout, active-engine segment size and zeroed padding; invalid-version and
truncated snapshots must be rejected. Optional `--host`, `--runner` and
`--windows` arguments allow the same cases to run under an emulator or Wine.
Primitive tests compare padding cleanup against `memset` for all lengths
through 2048, sixteen alignments, zero, dirty and sparse patterns.
These short synthetic cases are contract tests, not full game playthroughs.

The multiplayer suite joins four players in an original diagnostic game on
all six engines. Game scripts report held buttons and press/release edges
for each player. The suite checks isolated and simultaneous buttons, left
sticks, combined stick/D-pad directions and saved configurations. Engine
8020 also checks migration of legacy unbound P2-P4 profiles from game and
default configurations, while preserving custom mappings and unrelated
settings. The host accepts independent `OBOR_INPUT_P1` through
`OBOR_INPUT_P4` timelines; `OBOR_INPUT` remains available for player one.
Optional `--host`, `--runner` and `--windows` arguments support the same
checks under emulation or Wine. These tests inject virtual RetroPad inputs;
physical controller pairing remains the frontend's responsibility.
