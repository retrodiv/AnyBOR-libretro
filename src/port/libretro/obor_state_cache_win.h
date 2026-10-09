/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_CACHE_WIN_H
#define OBOR_STATE_CACHE_WIN_H
#include <windows.h>
#include "obor_block_state.h"

static void *coded_raw_reserve(size_t maximum)
{
    return VirtualAlloc(NULL, maximum, MEM_RESERVE, PAGE_NOACCESS);
}

static int coded_raw_grow(void *address, size_t old_size, size_t new_size)
{
    SYSTEM_INFO info;
    GetSystemInfo(&info);
    size_t page = info.dwPageSize;
    if (!page || new_size < old_size || new_size > OBOR_BLOCK_STATE_MAX_RAW)
        return 0;
    size_t first = (old_size + page - 1) / page * page;
    size_t last = (new_size + page - 1) / page * page;
    return last == first || VirtualAlloc((unsigned char *)address + first,
        last - first, MEM_COMMIT, PAGE_READWRITE) != NULL;
}

static void coded_raw_release(void *address, size_t maximum)
{
    (void)maximum;
    VirtualFree(address, 0, MEM_RELEASE);
}
#endif
