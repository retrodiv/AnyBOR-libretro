# OpenBOR (AnyBOR)

AnyBOR is an independent libretro core for OpenBOR games, offering selectable
engine profiles: v3.0 3400, v3.0 3780, v3.0 3783, v3.0 3789, v3.0 3793, v3.0 3797,
v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0 3829, v3.0 3831,
v3.0 3837, v3.0 3839, v3.0 3842, v3.0 4086, v3.0 4432, v3.0 4453, v3.0 6330,
v3.0 6391, v3.0 6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7086-dev, v3.0 7123-dev, v4.0 7142-alpha,
v4.0 7533 and v4.0 8023-dev.
Auto uses build tags and content clues to choose a profile. You can select one
manually when a game needs it. See [choosing a profile](HISTORICAL_PROFILES.md).
OpenBOR and Beats of Rage originate with Senile Team and OpenBOR Team; the port
is maintained by retrodiv. The combined core has multiple component licenses,
including OpenBOR 3400's no-sale terms. See [LICENSES.md](../LICENSES.md).

## Requirements and loading content

Use a supported 64-bit frontend: Linux x86-64/ARM64/RISC-V64, Windows x86-64,
macOS x86-64/ARM64 or Android ARM64 (API 24 or later).
Configure a writable **Save Files** directory in
the frontend. The core requires that directory even when a particular game does
not use ordinary saves. No BIOS or firmware is required or included.

Load one of these with **Load Content**, then select AnyBOR:

| Extension | Accepted content |
|---|---|
| `.pak` | An OpenBOR game archive. An otherwise complete, unencoded PACK with a damaged four-byte signature is repaired automatically after structural validation. |
| `.spk` | Accepted only for an ordinary PACK archive misnamed with this extension. A genuine SPAK/protected archive is recognized and rejected with an explicit error; it is never decoded. |
| `.txt` | Exactly the `data/models.txt` entry point of an unpacked game. |
| `.zip` | One PAK or one unpacked game's data tree. The core handles extraction. |

The core does not start without content. It includes no third-party games,
artwork or soundtracks. Use game data from sources you trust. A nearby OpenBOR
executable can be read as data for version detection; it is not executed.

## Features

| Feature | Support |
|---|---|
| Restart | Reboots the game and applies a changed Engine build option. |
| In-game saves/settings | Engine-managed files in the frontend save directory. |
| Save states and rewind | Supported; states require the same core build and content. Unavailable during model preloading or threaded video playback. |
| Netplay/runahead | The metadata advertises `serialized` state support; it makes no general deterministic/netplay/runahead compatibility claim. |
| Players and remapping | Up to four RetroPads, subject to the game's player limit; frontend button remapping supported. |
| Rumble | Optional forwarding of the game's hit vibration. |
| Core options | Version 2.0 categories, with a flat fallback for older frontends. |
| Frontend cheats | Not implemented. A game's own cheats/options remain game-specific. |
| Achievements | No integration is provided by this project. |
| Disk control, subsystems, hardware rendering | Not used. Video is software-rendered XRGB8888. |

## Controls

Frontend ports 1 through 4 each control the matching player independently.
Press Start on each controller to join, up to the game's player limit.
Configure controller assignments and button remapping in the frontend.

| RetroPad input | Default OpenBOR action |
|---|---|
| D-pad | Movement |
| Left analog stick | Movement when the analog option is enabled |
| Y (west) | Attack |
| B (south) | Jump |
| A (east) | Special |
| X | Attack 2 |
| L / R | Attack 3 / Attack 4 |
| Start | Start |
| Select | Escape/menu |
| L2 / R2 / L3 / R3 | Special-move macros when enabled and available in the active character's move list |

Games can assign different meanings to the engine's attack inputs. The core
can derive controller labels and move macros from the game's own metadata.
The macros account for the active character's facing direction.

## Core options

