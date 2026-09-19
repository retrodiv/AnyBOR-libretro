# AnyBOR

An independent libretro core for OpenBOR games, combining engine builds
3400, 3842, 4086, 4432, 6412 and 8020 in one library. The core selects an
engine for the content and supports save states, rewind and four players.
OpenBOR, Senile Team and libretro credits identify upstream work; they do
not imply endorsement of this port.

Original AnyBOR work by retrodiv is [BSD-3-Clause-licensed](LICENSE). Bundled engines and
dependencies retain their own licenses. The combined core includes OpenBOR 3400,
whose license requires prior written permission for sale of the combined sources
or binaries. See [licensing and redistribution](LICENSES.md) for the full scope.

## Build

This repository contains the complete core and dependency sources. Builds
require no network access and no other project checkout. On a Linux build
host, install GNU make, GCC/G++, binutils, Python 3.5 or later and NASM for
x86-64. A current Python release is recommended; 3.5 compatibility supports
older libretro build images. Configure scripts are included; autoreconf is
not required.

```sh
make -j8                         # native Linux x86-64 or ARM64
make platform=win64              # MinGW-w64 x86-64 cross toolchain
make TARGET=linux-aarch64        # GNU ARM64 cross toolchain
make TARGET=recalbox-aarch64     # ARM64, GLIBC ceiling 2.38
ANDROID_NDK=/path/to/ndk make platform=android
make platform=osx                # native macOS, Intel or Apple Silicon
make check
make release                    # ZIP and SHA-256 file under dist/
make source-release             # optional source tar.gz; also included in each release ZIP
```

The libraries are named `anybor_libretro.so`, `anybor_libretro.dll`,
`anybor_libretro_android.so` and `anybor_libretro.dylib`. `CC`, `CXX`, `AR`,
`LD`, `OBJCOPY`, `STRIP`, `CFLAGS`, `CXXFLAGS`, `LDFLAGS` and `NASM` can select
an installed toolchain. On macOS the build selects `clang`/`clang++` and the
system linker, and accepts the `LIBRETRO_APPLE_PLATFORM` and
`LIBRETRO_APPLE_ISYSROOT` variables the libretro `osx-arm64` recipe exports.
Set `NUMPROC` or `JOBS` to limit parallel compilation, and `OBOR_BUILD_ROOT`
to move temporary outputs outside this directory. Dependencies are built
from `src/deps/`; there is no download or prebuilt-library fallback.

Only 64-bit x86 and ARM targets are supported. Android uses ARM64 and API 24
or later. macOS targets Intel (10.13 or newer) and Apple Silicon (11.0 or
newer) and links only against `libSystem`. `jni/Android.mk` and
`jni/Application.mk` provide the ndk-build entry point used by the libretro
Android runner. `.gitlab-ci.yml` uses the libretro CI templates; GitHub Actions
also compiles and packages the core, including native macOS Intel and Apple
Silicon jobs.
Availability in RetroArch's Core Updater is managed by the libretro project.
The required submission files, target commands and external registration steps
are listed in [docs/PUBLISHING.md](docs/PUBLISHING.md). The core's frontend
requirements, controls and options are in [docs/ANYBOR.md](docs/ANYBOR.md).

## Content

Load a `.pak`, an unpacked game's `data/models.txt`, or a ZIP containing one
game. ZIP entries are checked before extraction. A content-adjacent engine
executable can be inspected as data for version selection; the core does
not execute that file. The `.txt` extension is for `data/models.txt`, not
arbitrary text documents. Newer engine versions are supported on a best
effort basis through the latest pinned engine.

No third-party game data, artwork, music, BIOS or game executables are included. Use
content you are entitled to use. Engine compatibility does not grant rights
to redistribute a game's assets. Saves use the directory supplied by the
frontend, under `AnyBOR/<game>/<engine build>/`; ZIP extraction uses
`AnyBOR-cache/zipcache/`. Save states require the same core build and content.

See [installation and data directories](docs/INSTALLATION.md) for frontend
setup, external INI configuration and backup guidance.

## Save states and rewind

Snapshots retain the running engine's writable state, complete allocated
game heap and live coroutine stack. The inactive engines' zero-initialized
data is excluded using linker-owned boundaries; shared data is retained.
A frontend that supports variable serialization sizes may receive a larger
state while content is loaded. On fixed-capacity frontends, the advertised
size stays fixed until content unload, even across Reset. Unused transport
bytes are deterministically zero, without rewriting reserve pages that are
already zero. There is no per-frame general compression stage or dependency
on an earlier snapshot.

Save states use the OBS v1 format. Games may grow their heap substantially
during play: the core records its observed peak for sizing the next session
and retains a growth allowance. Before the first recorded peak, packed
resource size also informs the initial reserve so menu-only allocations do
not set an unnecessarily small gameplay budget. The resource hint adds at
most 32 MiB before alignment, limiting the cost of large archives with mostly
music. These are estimates, not a guarantee of every possible later
allocation. On a fixed-capacity frontend, if a game exceeds that allowance,
restart the content to use the learned peak.
Saving, loading and rewind are unavailable during threaded video playback.
Frontend rewind history length also depends on its buffer size and the
amount of state that changes each frame.

