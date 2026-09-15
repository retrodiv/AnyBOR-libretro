# Publishing AnyBOR and requesting libretro integration

Infrastructure reference review: **2026-09-11**. This repository supplies the
source, metadata and build entry points for an independent 64-bit core. The
version in [src/pin.json](../src/pin.json) is the release identity used by the
core, metadata and versioned packages.

The current version is unreleased; [CHANGELOG.md](../CHANGELOG.md) records its
status. `source_date_epoch` fixes timestamps for reproducible builds and source
metadata. It is not a publication date.

## Publication material

| Material | Included file or command |
|---|---|
| Complete buildable sources | `make source-release` creates `dist/anybor_libretro-<version>-source.zip` and its SHA-256 file. |
| Per-target binary, receipt and notices | `make TARGET=<target> release` creates a versioned ZIP and checksum under `dist/`. |
| RetroArch core information | [anybor_libretro.info](../anybor_libretro.info). Keep this exact basename when submitting/installing it. |
| Libretro hosted build jobs | [.gitlab-ci.yml](../.gitlab-ci.yml), [Makefile](../Makefile), [jni/Android.mk](../jni/Android.mk), [jni/Application.mk](../jni/Application.mk). |
| Independent CI | [.github/workflows/ci.yml](../.github/workflows/ci.yml) builds/packages the four generic targets and uploads the source ZIP with the native Linux artifacts. |
| User documentation | [ANYBOR.md](ANYBOR.md), ready to adapt as `docs/library/anybor.md` in libretro's documentation repository. |
| Attribution and distribution terms | [LICENSES.md](../LICENSES.md), [NOTICE.txt](../NOTICE.txt), [LICENSES/](../LICENSES), [PROVENANCE.md](../PROVENANCE.md). |
| Modification evidence | [MODIFICATIONS.md](../MODIFICATIONS.md), its file inventories and source history. |
| Source identity and components | [SOURCES.json](../SOURCES.json), [SBOM.spdx.json](../SBOM.spdx.json), engine/dependency `ANYBOR-SOURCE.json` files. |
| Support and contributions | [SECURITY.md](../SECURITY.md), [CONTRIBUTING.md](../CONTRIBUTING.md). |

The source ZIP is created from the checked inventory rather than by archiving
the working directory. It includes hidden CI files and build inputs, and excludes
`.git/`, `.build/`, `dist/`, generated binaries, local game files and private
reports. The packager reopens the archive and verifies every member's hash.
Publish this ZIP alongside binary downloads, or provide the corresponding
tagged source repository. Binary ZIPs include the modification record and
documentation; their links into `src/` refer to the matching source distribution.

A local platform directory can contain just its DLL/SO. For a distribution
containing several platforms, keep a shared copy of the core-info file,
documentation and license dossier alongside those directories. Each release
ZIP remains self-contained with its own notices and build receipt. The embedded
notice dossier also remains in every core binary; see [LICENSES.md](../LICENSES.md).

## Target contracts

The core name supplied to libretro infrastructure is **`anybor`**, producing
the basename **`anybor_libretro`**. `MAKEFILE=Makefile`, `MAKEFILE_PATH=.` and
`STRIP_CORE_LIB=0` are set in `.core-defs`: the builder already strips the
published binary and records its exact hash and embedded notices.

| Target | Public invocation | Required output | Libretro template |
|---|---|---|---|
| Linux x86-64 | `make platform=unix CC=gcc CXX=g++` | `anybor_libretro.so` | `.libretro-linux-x64-make-default` |
| Linux ARM64 runner | `make platform=unix CC=gcc CXX=g++` on AArch64 | `anybor_libretro.so` | `.libretro-linux-aarch64-make-default` |
| Linux ARM64 cross build | `make TARGET=linux-aarch64` | `anybor_libretro.so` | Local alternative to the native ARM64 runner. |
| Windows x86-64 | `make platform=win64` with the runner's MinGW compiler variables | `anybor_libretro.dll` | `.libretro-windows-x64-mingw-make-default` |
| Android ARM64 | `"$NDK_ROOT/ndk-build" -C jni APP_ABI=arm64-v8a` | `libs/arm64-v8a/libretro.so` and `anybor_libretro_android.so` | `.libretro-android-jni-arm64-v8a` |

The Android template moves `libs/arm64-v8a/libretro.so` to
`anybor_libretro_android.so`. `APP_PLATFORM=android-24`; ELF load segments are
aligned to at least 16 KiB. The builder links the C++ runtime statically, so
the artifact does not need a separately distributed `libc++_shared.so`.