| Option | Key | Default and effect |
|---|---|---|
| Adjust for 4:3 CRT TV | `obor_crt_tv` | **Off**. Fit images wider than 364 pixels or taller than 244 pixels into 640x480, preserving their aspect with borders and sharp-bilinear scaling. Smaller images outside 4:3 +/-10% receive native-pixel black padding to 4:3, then the size limits are checked again. Applies during play; see the [video contract](#video-contract-adjust-for-43-crt-tv) for thresholds and examples. |
| Left analog stick as D-pad | `obor_analog` | **On**. Adds movement with the left stick. |
| Rumble | `obor_rumble` | **On**. Forwards game hit vibration. |
| Special move macros (L2/R2/L3/R3) | `obor_macros` | **On**. Executes supported character move sequences. |
| Engine build | `obor_engine` | **Auto**. Select an explicit compatibility profile when needed; changes apply on Restart. |
| Save state content | `obor_state_content` | **Smart** reconstructs resources after an exact byte proof. **Full** retains complete engine memory. Applies when content is loaded. |
| Save state compression | `obor_state_compression` | **On** compresses state blocks. **Off** leaves changed blocks uncompressed while retaining reuse of unchanged blocks. Applies when content is loaded. |
| Forward game log | `obor_gamelog` | **Off**. Mirrors the engine log into the frontend log. |
| Clear current game saved data on load | `obor_clear_local_data` | **Off**. In Development. Deletes the current game's entire `AnyBOR/<game>/` folder before loading, across all engine builds. |
| Clear current game cache on unload | `obor_clear_game_cache` | **On**. In Development. Deletes the cache directories used by this game after unloading or closing the core. The next load rebuilds them; saved data is unaffected. |
| Clear all game caches on load | `obor_clear_all_caches` | **On**. In Development. Empties `AnyBOR-cache/` before each load and before generating new cache files; saved data is unaffected. |

The state options share the existing System category. Their defaults are
**Smart + On on every platform**, including Android and macOS. Writer selection
is independent of the platform runtime policy. Supported targets enable
guarded dirty-page tracking, advance preparation and the synchronous compression
helper, with bounded pool maintenance. Frequently written pages remain writable
and always dirty for snapshot proofs on the page-protection backends; Windows
retains its native write-watch mechanism. No policy changes the complete-state contract.
Full + Off may exceed a 256 MiB rewind buffer in large
games. All combinations can be selected on every platform; see the
[state compatibility limits](../README.md#save-states-and-rewind), including
clean refusal whenever the core module address has changed, for both Smart
and Full on every platform. The log reports `state module address differs`
without changing the current game. macOS ASLR can therefore prevent loading
after closing and reopening the frontend. This refusal is intentional and affects
Full as well as Smart; choosing Full does not avoid it. This is a temporary
limitation until exact relocation is available. Same-session rewind and
restoration remain available. Loading a compatible Full state in Smart can
also retain fewer reconstruction recipes and change capture cost or rewind
duration. This is a performance limitation; saving again in Smart does not
recover recipes that were absent. A fresh game in Smart catalogs resources
as they load.

Automatic selection uses filename version tags, nearby engine-version data
and PAK content markers, with profile v3.0 6391 as the current fallback. An explicit
engine choice takes precedence. Games predating the available source history
use the 3400 anchor on a best-effort basis; games newer than the latest anchor
also have best-effort coverage. [COMPATIBILITY.md](../COMPATIBILITY.md) describes
the supported engine ranges.

Filename build tags may end in unknown digits. Auto analyzes the content
within that interval, then chooses the highest compatible stable or automatic
profile. With no narrower evidence, **Build 4XXX** selects 4453 and **Build 6XXX**
selects 6391. Palette conversion or 8/16-bit output excludes 4453; old boomerang
commands can constrain the 63XX interval to 6330. A development profile is considered
when no compatible stable or automatic profile remains in the interval.
**Build 42XX** has no available profile inside 4200–4299 and routes above it to 4432.
Lowercase `x` also works. See [content rules](AUTO_SELECTION_RULES.md).

For inclusive bounds, use **Build 3800-4200**. Each endpoint accepts trailing
unknown digits: **Build 63XX-7762** means 6300-7762, and **Build 6352-65XX**
means 6352-6599. **XXXX** leaves that endpoint open. A generation directly
before the Build tag intersects the range: **v.3.0 Build 63XX-7762** becomes
6300-7532, while **v.4.0 Build XXXX-7762** starts at 7142. A version in a
separate bracket or in the title does not constrain the range.

Auto intersects an inclusive interval with content evidence and prefers the
highest compatible stable or automatic profile inside it. If the evidence
contradicts the interval, the interval wins and the nearest declared candidate
is selected with a log message. For example, **Build 3780-3839** selects 3839 and
**Build 3792-3911** selects 3842. Only if none fits, it uses the first automatic revision
above the upper endpoint; 7369-7532 therefore uses 7533. If there is no later
profile, loading reports an error. An explicit interval takes precedence over
other inferred requirements; manual selection overrides it.

Build numbers and ranges require the word **Build**, followed by a space.
Matching is case-insensitive and uses only the filename, not its parent path.
**Build_6391**, **ReBuild 6391**, and unrelated numbers do not supply a build.
The historical **v.2.1933** filename form remains supported separately.

When no higher-priority clue supplies a build, a bounded PAK text scan combines
known command, animation, native-function and literal-constant introductions
and removals into an inclusive range, then keeps v3.0 6391 when it satisfies that range. Requirements beyond it
select the first compatible intervening era up to v4.0 7533; requirements
beyond that stable release select the latest compatible snapshot, currently
v4.0 8023-dev. Explicit filename intervals retain their highest-profile /
next-revision policy. Ordinary unlabelled inference offers only automatic
profiles, including the official releases v3.0 4453 and v3.0 6330. Test profiles
v3.0 6392-dev, v3.0 6412-dev and v3.0 6510-dev can be selected directly by an
exact filename Build tag or a manual choice. Accompanying executables and
ordinary unlabelled inference do not select these nonautomatic profiles.
Imprecise filename tags can select them when no stable or automatic candidate
remains compatible in the declared interval. Historical profiles 3780–3839
participate in Auto: a declared build selects the first available revision at
or above it, including declarations from an accompanying executable. Positive
content bounds in this engine era use the same revisions. No declaration
or usable evidence keeps the existing fallback. Native rules ignore comments and quoted
prose. Preprocessor directives or a local declaration of a reviewed builtin
make native evidence inconclusive; model evidence remains usable. This scan
is a heuristic and does not certify a whole game or resolve dynamic arguments,
imports, reachability, media dependencies, or temporary historical regressions.

A separate dependency probe follows the engine's fixed global script paths,
literal imports, and model paths listed by `load`/`cache` in `data/models.txt`.
It can retain a proven modern minimum when the broad scan exceeds its limit.
`child_follow_*` commands require the stable v4 era; literal
`GLOBAL_CONFIG_PROPERTY_*` constants and later coordinate, speed and sound-group
commands require a snapshot newer than v4.0 7533. Comments, strings, local
builtin declarations and uncertain conditional preprocessing supply no native
requirement. The dependency probe permits 4096 eligible entries, 2 MiB per
source, 16 MiB total and 65536 directory entries, with its own 750 ms deadline.

The content pass inspects at most 800 text files, 2 MiB per file, 16 MiB total,
and 65536 directory entries, with a 750 ms processing deadline. An incomplete
pass cannot establish a complete interval. For an imprecise filename tag,
complete model-command facts already observed remain usable; unread script
bindings and absent features establish no requirement. Ordinary unlabelled
inference retains its existing fallback unless a modern dependency probe
completed. Legacy API detection
has its own 750 ms budget and bounded argument lookahead. Filesystem reads
can still be delayed by the host storage. The older sparse token estimates
remain a fallback when no exact syntax rule fires.

Choose **v3.0 4453** explicitly or use a filename tagged **Build 4453** to select
that profile. It uses 32-bit color and ignores `colourdepth`.

### Video contract: Adjust for 4:3 CRT TV

`Video > Adjust for 4:3 CRT TV` defaults to `Off`. With it enabled, games keep
their native resolution, aspect and pixels when their width is at most 364,
their height is at most 244, and their aspect is within 4:3 +/-10%
(inclusive 1.2 through 22/15, approximately 1.4666667). Small images outside
that interval receive centred black padding on one axis to reach 4:3 without
resampling. Fractional extents round up; opposite borders may differ by one
pixel. The size limits are then checked again, including the padding.
If the width is greater than 364 **or** the height is greater than 244,
the complete original image is
scaled to fit inside a 640x480 frame with a 4:3 display aspect. The image keeps
its original aspect ratio without cropping. Wider-than-4:3 images have centred
black borders above and below; narrower images have borders on the left and
right. An exact 4:3 image fills the frame.

For example, 320x180 becomes 320x240 with 30 black rows above and below;
320x200 becomes 320x240 with 20 rows on each side. A square 240x240 image
becomes 320x240 with 40 black columns at each side. A 360x180 image would
need 360x270, exceeding the height limit, so it instead becomes a 640x320
image inside 640x480 with 80 black rows above and below. Likewise, 364x244
requires padding and then a 640x480 frame. A 368x240 image becomes 640x417,
while 320x256 becomes 600x480. Each dimension is checked independently.

With the option set to `On`, the standard OpenBOR video modes become:

| Mode | Internal resolution | Original aspect | Output frame | Game image inside the frame | Black borders: top / bottom |
|---|---|---|---|---|---|
| 0 | 320x240 | 4:3 | 320x240 | 320x240 (native) | None |
| 1 | 480x272 | Approximately 16:9 | 640x480 | 640x362 | 59 / 59 pixels |
| 2 | 640x480 | 4:3 | 640x480 | 640x480 (identity scale) | None |
| 3 | 720x480 | 3:2 | 640x480 | 640x426 | 27 / 27 pixels |
| 4 | 800x480 | 5:3 | 640x480 | 640x384 | 48 / 48 pixels |
| 5 | 800x600 | 4:3 | 640x480 | 640x480 | None |
| 6 | 960x540 | 16:9 | 640x480 | 640x360 | 60 / 60 pixels |

With `Off`, each mode keeps its internal resolution as the output frame,
without borders added by the core. With `On`, mode 0 stays below both limits
and **remains 320x240**. Mode 2 uses the 640x480 frame at identity scale and
also keeps its native pixels. The other modes are scaled to the image
dimensions above, without cropping. Scaled dimensions are truncated to whole pixels, giving
362 image lines in mode 1 and 426 in mode 3. None of these seven modes gains
left or right borders.

The output frame and border sizes refer to pixels submitted to the frontend,
not the physical CRT scan mode.
Changes apply during play. Scaling uses
sharp bilinear: integer enlargements stay crisp, while fractional scales
interpolate at pixel edges to reduce uneven text strokes and scrolling shimmer.
This changes the image submitted to the frontend; it does not reduce the
engine's internal drawing resolution or guarantee a frame rate.
The frontend controls the physical TV mode and interlacing;
use the core-provided aspect ratio or 4:3 in its video settings.

## Files and directories

Paths below are relative to the frontend's **Save Files** directory:

| Path | Purpose |
|---|---|
| `AnyBOR/<game>/<profile build>/` | Profile-specific saves, settings, logs and learned memory-peak data. Different settings layouts stay separate. |
| `AnyBOR-cache/zipcache/` | Cached extraction of ZIP content. |
| `AnyBOR-cache/input-<8-hex>/` | Prepared content derived from the source archive. |
| `anybor-license-notices.txt` | The complete notice dossier embedded in the loaded core; attempted in this directory when content is loaded. |

The three cleanup options are grouped in **Development**, including on frontends
with categorized Core Options. Turn both cache options Off to retain and reuse
cache files across sessions. Restart keeps the currently loaded cache available;
load cleanup runs when loading content. The unload option also honors a change
made in the frontend menu immediately before closing content.

Each game has its own folder named after the original PAK, SPK or ZIP without
its extension, or the unpacked mod directory. The name stays stable when content
is extracted or prepared. Identically named games share this namespace; give
unrelated games different filenames. Inside it, profiles use separate directories because their settings layouts can differ.

Saved-data cleanup removes that whole game folder, including settings, progress,
script output, logs, screenshots and learned memory peaks for every profile.
Other games and frontend save states remain intact. Script output explicitly
written outside the game's folder is outside this cleanup operation.

This layout replaces the earlier `AnyBOR/<engine>/` layout without migration.
Old saves and the old `AnyBOR/prepared-v1/` and `AnyBOR/zipcache/` caches are no
longer used and are left untouched.

The frontend places save-state files in its configured **Save States** directory.
Ordinary engine saves use their own files rather than a libretro save-RAM block.
Save states and rewind are temporarily unavailable during model preloading.
Some games do this briefly with the player already on screen, so a manual
save or load can be refused and rewind history can contain gaps until preloading
finishes.
States may be large because they retain the running engine's memory and stack.
Smart and Full with compression On use the fixed 64 MiB coded transport on
every platform, including during loading and Reset. Each state is independently
loadable; Smart can reconstruct exactly reproducible resources from the loaded
content. Full + Off uses the complete base writer and its content-sized
allowance; content that outgrows it requires a restart to use the learned peak.
See [README.md](../README.md#save-states-and-rewind) for the resource limits and
the recommended 256 MiB rewind history at granularity 10.
We only recommend enabling rewind on a Raspberry Pi 5 (quad-core Cortex-A76
at 2.4 GHz) or a device with an equivalent or faster CPU.

Optional developer diagnostics can write beside loaded content when explicitly
enabled; see [DEBUGGING.md](DEBUGGING.md). They are off by default.

## Geometry and timing

The frontend frame rate is **60 Hz** and the audio sample rate is **44,100 Hz**.
Geometry follows the game, with a declared maximum of 4096x4096. The default
aspect ratio follows the game framebuffer. The CRT option changes frontend
framing as documented above; the frontend controls the physical display mode
and interlacing.

## Troubleshooting

- If content fails before boot, check that the frontend supplies a writable
  save directory and that the selected TXT/ZIP has the supported structure.
- If engine detection chooses poorly, select an engine explicitly and use
  Restart. Keep existing saves/settings in their engine-specific directories.
- If a state cannot be loaded, use the same core build and game content and
  wait until threaded video playback has finished.
- For a report, include the core version, platform, selected engine and a small
  reproduction you can share. Follow [SECURITY.md](../SECURITY.md) for private
  reports; avoid attaching third-party PAKs or memory dumps.