## Video options

`Video > Adjust for 4:3 CRT TV` defaults to `Off`. With it enabled, games keep
their native resolution, aspect and pixels when their width is at most 364,
their height is at most 244, and their aspect is within 4:3 +/-10%
(inclusive 1.2 through 22/15, approximately 1.4666667). Small images outside
that interval receive centred black padding on one axis to reach 4:3 without
resampling. Fractional extents round up; opposite borders may differ by one
pixel. The size limits are then checked again, including the padding.
If the width is greater than 364 **or** the height is greater than 244,
the complete original image is
scaled to fit inside a 640x480 frame with a 4:3 display aspect. The image keeps
its original aspect ratio without cropping. Wider-than-4:3 images have centred
black borders above and below; narrower images have borders on the left and
right. An exact 4:3 image fills the frame.

For example, 320x180 becomes 320x240 with 30 black rows above and below;
320x200 becomes 320x240 with 20 rows on each side. A square 240x240 image
becomes 320x240 with 40 black columns at each side. A 360x180 image would
need 360x270, exceeding the height limit, so it instead becomes a 640x320
image inside 640x480 with 80 black rows above and below. Likewise, 364x244
requires padding and then a 640x480 frame. A 368x240 image becomes 640x417,
while 320x256 becomes 600x480. Each dimension is checked independently.

With the option set to `On`, the standard OpenBOR video modes become:

| Mode | Internal resolution | Original aspect | Output frame | Game image inside the frame | Black borders: top / bottom |
|---|---|---|---|---|---|
| 0 | 320x240 | 4:3 | 320x240 | 320x240 (native) | None |
| 1 | 480x272 | Approximately 16:9 | 640x480 | 640x362 | 59 / 59 pixels |
| 2 | 640x480 | 4:3 | 640x480 | 640x480 (identity scale) | None |
| 3 | 720x480 | 3:2 | 640x480 | 640x426 | 27 / 27 pixels |
| 4 | 800x480 | 5:3 | 640x480 | 640x384 | 48 / 48 pixels |
| 5 | 800x600 | 4:3 | 640x480 | 640x480 | None |
| 6 | 960x540 | 16:9 | 640x480 | 640x360 | 60 / 60 pixels |

With `Off`, each mode keeps its internal resolution as the output frame,
without borders added by the core. With `On`, mode 0 stays below both limits
and **remains 320x240**. Mode 2 uses the 640x480 frame at identity scale and
also keeps its native pixels. The other modes are scaled to the image
dimensions above, without cropping. Scaled dimensions are truncated to whole pixels, giving
362 image lines in mode 1 and 426 in mode 3. None of these seven modes gains
left or right borders.

The output frame and border sizes refer to pixels submitted to the frontend,
not the physical CRT scan mode.
Changes apply during play. Scaling uses
sharp bilinear: integer enlargements stay crisp, while fractional scales
interpolate at pixel edges to reduce uneven text strokes and scrolling shimmer.
This changes the image submitted to the frontend; it does not reduce the
engine's internal drawing resolution or guarantee a frame rate.
The frontend controls the physical TV mode and interlacing;
use the core-provided aspect ratio or 4:3 in its video settings.

## Licenses and redistribution

The combined core has multiple licenses. **Engine 3400 prohibits sale of its
source and binaries, including modified versions, without specific prior
written permission from the OpenBOR Team.** Free redistribution must retain
its terms and all other applicable notices. The port's BSD-3-Clause license does not
replace engine or dependency licenses. Read [LICENSES.md](LICENSES.md).

`make release` packages the exact binary with its license dossier, build
receipt and matching sources in a `source.tar.gz`. `PACKAGE.json` records the
binary and source-archive hashes. The complete dossier is also embedded in every core library; when content is
loaded, the core attempts to write it as `anybor-license-notices.txt` in the
frontend's save directory. This preserves access to notices
when an updater transports a bare DLL/SO. `NOTICE.txt` is the same dossier
in readable form. Redistributors should include that file and `LICENSES/`
with their downloads.

The original diagnostic fixture generator and native smoke test are described
in [docs/TESTING.md](docs/TESTING.md).

See [MODIFICATIONS.md](MODIFICATIONS.md) for changes from the six pinned
OpenBOR builds, with file inventories and source references,
[PROVENANCE.md](PROVENANCE.md) for source origins,
[CONTRIBUTING.md](CONTRIBUTING.md) for development, and
[SECURITY.md](SECURITY.md) for content trust and private reporting.

## Optional content preparation

Optional buffer transforms can extract an archive from a custom header or a
specified byte range, or convert stored 32-bit words to the byte order expected
by the reader. Select an adapter in the frontend system directory's `AnyBOR.ini`.
See [configuration and examples](docs/CONTENT_TRANSFORMS.md).
