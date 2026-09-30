/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RUNTIME_H
#define OBOR_RUNTIME_H
#include <stdint.h>
#ifdef __APPLE__
#define OBOR_RUNTIME __attribute__((section("__DATA,__obor_rt")))
#include "obor_macho.h"
#include <mach-o/getsect.h>
#else
#define OBOR_RUNTIME __attribute__((section("obor_rt")))
#endif
#ifdef _WIN32
#include <windows.h>
#elif !defined(__APPLE__)
#ifdef __cplusplus
extern "C" {
#endif
extern unsigned char __start_obor_rt[] __attribute__((visibility("hidden")));
extern unsigned char __stop_obor_rt[] __attribute__((visibility("hidden")));
#ifdef __cplusplus
}
#endif
#endif

/* Guard dispatch state belongs to the live process. Neither a pristine reset
 * nor a partially copied savestate may overwrite it. All engines place these
 * few fields in the same section; the two segment collectors omit it. */
static inline void obor_runtime_bounds(uintptr_t *begin, uintptr_t *end)
{
#ifdef _WIN32
    HMODULE module = NULL;
    *begin = *end = 0;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                           GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)&obor_runtime_bounds, &module)) return;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)module;
    const IMAGE_NT_HEADERS *nt = (const IMAGE_NT_HEADERS *)
        ((const char *)module + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *sections = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        const unsigned char *name = sections[i].Name;
        if (name[0]=='o' && name[1]=='b' && name[2]=='o' && name[3]=='r' &&
            name[4]=='_' && name[5]=='r' && name[6]=='t' && name[7]==0) {
            *begin = (uintptr_t)module + sections[i].VirtualAddress;
            *end = *begin + sections[i].Misc.VirtualSize;
            return;
        }
    }
#elif defined(__APPLE__)
    unsigned long bytes = 0;
    const struct mach_header_64 *header =
        obor_macho_own_header((const void *)&obor_runtime_bounds);
    *begin = header ? (uintptr_t)getsectiondata(header, "__DATA", "__obor_rt", &bytes) : 0;
    *end = *begin + bytes;
#else
    *begin = (uintptr_t)__start_obor_rt;
    *end = (uintptr_t)__stop_obor_rt;
#endif
}
#endif
