# Compatibility contract

The main profiles are v3.0 3400, v3.0 3842, v3.0 4086, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6412-dev, v3.0 6510-dev, v3.0 7123-dev, v4.0 7142-alpha, v4.0 7533, v4.0 8023-dev.
Historical v3.0 profiles 3780, 3783, 3789, 3793, 3797, 3805, 3814, 3818,
3822, 3824, 3829, 3831, 3837 and 3839 use physical engine 3842 and require
manual core-option selection. Auto does not infer an exact historical minor
revision from the absence of newer script features. State identity includes
the logical profile; states from a different profile are refused.
Before 3797, the player-property setter returns an integer success result and
a rejected numeric value returns false without changing its destination.
From 3797 it returns no value on success and rejects that value with a script
error. Player-property names and numeric selectors follow the corresponding
API expansion, the keys setter introduced in 3798 and the weapon-number
rename and setter introduced in 3821. Invalid names and unsafe arguments do
not regain historical undefined behavior. AI-flag names and numeric selectors
also follow the 3797 boundary, including the older read-only nested timer
properties. The engine memory layout and safety fixes remain shared.
Player spawn coordinates use the earlier vertical limit before 3800. Before
3805, multiple `spawnscript` declarations execute in source order and reuse the
same per-file script locals across entries. Later profiles retain the engine's
combined per-entry script behavior. See [manual selection and historical
limits](docs/HISTORICAL_PROFILES.md).
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
filename grammar, priorities, examples and processing limits. Filename tags and
manual options can select the existing explicit-only anchor variants. Historical
profiles require manual selection; content inference does not select them.
Builds newer than 8023 are best effort through the latest pinned v4 anchor;
they are not claimed as universally compatible.

Targets:

- `linux-x86_64`: generic desktop Linux with bundled static image dependencies.
- `linux-aarch64`: generic ARM64 Linux with static image dependencies.
- `linux-riscv64`: GNU LP64D Linux with static image dependencies and a portable
  VP8/VP9 decoder. Context switching, protected-page tracking, fixed-base states and fault recovery are
  exercised under user emulation; no real-hardware validation is claimed.
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
