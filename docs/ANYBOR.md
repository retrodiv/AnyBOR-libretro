# OpenBOR (AnyBOR)

AnyBOR is an independent libretro core for OpenBOR games. It combines OpenBOR
builds 3400, 3842, 4086, 4432, 6412 and 8020 and selects an engine for each game.
OpenBOR and Beats of Rage originate with Senile Team and OpenBOR Team; the port
is maintained by retrodiv. The combined core has multiple component licenses,
including OpenBOR 3400's no-sale terms. See [LICENSES.md](../LICENSES.md).

## Requirements and loading content

Use a supported 64-bit frontend: Linux x86-64/ARM64, Windows x86-64 or Android
ARM64 (API 24 or later). Configure a writable **Save Files** directory in
RetroArch. The core requires that directory even when a particular game does
not use ordinary saves. No BIOS or firmware is required or included.

Load one of these with **Load Content**, then select AnyBOR:

| Extension | Accepted content |
|---|---|
| `.pak` | An OpenBOR game archive. |
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
| Save states and rewind | Supported; states require the same core build and content. Unavailable during threaded video playback. |
| Netplay/runahead | The metadata advertises `serialized` state support; it makes no general deterministic/netplay/runahead compatibility claim. |
| Players and remapping | Up to four RetroPads, subject to the game's player limit; frontend button remapping supported. |
| Rumble | Optional forwarding of the game's hit vibration. |
| Core options | Version 2.0 categories, with a flat fallback for older frontends. |
| RetroArch cheats | Not implemented. A game's own cheats/options remain game-specific. |
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
| Y | Attack |
| B | Jump |
| A | Special |
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
| Adjust for 4:3 CRT TV | `obor_crt_tv` | **Off**. Fit images wider than 364 pixels or taller than 244 pixels into 640x480, preserving their aspect with borders and sharp-bilinear scaling. Smaller images outside 4:3 +/-10% receive native-pixel black padding to 4:3, then the size limits are checked again. Applies during play; see the [video contract](../README.md#video-options) for thresholds and examples. |
| Left analog stick as D-pad | `obor_analog` | **On**. Adds movement with the left stick. |
| Rumble | `obor_rumble` | **On**. Forwards game hit vibration. |
| Special move macros (L2/R2/L3/R3) | `obor_macros` | **On**. Executes supported character move sequences. |
| Engine build | `obor_engine` | **Auto**. Select an explicit pinned engine when needed; changes apply on Restart. |
| Forward game log | `obor_gamelog` | **Off**. Mirrors the engine log into the frontend log. |

Automatic selection uses filename version tags, nearby engine-version data
and PAK content markers, with build 6412 as the current fallback. An explicit
engine choice takes precedence. Games predating the available source history
use the 3400 anchor on a best-effort basis; games newer than the latest anchor
also have best-effort coverage. [COMPATIBILITY.md](../COMPATIBILITY.md) describes
the supported engine ranges.

## Files and directories

Paths below are relative to the frontend's **Save Files** directory:

| Path | Purpose |
|---|---|
| `AnyBOR/<engine build>/` | Engine-specific saves, settings, logs and learned memory-peak data. Different engine settings layouts stay separate. |
| `AnyBOR/zipcache/` | Cached extraction of ZIP content. |
| `anybor-license-notices.txt` | The complete notice dossier embedded in the loaded core; attempted in this directory when content is loaded. |

RetroArch places save-state files in its configured **Save States** directory.
Ordinary engine saves use their own files rather than a libretro save-RAM block.
States may be large because they retain the running engine's memory and stack.
A frontend that supports variable serialization sizes may receive a larger
state while content is loaded. On fixed-capacity frontends, the state capacity
stays fixed until content unload; a game that outgrows its allowance needs a
restart to use its learned peak. See [README.md](../README.md#save-states-and-rewind).

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
