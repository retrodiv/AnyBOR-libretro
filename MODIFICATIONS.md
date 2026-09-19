# AnyBOR port modification record

Record updated: **2026-09-12**. Port maintainer: **retrodiv**
(<retrodiv@proton.me>).

AnyBOR combines six modified OpenBOR snapshots with a shared libretro port.
The original engine work is credited to Senile Team, OpenBOR Team and the
contributors named in the retained sources. The port's own notices identify
its maintained code. Component terms remain as recorded in
[LICENSES.md](LICENSES.md), [PROVENANCE.md](PROVENANCE.md) and the engine licenses.

This catalogue describes the current differences from the **pinned OpenBOR
builds**, rather than comparing every engine to the latest upstream release.
It distinguishes integration features, compatibility choices, corrections and
source packaging. Adding a libretro feature does not imply that standalone
OpenBOR had a defect. [CHANGELOG.md](CHANGELOG.md) records release history;
this document records the resulting source delta.

The 2026-09-11 publication review also adds explicit core-info capability and
runtime notes, checked source-only ZIP packaging, and the infrastructure handoff
and user guide in [PUBLISHING.md](docs/PUBLISHING.md) and
[ANYBOR.md](docs/ANYBOR.md). Binary release ZIPs carry the modification record
and documentation alongside their existing notices and receipts.

## Record dates and file notices

The 2026-09-11 review catalogued existing changes and added file notices and
source references. It is not an implementation date for those earlier changes.
Existing dated comments keep their own dates. Each retained, modified upstream
C/header file has a short AnyBOR notice before its existing contents, with
its scope and a link to this record. Generated `version.h` files identify
their generator instead. Unchanged upstream files do not acquire modification
claims. The notices do not replace original copyright or license blocks.

The file notices state the BSD-3-Clause grant for original AnyBOR work and
retrodiv's original modifications, and distinguish it from the
unchanged upstream licenses. The notice dossier retains the earlier combined BSD
notice and all third-party notices, including OpenBOR 3400's sale conditions.
The notices are documentation; they do not change engine behavior.

## Baselines and complete file inventories

| OpenBOR build | Pinned commit | File inventory |
|---|---|---|
| 3400 | `66fa1529897131ca51528967fbb21ee124e45775` | [3400](docs/modifications/3400.md) |
| 3842 | `1f702a991ace7fa31884262e458a85e351f62713` | [3842](docs/modifications/3842.md) |
| 4086 | `af23dc9c2316bb7853bb266ccf40986aa9765aeb` | [4086](docs/modifications/4086.md) |
| 4432 | `2566cbee6185025e6a69d2aa1823b15c7a154ff9` | [4432](docs/modifications/4432.md) |
| 6412 | `d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8` | [6412](docs/modifications/6412.md) |
| 8020 | `9d81480f8481fbb9e76b0b5f2a5dfa408376761a` | [8020](docs/modifications/8020.md) |

Each inventory links every modified or added engine file to its explanation,
original source at the pinned commit (where it existed). The accompanying `ANYBOR-SOURCE.json` also lists unchanged
files, omitted files from the upstream `engine/` subtree, original/distributed
SHA-256 hashes, and modification topics. Files elsewhere in the upstream repository,
including its standalone tools and repository documentation, are outside this
engine export. Pins and dependency archive hashes are in [src/pin.json](src/pin.json).

The public engine imports include the portable circle and fixed-width endian
adaptations. Their replaced historical implementations are absent from the
distributed sources and documentation. The upstream baselines and original
hashes remain recorded for comparison.

## Platform integration

All six engines include `libretroport.h` through `source/globals.h` and expose
the platform/PNG helper declarations in `source/utils.c`. Builds 4432, 6412
and 8020 also declare libretro thread, mutex and condition types in
`source/gamelib/threads.h`. Each inventory identifies the affected files.

The platform implementation is shared under
[`src/port/libretro/`](src/port/libretro). It replaces standalone host backends
with frontend video, audio, controls and timing; its files are catalogued below.
Each engine gets a generated `version.h` with its pinned build number and a
`Makefile.libretro` from the shared overlay. The version header reports `VERSION_MAJOR="4"` for the 8020 anchor and
retains the historical v3 version strings for the five older anchors.

## Darwin platform support

