# AnyBOR port modification record

Record updated: **2026-10-31**. Port maintainer: **retrodiv**
(<retrodiv@proton.me>).

AnyBOR offers selectable engine profiles through its libretro port.
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

The repository includes core-info capability and runtime notes, checked
source-only ZIP packaging, and publication and user guides in
[PUBLISHING.md](docs/PUBLISHING.md) and [ANYBOR.md](docs/ANYBOR.md). Binary release ZIPs carry the modification record
and documentation alongside their existing notices and receipts.

## Unavailable sprite images

Sprite images that could not be loaded are left out of the drawing queue.
Available images retain native loading requests, queue order and draw methods.

## Sprite ownership cleanup

Sprite cleanup releases each owned sprite and filename once, followed by its
owning node and the alias map. Cleanup follows the owning list independently
of the number of shared references. The native release order, reset count and
retained map capacity are preserved.

## Sprite map growth

Sprite maps retain their native capacity policy and existing entries during
growth. An unavailable expansion retains the previous storage and capacity
and reports the native loading error. Unrepresentable allocation extents
stop loading before a new allocation is attempted.

## Sprite node loading

Sprite loading checks allocation and reload availability before using the data.
An incomplete node releases its new resources while retaining existing owners.
Shared images retain the native filename lookup, center coordinates and map
indices. Cache requests for absent nodes leave the cache unchanged.

## Rendering colourmaps

Rendering preserves each profile's selected colourmap entry, including empty
entries, and its palette fallback. Model and table availability are checked
before lookup.

## Script streams

File streams retain each profile's capacity, slot reuse and lifetime across
level changes. Type and argument-count errors preserve native return values,
result clearing and diagnostics. Argument checks, buffer extents and allocation checks give
unavailable storage a defined result while retaining existing owners.
Initialized byte extents are independent of the native size field. Cursor-based
reads stay within that extent; append and save use the buffer base independently
of the stored cursor.
Loaded buffers pass through aligned local outputs before their pointer and size
are stored in native stream records. Native field offsets and callback results
are preserved.
Input files close after their bytes have been loaded and when buffer allocation
fails; the stream retains its native data and return values.
Fixed-cache line and argument results keep the native prefix and a defined
terminator. Argument queries preserve each profile's comment recognition,
numeric conversions and retained parser bytes.
For these profiles, append retains the native formatting and mode behavior,
checks output allocation and preserves the existing buffer when storage is
unavailable.

## Script save records

Script saves retain the selected profile's 32-bit record fields and defined
read/write traversal. Variable names remain owned by the live script table.
Valid cached strings and live references retain their values; unavailable
references and out-of-range table accesses receive a defined refusal.

## Script integer conversion

Script integers retain their native signed 32-bit values. Decimal conversion
truncates toward zero when the result is representable. Unavailable arguments
and non-representable decimal results return a defined refusal and preserve
the destination value.

## Script shared storage

Copied scripts retain their shared interpreter and any diagnostic comment until
the last reference ends. Local variables remain independent. Script replacement
preserves the native callback order and retains an existing comment when the
replacement supplies none.

## Record dates and file notices

The port includes an independently authored RISC-V LP64D
coroutine backend, Linux RISC-V build selection and Sv39-compatible fixed
module/arena addresses. Video allocation follows native and CRT bounds,
grows for larger runtime modes, and preserves its current reservation across
state restoration. Focused tests cover register preservation, fault recovery,
geometry changes, and exact restored output.
RISC-V protected-page tracking uses readable, non-executable data mappings
and the saved instruction pointer to distinguish writes from execution
faults without an access-kind register. It retains hot-page learning and
registered-worker dispatch, with user-emulated regression coverage.
The glibc recovery translation unit uses the ordinary nonlocal-jump entry
point: its fortified counterpart assumes one stack and can reject valid jumps
from a separately allocated coroutine. Thread ownership and guard lifetime
checks remain in place, with allocator and memory-fault regression cases.
This is confined to the Linux recovery file; other translation units retain
their toolchain hardening. Android, Windows and macOS retain their existing
jump implementation. The regression forces both relative stack positions
with Fortify enabled in the caller.

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

