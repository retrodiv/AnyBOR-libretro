# AnyBOR port modification record

Record updated: **2026-10-10**. Port maintainer: **retrodiv**
(<retrodiv@proton.me>).

AnyBOR offers thirteen selectable profiles backed by nine OpenBOR engines with
a shared libretro port.
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
The 6391 and 6412 compatibility changes were recorded on 2026-09-29.
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
| v3.0 3400 | `66fa1529897131ca51528967fbb21ee124e45775` | [v3.0 3400](docs/modifications/3400.md) |
| v3.0 3842 | `1f702a991ace7fa31884262e458a85e351f62713` | [v3.0 3842](docs/modifications/3842.md) |
| v3.0 4086 | `af23dc9c2316bb7853bb266ccf40986aa9765aeb` | [v3.0 4086](docs/modifications/4086.md) |
| v3.0 4432 | `2566cbee6185025e6a69d2aa1823b15c7a154ff9` | [v3.0 4432](docs/modifications/4432.md) |
| v3.0 6391 | `494708eb34e71d1afda237873907701c4ec3a569` | [v3.0 6391](docs/modifications/6391.md) |
| v3.0 7123-dev | `81049d95c50c4c26e2637cc89ab3056bfcc77d16` | [v3.0 7123-dev](docs/modifications/7123.md) |
| v4.0 7142-alpha | `9dcd966d1dc8e93ff03c39edbd6bd262f4a2d7ab` | [v4.0 7142-alpha](docs/modifications/7142.md) |
| v4.0 7533 | `5c8261444de6b61f8e2ce6e79e3d86a2949e55bd` | [v4.0 7533](docs/modifications/7533.md) |
| v4.0 8023-dev | `16aae1a30b81063778f21977ae20b849bd1c76f9` | [v4.0 8023-dev](docs/modifications/8023.md) |

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

All engine source trees include `libretroport.h` through `source/globals.h` and expose
the platform/PNG helper declarations in `source/utils.c`. Engines v3.0 4432, v3.0 6391, v3.0 7123-dev, v4.0 7142-alpha,
v4.0 7533 and v4.0 8023-dev also declare libretro thread, mutex and condition types in
`source/gamelib/threads.h`. Each inventory identifies the affected files.

Engines v4.0 8023-dev place the player array in aligned storage. The PE linker otherwise
allocates its tentative common symbol at a four-byte boundary even though
compiled menu code reads it with a 16-byte SIMD operand.

The platform implementation is shared under
[`src/port/libretro/`](src/port/libretro). It replaces standalone host backends
with frontend video, audio, controls and timing; its files are catalogued below.
Each engine gets a generated `version.h` with its pinned build number and a
`Makefile.libretro` from the shared overlay. The version header reports `VERSION_MAJOR="4"` for v4.0 7533 and v4.0 8023-dev.
The other headers preserve upstream version 3, including v4.0 7142-alpha;
frontend labels describe its actual published alpha identity.

## Loading screen presentation

`28-loading-progress.patch` lets `update_loading` repaint when the actual
model/level progress crosses an integer percentage. Resource loading can do
substantial work without advancing the emulated frame clock; progress breaks
that cycle while keeping scheduling deterministic. The original background,
font, loading script and bar renderer remain responsible for the image.

For packed content, `36-cooperative-model-preload.patch` returns control to the frontend after
each newly completed model within explicit model-list or level preparation,
including nested loads. It re-presents the last frame without repainting or
calling loading scripts again. A single model still finishes synchronously.
Ordinary scripted model loads outside those preparation phases retain their
existing scheduling. Save, load and prepared-state capture callbacks refuse the
intermediate preparation context before touching state buffers or engine
memory; state capacity stays available and normal states resume after cleanup.
Reset and unload discard the context. No content identity selects this path.
Loose content still completes initial startup synchronously inside
`retro_load_game`; its boot waits do not return to the frontend between models.

A frontend that queues a rewind block despite a failed save callback may retain
a previous or uninitialized block during preparation. Core refusal preserves
the live engine; it does not guarantee the frontend discards that history entry.
Stock validation must keep rewind enabled through startup and level loading,
then check reverse playback and usable continuation after any rejected loads.

The shared coroutine returns its initial yield to the frontend and presents
that pending frame through `retro_run`. Later loading frames also run through
the ordinary video/audio callbacks. `obor_loading.h` supplies the progress
comparison, and the internal engine ABI exposes resource initialization
completion. State capacity reserves use packed resource sizes and learned
peaks before frontend rewind allocation. Gameplay diagnostic timelines start
after initialization.

Packed-content preparation runs on a separate disposable libco stack, yielding
between I/O and integrity-check blocks. The startup artwork has a determinate
bar: existing reads, writes and integrity checks report processed bytes within
weighted preparation phases. This estimates total preparation work, not time
remaining; optional extraction, repairs and external programs prevent an exact
time percentage. Unmeasurable operations hold their position until they finish.
The meter never advances just because another frame is drawn, never goes
backwards between passes and reaches 100% only after successful preparation
and engine boot. It adds no content scan, payload read, buffer allocation or
extra coroutine yield; the existing 32 ms checkpoint interval is retained.
The engine then supplies its
native loading screen. Preparation has no game snapshot: the negotiated
`MUST_INITIALIZE` quirk covers this interval, while a nonzero capacity estimate
lets frontends reserve rewind. Cancellation resumes normal cleanup before
destroying the preparation stack. No game identity or decoding recipe is added.

