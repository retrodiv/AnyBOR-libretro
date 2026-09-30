# Compatibility contract

Available engines are 3400, 3842, 4086, 4432, 4453, 6391, 6412, 7533 and 8023.
An explicit Build 4453 filename or the manual 4453 core option selects 4453.
It uses 32-bit color, ignores `colourdepth` and follows the removal of legacy
`remap` palette conversion. Select 4432 for games that need its older behavior.
Automatic routing selects 6391 for builds 4433 through 6412; a PAK explicitly
tagged Build 6412 or the manual 6412 core option selects 6412. Builds 6413
through 7533 select 7533; builds 7534 through 8023 select 8023.
Other routing combines filename/sidecar metadata with conservative content
markers.
Partial filename tags choose the highest selectable profile in their interval,
including explicit-only profiles: `Build 4XXX` selects 4453, `Build 6XXX`
selects 6412 and `Build 63XX` selects 6391. If the interval contains no profile,
its upper endpoint follows ordinary automatic routing: `Build 42XX` uses 4299
as the detected build and selects 4432; `Build 405X` uses 4059 and selects 4086.
Trailing `X` digits are case-insensitive. Manual selection and the existing
special-profile/legacy-script priorities still apply.
Builds newer than 8023 are best effort through the latest pinned v4 anchor;
they are not claimed as universally compatible.

Targets:

- `linux-x86_64`: generic desktop Linux with bundled static image dependencies.
- `linux-aarch64`: generic ARM64 Linux with static image dependencies.
- `recalbox-aarch64`: ARM64 Recalbox profile, GLIBC imports capped at 2.38;
  dynamic input labels, PAK padmap/macros and OSD messages are disabled because
  of observed frontend crashes. Basic controls remain available.
- `windows-x86_64`: static MinGW runtime/dependencies.
- `android-arm64`: Android API 24 ARM64; no `libc++_shared` dependency.
- `macos-x86_64`: Intel macOS 10.13 or newer (`platform=osx` on an Intel
  runner); only `libSystem` is a dynamic dependency.
- `macos-arm64`: Apple Silicon macOS 11.0 or newer (`platform=osx` on an
  Apple Silicon runner, or the libretro `osx-arm64` recipe with
  `LIBRETRO_APPLE_PLATFORM`/`LIBRETRO_APPLE_ISYSROOT`); only `libSystem` is a
  dynamic dependency.

Release confidence requires a real redistributable fixture for each anchor.
Where one is unavailable, metadata and code coverage do not substitute for a
runtime compatibility claim.
