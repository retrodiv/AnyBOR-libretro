# Local diagnostics

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
previously submitted video pixels remain valid. Invalid/incompatible states
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
allocator lock, the core retains the instance and requires restarting RetroArch;
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

On Linux x86-64/ARM64, `OBOR_STATE_COMPRESSION_WORKER=0` selects serial block
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
