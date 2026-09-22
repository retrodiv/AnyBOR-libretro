# Changelog

## 0.1.2 — the 8020 engine boots on Windows

### Recent changes

- Create the content's save tree through the platform's own directory attributes
  instead of `stat()`. An engine header can set `_FILE_OFFSET_BITS` once the C
  library headers were already read, and the Windows C library then bound the call
  to a larger structure than the one the caller had reserved; the write crossed the
  stack frame and crashed the boot of exactly the engines that expose that define,
  the 8020 build among them.

## 0.1.1 — the macOS targets build

### Recent changes

- Finalize the engine objects for Mach-O during the build: the moved commons are
  aligned and their references relocated, the arm64 page relocations are
  migrated, the region segment grows to hold the packed layout and the linker
  emits the `LC_UUID` dyld requires, so both Mach-O targets link with current
  Apple linkers.
- Probe the linker for the `-d` commons switch instead of assuming it: Xcode 15
  and later define tentative definitions themselves and refuse the option, while
  older toolchains keep it.
- Reserve the snapshot arena through macOS's native virtual-memory interface and
  give Apple Silicon its own free base, so content loading no longer depends on
  the kernel granting an address hint.
- Build every engine with the macOS SDK headers and satisfy the SDK's
  `ucontext` guard.
- Clear the diagnostics the Apple toolchain reports: room for the button-name
  table's exit entry and `intptr_t` for the values carried through the
  pointer-typed sound APIs.
- Read linker maps tolerantly when a build records its archive members, and stop
  denying dyld the `LC_UUID` it requires.

## 0.1.0 — first released version

### Recent changes

- Show `OpenBOR (AnyBOR)` as the core's name in frontends and the Core
  Downloader; the core name, library name and file names stay `AnyBOR` and
  `anybor_libretro`.
- Publish the core-info version as `Git`; the runtime version comes from
  `src/pin.json` and advances with each published state.
- Ship a commit hook that refuses a published state whose version did not
  advance, and confine version literals to the version records.
- Select desktop macOS toolchains for libvpx on Intel and Apple Silicon,
  preserving the configured minimum macOS version.
- Drop the retired PowerPC-era cpusubtype switch from the bundled Xiph build
  scripts so dependency builds link with current Apple linkers.
- Make native test-host descriptor and memory checks portable to macOS.
- Run rewind and CRT runtime regressions in Linux CI as well as macOS CI.
- Allow auxiliary local files during normal builds while retaining strict
  source inventories for publication checks and release packaging.
- Include matching source archives inside platform release ZIPs.
- Reject failed binary inspections and require the expected architecture,
  dependencies and exports in release checks.
- Bound Mach-O export parsing, preserve section addresses when collecting
  engine state, and query the Apple linker version through its native interface.

- Build the two Mach-O targets (Intel and Apple Silicon) with clang and
  Apple's linker, keeping save states, rewind and cross-process state loads.
- Flatten and shorten prepared-content cache paths for filesystem compatibility.
- Separate persistent game saves from disposable caches and manage cache cleanup.
- Isolate settings for unpacked content and read uncompressed indexed PCX images
  in the legacy engines.
- Bound rewind state capacity when the frontend supplies smaller buffers.

### Core implementation

- Include OpenBOR builds 3400, 3842, 4086, 4432, 6412 and 8020 with the shared
  libretro runtime, build tools and source inventories.
- Support PAKs, unpacked `data/models.txt` mods and single-game ZIPs.
- Provide save states, rewind, four-player controls and frontend configuration.
- Supply build profiles for Linux, Windows, ARM64, Android and Recalbox ARM64.
- Include the portable circle, endian and ADPCM implementations, resource
  lifecycle corrections and script/audio/animation memory improvements.
- Bundle pinned dependencies and their original notices for offline builds.
- License original AnyBOR work under BSD-3-Clause while preserving each component's
  terms, including OpenBOR 3400's conditions on sale.
- Include source checks, original diagnostic fixtures, binary build receipts
  and release packaging with the complete notice dossier.
