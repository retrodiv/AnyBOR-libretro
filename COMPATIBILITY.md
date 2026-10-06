# Compatibility contract

The thirteen available profiles are v3.0 3400, v3.0 3842, v3.0 4086, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6412-dev, v3.0 6510-dev, v3.0 7123-dev, v4.0 7142-alpha, v4.0 7533, v4.0 8023-dev.
An explicit Build 4453 filename or the manual 4453 core option selects 4453.
It uses 32-bit color, ignores `colourdepth` and follows the removal of legacy
`remap` palette conversion. Select 4432 for games that need its older behavior.
Profiles 6330 and 6510 also use the shared 6391 engine, with their original
behavior selected by an explicit Build tag or the manual core option.

Automatic routing selects 6391 for builds 4433 through 6412; a PAK explicitly
tagged Build 6412 or the manual 6412 core option selects 6412. Builds 6413
through 7123 select v3.0 7123-dev; builds 7124 through 7142 select
v4.0 7142-alpha; builds 7143 through 7533 select v4.0 7533. Builds 7534
through 8023 and later builds select v4.0 8023-dev.
Other routing combines filename/sidecar metadata with bounded content ranges
and sparse marker estimates. Filename ranges select the highest available
profile within their effective bounds, or the next physical engine above the
upper bound when none fits. Generation prefixes clip explicit ranges.
See [Engine build rules](docs/ANYBOR.md#core-options) for the authoritative
filename grammar, priorities, examples and processing limits. Filename tags
and manual options can select explicit-only profiles; content inference cannot.
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