The macOS targets reuse OpenBOR's own `DARWIN` branches, which upstream kept
in `source/ramlib/ram.c` (mach memory queries instead of `sysinfo`) and in the
script-visible platform constant, but which the Linux-only conditionals around
them had disabled. `30-darwin-platform.patch` extends those conditionals per
engine so the POSIX paths macOS also implements are compiled: case-insensitive
loose-file search and `isRawData()` in `source/gamelib/packfile.c`,
`O_BINARY`/`unistd.h` in `source/gamelib/packfile.h`, `dirent.h`,
`sys/stat.h` and the two-argument `mkdir` in `source/utils.c`, `stricmp` in
`source/gamelib/soundmix.c`, the PC video configuration in `openbor.c`, and
the mach-based memory queries in `source/ramlib/ram.c` instead of the
glibc-only `<malloc.h>`. Each engine's inventory links the affected files and
this topic.

Mach-O has no `objcopy`, no linker scripts and no `--wrap`, so the maintained
port supplies what those provided: [`macho_rewrite.py`](tools/macho_rewrite.py)
localizes one engine's symbols, renames its ABI entry points with the build
suffix and collects its zero-initialized statics into a single per-engine
section; the allocation and `fopen` entry points are defined by
[`obor_alloc.c`](src/port/libretro/obor_alloc.c) and
[`obor_files.c`](src/port/libretro/obor_files.c) so the glue keeps the system
allocator; segment discovery, the snapshot arena claim and the crash reporter's
module range use dyld through
[`obor_macho.h`](src/port/libretro/obor_macho.h) instead of `dl_iterate_phdr`.
The exported entry points are listed explicitly for `ld64` in
[`exports.macho`](src/glue/exports.macho); dyld slides every image, so save
states take the rebasing path rather than the fixed-image one.

## Repeated weapon lists

The 8020 anchor already includes upstream's dynamically sized, ownership-aware weapon-list replacement; it requires no corresponding modification.

Builds 3842, 4086, 4432 and 6412 now resize the model's weapon list
when a later `weapons` command replaces an earlier one. Previously, a longer
replacement wrote beyond the original allocation, corrupting the heap while
loading the affected model. Borrowed lists are copied
into owned storage before replacement. Build 3400 uses a fixed-size array
and does not need this change. The PAK itself is unchanged.

## Animation script safety

Build 3842 now checks that an entity-local animation interpreter exists before
reading its reset flag. Some scripted map entities have an initialized model
animation script before that optional local interpreter is allocated. The old
code dereferenced a null pointer when the entity entered its animation frame;
the guarded behavior matches the later 4086, 4432, 6412 and 8020 engines.
The correction is structural and applies to every build-3842 game.

## Script memory layout

Build 3842 now retains one `ScriptVariant` for each compiled constant instead
of allocating a second identical value. The interpreter pushes that canonical
value directly, matching the representation used by later OpenBOR engines.
The instruction opcode and its Boolean target-kind flag use their bounded
integer widths so each instruction occupies a smaller allocator class on
64-bit targets. These changes reduce the live heap of script-heavy games
without changing script values, execution order or the state restoration
contract.

Build 8020 now stores parser-only token and label pointers in the same slot as
the compiled call or jump target, and stores the mutually exclusive second
operand and call-parameter list in one slot. Its opcode and target kind also
use their bounded widths. This reduces each compiled instruction from 76 to 40
bytes on 64-bit targets while retaining explicit tags for cleanup, diagnostics
and runtime dispatch.

After compilation, all six builds copy the final instructions into one exact
contiguous allocation per interpreter and release the individual parser
allocations. The existing solid instruction pointer list is then retargeted to
the compact storage before entry points and jump targets are resolved. If the
allocation fails, the engines retain their original representation. This
reduces allocator overhead and the number of live chunks the state serializer
must traverse without changing script execution or state completeness.

All six builds resolve execution and jump entry points directly into that
contiguous allocation, and builds with indexed imports do the same for imported
entry points. They then release the redundant pointer table; instruction
stepping uses pointer arithmetic over the same ordered block.

All six builds also copy the independently allocated constant values owned by
those instructions into one exact contiguous allocation per interpreter. Every
instruction operand, call argument and compiled reference is retargeted before
the old value allocations are released. If ownership is ambiguous or either
allocation fails, the interpreter keeps the original values. Cleanup still
clears each value exactly once, so strings and other owned data retain their
normal lifetime while allocator overhead and serialized heap metadata shrink.

The parser workspace is now allocated only while an interpreter is compiling.
After labels, imports and entry points have been resolved, all six builds
release that workspace and keep only the compiled instruction representation.
Import-cache diagnostics check that parser state is still present before
reading parser-only metadata. Runtime scripts and complete save states therefore
retain their compiled program without carrying unused lexer/parser structures.

