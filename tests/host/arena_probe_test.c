/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <windows.h>
#include "host_arena_probe.h"

int main(void)
{
    void *base = (void *)(uintptr_t)OBOR_ARENA_BASE_VA;
    assert(check_host_arena_released());
    void *held = VirtualAlloc(base, 65536, MEM_RESERVE, PAGE_NOACCESS);
    assert(held == base);
    assert(!check_host_arena_released());
    MEMORY_BASIC_INFORMATION memory;
    assert(VirtualQuery(base, &memory, sizeof(memory)) == sizeof(memory));
    assert(memory.State == MEM_RESERVE && memory.AllocationBase == base);
    assert(VirtualFree(held, 0, MEM_RELEASE));
    assert(check_host_arena_released());
    assert(VirtualQuery(base, &memory, sizeof(memory)) == sizeof(memory));
    assert(memory.State == MEM_FREE);
    puts("arena_probe_occupied_refused=1 clear_released=1");
    return 0;
}
