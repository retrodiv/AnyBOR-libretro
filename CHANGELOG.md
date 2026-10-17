# Changelog

## Unreleased

- Store complete script variable names safely in older engines, preserving
  distinct names without truncation or a fixed name-length bound.
- Add historical logical profiles on engine 3842. Select player-property
  names, numeric IDs, AI-flag properties, setter results and rejected-value behavior at their
  upstream revision boundaries while retaining safe error handling.
- Preserve earlier player spawn coordinate limits and ordered, cached level
  spawn scripts in the corresponding historical profiles.
- Use generic GNU/Linux targets with an optional glibc requirement ceiling.
  Enable input labels, content-derived pad mappings and notifications on all
  targets without distribution-specific compile-time exclusions.
- Add Linux RISC-V64 LP64D builds, preserved integer/floating-point coroutine
  contexts, protected-page and hot-page tracking, fault locations and fixed
  addresses compatible with Sv39.
- Keep glibc fault recovery compatible with separately allocated coroutine
  stacks when the toolchain enables fortified nonlocal jumps.
- Declare content-sized video bounds, reserve both native and CRT output, and
  grow allocation only when a larger runtime mode requires it. Preserve bounds
  while loading states and report restored geometry before presenting frames.

- Present the complete restored video and audio while the frontend reports
  rewind, including rejected history entries, without advancing into model
  preparation or restarting movie workers. Resume normal input and execution
  immediately when reverse playback ends.

- Copy the transform work buffer only when an external program writes to it.
  Keep unchanged input slices alive through preparation without a second full
  archive allocation, preserving the configured program's buffer semantics.

- Enable supported macOS snapshot policies, including guarded dirty-page
  tracking, advance preparation, bounded pool maintenance and the synchronous
  encoder helper. Retain native Windows write tracking across classic decoder
  workers and enable its native encoder helper and thread CPU clock.
- Keep diagnostic frame prefixes, capture ranges and native function caches
  outside saved engine state. Validate protected-page I/O bindings and native
  signal chaining in the platform checks.
- Drain any interrupted encoder helper after state-fault recovery, before
  reusing its workspace or releasing the engine.

- Keep managed build artifacts in separate target directories and verify their
  recorded identities before runtime checks, preserving ordinary make output.

- Enable guarded dirty-page tracking, registered decoder-worker tracking,
  advance state preparation, bounded encoder-pool maintenance and the
  synchronous compression helper on supported Android targets.
- Learn frequently written pages within a bounded budget. These pages remain
  writable and are always treated as dirty by snapshot proofs.
- Reuse validated resource-recipe metadata and merge allocation-range changes
  while preserving complete snapshots and global nonoverlap checks.

- Avoid clearing complete resource manifests before overwriting active records; inactive records remain fully zeroed.
- Invalidate refused capture headers so a frontend cannot silently load an older
  state left in its buffer. Verify failed captures, intact continuation and
  successful recovery across all profiles and state writers.
- Reuse bounded geometric resource-manifest storage while the catalogue grows,
  including after state loads, without changing serialized bytes or format.

- Preserve live process TLS indices when loading states built with emulated
  thread-local storage. Exclude compiler-generated control descriptors even
  when they are emitted inside an engine object, and audit the final layout.

- Return to the frontend between newly completed models during model-list and
  level preparation, including nested loads. Defer save/load callbacks until
  preparation cleans up, and preserve ordinary scripted gameplay loads.
  Loose content still completes its initial load inside `retro_load_game`.

- Default to Smart save state content with compression On on every platform,
  including Android and macOS, while retaining the existing platform scope of
  runtime optimizations. Keep the intentional same-module-address requirement
  for both Smart and Full, including after restarting RetroArch on macOS.
  Document the performance limit when loading Full states in Smart sessions.

- Exercise successful state loads within each CRT/profile test session, handle
  ASLR independently in cross-process tests, and prevent address-refusal probes
  from aliasing a real module base. Retain native CI failure diagnostics.