## Animation draw-method storage

Build 3842 interns byte-identical draw methods used by animation frames. These
methods are immutable after model loading and are copied to a temporary value
before entity-specific rendering adjustments. A reference-counted hash table
therefore lets frames share the same method while preserving model unloading
and save-state ownership. The table and its entries are part of the ordinary
fixed-address state, so restoration does not require rebuilding pointers or
consulting game identity.

## Collision memory layout

Build 8020 keeps the 64 author-facing collision indexes and their active
bitmask, but allocates each collection's pointer table only through its highest
used index. Lookup, cloning, mutation and cleanup retain the same indexed
behavior, including sparse indexes. This avoids reserving 64 native pointers
for every animation frame whose collision collection uses only a few slots.

## Animation memory layout

All six engines initially allocate each model's animation pointer table for
the built-in animation range and grow it in bounded blocks only when authored
content assigns a higher animation index. Lookup, sprite-cache, model-copy,
normalization and cleanup paths use the model's recorded capacity. The global
author-facing animation limit and sparse numeric indexes remain unchanged, so
scripts and model data keep their existing semantics without reserving the
largest table for every loaded model.

## Empty player slot safety

All six engines now require both remaining lives and a selected model name
before automatically spawning a player at the start of a level. Game scripts
may assign lives to an empty multiplayer slot before that player joins; the
previous condition then tried to spawn an unnamed model and aborted the level.
The empty slot remains available through the engines' existing join path. Each engine inventory identifies the affected source.

## Active content PAK aliases

All six libretro engines treat a missing basename-only `Paks/*.pak` file read
as a probe of the active, already validated content archive. Some mods check
the archive name they were originally distributed with from a loading script;
a frontend may legitimately rename that file when organizing a library. The
fallback happens only after an ordinary external-file lookup fails, rejects
subdirectories and traversal, and does not select behavior by title or digest.
Only the first successful missing basename is bound to the active archive;
later opens of the same alias remain valid while alternative platform-specific
names fail, preventing one loading script from retaining multiple full archive
buffers. It reads the current prepared archive without creating a second PAK
file. Each engine inventory identifies the affected source.

The glue also checks a packed game's directory and asset bounds before boot.
A malformed PAK now returns a diagnostic instead of feeding index bytes to
an engine parser. A uniform stale directory base can be recovered structurally:
all entries must describe contiguous data exactly filling the archive, and two
image signatures must corroborate the corrected positions. Gaps, overlaps,
invalid names, truncation and other damage are rejected. No game-name or digest
catalog selects this repair. It changes only directory offsets in a local cache.

Optional input preparation is supplied by `[transforms]` in the frontend system
directory's `AnyBOR.ini`. A bounded buffer compiler and interpreter support
custom headers, embedded archive ranges and byte-order conversion. The normal
PACK validator checks every prepared result. See [content transforms](docs/CONTENT_TRANSFORMS.md).

Auto checks script API support before filename, adjacent EXE or vocabulary
heuristics. A literal call to `getentityproperty(..., "attack", ...)` requires
the legacy API available through pinned build 4086: 4432 and later reject this
property during compilation. The bounded script scan ignores comments and
quoted prose, handles nested first arguments and selects 4086 for this generic
compatibility condition. No game or script digest selects this correction.
Manual engine selection still takes precedence.

## Image loader safety

The legacy image probe validates the PCX signature before using its header
bytes as dimensions. If authored animation data points a frame at a RIFF/WAVE
asset, the engine preserves that animation slot as an empty transparent frame
instead of decoding audio bytes as pixels or allocating a bogus bitmap.

## Four player controls

All engines receive four independent RetroPads through the shared port.
The upstream **8020** engine leaves the entire default control rows for players
2-4 unbound, relying on joystick assignment from its standalone backend.
The port supplies each player's libretro virtual keys
when defaults are initialized or restored from the in-game control menu.
When loading a game configuration or `default.cfg`, it also repairs the exact
legacy profile whose twelve gameplay/screenshot bindings are all `CONTROL_NONE`.
Partial/custom bindings, player 1, rumble preferences and other settings remain
unchanged. See [`openbor.c`](src/engines/8020/openbor.c).

The multiplayer regression uses four independent frontend input timelines
and an original diagnostic game that reports each player's held, newly pressed
and released keys. It checks the game-visible inputs, not just frontend polling.

