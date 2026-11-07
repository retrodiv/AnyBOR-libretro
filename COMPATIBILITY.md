# Compatibility contract

Selectable engine profiles: v3.0 3020-dev, v3.0 3057, v3.0 3062, v3.0 3073,
v3.0 3081, v3.0 3109, v3.0 3117, v3.0 3143, v3.0 3160, v3.0 3173, v3.0 3192,
v3.0 3208, v3.0 3273, v3.0 3288, v3.0 3303, v3.0 3307, v3.0 3310, v3.0 3311,
v3.0 3316, v3.0 3317, v3.0 3318, v3.0 3327, v3.0 3328, v3.0 3330, v3.0 3332,
v3.0 3335, v3.0 3337, v3.0 3340, v3.0 3341, v3.0 3342, v3.0 3350, v3.0 3351,
v3.0 3352, v3.0 3353, v3.0 3354, v3.0 3355, v3.0 3356, v3.0 3357, v3.0 3360,
v3.0 3361, v3.0 3362, v3.0 3365, v3.0 3366, v3.0 3367, v3.0 3371, v3.0 3372,
v3.0 3373, v3.0 3375, v3.0 3379, v3.0 3380, v3.0 3381, v3.0 3383, v3.0 3385,
v3.0 3388, v3.0 3391, v3.0 3394, v3.0 3397, v3.0 3400, v3.0 3406, v3.0 3411,
v3.0 3415, v3.0 3416, v3.0 3420, v3.0 3422, v3.0 3427, v3.0 3428, v3.0 3431,
v3.0 3434, v3.0 3436, v3.0 3441, v3.0 3445, v3.0 3446, v3.0 3449, v3.0 3454,
v3.0 3458, v3.0 3461, v3.0 3463, v3.0 3465, v3.0 3467, v3.0 3469, v3.0 3472,
v3.0 3477, v3.0 3482, v3.0 3500, v3.0 3509, v3.0 3511, v3.0 3515, v3.0 3517,
v3.0 3520, v3.0 3526, v3.0 3549, v3.0 3550, v3.0 3551, v3.0 3552, v3.0 3553,
v3.0 3554, v3.0 3557, v3.0 3559, v3.0 3562, v3.0 3565, v3.0 3567, v3.0 3568,
v3.0 3581, v3.0 3583, v3.0 3585, v3.0 3586, v3.0 3587, v3.0 3591, v3.0 3594,
v3.0 3596, v3.0 3597, v3.0 3602, v3.0 3604, v3.0 3605, v3.0 3608, v3.0 3609,
v3.0 3611, v3.0 3614, v3.0 3618, v3.0 3619, v3.0 3623, v3.0 3624, v3.0 3626,
v3.0 3629, v3.0 3631, v3.0 3633, v3.0 3635, v3.0 3638, v3.0 3639, v3.0 3640,
v3.0 3644, v3.0 3646, v3.0 3647, v3.0 3649, v3.0 3650, v3.0 3651, v3.0 3655,
v3.0 3656, v3.0 3657, v3.0 3660, v3.0 3661, v3.0 3663, v3.0 3664, v3.0 3665,
v3.0 3666, v3.0 3667, v3.0 3669, v3.0 3670, v3.0 3671, v3.0 3672, v3.0 3673,
v3.0 3674, v3.0 3675, v3.0 3677, v3.0 3678, v3.0 3679, v3.0 3680, v3.0 3682,
v3.0 3685, v3.0 3686, v3.0 3689, v3.0 3690, v3.0 3691, v3.0 3692, v3.0 3693,
v3.0 3694, v3.0 3697, v3.0 3699, v3.0 3701, v3.0 3703, v3.0 3704, v3.0 3707,
v3.0 3708, v3.0 3709, v3.0 3710, v3.0 3711, v3.0 3713, v3.0 3714, v3.0 3715,
v3.0 3716, v3.0 3722, v3.0 3725, v3.0 3726, v3.0 3727, v3.0 3728, v3.0 3729,
v3.0 3730, v3.0 3732, v3.0 3738, v3.0 3740, v3.0 3741, v3.0 3742-dev, v3.0
3761-dev, v3.0 3769, v3.0 3773, v3.0 3780, v3.0 3783, v3.0 3789, v3.0 3793,
v3.0 3797, v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0 3829,
v3.0 3831, v3.0 3837, v3.0 3839, v3.0 3842, v3.0 3846, v3.0 3847-dev, v3.0
3849, v3.0 3854, v3.0 4086, v3.0 4088-dev, v3.0 4107, v3.0 4111, v3.0 4129,
v3.0 4153, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6391-mod, v3.0
6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7086-dev, v3.0 7123-dev, v4.0
7142-alpha, v4.0 7533 and v4.0 8023-dev.

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
Manual profile choices take priority over verified engine-executable hashes,
which take priority over filename and content evidence. An identified engine
uses its exact profile when available, or the available-profile rules for its
build. Unknown, absent, conflicting or incompletely scanned executables leave
the filename/content rules unchanged. See the
[verified engine catalog](docs/ENGINE_EXECUTABLES.json).

An explicit **Build 6391 Mod** variant or manual choice selects v3.0 6391-mod.
Bare numeric tags, ordinary content evidence and unidentified executable declarations do
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
candidate remains compatible. Unidentified sidecar declarations and unlabelled inference use
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
