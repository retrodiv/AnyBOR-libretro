# Local diagnostics

## Reproducible WebM scheduling

`OBOR_DIAG_WEBM_REPRODUCIBLE=1` explicitly enables a development-only media
scheduler. Unset, `0` and other values retain normal scheduling. Keep the value
constant for the whole process and record it in test receipts. This is not a
frontend option or a production performance setting.

The common layer coordinates video readiness and PCM consumption with the
engine's decoder. It uses host monotonic time for two-second active deadlines;
it does not modify the engine clock, seed its RNG or insert emulated frames.
Classic mixers use owner/producer handoffs. Newer movie channels wait for
bounded preroll and owned PCM reserves, with deterministic look-ahead.
Background music during a silent movie is serviced by the owner. A deliberately
paused frontend may retain full queues; workers check cancellation at bounded
condition waits and resume when consumption resumes.

Per decoder, decoded image reservations are limited to64MiB. Each compressed
queue has a16MiB payload bound and retains its fixed item-count limit; each
container block is limited to2MiB before packet allocation. These are decoder
buffers, not state history. Existing codec/track structures and authored movie
source storage are separate. Over-budget media is refused in diagnostic mode.

`[obor-media-diag] schema=1 enabled=1 ...` records the policy and bounds.
Any `invalid=1` record fails the diagnostic run, even if playback later ends
cleanly. Reproducibility means comparing two fresh executions of the same
binary, content and inputs, including video records and all PCM samples.
Repeat normal-policy ON/OFF rewind measurements with this variable absent.
The diagnostic does not enable snapshots during active threaded playback.

## Exact-build state compatibility

Saved states contain internal addresses. The linked core is stamped with its
exact module/layout identity, which is included in every state representation.
A state from a different binary, or an older state without this identity, is
rejected before modifying the running engine. A version number alone is not a
layout guarantee. The build tool stamps the stripped module and matching debug
image before platform packaging; bypassing this step produces an incomplete
build. Ordinary in-game saves are unaffected by this state-format boundary.

## Engine memory faults

Every engine uses the same protected execution path. A synchronous SIGSEGV or
SIGBUS on that thread (Windows access violation or in-page error), a fatal
dlmalloc corruption/usage check, or exhaustion of the engine coroutine stack
stops the engine and shows a 320x240 error frame with the file name, engine and
available fault details. Error mode rejects save states and rewind.
Changing the engine option and using Restart starts a fresh engine instance.

Protection covers the coroutine during startup and frame execution, audio
mixing, state-size calculation, serialization (including tail padding) and
restoration. A state fault is displayed on the next retro_run; until then the
last submitted video pixels remain valid. Invalid/incompatible states
rejected before mutation leave the current game running. A failed restore after
mutation abandons the world. Guard dispatch and the live resource ledger are
excluded from both pristine and savestate copies.

Protection does not intercept unrelated frontend faults, user-generated signals or faults on
decoder worker threads. Recovery remains best effort: arbitrary memory
corruption and faults inside shared runtime libraries can damage resources
that an in-process core cannot safely repair. POSIX uses an alternate signal
stack. Windows arms a stack alarm above a committed 64 KiB emergency reserve;
normal stack growth faults while Windows still has room to dispatch it. The
failed coroutine is discarded; execution resumes on the frontend stack.

Before discarding an arena, movie workers must be joined. If their cleanup
itself faults, or an allocator failure could leave workers waiting on the
allocator lock, the core retains the instance and requires restarting the frontend;
it must not reset or unload memory and code still in use by a worker.

For tests only, `OBOR_TEST_FAULT=<engine>:<yield>:<read|write|null|context|allocator|stack>` injects
a real invalid access inside the selected engine. Yield 0 faults before startup;
a later yield exercises runtime recovery. The variable is inert when unset.
The context variant also damages the engine's saved frontend handle, to check
that recovery uses the live identity retained outside the engine's globals.
`OBOR_TEST_CALL_FAULT=<engine>:<phase>:<read|write|null|context|allocator>` injects
inside protected frontend-stack calls. Phases are `audio`, `audio-mix`, `size`,
`save`, `save-copy`, `save-padding`, `load`, `load-partial`, `load-copy` and
`load-heap`. The partial/copy/heap phases exercise an interrupted restore, not
merely an invalid header. Both variables are inert when unset.

## State compression comparisons