## Darwin platform support

Darwin compilations enable `_DARWIN_C_SOURCE` before any system header is read.
This keeps `Dl_info` and `dladdr` visible even in port files that request a
POSIX namespace. The setting applies to every engine and the shared glue.

The macOS targets reuse OpenBOR's own `DARWIN` branches, which upstream kept
in `source/ramlib/ram.c` (mach memory queries instead of `sysinfo`) and in the
script-visible platform constant, but which the Linux-only conditionals around
them had disabled. `30-darwin-platform.patch` extends those conditionals per
engine so the POSIX paths macOS also implements are compiled: case-insensitive
loose-file search and `isRawData()` in `source/gamelib/packfile.c`,
`O_BINARY`/`unistd.h` in `source/gamelib/packfile.h`, `dirent.h`,
`sys/stat.h` and the two-argument `mkdir` in `source/utils.c`, `stricmp` in
`source/gamelib/soundmix.c`, the PC video configuration in `openbor.c`, the
standard allocation declarations in `source/utils.c`,
`source/preprocessorlib/pp_parser.c` and `source/pnglib/savepng.c` where the
macOS SDK does not provide the glibc-only `<malloc.h>`, and the mach-based
memory queries in `source/ramlib/ram.c` plus 6391's out-of-memory diagnostic in
`source/utils.c`. Each engine's inventory links the affected files and
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
[`exports.macho`](src/glue/exports.macho). Because dyld can slide the image,
cross-process states may be refused when its address changes; the unsafe
pointer-guessing rebase path has been removed.

## Repeated weapon lists

The 8023 anchor already includes upstream's dynamically sized, ownership-aware weapon-list replacement; it requires no corresponding modification.

Builds 3842, 4086, 4432 and 6391 now resize the model's weapon list
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
the guarded behavior matches the later 4086, 4432, 6391, 7533 and 8023 engines.
The correction is structural and applies to every build-3842 game.

## Script memory layout

After compilation, the common executable-stream compactor removes instruction
records used only by the compiler. Each engine supplies its instruction and
export metadata before pointer resolution. Entry points, branch targets,
exported functions, sentinel records and every owned mutable value remain
valid. A separate value count governs exactly-once cleanup, including values
whose compiler records have been removed. Legacy opcode behavior is retained;
an unsupported representation or allocation failure keeps the original stream.
This reduces the state that actually needs copying and compression, without
omitting mutable script data or selecting behavior by game identity.

Build 3842 now retains one `ScriptVariant` for each compiled constant instead
of allocating a second identical value. The interpreter pushes that canonical
value directly, matching the representation used by later OpenBOR engines.
The instruction opcode and its Boolean target-kind flag use their bounded
integer widths so each instruction occupies a smaller allocator class on
64-bit targets. These changes reduce the live heap of script-heavy games
without changing script values, execution order or the state restoration
contract.

Build 8023 now stores parser-only token and label pointers in the same slot as
the compiled call or jump target, and stores the mutually exclusive second
operand and call-parameter list in one slot. Its opcode and target kind also
use their bounded widths. This reduces each compiled instruction from 76 to 40
bytes on 64-bit targets while retaining explicit tags for cleanup, diagnostics
and runtime dispatch.

After compilation, all engine builds copy the final instructions into one exact
contiguous allocation per interpreter and release the individual parser
allocations. The existing solid instruction pointer list is then retargeted to
the compact storage before entry points and jump targets are resolved. If the
allocation fails, the engines retain their original representation. This
reduces allocator overhead and the number of live chunks the state serializer
must traverse without changing script execution or state completeness.

All engine builds resolve execution and jump entry points directly into that
contiguous allocation, and builds with indexed imports do the same for imported
entry points. They then release the redundant pointer table; instruction
stepping uses pointer arithmetic over the same ordered block.

All engine builds also copy the independently allocated constant values owned by
those instructions into one exact contiguous allocation per interpreter. Every
instruction operand, call argument and compiled reference is retargeted before
the old value allocations are released. If ownership is ambiguous or either
allocation fails, the interpreter keeps the original values. Cleanup still
clears each value exactly once, so strings and other owned data retain their
normal lifetime while allocator overhead and serialized heap metadata shrink.

The parser workspace is now allocated only while an interpreter is compiling.
After labels, imports and entry points have been resolved, all engine builds
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

Build 8023 keeps the 64 author-facing collision indexes and their active
bitmask, but allocates each collection's pointer table only through its highest
used index. Lookup, cloning, mutation and cleanup retain the same indexed
behavior, including sparse indexes. This avoids reserving 64 native pointers
for every animation frame whose collision collection uses only a few slots.

## Animation memory layout

All thirteen selectable engines initially allocate each model's animation pointer table for
the built-in animation range and grow it in bounded blocks only when authored
content assigns a higher animation index. Lookup, sprite-cache, model-copy,
normalization and cleanup paths use the model's recorded capacity. The global
author-facing animation limit and sparse numeric indexes remain unchanged, so
scripts and model data keep their existing semantics without reserving the
largest table for every loaded model.