## Packfile state and resource lifecycle

| Change | Previous condition and current behaviour | Implementation |
|---|---|---|
| Restore PAK descriptors | A memory snapshot cannot restore an operating-system file descriptor. Legacy restored handles are checked with `fstat`; the modern dynamic handle table closes live direct readers before restore and reopens saved sources at their logical offsets. | `source/gamelib/packfile.c`, `obor_packfile_fixup`. |
| Close resources on reset/unload | Rebooting the coroutine must also close the PAK descriptors belonging to the discarded engine instance. The port closes the handle table and the cache PAK descriptor. | `packfile.c`, `obor_packfile_closeall`. |
| Preserve process resources across snapshots | Cache descriptors originally private to `packfile.c` and `filecache.c` are exposed to the port, initialized to `-1`, and invalidated after failed PAK opens. The state layer can preserve current-process descriptors while restoring engine memory. | `pakfd`, `real_pakfd`; [`obor_state.c`](src/port/libretro/obor_state.c). |

These adaptations support AnyBOR snapshots and repeated content loading in a
frontend process. They do not describe a standalone OpenBOR save-file format.

## Legacy content fallbacks

Build **3400 only** handles legacy template files that name absent custom
model or level lists by falling back to `data/models.txt` / `data/levels.txt`.
Its video-settings loader also drops missing level, model, scene and background
overrides. This is a deliberate compatibility fallback for older content, not
a claim that every missing override should be ignored by upstream OpenBOR.
See [`openbor.c`](src/engines/3400/openbor.c), `load_models`, `load_levelorder`
and the video-settings loader.

## WebM playback lifecycle

Builds **4432 and 6412** change `source/webmlib/vidplay.c`:

- Worker-thread sleeps use the host OS sleep function; they must not advance
  the engine coroutine's emulated clock.
- Worker quit flags use atomic loads/stores. An active playback context is
  retained so `obor_webm_stop` can shut down and join workers when a parked
  engine coroutine is discarded on unload/reset.
- `webm_get_next_frame` waits briefly and then yields without holding the queue
  mutex. This lets the frontend consume audio while demux/video workers make
  progress, avoiding a blocking video wait with a full audio queue.

Build **8020** uses upstream's asynchronous movie layer. Its worker sleeps and timeout clocks use wall time, SDL atomics and CPU queries use the native port, and reset joins the entire movie pool. Persistent native synchronization is rebuilt after a state restore.

The platform's [`threads.c`](src/port/libretro/threads.c) publishes each live
worker before its entry point can run, and rolls the count back if native
thread creation fails;
[`obor_state.c`](src/port/libretro/obor_state.c) rejects snapshot operations
during threaded playback. This remains a limitation of save/load/rewind.

## Replacement implementations and attribution

| Scope | Current difference | Source and evidence |
|---|---|---|
| Circle drawing, all engines | Replace the inherited circle routine with the port's integer geometry rasterizer, keeping each engine's pixel-writing interface, clipping and alpha handling. | `source/gamelib/draw.c`, `circle` / `obor_circle_emit`; [`obor_circle.h`](src/port/libretro/obor_circle.h). |
| Endian helpers, all engines | Replace the historical SDL-derived endian implementation with fixed-width types; a 64-bit Windows `long` assumption no longer determines the width of a 64-bit conversion. | `source/gamelib/borendian.h`; [`obor_endian.h`](src/port/libretro/obor_endian.h). |
| ADPCM, shared replacement | Compile the port's IMA ADPCM encoder/decoder for the existing OpenBOR audio API. The inherited `adpcm.c` implementation is omitted from the export; the required upstream interface header is retained. | [`obor_adpcm.c`](src/port/libretro/obor_adpcm.c); [`Makefile.libretro`](src/engines/6412/Makefile.libretro); [provenance](PROVENANCE.md). |
| halloc terms, WebM engines | Add a local `source/webmlib/halloc/LICENSE` containing the terms referenced by the original headers. This is a notice addition. | The 4432, 6412 and 8020 inventories; [provenance](PROVENANCE.md). |

## Source selection and pruning

The export retains compiled engine units and their actual header dependency
closure, plus original license notices. Standalone SDL/console frontends,
their menus, IDE projects, tools and unused data are omitted. Engine source
omissions are inventoried separately from retained files that were edited.

