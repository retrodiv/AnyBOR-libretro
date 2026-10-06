# Changelog

## Unreleased

- Validate macOS release exports against the linker symbol list, including the
  optional rewind interface. Wait for cooperative initialization before rewind
  regression captures and after Reset, retaining the original buffer capacity
  and reporting host diagnostics on failure.
- Read game video settings before showing preparation artwork, using native
  320x240, 480x272 or 640x480 backgrounds derived at build time from one master
  and an ephemeral centred Lanczos3 resize for other sizes. Share video geometry and CRT adjustment with
  native loading and gameplay so their output modes agree at transition.
- Preserve inline animation allocation handles and next-animation timestamps
  across the shared 6330, 6391, 6412 and 6510 profiles, allowing scripted
  cutscenes to finish and retaining exact animation scheduling.
- Show the credited OpenBOR artwork with an animated blue preparation bar
  before packed-content I/O, then pass through the game's original loading
  screen and progress bar.
- Present the game's loading screens and real progress during cooperative
  resource initialization, reserving state capacity from packed resources
  and learned peaks before the frontend allocates its rewind buffers.
- Preserve the current session's content and save paths when restoring a
  state from another session.
- Capture engine-owned random state so restored gameplay follows the same
  random sequence independently of frontend activity.
- Add optional Linux ARM64 rewind captures with complete states, conservative
  change ranges and explicit buffer ownership across load, reset and unload.
- Avoid copying the allocator's unused top space while retaining live data
  and allocator metadata, with ordinary serialization as the fallback.
- Accept explicit Autoconf host and build triplets for external toolchains,
  with compiler-host and native-build detection available through `auto`.
- Respect inclusive filename build intervals, including unknown endpoints,
  and report when no available physical engine fits the bounds.
- Release the snapshot arena on macOS module unload by keeping fault guards
  in temporary pthread slots instead of compiler thread-local storage.
- Reject macOS cores with compiler TLS during binary inspection and probe
  arena release with an exact, non-overwriting Mach reservation.
- Resolve partial filename build tags to the highest available profile in
  their interval, or route the interval's upper endpoint when none exists.
- Add engine 4453, selectable by its core option or an explicit Build 4453
  filename, with its original 32-bit color and palette behavior.
- Preserve native settings and separate saved data for 4432 and 4453.

## 0.1.6 — eight selectable engines

- Add the 7533 engine and replace the 8020 physical anchor with the public
  8023 controller branch. Core Options offers eight engines plus Auto.
- Bridge the controller branch to four RetroPads, including saved button
  mappings and in-game reassignment. Align player state so the Windows core
  can enter gameplay safely.
- Open structurally valid PACK archives whose four-byte header is damaged.
- Keep external transform programs in the frontend system directory's
  `AnyBOR.ini`.

## 0.1.3 — release regression checks

### Recent changes

- Validate the exact outgoing Git revisions before pushing, and check source
  inventories before CI starts platform builds or release packaging compiles.
- Boot every Windows engine under Wine with fresh and existing saves, preserving
  existing user data and checking visible frames and runtime notices.
- Bound Linux build and test process trees with separate memory and time limits.
- Keep release notes and generated source inventories synchronized.

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