On supported targets, `OBOR_STATE_COMPRESSION_WORKER=0` selects serial block
compression for a local comparison. Leaving it unset selects the compiled
policy, which considers the preceding same-phase codec CPU cost and changed
block count. At most one helper completes within an eligible capture.
An explicit `1` bypasses that work estimate; resource bounds and serial
fallback still apply. Neither override changes state contents or history size.
Remove overrides before validating compiled defaults.

With state timing enabled, the `obor-codec-cpu` records report owner and helper
thread CPU costs; preparation records have a `-prepare` suffix. They exclude
scheduler waits and are distinct from elapsed capture time. These diagnostic
logs do not establish presentation cadence. Detailed per-block timing uses
the serial path and cannot measure the parallel pipeline.

## Diagnostic files

Diagnostics are disabled by default. The core does not send telemetry or
upload files. `OBOR_DEBUG=1` or a local `obor_debug.enable` file enables
engine diagnostics. `OBOR_TRACE=/path/to/file` records frontend frame and
save-state calls. `OBOR_GLUE_DUMP=/path/prefix` writes local frame captures
around state restoration. `OBOR_GLUE_INPUT` supplies scripted test input.
With `OBOR_GLUE_INPUT_AFTER_LOAD=1`, its frame ranges start at the most recent
successful state load; the next run is frame 1 and no scripted input is sent
before the load. This permits repeatable checkpoint comparisons despite
frontend command latency. Failed loads do not move the origin; reset and
content changes require a new successful load. Leave it unset for routes that
use absolute frame numbers or traverse menus through real rewind.
The game-log core option displays local engine log messages.

Logs and captures may contain local paths, game names, game script text or
game imagery. Review them before attaching them to a public issue. Disable
diagnostic variables after reproducing an issue and remove the local marker
file to restore the normal configuration.

## Frame latency boundaries

Set `OBOR_DIAG_LATENCY_BOUNDARIES` to a new, writable file path to record
monotonic timestamps around active frame processing. This development
instrumentation is disabled by default and is independent of `OBOR_PROFILE`.
The output path is created exclusively: an existing file is never overwritten.
Failure to create the file leaves the recorder inactive.

The recorder keeps at most 65,536 events (2 MiB) in memory and writes them when
content is unloaded. It stores event numbers, frontend frame numbers and
monotonic nanoseconds, without video, audio or state payloads. It adds no worker
thread and performs no per-event file writes. A full buffer stops retaining
new events and counts drops; it never evicts an older event to make a trace
look complete. The final `summary,count,dropped,0` row reports completeness.
A missing footer or nonzero drop count makes the trace incomplete. A crash or
forced termination may leave an empty file because unloading did not run.

The CSV columns are `event,frame,begin_ns,end_ns`. Events are:

| Event | Measured interval |
| --- | --- |
| 1 | Video preparation, including geometry and optional pixel processing |
| 2 | The frontend video callback itself |
| 3 | Writing an enabled `OBOR_PROFILE` record |
| 4 | Active `retro_run` scope, including its final profile write and early returns |
| 5 | The frontend batch audio callback itself |

Intervals are nested; do not add them as independent CPU costs. A callback
interval includes any wait performed by the frontend, and elapsed time can
include thread descheduling. A gap between frame scopes alone does not identify
which component caused it. Compare enabled and disabled controls from the same
state and binary before using this observer to diagnose a presentation pause.

## Dirty-page policy controls

`OBOR_STATE_HOT_PAGES=0` disables bounded hot-page learning; `1` enables it on
supported write-watch targets. The default is enabled wherever
the page-protection watcher is supported. Hot pages remain writable and can never prove a resource or state
block unchanged. This override changes work allocation, not snapshot contents.

`OBOR_STATE_PREPARE=0`, `OBOR_STATE_WORKER_WATCH=0` and
`OBOR_STATE_COMPRESSION_WORKER=0` retain independent diagnostic controls for
advance preparation, registered decoder tracking and the synchronous helper.
The normal safety checks and complete fallback paths remain in effect.

Darwin handles protected arena writes through the existing BSD signal guard,
including the `SIGBUS` protection faults produced by XNU. It leaves Mach
exception ports untouched and chains unrelated signals to their previous
owner. Native platform tests exercise CPU writes, kernel I/O and foreign
threads. Windows write tracking needs no protected-page signal handler.

Diagnostic PPM prefixes, ranges and emission counts belong to the current
process and survive a state load without being restored from that state.
They never supply saved engine or presentation data. Native system-function
lookup caches likewise remain outside captured engine memory.
