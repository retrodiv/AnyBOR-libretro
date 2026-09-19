# Changelog

## 0.1.0 — first released version

### Recent changes

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