The source selection removes six packfile APIs used only by omitted
standalone browsers and music-preview frontends: `readpackfile_noblock`,
`packfileeof`, `packfile_supported`, `packfile_get_titlename`,
`packfile_music_read` and `packfile_music_play`, plus their public declarations
where present. The remaining engine logic is retained; ordinary linker dead
code removal is not represented as a source edit. See each engine's
`source/gamelib/packfile.c` and `packfile.h`.

## Shared port and frontend

These maintained sources are additions or platform replacements, rather than
unchanged OpenBOR engine files. Existing incorporated-material notices remain
in their respective files.

| Capability or change | Behaviour and current implementation |
|---|---|
| Six engines in one core | Each engine is partially linked with private symbols; suffixed ABI entry points select the active engine. [`obor_abi.h`](src/glue/obor_abi.h), [`obor_engines.h`](src/glue/obor_engines.h), [`Makefile.libretro`](src/engines/6412/Makefile.libretro), [`tools/build.py`](tools/build.py). |
| Automatic engine selection | An explicit core option takes precedence; otherwise inspect legacy script API requirements, filename tags, nearby executables as data, and PAK content tokens, then use the pinned fallback. Selection is rerun on Reset. [`libretro.cpp`](src/glue/libretro.cpp), `decide_engine`, `pick_anchor`, `build_from_content`; [`obor_markers.h`](src/glue/obor_markers.h). |
| Frontend-owned frame delivery | Run the engine main loop on a libco coroutine, yield at video submission, and advance an emulated microsecond clock. Sleep/input-wait paths also yield so frontend input remains live. [`libretroport.c`](src/port/libretro/libretroport.c), [`libretroport.h`](src/port/libretro/libretroport.h), [`timer.c`](src/port/libretro/timer.c). |
| Video and audio backends | Convert engine video to XRGB8888, publish geometry, and pull engine audio through the frontend. [`video.c`](src/port/libretro/video.c), [`video.h`](src/port/libretro/video.h), [`vga.h`](src/port/libretro/vga.h), [`sblaster.c`](src/port/libretro/sblaster.c), [`sblaster.h`](src/port/libretro/sblaster.h). |
| Four-player controls and move macros | RetroPad/optional analog input, rumble, content-derived control labels and facing-aware special-move macros. [`control.c`](src/port/libretro/control.c), [`control.h`](src/port/libretro/control.h), [`playerinfo.c`](src/port/libretro/playerinfo.c), [`obor_padmap.h`](src/glue/obor_padmap.h), `macro_frame` / `rumble_frame` in [`libretro.cpp`](src/glue/libretro.cpp). |
| Optional CRT framing | Fit images wider than 364 pixels or taller than 244 pixels into 640x480 with their original aspect, centred borders and sharp-bilinear scaling, preserving the engine's internal render size. Smaller images outside 4:3 +/-10% receive native-pixel black padding on one axis, then the size limits are checked again. [`obor_crt.h`](src/glue/obor_crt.h), `retro_run` in [`libretro.cpp`](src/glue/libretro.cpp); [option contract](README.md#video-options). |
| Memory snapshots and rewind | Allocate engine state and coroutine stack in a fixed-address arena; preserve writable module data, repair process resources, and retain historical input on rewind. [`obor_alloc.c`](src/port/libretro/obor_alloc.c), [`obor_state.c`](src/port/libretro/obor_state.c), `glue_save` / `glue_load` in [`libretro.cpp`](src/glue/libretro.cpp). |
| Snapshot size and reset correctness | Exclude inactive engines' BSS using linker boundaries; permit growth only when the frontend supports variable serialization sizes, otherwise keep the advertised size fixed until unload; clear unused transport bytes; restore the pristine writable module image for a new engine boot. [`state_layout.py`](tools/state_layout.py), [`obor_state_padding.h`](src/glue/obor_state_padding.h), `pristine_restore` / `retro_reset` in [`libretro.cpp`](src/glue/libretro.cpp). |
| Mach-O targets | Apple's linker performs the relocatable engine link (`ld -r -d`); [`macho_rewrite.py`](tools/macho_rewrite.py) then localizes each engine's symbols, applies the ABI build suffix and merges its zero-initialized statics into one `__obss<build>` section whose boundaries the engine region table uses. Allocation and `fopen` interposers in the port layer replace `--wrap`, dyld supplies segment and image ranges through [`obor_macho.h`](src/port/libretro/obor_macho.h), and the exported entry points come from [`exports.macho`](src/glue/exports.macho). [`macho_inspect.py`](tools/macho_inspect.py) reads the same fields back for build receipts and checks. |
| PAK, unpacked content and ZIP loading | Accept a PAK, `data/models.txt`, or one game in a ZIP. Validate archive paths and limits before extraction and key the extraction cache by content hash. [`obor_zip.h`](src/glue/obor_zip.h), [`obor_zip_path.h`](src/glue/obor_zip_path.h), [`obor_sha256.h`](src/glue/obor_sha256.h). |
| Frontend save directories | Place per-engine saves/settings under the frontend directory's `AnyBOR/<game>/<build>/`, create missing parents, and use `AnyBOR-cache/zipcache/` for extraction. This isolates incompatible settings layouts. `retro_load_game` / `mkdir_p` in [`libretro.cpp`](src/glue/libretro.cpp), `obor_boot` in [`libretroport.c`](src/port/libretro/libretroport.c). |
| Threading and host portability | Supply pthread/Windows workers and synchronization, publish workers before execution so snapshots cannot race startup, preserve Windows coroutine stack bounds, isolate MinGW reference sections, and generate ELF/PE BSS layouts. [`threads.c`](src/port/libretro/threads.c), [`libretroport.c`](src/port/libretro/libretroport.c), [`tools/build.py`](tools/build.py), [`glibc_compat_math.c`](src/compat/glibc_compat_math.c). The Recalbox target disables input descriptors, content-derived pad labels and routine on-screen notifications (load errors remain visible), and enforces a GLIBC 2.38 ceiling. |
| Diagnostics and frontend interfaces | Expose core options, engine-selection notifications, input descriptors and memory maps; provide optional game-log forwarding and crash/frame/rewind diagnostics. [`libretro.cpp`](src/glue/libretro.cpp), [`obor_debug.h`](src/glue/obor_debug.h); [diagnostic controls](docs/DEBUGGING.md), [API contract](docs/LIBRETRO.md). |
| Source/build publication | Bundle build inputs and notices, limit exports with [`exports.map`](src/glue/exports.map), and provide source checks, build receipts and release packaging. The notice dossier is embedded via [`obor_notices.h`](src/glue/obor_notices.h) and can be written to a frontend directory. [Source inventory](SOURCES.json), [SBOM](SBOM.spdx.json), [`tools/release.py`](tools/release.py). |