## Empty player slot safety

All thirteen selectable engines now require both remaining lives and a selected model name
before automatically spawning a player at the start of a level. Game scripts
may assign lives to an empty multiplayer slot before that player joins; the
previous condition then tried to spawn an unnamed model and aborted the level.
The empty slot remains available through the engines' existing join path. Each engine inventory identifies the affected source.

## Active content PAK aliases

All thirteen selectable engines treat a missing basename-only `Paks/*.pak` file read
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

Filename build tags accept a numeric prefix followed by trailing `X` digits.
The selector picks the highest available logical profile inside that interval,
including explicit-only profiles, and preserves that profile directly. If
there is no match, the interval's upper endpoint goes through ordinary
automatic routing. Existing exact-build, manual and legacy-API priorities
remain in effect.
Explicit inclusive intervals (`Build 3800-4200`, with `XXXX` allowed at either
endpoint) constrain both the selected profile and its physical engine. Auto
reports an unavailable engine if no candidate lies within those bounds;
manual selection can override them. The bounds describe content evidence,
independently of the engines included in a particular release.

## Image loader safety

The legacy image probe validates the PCX signature before using its header
bytes as dimensions. If authored animation data points a frame at a RIFF/WAVE
asset, the engine preserves that animation slot as an empty transparent frame
instead of decoding audio bytes as pixels or allocating a bogus bitmap.

## Four player controls

All engines receive four independent RetroPads through the shared port.
The upstream 7533 engine leaves players 2-4 without default bindings; the
port initializes those rows and repairs wholly empty older profiles. The
8023 controller branch uses four independent RetroPad devices and persists
per-device button mappings in `.controls` files. Its in-game control menu can
reassign devices and buttons. The frontend can remap each RetroPad as usual.
See [`openbor.c`](src/engines/8023/openbor.c).

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

Builds **4432, 6391, 7123, 7142 and 7533** change `source/webmlib/vidplay.c`:

- Worker-thread sleeps use the host OS sleep function; they must not advance
  the engine coroutine's emulated clock.
- Worker quit flags use atomic loads/stores. An active playback context is
  retained so `obor_webm_stop` can shut down and join workers when a parked
  engine coroutine is discarded on unload/reset.
- `webm_get_next_frame` waits briefly and then yields without holding the queue
  mutex. This lets the frontend consume audio while demux/video workers make
  progress, avoiding a blocking video wait with a full audio queue.

Build **8023** uses upstream's asynchronous movie layer. Its worker sleeps and timeout clocks use wall time, SDL atomics and CPU queries use the native port, and reset joins the entire movie pool. Persistent native synchronization is rebuilt after a state restore.

The explicitly enabled reproducible-media diagnostic uses a shared bounded
readiness policy and engine adapters for the classic mixer and newer movie
channels. Audio is ready before mixing and requested video is ready before
consumption. Silent movies service background music on the owner thread.
Normal scheduling remains the default. Diagnostic blocks are limited before
allocation, compressed queues have byte and item bounds, and decoded image
reserves are bounded. Readiness failures invalidate the diagnostic; no hidden
guest frames, frozen clocks, additional rewind history or unbounded queues
make a comparison appear reproducible. See [Local diagnostics](docs/DEBUGGING.md).

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
| ADPCM, shared replacement | Compile the port's IMA ADPCM encoder/decoder for the existing OpenBOR audio API. The inherited `adpcm.c` implementation is omitted from the export; the required upstream interface header is retained. | [`obor_adpcm.c`](src/port/libretro/obor_adpcm.c); [`Makefile.libretro`](src/engines/6391/Makefile.libretro); [provenance](PROVENANCE.md). |
| halloc terms, WebM engines | Add a local `source/webmlib/halloc/LICENSE` containing the terms referenced by the original headers. This is a notice addition. | The 4432, 6391, 7533 and 8023 inventories; [provenance](PROVENANCE.md). |

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

## Compiler warning cleanup

The engine is built with `-Wall` on clang, and the exported sources now compile
free of warnings on every target. The cleanup only restores intended behaviour;
no structure layout changes, and the pack-state edits were verified with
record-layout dumps to leave every type byte-identical:

- Headers that set a `#pragma pack` alignment for their own declarations now
  bracket it with `push`/`pop` (`openbor.h`, `source/gamelib/anigif.h`,
  `source/gamelib/depends.h`), so including them no longer leaves the caller's
  alignment modified. The packed declarations themselves are unchanged.
- The draw-method one-bit flags are declared `unsigned`; the engine assigns
  them `1`, which a signed one-bit field stores as `-1`.
- Entry points that were declared with empty parentheses while their
  definitions take parameters now carry real prototypes (`standard_palette`,
  `inputrefresh`, `cache_model_sprites`, `free_model`, `StrCache_Pop`).
- Command-list lookups and stored indices convert through `intptr_t`/`uintptr_t`
  instead of plain pointer casts; the values themselves are unchanged.
- Genuine defects found by the same pass: the level loader's file buffer and
  the imported script text are initialized before their error paths can free
  them, an optional text-object timeout and an optional stall argument start at
  zero, bounce velocities use the float absolute value, and dead tests or
  statements (always-true array checks, a self-comparison, a self-assignment,
  an unused local typedef) were removed.
