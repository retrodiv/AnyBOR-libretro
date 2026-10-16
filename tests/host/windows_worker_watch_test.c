/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <windows.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gamelib/threads.h"
#include "obor_fault.h"
#include "obor_state_config.h"

obor_state_settings obor_state_session_settings;
extern int obor_live_threads;
static unsigned suspended;
static unsigned char *memory;
static size_t page;
static int fail_join;
extern DWORD (WINAPI *__real___imp_WaitForSingleObject)(HANDLE, DWORD);
static DWORD WINAPI test_wait(HANDLE handle, DWORD milliseconds)
{
    if (fail_join) { SetLastError(ERROR_INVALID_HANDLE); return WAIT_FAILED; }
    return __real___imp_WaitForSingleObject(handle, milliseconds);
}
DWORD (WINAPI *__wrap___imp_WaitForSingleObject)(HANDLE, DWORD) = test_wait;
void obor_state_owned_suspend(void) { ++suspended; }
void obor_fault_abort(uint32_t kind, uintptr_t address)
{
    (void)address;
    assert(kind == OBOR_FAULT_STATE && obor_live_threads == 1);
    puts("join_failure_kept_live_worker=1");
    fflush(stdout);
    ExitProcess(91);
}
static int write_pages(void *unused)
{
    (void)unused;
    memory[0]++;
    memory[page * 2]++;
    return 0;
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    int disabled = !strcmp(argv[1], "disabled");
    fail_join = !strcmp(argv[1], "failed-join");
    assert(disabled || fail_join || !strcmp(argv[1], "default"));
    assert(!_putenv(disabled ? "OBOR_STATE_WORKER_WATCH=0" : "OBOR_STATE_WORKER_WATCH="));
    SYSTEM_INFO system; GetSystemInfo(&system); page = system.dwPageSize;
    memory = VirtualAlloc(NULL, page * 3, MEM_RESERVE | MEM_COMMIT | MEM_WRITE_WATCH,
                          PAGE_READWRITE);
    assert(memory);
    memset(memory, 0, page * 3);
    for (unsigned cycle = 0; cycle < 16; ++cycle) {
        assert(!ResetWriteWatch(memory, page * 3));
        bor_thread *thread = thread_create(write_pages, "native-watch", NULL);
        assert(thread && obor_live_threads == 1);
        thread_join(thread);
        assert(!obor_live_threads);
        void *addresses[3]; ULONG_PTR count = 3; ULONG granularity = 0;
        assert(!GetWriteWatch(0, memory, page * 3, addresses, &count, &granularity));
        assert(count == 2 && granularity == page);
        unsigned bits = 0;
        for (ULONG_PTR i = 0; i < count; ++i) {
            assert((unsigned char *)addresses[i] >= memory &&
                   (unsigned char *)addresses[i] < memory + page * 3);
            bits |= 1U << ((size_t)((unsigned char *)addresses[i] - memory) / page);
        }
        assert(bits == 5);
    }
#ifdef OBOR_HAS_MOVIE_PLAYBACK
    assert(suspended == 16);
#else
    assert(suspended == (disabled ? 16 : 0));
#endif
    assert(VirtualFree(memory, 0, MEM_RELEASE));
    puts("native_write_watch_worker_passed=1 captures_require_join=1 cycles=16");
    return 0;
}
