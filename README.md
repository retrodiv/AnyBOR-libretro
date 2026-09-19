# AnyBOR

An independent libretro core for OpenBOR games, combining engine builds
3400 (2011-08-31), 3842 (2013-02-23), 4086 (2014-11-02), 4432 (2017-01-25),
6412 (2018-08-29) and 8020 (2026-08-24) in one library. Spanning the oldest
build to the newest gives the core maximum compatibility: it automatically
selects the most accurate engine for each .pak, whatever its release date.
Save states, rewind and four players are supported. OpenBOR, Senile Team and
libretro credits identify upstream work; they do not imply endorsement of
this port.

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
NUMPROC=4 make                   # native Linux x86-64 or ARM64
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

Normal builds allow local logs and editor files outside `SOURCES.json`; these
files are not added to the build's source receipt. `make check`, `make release`
and `make source-release` require the checked source inventory. Keep temporary
files under `.build/` or outside the checkout when running publication checks.
For intentional source additions, see [CONTRIBUTING.md](CONTRIBUTING.md).

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
requirements, controls and core options are in [docs/ANYBOR.md](docs/ANYBOR.md).

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