- Add System options for save state content (Smart/Full) and compression (On/Off).
  Apply selections at content load, retain diagnostic
  overrides, and accept compatible states independently of the active writer.
  Refuse relocated Smart and Full states before changing the current game.

- Keep statically linked process runtime storage outside game states and pristine
  reset images. Preserve thread/TLS registrations, exit handlers, locks and
  exception bookkeeping across cold loads; audit final link ownership and
  exercise handled Windows exceptions after unloading every engine profile.

- Bind native file calls to the matching SDK/CRT ABI in every engine. Preserve
  session-relative paths with Windows function imports and Darwin's versioned
  stat, directory and stdio entry points; verify caller bindings during builds.
- Ignore optional model defense and offense entries outside the configured attack
  range with a log warning. Keep valid entries and prevent heap corruption in all
  engine profiles.
- Keep Darwin extension declarations visible in POSIX port files. Resolve
  Windows path-stat wrappers through native CRT exports on older and newer MinGW.
- Verify repeated movie restoration against original video and full PCM for
  both decoder adapters, including nested-worker teardown.
- Exercise fixed-capacity rewind and cold loads with both the current block
  transport and the raw fallback, retaining independent layout/padding checks.
- Sample live controls on the first frame after an ordinary state load in all
  engine profiles. Retain saved controls only while the frontend reports rewind.
- Accept inputs up to 1.5 GiB for configured buffer preparation, retaining
  bounded 64-bit instruction budgets and allocation-failure rejection.
- Finish writing newly prepared content before the engine reads it, keeping
  loading progress responsive. This avoids moving delayed filesystem
  writeback into gameplay.
- Group complete unchanged state blocks into bounded proof queries, preserving
  per-block fallback, lossless contents and the existing rewind capacity.
- Check the live working directory before Windows engine switches and restore
  the frontend directory after each call. Skip redundant directory changes and
  stop the engine if restoration fails.
- Add opt-in, bounded latency records for video preparation, frontend video and
  audio callbacks, profile output and the complete active frame scope.
- Preserve Linux engine and frontend directory identities with bounded file
  descriptors across coroutine switches. Avoid repeated pathname lookups on
  userspace filesystems and release handles on load failure, reset and unload.
- Select a bounded, single-helper compression pipeline on Linux from observed
  encoding CPU work and changed blocks. Preserve byte-identical complete states,
  serial fallback and capture frequency without additional rewind history.
- Use complete, independently loadable compressed states on Windows x86-64
  and Linux x86-64/ARM64, with a fixed 64 MiB transport and a recommended
  maximum rewind history of 256 MiB at granularity 10.
- Let engines declare reconstructible sprite bodies and resident PCM ranges.
  Verify their bytes in the common state layer, retain modified resources as
  mutable state, and reconstruct from content when loading with an empty cache.
- Prepare state blocks around observed capture intervals and maintain their
  slots within bounded work budgets, without changing capture frequency or
  keeping additional rewind history.
- Preserve write tracking for engine-owned classic movie workers on Linux;
  retain conservative invalidation for the asynchronous movie adapter and
  reject captures while decoder workers are active.
- Fill the preparation bar from completed I/O and verification work instead
  of animating a moving segment. Keep progress monotonic across optional
  phases and reserve a full bar for successful preparation and engine boot.
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
- Show the credited OpenBOR artwork with a blue preparation bar
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
- Supply build profiles for Linux, Windows, ARM64 and Android.
- Include the portable circle, endian and ADPCM implementations, resource
  lifecycle corrections and script/audio/animation memory improvements.
- Bundle pinned dependencies and their original notices for offline builds.
- License original AnyBOR work under BSD-3-Clause while preserving each component's
  terms, including OpenBOR 3400's conditions on sale.
- Include source checks, original diagnostic fixtures, binary build receipts
  and release packaging with the complete notice dossier.
