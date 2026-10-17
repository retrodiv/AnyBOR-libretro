/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef ANYBOR_HOST_ARENA_PROBE_H
#define ANYBOR_HOST_ARENA_PROBE_H
#ifdef _WIN32
#include "obor_abi.h"
static int check_host_arena_released(void)
{
    void *base = (void *)(uintptr_t)OBOR_ARENA_BASE_VA;
    void *probe = VirtualAlloc(base, (SIZE_T)OBOR_ARENA_MAX_SZ,
                              MEM_RESERVE, PAGE_NOACCESS);
    if(probe != base)
    {
        if(probe) VirtualFree(probe, 0, MEM_RELEASE);
        fprintf(stderr, "arena reservation leaked after FreeLibrary\n");
        return 0;
    }
    if(!VirtualFree(probe, 0, MEM_RELEASE)) return 0;
    puts("arena_released=1");
    return 1;
}
#endif
#endif
