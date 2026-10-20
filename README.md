# AnyBOR

An independent libretro core for OpenBOR games, offering selectable engine profiles: v3.0 3400, v3.0 3780, v3.0 3783, v3.0 3789, v3.0 3793, v3.0
3797, v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0 3829, v3.0
3831, v3.0 3837, v3.0 3839, v3.0 3842, v3.0 4086, v3.0 4088-dev, v3.0 4107,
v3.0 4111, v3.0 4129, v3.0 4153, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6391-mod,
v3.0 6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7086-dev, v3.0 7123-dev,
v4.0 7142-alpha, v4.0 7533 and v4.0 8023-dev.
Core Options also provides Auto, which uses build tags and content clues to
choose a profile. You can select one manually when a game needs it.
See [choosing a profile](docs/HISTORICAL_PROFILES.md) for details.
Save states, rewind and four players are supported. OpenBOR, Senile Team and
libretro credits identify upstream work; they do not imply endorsement of
this port.

Original AnyBOR work by retrodiv is [BSD-3-Clause-licensed](LICENSE). Bundled components and
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
NUMPROC=4 make                   # native Linux x86-64, ARM64 or RISC-V64
make platform=win64              # MinGW-w64 x86-64 cross toolchain
make TARGET=linux-aarch64        # GNU ARM64 cross toolchain
make TARGET=linux-riscv64        # GNU RISC-V64 LP64D cross toolchain
make TARGET=linux-aarch64 GLIBC_MAX=2.38  # optional GNU/Linux ABI ceiling
ANDROID_NDK=/path/to/ndk make platform=android
make platform=osx                # native macOS, x86-64 or ARM64
make check
make release                    # ZIP and SHA-256 file under dist/
make source-release             # optional source tar.gz; also included in each release ZIP
```

The RISC-V target uses the GNU `riscv64-linux-gnu` toolchain and a portable
VP8/VP9 decoder. Its fixed module and arena addresses fit the Sv39 userspace
range. It is checked under user emulation; real hardware remains unverified.
Protected-page tracking, hot-page handling and preparation use the same
policies as the other Linux targets.

Video allocation follows the known content size or starts at 1920x1080 when
the mode is not yet known. Larger modes expand it on demand; smaller modes
and CRT option changes reuse the existing allocation. Bounds cover both the
native raster and its CRT output. Restored frames reannounce their geometry.
Growing the allocation requires frontend support for AV-info changes;
geometry-only updates remain the fallback when that request is refused.

The libraries are named `anybor_libretro.so`, `anybor_libretro.dll`,
`anybor_libretro_android.so` and `anybor_libretro.dylib`. `CC`, `CXX`, `AR`,
`LD`, `OBJCOPY`, `STRIP`, `CFLAGS`, `CXXFLAGS`, `LDFLAGS` and `NASM` can select
an installed toolchain. On macOS the build selects `clang`/`clang++` and the
system linker, and accepts the `LIBRETRO_APPLE_PLATFORM` and
`LIBRETRO_APPLE_ISYSROOT` variables the libretro `osx-arm64` recipe exports.
Set `NUMPROC` or `JOBS` to limit parallel compilation, and `OBOR_BUILD_ROOT`
to move build outputs outside this directory. With `OBOR_BUILD_ROOT` set,
consume the library and its `build.json` receipt only from
`$OBOR_BUILD_ROOT/dist/<target>/`; managed builds do not overwrite a library
in the source root. Ordinary `make` without this variable retains the
conventional root library for frontend/buildbot compatibility. Dependencies
are built from `src/deps/`; there is no download or prebuilt-library fallback.

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

Only 64-bit x86, ARM and RISC-V targets are supported. Android uses ARM64 and API 24
or later. macOS targets x86-64 (10.13 or newer) and ARM64 (11.0 or
newer) and links only against `libSystem`. `jni/Android.mk` and
`jni/Application.mk` provide the ndk-build entry point used by the libretro
Android runner. `.gitlab-ci.yml` uses the libretro CI templates; GitHub Actions
also compiles and packages the core, including native macOS x86-64 and ARM64 jobs.
Availability through core download services is managed by their maintainers.
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

For rewind, we recommend **Rewind Frames** set to **10** and
**Rewind Buffer Size (MB)** set to **256**. We only recommend enabling rewind
on a Raspberry Pi 5 (quad-core Cortex-A76 at 2.4 GHz) or a device with an
equivalent or faster CPU.

The **System** category offers **Save state content** (Smart / Full) and
**Save state compression** (On / Off). Smart reconstructs resources only when
their bytes can be reproduced exactly; Full retains complete engine memory.
Compression Off leaves changed blocks uncompressed and keeps the reuse of
unchanged blocks. These options apply when content is loaded; changing them
during a session, resetting or loading a state does not change that session's
writer. Diagnostic environment overrides retain priority.

The default is **Smart + On**.
Supported targets also enable dirty-page tracking, advance state preparation,
bounded encoder-pool maintenance and the synchronous compression helper.
Linux, Android and macOS use guarded page protection; Windows uses its native
write-watch API. **Full + Off may not fit the
256 MiB rewind buffer in large games.** The available duration and capture cost
depend on the game, machine and selected combination.

Smart, and Full with compression On, use complete, independently loadable
states with a fixed 64 MiB libretro transport. This is the size of
one serialized state, not additional rewind history. The frontend owns the
history within its 256 MiB buffer. Its available duration depends on how much
state changes: a large transition can shorten it substantially.

The engines identify source-backed sample bytes; engines 3842 and later also
identify reconstructible sprite bodies. Engine 3400 retains its sprite bytes
in the mutable state. The common state layer verifies resource contents before
replacing them with reconstruction recipes. Script-modified or unrecognized data stays in the
mutable state. Headers, palettes, internal references, allocator metadata,
engine globals, the live coroutine stack and audio playback state are retained.
This selection depends on resource structure and lifetime, never game names
or fingerprints.

Every snapshot contains the information needed to rebuild its resources from
the loaded content, including in a new session with an empty cache. The resource
cache is bounded to 128 MiB and holds only source-derived data. Restoration
staging is bounded to 256 MiB; resources beyond that budget remain ordinary
state bytes. The block codec caches only its current image. None of these
caches stores additional rewind history. A failed reconstruction or a complete
state that exceeds its transport budget is rejected; data is never truncated
to make a capture fit.

The compressed transport uses OBC1 with independently encoded blocks and a
resource manifest. Each image is complete and can be decoded without an earlier
snapshot. New blocks use a compact initial encoding; changed blocks use a fast
lossless codec. Bounded slot maintenance limits fragmentation. State preparation
follows the frontend's observed capture interval and stops when captures stop;
the requested capture still validates the current bytes. Unused transport
bytes are deterministically zero. Fixed frontend capacity remains unchanged
across loading, gameplay and Reset.

On supported Windows, Linux, Android and macOS targets, captures with
enough observed encoding work can use
one auxiliary compression thread. It finishes before capture returns; the
engine never advances while it is working. Scratch space stays below 2.1 MiB
and stores no rewind history. Lighter updates, unavailable CPU measurements
or threads, and single-CPU systems retain serial compression. Both paths
produce the same serialized bytes and preserve the capture frequency.

On supported targets, classic movie decoders retain write tracking while
their engine-owned workers run, including between frontend calls. This avoids
rechecking untouched resources after playback. Captures remain unavailable
while workers are active. The asynchronous movie adapter has additional worker
ownership and conservatively invalidates those proofs before playback instead.

On supported page-protection tracking targets, bounded learning identifies
frequently written pages and leaves
those pages writable. Every such page remains dirty for state validation,
including repeated writes between captures. It never supplies an immutable
resource or block proof. Resource recipe metadata and allocation ordering are
reused only while their validity checks hold; all allocation bounds and global
nonoverlap checks are retained. These policies do not omit mutable state or
change the frontend's fixed state capacity.

The Android core is one installable `.so`. It contains a small libretro
loader and the engine ELF; Android's `android_dlopen_ext` loads the engine at
a reserved, stable address. This preserves saved code/static-data pointers
without scanning and modifying arbitrary game data after ASLR changes.
An address collision fails safely. Incompatible states are rejected before
restoring engine memory.

Full + Off uses the complete OBS writer with binary-identity and
runtime-storage checks. It sizes its fixed capacity from
packed content and measured heap peaks; content that outgrows its allowance
requires a restart to use the learned peak. Save states should be made and
loaded with the same core build and content.

The reader accepts states from all four combinations regardless of the current
writer selection. The ordinary build, layout, content and resource checks still
apply. Both Smart and Full require the module to be at its original address.
If its address changes on any platform, loading is refused with a
`state module address differs` log message before changing the live game.
The core does not guess which memory words are pointers or silently change
the selected writer. This limits cross-process save states on macOS, where ASLR can move the dylib. After closing and reopening
the frontend on macOS, expect loads to be refused if the module address changed.
Selecting Full does not bypass the address check. Same-session
rewind and restoration do not require relocation and remain available.

Within a compatible core build, loading a Full state in a Smart session
preserves the game, but resources without reconstruction recipes remain stored
as bytes. Capture cost and rewind duration may differ from a game started in
Smart. Saving again as Smart does not recover missing recipes; starting the
game afresh in Smart rebuilds them as resources load.

Save states and rewind are temporarily unavailable while the engine preloads
models. Some games also preload models briefly while the player is already on
screen. A manual save or load can be refused during that interval, and rewind
history can contain gaps. Normal operation resumes when preloading finishes.

Loading a state retains the current session's content and writable-directory
paths. Engine random-number state is captured with the world so external
frontend activity does not change the restored AI sequence. Saving, loading
and rewind are unavailable during internally threaded movie playback;
the frontend's separate threaded-video setting does not trigger this exclusion.
Returning from gameplay to an earlier menu requires its state to remain
within the finite history. Entering gameplay does not clear the history.

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

See [MODIFICATIONS.md](MODIFICATIONS.md) for changes to the selectable profiles,
with file inventories and source references,
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
