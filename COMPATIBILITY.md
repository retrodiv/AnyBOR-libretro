# Compatibility contract

Pinned engine anchors are 3400, 3842, 4086, 4432, 6412 and 8020. Automatic
routing combines filename/sidecar metadata with conservative content markers.
Builds newer than 8020 are best effort through the latest pinned v4 anchor;
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

