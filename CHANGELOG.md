# Changelog

## Unreleased — 0.1.0

### Recent changes

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