- Headers that only declared `inline` helpers whose definitions live in the
  matching source file now declare ordinary functions (`ScriptVariant.h`,
  `source/gamelib/transform.h`).

## Logical profile compatibility

Patch `96-logical-4453-compat.patch` adapts the behavior of upstream
[4453](https://github.com/DCurrent/openbor/commit/7906e2573fcd70e9eafcd30fbdcc680832c4ae42)
(2017-04-08). Profile 4453 forces 32-bit screens, keeps model-local indexed
palettes, ignores `colourdepth` and skips the legacy `remap`-to-palette
conversion removed in that revision. The earlier profile retains its video
configuration and palette conversion. Native settings I/O packs and unpacks
the original 4432 12-entry
layout and uses the 4453 13-entry layout directly. Profile identity keeps
their directories and save states separate. The later control menu disables
Exit reassignment. Both profiles bound the DOT loop to its allocated slots
and keep control-menu indexing within its arrays.


Engine 6391 uses upstream commit
[`494708eb34e71d1afda237873907701c4ec3a569`](https://github.com/DCurrent/openbor/commit/494708eb34e71d1afda237873907701c4ec3a569).
Patch `96-logical-6412-compat.patch` adapts the later upstream 6412 script
changes from commit
[`d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8`](https://github.com/DCurrent/openbor/commit/d9bfceeb0d53cd43ed7cf5cfdfb0c60bba4df3f8)
for engine 6412. Engine 6391 retains its scalar binding properties
and numeric property IDs. Engine 6412 exposes axis-handle binding
properties, owner and opponent entity properties, binding animation flags,
the corrected Y-axis setter, frame-kill binding behavior, and `unload_model`.
Each profile has its own save directory.

Patches `97-logical-6330-compat.patch` and `98-logical-6510-compat.patch`
adapt the earlier [6330 source](https://github.com/DCurrent/openbor/commit/4b1705fa37457ab38bc5d0fcc561242019588e32)
and later [6510 source](https://github.com/DCurrent/openbor/commit/ecce29b95700468aa3401915625dac2d56e4ca60)
inside the same 6391 engine object. Runtime profile branches restore 6330's
boomerang model commands, projectile movement and catching, earlier juggle
condition and settings layout. The 6510 branches supply binding matching,
positioning, tags, overrides and script events, revised blocking and flashes,
and the distinct boss-death attack type. Native animation, attack, entity,
subtype and spawn IDs are translated at script boundaries so adding shared
selectors does not change the public numbering of older profiles. The earlier
collision scripting entry points remain unavailable in profile 6330.

## Shared port and frontend

These maintained sources are additions or platform replacements, rather than
unchanged OpenBOR engine files. Existing incorporated-material notices remain
in their respective files.

| Capability or change | Behaviour and current implementation |
|---|---|
| Eleven selectable engines | Core Options offers 3400, 3842, 4086, 4432, 4453, 6330, 6391, 6412, 6510, 7533 and 8023, plus Auto. Each selection retains its own compatibility behavior and save directory. [`obor_abi.h`](src/glue/obor_abi.h), [`obor_engines.h`](src/glue/obor_engines.h), [`Makefile.libretro`](src/engines/6391/Makefile.libretro), [`tools/build.py`](tools/build.py). |
| Automatic engine selection | An explicit core option takes precedence; otherwise inspect legacy script API requirements, filename tags, nearby executables as data, and PAK content tokens, then use the pinned fallback. Selection is rerun on Reset. [`libretro.cpp`](src/glue/libretro.cpp), `decide_engine`, `pick_anchor`, `build_from_content`; [`obor_markers.h`](src/glue/obor_markers.h). |
| Frontend-owned frame delivery | Run the engine main loop on a libco coroutine, yield at video submission, and advance an emulated microsecond clock. Sleep/input-wait paths also yield so frontend input remains live. [`libretroport.c`](src/port/libretro/libretroport.c), [`libretroport.h`](src/port/libretro/libretroport.h), [`timer.c`](src/port/libretro/timer.c). |
| Video and audio backends | Convert engine video to XRGB8888, publish geometry, and pull engine audio through the frontend. [`video.c`](src/port/libretro/video.c), [`video.h`](src/port/libretro/video.h), [`vga.h`](src/port/libretro/vga.h), [`sblaster.c`](src/port/libretro/sblaster.c), [`sblaster.h`](src/port/libretro/sblaster.h). |
| Four-player controls and move macros | RetroPad/optional analog input, rumble, content-derived control labels and facing-aware special-move macros. [`control.c`](src/port/libretro/control.c), [`control.h`](src/port/libretro/control.h), [`playerinfo.c`](src/port/libretro/playerinfo.c), [`obor_padmap.h`](src/glue/obor_padmap.h), `macro_frame` / `rumble_frame` in [`libretro.cpp`](src/glue/libretro.cpp). |
| Optional CRT framing | Fit images wider than 364 pixels or taller than 244 pixels into 640x480 with their original aspect, centred borders and sharp-bilinear scaling, preserving the engine's internal render size. Smaller images outside 4:3 +/-10% receive native-pixel black padding on one axis, then the size limits are checked again. [`obor_crt.h`](src/glue/obor_crt.h), `retro_run` in [`libretro.cpp`](src/glue/libretro.cpp); [option contract](docs/ANYBOR.md#video-contract-adjust-for-43-crt-tv). |
| Memory snapshots and rewind | Allocate engine state and coroutine stack in a fixed-address arena; preserve writable module data, repair process resources, and retain historical input when the frontend explicitly reports rewind. Ordinary state loads sample live input on the first forward frame, including frontends without throttle reporting. [`obor_alloc.c`](src/port/libretro/obor_alloc.c), [`obor_state.c`](src/port/libretro/obor_state.c), `glue_save` / `glue_load` in [`libretro.cpp`](src/glue/libretro.cpp). |
| Snapshot size and reset correctness | Exclude inactive engines' BSS using linker boundaries; permit growth only when the frontend supports variable serialization sizes, otherwise keep the advertised size fixed until unload; clear unused transport bytes; restore the pristine writable module image for a new engine boot. [`state_layout.py`](tools/state_layout.py), [`obor_state_padding.h`](src/glue/obor_state_padding.h), `pristine_restore` / `retro_reset` in [`libretro.cpp`](src/glue/libretro.cpp). |
| Mach-O targets | Apple's linker performs the relocatable engine link (`ld -r`); the common-definition switch is probed by linking a trivial object and only passed when the toolchain accepts it, since the linker in Xcode 15 and later defines commons itself. [`macho_rewrite.py`](tools/macho_rewrite.py) then localizes each engine's symbols, applies the ABI build suffix, gives any tentative definition the linker left unresolved storage in the engine's region, and merges its zero-initialized statics into one `__obss<build>` section whose boundaries the engine region table uses; references that address the moved section by ordinal are repointed at the region and refused when their form cannot be followed safely. Allocation and `fopen` interposers in the port layer replace `--wrap`, dyld supplies segment and image ranges through [`obor_macho.h`](src/port/libretro/obor_macho.h), and the exported entry points come from [`exports.macho`](src/glue/exports.macho). [`macho_inspect.py`](tools/macho_inspect.py) reads the same fields back for build receipts and checks. |
| PAK, unpacked content and ZIP loading | Accept a PAK, `data/models.txt`, or one game in a ZIP. Validate archive paths and limits before extraction and key the extraction cache by content hash. [`obor_zip.h`](src/glue/obor_zip.h), [`obor_zip_path.h`](src/glue/obor_zip_path.h), [`obor_sha256.h`](src/glue/obor_sha256.h). |
| Frontend save directories | Place per-engine saves/settings under the frontend directory's `AnyBOR/<game>/<build>/`, create missing parents, and use `AnyBOR-cache/zipcache/` for extraction. This isolates incompatible settings layouts. `retro_load_game` / `mkdir_p` in [`libretro.cpp`](src/glue/libretro.cpp), `obor_boot` in [`libretroport.c`](src/port/libretro/libretroport.c). |
| Threading and host portability | Supply pthread/Windows workers and synchronization, publish workers before execution so snapshots cannot race startup, preserve Windows coroutine stack bounds, isolate MinGW reference sections, and generate ELF/PE BSS layouts. [`threads.c`](src/port/libretro/threads.c), [`libretroport.c`](src/port/libretro/libretroport.c), [`tools/build.py`](tools/build.py), [`glibc_compat_math.c`](src/compat/glibc_compat_math.c). The Recalbox target disables input descriptors, content-derived pad labels and routine on-screen notifications (load errors remain visible), and enforces a GLIBC 2.38 ceiling. |
| Diagnostics and frontend interfaces | Expose core options, engine-selection notifications, input descriptors and memory maps; provide optional game-log forwarding and crash/frame/rewind diagnostics. [`libretro.cpp`](src/glue/libretro.cpp), [`obor_debug.h`](src/glue/obor_debug.h); [diagnostic controls](docs/DEBUGGING.md), [API contract](docs/LIBRETRO.md). |
| Source/build publication | Bundle build inputs and notices, limit exports with [`exports.map`](src/glue/exports.map), and provide source checks, build receipts and release packaging. The notice dossier is embedded via [`obor_notices.h`](src/glue/obor_notices.h) and can be written to a frontend directory. [Source inventory](SOURCES.json), [SBOM](SBOM.spdx.json), [`tools/release.py`](tools/release.py). |

## Imported dependencies and verification

The libretro API header, miniz, LZ4, dlmalloc, retained libco files and the selected
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

The 7533 anchor is upstream release commit
[`5c8261444de6b61f8e2ce6e79e3d86a2949e55bd`](https://github.com/DCurrent/openbor/commit/5c8261444de6b61f8e2ce6e79e3d86a2949e55bd)
(2024-01-01). Its own patched source, engine object, logical profile and
save directory are separate from 8023. The port includes PAK-handle
repair for save states, resource cleanup on reset, bounded animation tables,
compact script storage and the common WebM lifecycle correction.

The 8023 anchor is upstream `new_controller_code` branch commit
`16aae1a30b81063778f21977ae20b849bd1c76f9` (2026-09-28), verified on
2026-09-29. It provides the latest selectable engine;
6391 remains the default fallback. Content markers are updated for this set.

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

The modern engine explicitly enumerates owned copies of the content path in
sample caches and direct handles. On a state load, the common layer rebinds
exact references to the saving session's content to the current frontend's
content path before reopening files. Unrelated packages and loose files retain
their paths. This also covers new sound streams started after restoration and
repeated saves across sessions whose prepared-content directories differ.
Allocation failure rejects restoration; no previous session directory is kept
alive to make a load work.

## Audio memory layout

Large decoded sound effects use the modern engine's existing streamed-sample
path so immutable PCM does not become part of every rewind checkpoint.

## Reconstructible resources

A preparation path observes successful capture intervals and updates
the codec's existing current image before the presentation callback on a
predicted capture frame. It finishes audio mixing first. Ordinary serialization
still checks current bytes and writes a complete independent state, including
changes made after preparation. The prediction schedules work only; it never
changes the frontend's capture frequency. Missed predictions expire, loads and
resets clear the schedule, and preparation retains no additional history.
This path defaults on for Windows x86-64 and non-Android Linux x86-64/ARM64.
`OBOR_STATE_PREPARE=0` disables preparation for diagnostic comparisons without
changing the requested captures or their contents.

Diagnostic input sequences can use the most recent successful load as their
frame origin. This permits matched checkpoint comparisons when a frontend's
load command arrives asynchronously. The option is disabled in ordinary use;
it does not change state contents or the frontend's rewind history.

The resource-state path receives explicit resolved image-member
names, bitmap dimensions, crop coordinates and initialized sprite-body ranges
from engines 3842, 4086, 4432, 6391, 7123, 7142, 7533 and 8023. Older engines
also report physical bitmap compaction; consecutive crops compose within the
original source rectangle and invalid provenance falls back to ordinary bytes.
Engine 3400's different sprite encoding remains represented as ordinary state.
Shared code independently reconstructs indexed PNG/GIF images
and RLE8 bodies, requiring exact byte equality before replacing body bytes with
logical zeros in the compressed state. Sprite headers, palettes, pointers,
padding and modified bodies retain their ordinary mutable representation.

All nine physical engines also declare exact resident PCM member offsets and
byte counts after a successful sample read. The shared versioned recipe has an
explicit member-slice kind, validates the source and compares the entire body
before omitting bytes. Mixer positions, format parameters and allocation tails
remain ordinary state. Modified samples fall back to raw state; shared and
freed/reused samples obey the same catalog lifetime rules as images. A cold
restore reconstructs from the state recipe and content, without engine handles
or a later session's samples. Unsupported sources and oversized members retain
their complete bytes. The existing bounded source-derived cache is shared by
both kinds; no sample history is retained outside frontend states.

An OBS5 state carries a complete versioned resource manifest in a fixed window,
with a fixed stack window keeping heap and resource addresses independent of
growth; the reader still accepts OBS4. The source reader
uses the current ordinary PACK archive and never resolves a state-provided host
path. A bounded 128 MiB cache contains only losslessly compressed source-derived
resources and their recipe metadata; cache misses
rebuild from the manifest and content. Free, successful realloc, reset and state
restoration invalidate the appropriate current-object provenance. Restoration
preflights resource reconstruction, heap ownership and logical zero ranges
before replacing live bytes. Transient reconstruction staging is capped at
256 MiB; additional resources remain ordinary state bytes.

On non-Android Linux, updates to a valid coded image can use a bounded
compression pipeline. The owner reads and copies source blocks; one helper
encodes them and computes their checksums. Only the owner updates slots,
metadata and the current decoded cache, in serial block order. Two batches
use less than 2.1 MiB of scratch. The helper starts after a full batch of 32
dirty blocks and is joined before capture returns, repacking, cache invalidation
or further engine execution. Scratch counts are cleared and restoration never
consults them. OBC1 bytes, slot order and capture frequency are unchanged.

The automatic policy requires at least 64 changed 16 KiB blocks and 5 ms of
codec CPU work in the preceding call of the same phase. Preparation and final
serialization keep separate estimates, cleared on cache invalidation or restore.
Owner and helper thread CPU times are added after joining; waits and preemption
do not inflate this estimate, and a shorter parallel wall time does not by
itself disable the next capture's helper. Missing clocks select the serial path.
A changing workload can use the less efficient path once without changing the
state contents. This is a workload policy, never a game identity selector.

Single-CPU execution, allocation/thread failures and unsupported targets retain
the serial path. Detailed per-block timing also uses serial encoding.
`OBOR_STATE_COMPRESSION_WORKER=0` supplies a diagnostic serial control; leaving
it unset uses the compiled platform policy. An explicit `1` bypasses the
workload estimate, while retaining the bounded pipeline and serial fallbacks.
This is compression within one capture, not asynchronous engine execution or
an extra snapshot history.

New resource-state blocks use the compact initial DEFLATE encoding on supported
default targets; changed blocks use LZ4, within the same fixed image capacity.
An optional `OBOR_STATE_RAW_MUTABLE=1` experiment
keeps changed blocks in raw stable slots to measure frontend delta amplification.
Neither format depends on a prior snapshot. Movie workers can be stopped
after all target preflights pass, allowing an earlier non-threaded state to load
from current playback; interior movie snapshots remain unsupported. This also
applies to the asynchronous movie adapter: its shutdown joins active and retired
decoder lifecycles, nested demux/video/audio workers and codec workers before
target state is copied. The running-movie write-watch capture policy is separate
from permission to restore an earlier state. Runtime tests compare repeated
restored continuations and check native Linux tasks return to baseline, including
a movie resolution that activates libvpx's own workers.

Linux x86-64/ARM64 classic decoder workers explicitly register for write-watch
dispatch. The owner pins dispatch before publishing each worker and releases it
after join, so writes between frontend callbacks preserve exact page proofs.
Owner fault recovery remains scoped to its callback; registered workers only
handle protected-page writes, and real/foreign faults keep their prior handler.
Concurrent faults on one page use lock-free epoch stores and idempotent page
unprotection. Rearming, resizing or destroying the watcher requires joined
workers. No watcher means no persistent dispatch. The asynchronous movie layer
declares a different ownership model, including nested/third-party workers;
it retains conservative suspension. `OBOR_STATE_WORKER_WATCH=0` provides a
diagnostic control on the supported classic path, without changing history.

Diagnostic image-capacity choices are shared by the initial frontend query and
engine writer, fixed for the content session and bounded by the existing format
maximum. A smaller budget rejects complete images that cannot fit; it never
truncates them or changes the frontend's history allocation.

The optional `OBOR_REVERSE_PRESENTATION=1` path checks the frontend's explicit
libretro rewind throttle mode after a successful restore. It presents the
already serialized framebuffer and current audio output without advancing the
engine or mixer. This avoids restarting a movie while presenting older frames.
The audio output replaces the existing static mixing buffer and belongs to the
ordinary snapshot; no separate past-frame history is retained. Unsupported
frontends and ordinary loads retain the forward execution path.

Reverse presentation requires the resource and compressed-state paths to be
enabled. It remains opt-in; ordinary rewind uses the normal engine presentation
path. Resource and compressed states themselves default on for Windows x86-64
and non-Android Linux x86-64/ARM64, as described in the README. Other targets
retain their existing writer while equivalent acceptance is pending.

## Model attack type bounds

Optional model `defense normalN` and `offense normalN` entries are checked
against the configured `maxattacktypes` before computing their table index.
An entry outside that range is ignored with a warning in the engine log,
including its file, command and configured limit. Valid entries retain the
engine's existing mapping and behavior. This prevents an invalid optional
entry from overwriting adjacent heap storage in every engine profile.

## Session relative filesystem

The native file interposers retain the ABI selected by the target's headers.
Darwin lookups use SDK-provided symbol suffixes rather than an undecorated
legacy entry point. Native lookups are checked against compiled SDK declarations
and the actual forwarder object for both supported Darwin architectures.
Windows function imports use ordinary function relocations so the engine's
partial-link wrappers see them; imported data keeps its normal ABI. Explicit
CRT spellings of directory, descriptor, permission and removal operations share
the same live path resolver as the POSIX spellings.

Builds inspect each engine caller and its static dependency archives against
the actual interposer definitions and recorded partial-link wrapper arguments.
Native forwarders and the glue still use the system library. Their legitimate
imports do not establish whether an engine caller bypassed its session root.
Linux regression controls exercise an existing save root with incompatible
legacy/current status layouts, relative file/directory I/O and a preserved
frontend working directory. The stock frontend smoke retains its fresh/existing
save-directory checks.

Windows stat wrappers accept the caller's native time/file-size buffer ABI
through both underscore and POSIX spellings. They forward to underscore CRT
exports, which are present even when MinGW's optional POSIX aliases are absent.

All engines resolve relative file operations against their own live session
root. Entering a frame does not query or change the frontend process directory.
Operating-system handles remain outside saved states and are rebound to the
current session on a cold load. Genuine resource loads and script file access
still use the filesystem.

Reserved output directories use the same destination for directory creation,
metadata queries, descriptor I/O and stream I/O. Unpacked content retains its
own input root while script saves, logs and screenshots use the frontend's
output location.

Output filenames are derived from the content basename before changing its
extension. Long parent directories never pass through the engines' old
256-byte filename temporary. Each caller supplies its destination capacity;
unrepresentable names and output path joins fail without truncating a save
filename or writing beyond the destination.
Host content paths use a separate bounded 4096-byte representation, including
the session values kept across restoration. They are not shortened to the
engines' logical filename capacity. Oversized host paths fail before boot.
The optional game-log mirror consumes long lines in bounded chunks, preserving
its per-frame work cap without hiding subsequent records behind a long path.

Packed readers consult a bounded index of names in that root before attempting
a loose override. Read-only stream and descriptor probes share that proof,
including script filestream helpers that check loose input before the PAK.
Each absence also needs a native lookup, so unlisted aliases
such as filesystem short names are not discarded. At most 256 root names and
64 exact-spelling absence proofs occupy 80 KiB of name storage per engine.
An absence is usable only on a locally observable filesystem while change
notifications remain valid; mutations invalidate the index. Existing entries retain the original
case-insensitive lookup and override precedence. Unavailable notifications,
unsupported names, enumeration errors or capacity overflow retain the original
lookup instead of inventing an absence. This index contains no game bytes or
rewind history.


### Process runtime storage and cold state loads

Writable data from compiler startup objects and statically linked host runtimes
is process-owned. The linker groups these inputs into the existing `obor_rt`
region, excluded by both pristine-reset and engine-state collectors. This covers
Winpthreads TLS keys/VEH registrations, MinGW CRT on-exit tables and locks,
libgcc/libstdc++ exception bookkeeping and allocator pools, and equivalent static
runtime inputs on ELF targets. Engine and codec data retain their ordinary state
ownership. ELF RELRO inputs keep their original read-only protection. Windows
loader/TLS template sections are also excluded; the previous positional guess
that the first32 bytes of `.bss` belonged to the CRT is removed.
Darwin excludes loader binding tables, constructor tables and TLS sections by
their Mach-O ABI section types, preserving ordinary initialized data and BSS.

Every final build audits allocated link-map inputs against the actual image
ranges, refusing captured process runtime storage. Darwin targets use external
libSystem and no static language runtime; the gate refuses an unexpected static
runtime input until its ownership is established. It also verifies that Darwin's
split ranges fit the existing fixed tables for every engine. The Windows headless host can
dispatch a private handled exception after `FreeLibrary`, detecting stale
exception callbacks even when the frontend would otherwise exit quietly. The
rewind regression requires this check in fresh and cross-process loads for all
thirteen profiles, in both compressed and raw modes. No game identity or runtime
symbol address selects the exclusion.
The bounded Windows test batch starts a dedicated Wine prefix with persistent
services, avoiding a server/service restart between hosts. Its server and prefix
are removed on completion or failure; no existing Wine prefix is managed.
CI places this prefix and the large temporary state files on disk, rather than
charging a host tmpfs against the runtime test's memory budget.

### Conditional reconstruction of the presented frame

The 32-bit video backend records the source of its last converted output copy.
At capture, the resource catalog may omit that copy only after proving exact
byte equality with the deterministic ABGR-to-XRGB conversion of the source.
The proof includes the unused output byte. An unchanged proof is reusable only
when both source and output bytes are proven unchanged. The source screen,
palette and logical engine state remain captured. Unsupported formats, stale
sources, previous frames retained across a yield, or any pixel mismatch retain
the ordinary output bytes unless equality is independently proven.

The frame descriptor contains bounded allocation offsets, dimensions and stride;
it never identifies content. Its source must be saved ordinary bytes, without
dependencies on omitted resources. Restore validates the incoming snapshot's
allocation ownership and sparse ranges, then stages conversion from that
snapshot before changing live state. It never reuses mutable frame pixels from
the current game merely because a descriptor matches. Output allocation tails
remain ordinary bytes. Existing fixed state, resource-cache and staging limits
are unchanged. Synthetic cases cover exact equality, modified pixels, source
lifetime, incoming mutable data and atomic rejection of invalid descriptors.

### Load-time state content and compression options

Two options in the existing System category independently select resource
reconstruction (Smart / Full) and compression (On / Off). The default is
Smart + On on every platform, including Android and macOS. This writer default
is independent of the existing platform policy for preparation, encoder
maintenance, compression helpers and write tracking. Off with Smart uses the existing raw-mutable encoder;
unchanged block proofs and reuse remain enabled. Full + Off uses the complete
base writer with all common restoration and runtime-storage fixes.

The glue samples both options only at content load and passes the selection
through the engine boot ABI. The selection belongs to excluded session runtime
storage, so reset and state restoration cannot overwrite it. Diagnostic
environment variables retain their existing precedence. Incoming state size is
validated by the reader's format and bounds, independently of the current
writer's smaller capacity. Full sessions can open resource reconstruction
services on demand to read a Smart state without changing their writer policy.

All four combinations remain visible on every platform. A state whose module
address changed is refused before modifying live engine memory, regardless of
the writer. It is not automatically converted to another format. This
temporarily limits cross-process Smart and Full loads on macOS.
Authored runtime tests cover every profile and writer/reader combination,
complete 200-frame image/PCM continuations and option latching through reset.

### Refuse module relocation without exact pointer metadata

The former Full-state rebase scanned aligned memory words for numbers inside
the saved module range. Integer pairs can have the same representation as a
pointer, so this cannot prove which values need relocation. Both Full and
Smart now require the saved and current module bases to match on every
platform, before resource staging, worker shutdown or live-memory writes.
Same-base loads retain their existing checks and behavior. Tests shift the
declared module and segment addresses in valid raw and compressed snapshots
for all 13 profiles and four writers; rejection must leave 200 frames of
image and complete PCM identical to uninterrupted playback. Cross-process
tests distinguish an observed address change from any unexpected load failure.
Every writer also restores within the same process after advancing 200 frames
and must reproduce the original video and complete PCM, even on ASLR hosts.

### Preserve non-UTF-8 bytes in linker maps

Apple ld64 maps can contain literal bytes outside UTF-8. Runtime-storage
auditing reads them with UTF-8 surrogate escapes, retaining every byte while
parsing the ASCII object-origin records as before. Synthetic Mach-O maps
include such bytes in symbols and paths, and still require rejection of
forbidden static-runtime origins. These cases run in the builder preflight;
SDK cross-links alone do not reproduce every native Apple linker behavior.