## Imported dependencies and verification

The libretro API header, miniz, dlmalloc, retained libco files and the selected
zlib/libpng/libogg/libvorbis/libvpx sources are pinned imports. They are not
claimed as port-authored engine modifications. Their original notices and
archive identities are retained. libco includes the AMD64 and AArch64 backends
needed by the published targets; dependency examples, media and unused platform
files are omitted as described in their manifests and [PROVENANCE.md](PROVENANCE.md).

Bundled build scripts run as published; where a released script would set a
linker switch the local toolchain rejects, the build removes that switch from
its own disposable copy instead of editing the pinned archive.

`make check` checks the source inventory, component hashes, file
notices and catalogue links, and runs the public primitive checks. The original
diagnostic fixture and smoke/regression/rewind/CRT tools are described in
[docs/TESTING.md](docs/TESTING.md). These tests are regression evidence for the
port; this record makes no claim of exhaustive equivalence with standalone
OpenBOR for every game or target.

This record and the per-engine inventories describe the maintained source
release. Git history records source changes, including modification notices.
Release checks ensure that
every retained change has an explanation, evidence and an applicable notice.

## Current v4 integration

The 8020 anchor is official upstream master commit
`9d81480f8481fbb9e76b0b5f2a5dfa408376761a` (2026-08-24), verified on
2026-09-12. Its import follows the five historical engines;
6412 remains the default fallback. Content markers are updated for this set.

The shared audio backend converts upstream's signed 32-bit transport for
24-bit PCM at 48 kHz into libretro stereo PCM at 44.1 kHz. Recursive audio
ownership synchronizes decoder workers with frontend mixing. The modern
movie layer uses the native thread backend, real worker clocks and 32-bit
YUV conversion. Its persistent mutex is reinitialized after state restores;
active workers continue to prevent unsafe snapshots.

Direct PAK and loose-file readers retain their source path and logical
position. State restoration closes current direct descriptors before
replacing memory, then reopens the saved readers. Saved descriptor numbers
are never used to close frontend resources. The legacy ADPCM replacement is
compiled only for engines that retain that API.
## Audio memory layout

Large decoded sound effects use the modern engine's existing streamed-sample
path so immutable PCM does not become part of every rewind checkpoint.
