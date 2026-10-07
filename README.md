# AnyBOR

An independent libretro core for OpenBOR games, offering thirteen selectable
engines in one library: v3.0 3400, v3.0 3842, v3.0 4086, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6412-dev, v3.0 6510-dev, v3.0 7123-dev, v4.0 7142-alpha, v4.0 7533 and v4.0 8023-dev.
Core Options also provides Auto, which uses build tags and content clues to
choose an engine. You can select one manually when a game needs it.
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

Preparation artwork has one source PNG. Builds derive three native-size
backgrounds with Lanczos3 on the host; install Pillow for that host's Python
interpreter when changing the master image or its generator. Unchanged builds
can use the included generated data after validating both input hashes, so
Pillow is not a runtime dependency or required on older build images.

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

External toolchains can set `CONFIGURE_HOST` and `CONFIGURE_BUILD` to the
Autoconf system triplets used by libpng, libogg and libvorbis. For a Buildroot
package, pass `CONFIGURE_HOST="$(GNU_TARGET_NAME)"` and
`CONFIGURE_BUILD="$(GNU_HOST_NAME)"` to Make alongside its toolchain environment.
The host is where the resulting library runs; the build is where compilation
takes place. These settings do not select a compiler or a new AnyBOR target.

`CONFIGURE_HOST=auto` queries the selected `CC` with `-dumpmachine`, including
compiler launchers such as `ccache`. An explicit host also selects the build
triplet using the bundled `config.guess` unless `CONFIGURE_BUILD` is supplied.
`CONFIGURE_BUILD=auto` requests that same detection, honoring `CC_FOR_BUILD`
or `HOST_CC` instead of the cross compiler. Both resolved values invalidate
the dependency cache when changed. With neither setting, existing target
defaults apply.

Direct Python calls accept `--configure-host=TRIPLET|auto` and
`--configure-build=TRIPLET|auto`; command-line values override the environment.
For example:

```sh
CC=x86_64-buildroot-linux-gnu-gcc make TARGET=linux-x86_64 CONFIGURE_HOST=auto
```

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

For rewind in RetroArch, we recommend **Rewind Frames** set to **10** and
**Rewind Buffer Size (MB)** set to **512**. On older RetroArch versions,
keep the rewind buffer larger than twice the core's uncompressed state
capacity: a large transition can otherwise overwrite a history link when
the ring wraps. A 256 MB buffer is insufficient for a 243 MB state, even
when its on-disk compressed save is much smaller. Larger buffers also retain
more history, but keep this setting at or below 512 MB. If the state does
not fit, rewind is unsupported for that state until its representation is
improved; increasing the buffer is not the prescribed workaround.

Snapshots retain the running engine's writable state, complete allocated
game heap and live coroutine stack. The inactive engines' zero-initialized
data is excluded using linker-owned boundaries; shared data is retained.
A frontend that supports variable serialization sizes may receive a larger
state while content is loaded. On fixed-capacity frontends, the advertised
size stays fixed until content unload, even across Reset. Unused transport
bytes are deterministically zero, without rewriting reserve pages that are
already zero. There is no per-frame general compression stage or dependency
on an earlier snapshot.

Contiguous snapshots omit the unused free top of the heap. Fragmented heaps
use the allocator's free-block index to skip large holes while retaining all
live bytes and allocator metadata. Highly fragmented or unsupported layouts
fall back to the ordinary chunk walker. These choices depend on heap layout,
not on the game or the current screen.

The Android core remains one installable `.so`. It contains a small libretro
loader and the engine ELF; Android's `android_dlopen_ext` loads the engine at
a reserved, stable address. This preserves saved code/static-data pointers
without scanning and modifying arbitrary game data after ASLR changes.
An address collision fails safely. States from the older ASLR core are
rejected before restoring engine memory; create new states with this build.

Save states use the OBS v3 format and identify the selected engine.
Games may grow their heap substantially
during play: the core records its observed peak for sizing the next session
and retains a growth allowance. Packed content reserves its initial state
capacity before preparation, using archive size and learned peaks. Captures
become available after resource initialization, which updates the measured
peak even if an older cache contains only startup allocations.
Captures that outgrow a fixed frontend buffer also record the needed heap
without overwriting the previous snapshot. If no measured peak can be read,
packed resource size informs the initial reserve. These are estimates, not
a guarantee of every possible later
allocation. On a fixed-capacity frontend, if a game exceeds that allowance,
restart the content to use the learned peak.
Loading a state retains the current session's content and writable-directory
paths. Engine random-number state is captured with the world so external
frontend activity does not change the restored AI sequence.
Saving, loading and rewind are unavailable during threaded video playback.
Frontend rewind history length also depends on its buffer size and the
amount of state that changes each frame.

An optional AnyBOR frontend interface, declared in `src/glue/obor_rewind.h`,
allows a cooperating Linux ARM64 frontend to register two immutable rewind
buffers and obtain conservative change ranges. Captures remain complete OBS v3
states at the ordinary advertised capacity. The first capture initializes every
byte; subsequent captures copy heap pages changed since that destination was
last used. Ordinary libretro serialization retains complete initialization.
The frontend must end ownership before modifying either buffer or writing
through a cheat/debugger memory map, and before reset or unload. Any load attempt
ends ownership. Protection is suspended before engine workers start; threaded
playback retains its existing capture exclusion. Frontends without this optional
integration continue to use the ordinary serializer. This interface alone does
not establish a game performance result.

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

See [MODIFICATIONS.md](MODIFICATIONS.md) for changes supporting the thirteen
selectable OpenBOR engines, with file inventories and source references,
[PROVENANCE.md](PROVENANCE.md) for source origins,
[CONTRIBUTING.md](CONTRIBUTING.md) for development, and
[SECURITY.md](SECURITY.md) for content trust and private reporting.

## Optional content preparation

An otherwise complete, unencoded PACK with a damaged four-byte signature is
repaired automatically after its directory and plain image assets are validated.
This does not require `AnyBOR.ini`.

Optional buffer transforms can extract an archive from a custom header or a
specified byte range, or convert stored 32-bit words to the byte order expected
by the reader. Select an adapter in the frontend system directory's `AnyBOR.ini`.
See [configuration and examples](docs/CONTENT_TRANSFORMS.md).