See the [technical source baselines](docs/HISTORICAL_PROFILES.md#baselines-and-complete-file-inventories) for pinned revisions and complete per-file inventories.

## Platform integration

All engine source trees include `libretroport.h` through `source/globals.h` and expose
the platform/PNG helper declarations in `source/utils.c`. Thread-capable source trees also declare libretro thread, mutex and condition types in
`source/gamelib/threads.h`. Each inventory identifies the affected files.

The newest source tree places the player array in aligned storage. The PE linker otherwise
allocates its tentative common symbol at a four-byte boundary even though
compiled menu code reads it with a 16-byte SIMD operand.

The platform implementation is shared under
[`src/port/libretro/`](src/port/libretro). It replaces standalone host backends
with frontend video, audio, controls and timing; its files are catalogued below.
Generated version headers preserve upstream version identities; frontend labels follow their published revision names. Each source tree uses the common build overlay.

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
This is a save-state and rewind limitation: some games briefly preload models
with the player already on screen. Manual state operations can be refused and
rewind history can contain gaps until the enclosing preparation finishes.
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

Builds 3842, 4086, 4432 and 6391 resize the model's weapon list
to fit each replacement `weapons` declaration. Borrowed lists are copied
into owned storage before replacement. Build 3400 uses a fixed-size array
and does not need this change. The PAK itself is unchanged.

## Animation script safety

Build 3842 checks that an entity-local animation interpreter exists before
reading its reset flag. Scripted map entities can have an initialized model
animation script while that optional local interpreter is absent; the guard
permits this state without dereferencing a null pointer.
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

Build 3842 retains one `ScriptVariant` for each compiled constant instead
of allocating a second identical value. The interpreter pushes that canonical
value directly, matching the representation used by later OpenBOR engines.
The instruction opcode and its Boolean target-kind flag use their bounded
integer widths so each instruction occupies a smaller allocator class on
64-bit targets. These changes reduce the live heap of script-heavy games
without changing script values, execution order or the state restoration
contract.

Build 8023 stores parser-only token and label pointers in the same slot as
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

The parser workspace is allocated only while an interpreter is compiling.
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

All selectable profiles initially allocate each model's animation pointer table for
the built-in animation range and grow it in bounded blocks only when authored
content assigns a higher animation index. Lookup, sprite-cache, model-copy,
normalization and cleanup paths use the model's recorded capacity. The global
author-facing animation limit and sparse numeric indexes remain unchanged, so
scripts and model data keep their existing semantics without reserving the
largest table for every loaded model.
Model changes check the destination table before retaining an existing
animation. Each profile preserves its reset, synchronization and timing
behavior within that allocated capacity.

## Playable model validation

Player selection validates a missing model before accessing its name. The
historical missing-model diagnostic is retained, and failure returns control
to the frontend through controlled engine shutdown.

## Empty player slot safety

All selectable profiles require both remaining lives and a selected model name
before automatically spawning a player at the start of a level. Script-assigned
lives in an empty multiplayer slot do not load a model until the player joins.
The empty slot remains available through the engines' existing join path. Each engine inventory identifies the affected source.

## Active content PAK aliases

All selectable profiles treat a missing basename-only `Paks/*.pak` file read
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
A malformed PAK returns a diagnostic instead of feeding index bytes to
an engine parser. A uniform stale directory base can be recovered structurally:
all entries must describe contiguous data exactly filling the archive, and two
image signatures must corroborate the corrected positions. Gaps, overlaps,
invalid names, truncation and other damage are rejected. No game-name or digest
catalog selects this repair. It changes only directory offsets in a local cache.

Optional input preparation is supplied by `[transforms]` in the frontend system
directory's `AnyBOR.ini`. A bounded buffer compiler and interpreter support
custom headers, embedded archive ranges and byte-order conversion. The normal
PACK validator checks every prepared result. See [content transforms](docs/CONTENT_TRANSFORMS.md).

The interpreter materializes its private work copy on the first valid write,
preserving the immutable input for subsequent reads. A result that still refers
to unchanged input borrows its selected range through validation and cache
publication. Work and scratch results reuse their own allocations; the existing
owned-output API continues to return independent storage. Rejection and
cancellation release all owned buffers. Read-only programs therefore avoid a
second full archive allocation without bypassing the configured program or
changing its instructions, resource limits or cache identity.

Manual choices and available exact filename profiles retain their existing
priority. Imprecise declarations and unavailable exact profiles are checked
against proved content requirements. A literal call to
`getentityproperty(..., "attack", ...)` requires the native API through build
4166; build 4167 and later reject it. The bounded scan ignores comments and
quoted prose and handles nested first arguments. Triage intersects that
requirement with the declaration; without a higher-priority declaration, the
legacy preflight selects 4086. Exact-only development snapshots are excluded
from triage alternatives and ordinary inference. No game or script digest
selects a compatibility correction.

Filename build tags accept a numeric prefix followed by trailing `X` digits.
The selector picks the highest automatic profile inside that interval
and preserves that profile directly. Exact filename tags and manual choices retain direct selection. Imprecise
tags additionally use syntax-scoped content evidence, preferring stable or
automatic profiles. Ordinary sidecar and unlabelled inference use automatic
profiles only. If
there is no match, the interval's upper endpoint goes through ordinary
automatic routing. Existing exact-build, manual and legacy-API priorities
remain in effect.
Explicit inclusive intervals (`Build 3800-4200`, with `XXXX` allowed at either
endpoint) select the highest eligible profile inside the interval, or the
first automatic revision above it when none fits. Auto reports an unavailable
profile if no later revision is available. Manual selection can override them.
The bounds describe content evidence independently of the profiles available
in a particular release.

## Image loader safety

The legacy image probe validates the PCX signature before using its header
bytes as dimensions. If authored animation data points a frame at a RIFF/WAVE
asset, the engine preserves that animation slot as an empty transparent frame
instead of decoding audio bytes as pixels or allocating a bogus bitmap.

Palette-only requests preserve each profile's native filename routing and
acceptance rules. The PCX palette path reads the final 256 RGB colours into a
bounded buffer, retains its native three-plane refusal and converts the table
to the active palette format. Sprite requests validate image headers before
using dimensions. Direct raw-palette readers retain their native in-range
layout and cannot write beyond the declared palette allocation.

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

Builds **4432, 6391, 7142 and 7533** change `source/webmlib/vidplay.c`:

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
| Endian helpers, all engines | Replace the historical SDL-derived endian implementation with fixed-width types; 64-bit conversions use explicit widths independently of the Windows `long` type. | `source/gamelib/borendian.h`; [`obor_endian.h`](src/port/libretro/obor_endian.h). |
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

The engine is built with `-Wall` on Clang. Its type and alignment declarations
preserve the intended behavior and structure layouts; record-layout dumps
verify that the pack-state declarations leave every type byte-identical:

- Headers that set a `#pragma pack` alignment for their own declarations
  bracket it with `push`/`pop` (`openbor.h`, `source/gamelib/anigif.h`,
  `source/gamelib/depends.h`), preserving the caller's alignment. The packed declarations themselves are unchanged.
- The draw-method one-bit flags are declared `unsigned`; the engine assigns
  them `1`, which a signed one-bit field stores as `-1`.
- Entry points with parameters use matching prototypes (`standard_palette`,
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
  matching source file declare ordinary functions (`ScriptVariant.h`,
  `source/gamelib/transform.h`).

## Script variable names

The two oldest engines store complete script variable names in owned allocations,
matching the later upstream name-storage semantics. Distinct names remain
distinct even when their first 24 bytes match. Reused slots release their former
name, and shutdown releases every active or retired name. Allocation failure
leaves the live table unchanged; null and empty names also fail cleanly. The
later engines retain their existing allocated-name tables. This safety fix is
enabled for every profile.

## Logical profile compatibility

Screen centering and indexed palette transparency follow each profile's native drawing rules.
Indexed transformations follow each profile's remap, fill and blend order.
Transparency tests the source index before fill replacement; fill indices use their low eight bits.
Centered sprites retain each profile's native drawing route and palette blending.

Profile contracts and their implementation are documented in the [technical profile reference](docs/HISTORICAL_PROFILES.md#profile-implementation-details).

## Shared port and frontend

These maintained sources are additions or platform replacements, rather than
unchanged OpenBOR engine files. Existing incorporated-material notices remain
in their respective files.

| Capability or change | Behaviour and current implementation |
|---|---|
| Selectable engine profiles | Core Options offers v3.0 3400, v3.0 3741, v3.0 3780, v3.0 3783, v3.0 3789, v3.0 3793, v3.0 3797, v3.0 3805, v3.0 3814, v3.0 3818, v3.0 3822, v3.0 3824, v3.0 3829, v3.0 3831, v3.0 3837, v3.0 3839, v3.0 3842, v3.0 4086, v3.0 4088-dev, v3.0 4107, v3.0 4111, v3.0 4129, v3.0 4153, v3.0 4432, v3.0 4453, v3.0 6330, v3.0 6391, v3.0 6391-mod, v3.0 6392-dev, v3.0 6412-dev, v3.0 6510-dev, v3.0 7086-dev, v3.0 7123-dev, v4.0 7142-alpha, v4.0 7533 and v4.0 8023-dev. Auto uses build tags and content clues. Each profile retains its compatibility behavior and save directory. [`obor_abi.h`](src/glue/obor_abi.h), [`obor_engines.h`](src/glue/obor_engines.h), [`tools/build.py`](tools/build.py). |
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
| Threading and host portability | Supply pthread/Windows workers and synchronization, publish workers before execution so snapshots cannot race startup, preserve Windows coroutine stack bounds, isolate MinGW reference sections, and generate ELF/PE BSS layouts. [`threads.c`](src/port/libretro/threads.c), [`libretroport.c`](src/port/libretro/libretroport.c), [`tools/build.py`](tools/build.py), [`glibc_compat_math.c`](src/compat/glibc_compat_math.c). GNU/Linux targets support an optional glibc requirement ceiling. Input descriptors, content-derived labels and routine notifications are enabled on all targets. |
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
(2024-01-01). Settings and save directories remain separate between selected revisions. The port includes PAK-handle
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
This path defaults on for Windows x86-64 and Linux x86-64/ARM64, including supported Android targets.
`OBOR_STATE_PREPARE=0` disables preparation for diagnostic comparisons without
changing the requested captures or their contents.

Diagnostic input sequences can use the most recent successful load as their
frame origin. This permits matched checkpoint comparisons when a frontend's
load command arrives asynchronously. The option is disabled in ordinary use;
it does not change state contents or the frontend's rewind history.

The resource-state path receives explicit resolved image-member
names, bitmap dimensions, crop coordinates and initialized sprite-body ranges
from engines 3842, 4086, 4432, 6391, 7142, 7533 and 8023. Older engines
also report physical bitmap compaction; consecutive crops compose within the
original source rectangle and invalid provenance falls back to ordinary bytes.
Engine 3400's different sprite encoding remains represented as ordinary state.
Shared code independently reconstructs indexed PNG/GIF images
and RLE8 bodies, requiring exact byte equality before replacing body bytes with
logical zeros in the compressed state. Sprite headers, palettes, pointers,
padding and modified bodies retain their ordinary mutable representation.

All supported implementations also declare exact resident PCM member offsets and
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

On Linux, including supported Android targets, updates to a valid coded image can use a bounded
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

After the first successful restore, the frontend's explicit libretro rewind
throttle mode presents the already serialized framebuffer and audio output
without advancing the engine or mixer.
It also holds that complete output across rejected history entries until a
valid older state arrives or the frontend resumes forward playback. This avoids
entering model preparation or restarting movie workers between restored frames.
The audio output replaces the existing static mixing buffer and belongs to the
ordinary snapshot; no separate past-frame history is retained. Unsupported
frontends and ordinary loads retain the forward execution path.

This presentation rule is shared by all engines and state writers. A throttle
label remains authoritative through failed restore callbacks; an old successful
load is not used as a timeout that can restart the engine during held rewind.
Ordinary loads sample live input immediately. Playback direction applies without a diagnostic override. Smart content and compression On remain the defaults on every target.
If rewind starts while model preparation still defers all restores, that
preparation can finish before the first complete snapshot is restored. The
playback-direction flag belongs to the current frontend session, is cleared on
forward playback/reset/unload, and is never serialized into game history.

## Panel order bounds

Dynamic panel tables are indexed only for panels declared by the level.
An order slot without a loaded panel keeps its position and contributes no
render layer. Loaded panels, optional layers and repeated entries retain
their bindings and offsets. Sanitizer fixtures exercise these boundaries
in every engine with a dynamic panel table.

## Model attack type bounds

Optional model `defense normalN` and `offense normalN` entries are checked
against their allocated table extent before accessing it. Each profile retains
its mapping and any extra slot reserved by its model allocation. An entry
outside the supported extent is ignored with a warning in the engine log,
including its file, command and configured limit. Valid entries retain the
engine's existing behavior.

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

Compiler-generated emulated-TLS controls also belong to the current process,
including those emitted alongside engine code rather than inside a runtime
archive. The linker classifies their ABI input-section family into `obor_rt`;
the final-image audit applies the same classification. Their slot indices must
remain associated with the current runtime's per-thread allocations. A bounded
two-process regression initializes TLS objects in opposite orders and verifies
that restoring engine data preserves those associations. It exercises real
GNU ld and LLD layouts while retaining ordinary game globals in the state.

Every final build audits allocated link-map inputs against the actual image
ranges, refusing captured process runtime storage. Darwin targets use external
libSystem and no static language runtime; the gate refuses an unexpected static
runtime input until its ownership is established. It also verifies that Darwin's
split ranges fit the existing fixed tables for every engine. The Windows headless host can
dispatch a private handled exception after `FreeLibrary`, detecting stale
exception callbacks even when the frontend would otherwise exit quietly. The
rewind regression requires this check in fresh and cross-process loads for all
all published profiles, in both compressed and raw modes. No game identity or runtime
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

Two options in the System category independently select resource
reconstruction (Smart / Full) and compression (On / Off). The default is
Smart + On. Writer selection is independent of the platform policy for
preparation, encoder maintenance, compression helpers and write tracking.
Smart + Off uses the raw-mutable encoder with unchanged-block proofs and reuse.
Full + Off uses the complete base writer with common restoration and
runtime-storage checks.

The glue samples both options only at content load and passes the selection
through the engine boot ABI. The selection belongs to excluded session runtime
storage, so reset and state restoration cannot overwrite it. Diagnostic
environment variables retain their existing precedence. Incoming state size is
validated by the reader's format and bounds, independently of the current
writer's smaller capacity. Full sessions can open resource reconstruction
services on demand to read a Smart state without changing their writer policy.

All four combinations are available on every platform. A state whose module
address changed is refused before modifying live engine memory, regardless of
the writer. It is not automatically converted to another format. This
limits cross-process Smart and Full loads on macOS.
Authored runtime tests cover every profile and writer/reader combination,
complete 200-frame image/PCM continuations and option latching through reset.

### Refuse module relocation without exact pointer metadata

Both Full and Smart require the saved and current module bases to match on
every platform, before resource staging, worker shutdown or live-memory writes.
The reader does not infer pointer identity from aligned integer values.
Same-base loads retain their existing checks and behavior. Tests shift the
declared module and segment addresses in valid raw and compressed snapshots
for all published profiles and four writers; rejection must leave 200 frames of
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


### Failed capture buffers and manifest storage

The common libretro capture boundary clears the complete supported output
buffer on failure, for every engine and writer. Alternating caller buffers
therefore contain the same invalid representation, avoiding repeated large
deltas from stale payloads in frontends that retain refused captures. Raw and
coded readers reject the invalid header before live engine mutation.
Successful images keep their existing format and bytes. Requests larger than
the engine's 32-bit size API retain four-byte header invalidation. Null and
zero-length output buffers provide no bytes to clear. A frontend that rejects
a size without calling the core remains outside this boundary.

The public state-options regression retains a valid buffer, requests an
undersized capture, tries to load that same full allocation, and requires
refusal. Two hundred subsequent video callbacks and complete PCM must match an
uninterrupted reference before a valid load verifies recovery. All published
profiles and four writers run this probe. Synthetic caller buffers cover early,
partial and oversized refusals, repeated alternation, bounds and unchanged
successful recovery. Nested model-preload regressions also
exercise full-capacity refusals and reject their buffers after preparation ends.

Resource manifests reserve storage with the catalogue's existing bounded
geometric slot capacity during preparation and state adoption. The published
manifest length remains exact, and only logical bytes are copied or stored.
Allocation failure preserves the previous allocation until the ordinary refusal
path handles it; restore preflights retain their atomic behavior. Synthetic
checks cover retirement/reuse, nonzero allocator fill, growth and load failures,
the slot limit and byte equality with the previous writer. No resource proof or
serialized field is omitted by this allocation change.

The complete manifest writer overwrites its 32-byte header and all 600 bytes of every active record. It clears only inactive records, avoiding a redundant full-manifest zero pass while retaining deterministic zero bytes for retired slots. Recipe validation, eligibility proofs, bounds and restore preflights are unchanged. The authored allocation-lifecycle fixture observes actual clear requests in the catalog translation unit, forwards every write to libc, checks A5-filled reserves and canonical streams, and covers retire/reuse/load and allocation failure. This does not infer immutability from an always-writable page.

### Android capture policies and reusable catalogue metadata

Supported Android targets enable the existing guarded write watcher, classic
registered-worker tracking, advance preparation, bounded pool maintenance,
compact initial encoding and the synchronous compression helper. The helper's
policy uses owner/helper thread CPU clocks, with the existing serial fallbacks.
The asynchronous movie adapter still invalidates its page proofs; capturing
with active engine workers remains unsupported.

A bounded hot-page policy is enabled by default on supported page-protection
tracking targets. Only real repeated
CPU writes train it; kernel-I/O marks and empty protection epochs do not. Hot
pages remain writable and return an unknown page epoch to every reuse proof,
including multiple snapshots within the same protection epoch. Learning state
lives outside captured engine memory. Windows retains its native write-watch
backend without protected-page learning. The diagnostic override is generic
and does not identify content.

The resource catalogue retains validated immutable recipe bytes and rewrites
changed owners, flags and inactive records completely. A complete allocation
index merges newly ordered ranges with a validated preceding index, including
raw allocations. Bounds and global nonoverlap are checked before filtering the
omission mask. Loads, changed backing storage, failed preparation and invalid
generations discard the corresponding reuse guarantee. The frontend capacity,
state format, independent-state contract and exact resource comparisons do not
change.

### Native snapshot policies across supported targets

Darwin enables advance preparation, bounded pool maintenance, compact initial
encoding and the synchronous compression helper. The page watcher accepts
only protected arena writes from the owner or registered classic decoder
workers, checking the architecture's saved exception context. It handles
XNU's protection-related SIGBUS, including the shared alignment code used by
its ARM signal adapter, without installing or replacing Mach exception ports.
The saved exception syndrome still rejects actual alignment faults. Pthread
keys retain worker identity across owner callbacks and are
released only after the corresponding workers are joined; compiler TLS does
not pin the dylib. Read and stdio-read interposers prepare kernel destinations
and use the SDK-selected native ABI. The binding audit checks callers,
forwarders and process-local function caches against actual compiled objects.

Windows retains kernel write-watch history while classic decoder workers
execute; captures still refuse active workers, and the asynchronous adapter
continues to invalidate proofs. Native critical sections, condition variables
and a joined Windows thread implement the existing single-helper pipeline.
Thread CPU measurements use GetThreadTimes, with zero reserved for unavailable
measurements and the complete serial fallback. Failure to join an engine
worker cannot release its memory or decrement the live-worker count.

Encoder-helper activation is applied by the actual state consumer on each
supported platform. State-fault recovery drains any interrupted helper outside
the signal or exception handler before reusing its workspace or destroying the
encoder. Partially encoded images are invalidated; successful captures retain
their existing bytes and complete-state contract.
Darwin x86-64 also uses the existing bounded POSIX heap-copy path. Other
AArch64 targets retain their serial large-copy policy to avoid shared-memory
bandwidth contention.

PPM environment pointers, range configuration and emission counters stay in
process runtime storage. Loads cannot restore an expired environment pointer
or suppress the current process's requested diagnostic captures. Trace
initialization and native function lookup caches are also process-local.
The runtime layout remains outside both pristine resets and saved images.
State format, fixed transport capacity, exact resource proofs and the clean
module-address rejection contract remain unchanged.

### Historical rejection boundaries and shared parser safety

Historical profiles retain the earlier user-macro namespace before
3802, nonfatal rejected level values before 3820, tolerant text setters before
3821, and empty-success unknown textual constants before 3826. Later profiles
retain their strict errors. Level selectors stay in their logical numeric
namespace when compiled string arguments are cached. The corrected level name
mapper and safe error/type checks remain enabled instead of restoring unsafe
historical union reads or malformed-input behavior.

## Script property names

Text-property lookups stay within their actual table bounds. Getter and setter
name tables remain separate where their contracts differ, preserving their
declared numeric selectors. Rejected names retain the selected profile's
defined diagnostic and result. Available-property lists stay within their
declared entries.

## Colourmap loading

Historical profiles retain fixed-table slot selection and limits or dynamic
append behavior, with their own counter updates when image loading fails.
Fixed-table queries retain occupied slots above a counter reduced by hole
reuse, while keeping accesses within the initialized allocation. Remap flags
retain their fixed-table or dynamic storage behavior and survive failed growth.
Alternate palettes respect the historical table limit; missing allocations
produce a defined load error.

Inherited palette slots retain their historical copying behavior. Models and
entities retain borrowed maps while they are in use; changing a child model's
maps preserves the data held by its other owners.

## Palette conversion safety

Palette conversion preserves selected colour bytes, untouched slots and native
allocation failures. Missing map or flag data produces a defined failure, and
unselected slots remain untouched. Model loading reports selected conversion
failures while retaining valid models without a palette.

## Colourtable selector bounds

Colourtable queries retain valid colourmap pointers and palette fallback.
Missing indices produce an empty result; invalid fixed-table indices and missing
dynamic storage produce null results. Selector arithmetic stays defined at the
integer limits, and missing models or tables do not cause an invalid read.

## Sprite and statistics queries

Sprite, icon and statistics getters preserve each profile's valid results,
including sprite centers, absent-icon sentinels and model/entity statistics
selection. Missing arguments, unavailable sprite data and indices outside
initialized entries produce an empty result. Sprite filename results must fit
the script string capacity.

Statistics writes preserve model/entity selection, decimal index conversion and
each profile's callback result. Missing arguments and indices outside the
statistics array leave its values unchanged.

## Script list bounds

String lookup keeps adjacent reads within the declared table while retaining
the search order and duplicate preference. Staydown property lookup uses its
own name-table length. Missing entries return a failed lookup.

## Script parser table safety

The grammar-table constructor bounds terminal writes to the declared
production count while retaining valid entries and token membership.
The historical parser refuses instructions with an unresolved control target
before recording them; valid label instructions retain their native behavior.

## Script preprocessor safety

Legacy preprocessor string scanners reject end-of-input, unfinished escapes and
fixed token overflow before consuming an invalid byte. The dynamic-string engine
keeps its existing complete-source-view implementation and receives the same
malformed-input regression coverage.

The early script parser releases temporary parameter storage after rejecting a
macro definition, retaining the selected profile's diagnostic and token results.

Historical profiles preserve their source-defined initializer and compile-time
name-conversion passes while retaining complete instruction storage and ordinary
call arguments.

Callback cleanup and copy order preserve each profile's local-variable visibility
while retaining reference-counted interpreter ownership.

Configuration files retain the selected profile's field layout through explicit
conversion, preserving settings values and partial-read behavior.

Level command diagnostics retain the profile's text and blank-line policy;
historical fatal errors request a controlled engine stop.

File-command feedback retains each loader's diagnostic, continuation and input
buffer release. Model-list lookup preserves the profile's zero-command alias
and resulting idle-animation limit updates.

Level-list commands retain their case, blank-line warnings and fatal-error
policy. Invalid level ordering reports the selected profile's diagnostic and
requests a controlled engine stop; input buffers are released safely.

Contained items retain each profile's player-count requirement through level
entry creation, spawning and item drops.

Attack commands retain each profile's accepted names and attack-type mapping,
including numeric suffixes and consecutive freeze/steal updates.

Model inheritance retains each profile's command availability and animation
script compilation. Callback storage remains independently owned, with shared
interpreters retained until their final reference ends.

Combo timing retains each profile's fixed or configurable delay. Unsupported
combo-delay directives follow the profile's original model-list lookup behavior.

CI partitions rewind and state-option matrices into explicit profile groups,
verified for complete and unique coverage in each platform path. The Windows
test host verifies arena release with an actual reserve/release probe; a separate
negative control proves an occupied arena is not reported as released.


### Historical runtime contracts

The selected historical revision controls coupled attack-type numbering,
environmental damage, defense defaults, script numeric selectors, weapon update
order, idle timing, shadow color conversion, native model-save loading,
animation-command grouping, nested interpreter behavior, camera framing and
sample-playback results. Callback names, automatic creation dispatch and
post-compilation reset state follow each profile's source contract. New function
names follow their introduction boundaries.
Model construction preserves each profile's fixed or configured jump, grab and
throw defaults, initial special-move allocation extent and its historical
load-stop response when that allocation fails.
Attack decisions preserve native distance and group probabilities, always-attack
availability, offscreen suppression and model throttling. Attack priority, think
intervals and cooldown responses to target actions follow the selected revision.
Normal attacks retain native wait checks, probability arguments, callback order
and clock arithmetic. AI attack commands retain native argument handling,
switch state and load diagnostics. Jump attacks retain native wait checks,
probability arguments, movement and spawn callback order.
Platform and obstacle collision queries retain the native per-profile scene
counts, update sites and reset behavior, with bounded integer arithmetic.
Entity combat factors start at their native zero or copied model values.
A model change with no previous model uses an empty platform source.
Wandering retains native chase distances and destination arithmetic. Grab
placement and movement retain each profile's distance checks, eligible types,
lookup coordinates and action order.
An absent model retains the selected revision's diagnostic and leaves entity
state unchanged.
Line parsing preserves each profile's argument count, line capacity and
`MAX_ARG_LEN` script constant. Reader storage remains bounded.
Argument lookup preserves the profile's comment recognition, signed-index
scanning and initialized bytes retained between queries.

Authored collision bounds retain each profile's accepted coordinates, frame
conversion order, default depth tolerance and reported impact position.
Coordinate queries validate arguments, animation/frame indices and native
coordinate extents. Unsupported indices return a defined empty value.

WAV reads retain each profile's byte/sample counts and 16-bit padding, with
checked allocation and read sizes. Resident-byte ranges cover the actual loaded
bytes; padding and mutable mixer state remain ordinary state data.
Additive grammar remains available, and memory-safety and lifecycle corrections
remain active for every profile. The boundary table and limits are recorded in
[choosing a profile](docs/HISTORICAL_PROFILES.md).

### Reconstructed variants

v3.0 6391-mod retains four incoming attack IDs, the default multihit correction
and its native cheat toggle. `gotomainmenu(9)` exits character selection;
`backtotitle` is absent from its API. Explicit variant tags and manual choices
select it. Its settings directory and state identity are separate from 6391.
The variant reader uses the declared profile table for exact, partial and range
tags. Executable labels without a build number do not use compile-date inference.

v3.0 6392-dev reconstructs the author's published test behavior using the later
upstream multihit changes: four incoming attack IDs, the native cheat-menu toggle
(correction enabled by default), and selection-screen return-to-title requests.
`gotomainmenu(9)` is supported, with `backtotitle(flag)` as the earlier test alias.
This is not a recovered copy of the original test sources. Standalone controller
and mod-menu changes do not apply to libretro. See
[profile provenance](docs/HISTORICAL_PROFILES.md#reconstructed-variants).


### Content evidence within declared intervals

Official v3.0 4453 and v3.0 6330 releases participate in automatic routing.
Imprecise filename declarations are intersected with bounded syntax evidence;
stable or automatic candidates take priority. Temporary feature removal and
divergent branches are represented explicitly. Conflicting content does not
override the declaration, and the log records the applicable rules. Exact
declarations and unlabelled inference retain their existing priority. See
[source-backed rules](docs/AUTO_SELECTION_RULES.md).

## Script text object ownership

Replacing a text object's contents reuses its existing owned storage in the
older fixed-buffer implementations. Repeated updates retain that allocation. The earlier reuse path and later exact-size replacement path keep
their native behavior; tests check ownership across every retained profile.

In the 3400 and 3741 trees, fixed text storage includes the string terminator
and preserves native padding when contents change. Unavailable storage leaves
an existing owner intact. Queries for an object without text, and fixed-table
callbacks without an active level, return a defined error.

The 3741 and 3842 trees validate text-table indices and growth arithmetic.
Unavailable growth preserves the table and existing objects. Out-of-range
queries and integer or void results follow the selected profile.

The 3842 tree keeps text terminators inside owned storage and checks native
string extents before copying. Bounded conversion uses each variant type's
native format. A formatted value that does not fit returns a defined error
without replacing existing text. Earlier partial field updates retain their
profile's order.

Text callbacks validate argument and required result slots before use. Missing
entries have defined results. Valid numeric fields, optional result values, lazy
index results and partial updates retain their selected profile's behavior.

Level text collection/count accessors preserve native returns and field-update
order. Missing arguments, required result slots and level handles produce
defined errors; valid setters retain optional result slots.

Text property-name lookups retain native selector values and use each table's
actual entry count with bounded string-cache queries. The 4086 and 4432
trees preserve rejected-name returns and the native getter/setter diagnostic
order. Earlier name mappers retain their own warning text. Modular diagnostics
list only the available table entries. The early fixed-buffer text writers
validate cached string IDs before copying. Valid
queries retain the native cache data and released-slot behavior.
Cached names must terminate within their allocated storage before lookup.

Font selection retains its native modulo wrapping. A negative remainder
returns zero or performs no operation before accessing the font table.
Valid font selection, measurement and glyph output retain their native paths.

## Script property error bounds

Unknown-property diagnostics stop at the mapping table's declared length.
A table does not need a trailing null sentinel; rejected names retain their
normal return and error behavior without reading unrelated storage.
Native sanitizer checks cover each affected script entry-point macro.

## Encoded sprite safety

The modified sprite encoder measures storage with byte counters without forming
addresses from a null destination. Encoded bytes, allocation sizes and resource notifications
retain their native representation. Clip endpoints use bounded arithmetic;
empty intersections with the output viewport return before raster access.
Indexed font sheets must provide an owned palette with enough entries for the
active output format before their colors are copied. Valid font pixels remain
unchanged. Top clipping advances an optional sprite mask only when it exists;
unmasked indexed sprites retain the same pixels without null-pointer arithmetic.
Transform seeks and cursor steps keep absent mask pointers null.
Encoded sprite validation remains strict.

## Damage-over-time safety

Periodic damage-over-time scans iterate over the declared effect slots. The
final valid slot retains its tick and expiration behavior without an extra
iteration beyond the effect arrays.


## Script container alignment

Script containers retain their pointer values and native copy and cleanup order
when embedded records have narrower alignment than host pointers. Access uses
byte copies without changing the record layout. Missing containers are ignored.
Allocation and release accept byte storage for packed pointer fields, using
aligned local pointer values before accessing or releasing scripts.

Binding-script destruction callbacks follow their profile's source declaration
order while the shared record layout remains unchanged.

## Native hit-pause timing

Hit-pause accumulation and animation resets follow each profile's frame-based
or timer-based rules. The pause state shares storage without changing the
entity record extent.

Animation refusal diagnostics follow each profile's contract. Idle target
queries retain their native context, and a missing context leaves a defined
idle fallback.

Animation-frame spawn, summon and removal order, removal attack defaults and
script interruption follow the selected profile. Idle context restoration
preserves the profile's explicit scan or animation-series behavior.

Fresh script records retain the selected profile's initial validity marker
and empty variables, with explicit initialization handled separately.

## Drawing record alignment

Drawing methods retain their field values, offsets and sizes when embedded in
packed engine records. Their declared alignment permits safe property changes
and drawing calls through those records.

## Primitive coordinate bounds

Point coordinates outside the screen leave its pixels unchanged. Coordinates
inside the screen retain the selected profile's color and blending behavior.

## Screen blend bounds

Screen drawing selects blend operations within each profile's supported range.
Missing indexed tables use transparent copy. Unavailable true-color operations
use the existing unblended path. Valid native blend and tint selections retain
their operation and side effects.


## Bitmap row bounds

Bitmap row reads stay within the requested output width. Palette-only reads
retain their native behavior. Bitmap loading applies the selected profile's
native image dimensions.
