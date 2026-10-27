# Compatibility contract

Selectable engine profiles: v3.0 3400, v3.0 3666, v3.0 3667, v3.0 3669, v3.0 3670, v3.0 3671, v3.0 3672,
v3.0 3673, v3.0 3674, v3.0 3675, v3.0 3677, v3.0 3678, v3.0 3679, v3.0 3680,
v3.0 3682, v3.0 3685, v3.0 3686, v3.0 3689, v3.0 3690, v3.0 3691, v3.0 3692,
v3.0 3693, v3.0 3694, v3.0 3697, v3.0 3699, v3.0 3701, v3.0 3703, v3.0 3704,
v3.0 3707, v3.0 3708, v3.0 3709, v3.0 3710, v3.0 3711, v3.0 3713, v3.0 3714,
v3.0 3715, v3.0 3716, v3.0 3722, v3.0 3725, v3.0 3726, v3.0 3727, v3.0 3728,
v3.0 3729, v3.0 3730, v3.0 3732, v3.0 3738, v3.0 3740, v3.0 3741, v3.0
3742-dev, v3.0 3761-dev, v3.0 3769, v3.0 3773, v3.0 3780, v3.0 3783, v3.0
3789, v3.0 3793, v3.0 3797, v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0
3824, v3.0 3829, v3.0 3831, v3.0 3837, v3.0 3839, v3.0 3842, v3.0 4086, v3.0
4088-dev, v3.0 4107, v3.0 4111, v3.0 4129, v3.0 4153, v3.0 4432, v3.0 4453,
v3.0 6330, v3.0 6391, v3.0 6391-mod, v3.0 6392-dev, v3.0 6412-dev, v3.0
6510-dev, v3.0 7086-dev, v3.0 7123-dev, v4.0 7142-alpha, v4.0 7533 and v4.0
8023-dev.

Auto uses build tags and content clues to choose a profile. Manual selection
remains available. States require the same profile; states from another
profile are refused.
Before 3797, the player-property setter returns an integer success result and
a rejected numeric value returns false without changing its destination.
From 3797 it returns no value on success and rejects that value with a script
error. Player-property names and numeric selectors follow the corresponding
API expansion, the keys setter introduced in 3798 and the weapon-number
rename and setter introduced in 3821. Invalid names and unsafe arguments do
not regain historical undefined behavior. AI-flag names and numeric selectors
also follow the 3797 boundary, including the older read-only nested timer
properties. Safety corrections remain enabled.
Player spawn coordinates use the earlier vertical limit before 3800. Before
3805, multiple `spawnscript` declarations execute in source order and reuse the
same per-file script locals across entries. Later profiles retain the engine's
combined per-entry script behavior. See [manual selection and historical
limits](docs/HISTORICAL_PROFILES.md).
Declared revisions from 4087 through 4153 use the first official automatic
profile at or above the declaration, except that the exact unofficial Build
4088 tag selects its development profile. That development profile is excluded
from imprecise-tag and content-based replacement choices.
Automatic routing includes v3.0 4453 for declared builds 4433–4453 and
v3.0 6330 for 4454–6330. Profile v3.0 6391 covers 6331–6412, except that an
exact filename Build 6392 or Build 6412 tag selects the corresponding test
profile. Manual selection remains available. Profile v3.0 4453 uses 32-bit
color, ignores `colourdepth` and removes legacy `remap` palette conversion;
content needing those features requires an earlier compatible profile.
An explicit **Build 6391 Mod** variant or manual choice selects v3.0 6391-mod.
Bare numeric tags, ordinary content evidence and accompanying executables do
not select that variant. Missing build numbers are not inferred from an
executable's compile date. See [variant rules](docs/ANYBOR.md#core-options).
Builds 6413 through 7142 select v4.0 7142-alpha, unless an exact test-build
tag or a manual choice selects v3.0 7086-dev or v3.0 7123-dev; builds 7143 through 7533 select v4.0 7533. Builds 7534
through 8023 and later builds select v4.0 8023-dev.
Other routing combines filename/sidecar metadata with bounded content ranges
and sparse marker estimates. Filename ranges prefer the highest compatible stable or automatic
profile within their effective bounds, or the next automatic revision above the
upper bound when none fits. A range describes inclusive compatibility: Build 3792-3911 selects 3842, which lies inside it. Generation
prefixes clip explicit ranges.
See [Engine build rules](docs/ANYBOR.md#core-options) for the authoritative
filename grammar, priorities, examples and processing limits. Exact filename Build tags and manual options select test variants directly.
Imprecise filename declarations use content evidence and prefer stable or
automatic candidates; nonautomatic candidates are considered only when no such
candidate remains compatible. Ordinary sidecar and unlabelled inference use
automatic profiles only. Exact Build tags without their own selectable profile
check the ordinary automatic candidate against proved content requirements;
a conflicting candidate is replaced by the nearest profile satisfying all
requirements. If none exists, the conflict is logged and existing routing is
retained. Exact tags with their own profile keep their existing priority.
See [the source-backed rules](docs/AUTO_SELECTION_RULES.md). Historical
profiles also participate in Auto declarations and bounded content evidence.
The first available revision at or above a declared build is used;
without a declaration or usable evidence, Auto uses its fallback profile.
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
- `macos-x86_64`: x86-64 macOS 10.13 or newer (`platform=osx` on an x86-64
  runner); only `libSystem` is a dynamic dependency.
- `macos-arm64`: ARM64 macOS 11.0 or newer (`platform=osx` on an
  ARM64 runner, or the libretro `osx-arm64` recipe with
  `LIBRETRO_APPLE_PLATFORM`/`LIBRETRO_APPLE_ISYSROOT`); only `libSystem` is a
  dynamic dependency.

Release confidence requires a real redistributable fixture for each anchor.
Where one is unavailable, metadata and code coverage do not substitute for a
runtime compatibility claim.


v3.0 6392-dev is a reconstruction of published test behavior, not its exact
original sources. Its multihit correction defaults on, and its cheat menu can
select one-ID behavior. It accepts selection-screen title requests
through `gotomainmenu(9)` and the earlier `backtotitle(flag)` alias. Standalone
controller and mod-menu changes are outside the libretro interface.