The Windows template supplies the MXE `x86_64-w64-mingw32.static-*` tools via
`CC`, `CXX`, `AR`, `AS` and `WINDRES`. The builder derives companion tool names
from the selected compiler and also accepts explicit overrides. Linux's `unix`
entry point detects the compiler's target triple, including native AArch64.

Host requirements are GNU make, GCC/G++, binutils, Python 3.5 or newer and NASM
for x86-64, plus the selected cross toolchain or Android NDK. The bundled release
configure scripts are used directly; builds do not need network access,
Autotools regeneration or installed libpng/zlib/Vorbis/VPX development
packages.

Recalbox has a separate local `TARGET=recalbox-aarch64` profile with its
documented frontend adjustments and GLIBC 2.38 ceiling. It is not a fifth generic
libretro job. The repository does not advertise 32-bit, macOS, iOS, console or
static-core targets. The exact hosted images and tool versions are controlled
by libretro's templates and may change independently of this repository.

## Checks before uploading a release

Run these in a fresh checkout or extracted source distribution:

```sh
make check
make -j8
make check-binary BINARY=anybor_libretro.so
python3 tools/smoke.py
make release
make source-release
```

Repeat the build/package step for each advertised target with its installed
toolchain. Exercise the public regression suites for changes to the runtime;
their scope and commands are in [TESTING.md](TESTING.md). A source/package check
does not substitute for a device test. In particular, an Android build and ELF
inspection are distinct from running RetroArch on an Android device.

The binary receipt records source hashes, compiler/linker, imports and selected
static archive members. Packaging rejects changed sources, changed notices or
a mismatched binary. Preserve the archive checksums and CI logs with the release.

## External registration

The [official core-development instructions](https://docs.libretro.com/development/cores/developing-cores/#add-your-core-to-libretro-infrastructure)
describe the separate steps for Core Downloader availability:

1. Publish the reviewed source tree at the maintainer's chosen public repository
   and identify its branch and immutable release tag/commit. Those hosting
   details are not inferred or assigned by this source tree.
2. Submit `anybor_libretro.info` to
   [libretro-super/dist/info](https://github.com/libretro/libretro-super/tree/master/dist/info).
   For a local test, put it in RetroArch's configured **Core Info** directory,
   load the matching core and inspect **Information > Core Information**.
3. Request that libretro maintainers connect/import the source repository into
   their CI/CD infrastructure using the included `.gitlab-ci.yml`. Supply the
   repository URL, branch/tag, `CORENAME=anybor`, supported target matrix,
   tool prerequisites, source/binary checksums and the distribution terms.
4. Submit the user documentation to [libretro/docs](https://github.com/libretro/docs)
   and add its navigation entry following that repository's contribution rules.
5. If adding automatic database-based playlists, submit the corresponding
   metadata to [libretro-database](https://github.com/libretro/libretro-database)
   and suitable playlist/content icons to
   [retroarch-assets](https://github.com/libretro/retroarch-assets).
   Basic content loading and manually created playlists do not require those
   optional submissions. No third-party game collection is bundled here.

GitHub Actions artifacts and a local `.info` file do not by themselves register
a Core Downloader entry. Importing the repository, running the hosted pipelines,
accepting the metadata/documentation and making the core available remain
external steps. Local verification must not be described as a successful run
on libretro's hosted buildbot.

The combined core includes OpenBOR 3400's no-sale terms, reflected by
`license="Non-commercial"`. Provide [LICENSES.md](../LICENSES.md) and the complete
dossier when requesting redistribution; do not present the combined artifact
as BSD-only. The source snapshot itself and each binary retain the relevant
component notices.

Template references reviewed for this handoff:
[Linux x86-64](https://git.libretro.com/libretro-infrastructure/ci-templates/-/blob/master/linux-x64.yml),
[Linux ARM64](https://git.libretro.com/libretro-infrastructure/ci-templates/-/blob/master/linux-aarch64.yml),
[Windows x86-64](https://git.libretro.com/libretro-infrastructure/ci-templates/-/blob/master/windows-x64-mingw.yml),
[Android JNI](https://git.libretro.com/libretro-infrastructure/ci-templates/-/blob/master/android-jni.yml),
and the [core-info field reference](https://github.com/libretro/libretro-super/blob/master/dist/info/00_example_libretro.info).
