/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_ENGINE_RESOURCES_H
#define OBOR_ENGINE_RESOURCES_H
#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif
/* This ledger belongs to the glue, outside the engine arena. In particular,
 * cleanup after a fault must not trust packhandle[] or engine FILE pointers.
 * Its live contents are preserved when module data is restored from a state. */
typedef struct {
    uintptr_t handle;
    uint32_t kind;
} obor_resource_record;
typedef struct {
    int lock;
    obor_resource_record records[2048];
} obor_resource_ledger;
static obor_resource_ledger g_engine_resources OBOR_RUNTIME;

static void engine_resource_event(uint32_t kind, uintptr_t handle)
{
    uint32_t opened = kind == OBOR_RESOURCE_FILE_CLOSE ? OBOR_RESOURCE_FILE_OPEN :
                      kind == OBOR_RESOURCE_FD_CLOSE ? OBOR_RESOURCE_FD_OPEN : kind;
    int closing = opened != kind;
    while (__atomic_exchange_n(&g_engine_resources.lock, 1, __ATOMIC_ACQUIRE)) {}
    size_t free_slot = 2048;
    for (size_t i = 0; i < 2048; ++i) {
        obor_resource_record *record = &g_engine_resources.records[i];
        if (!record->kind && free_slot == 2048) free_slot = i;
        if (record->kind == opened && record->handle == handle) {
            if (closing) record->kind = 0;
            __atomic_store_n(&g_engine_resources.lock, 0, __ATOMIC_RELEASE);
            return;
        }
    }
    if (!closing && free_slot != 2048) {
        g_engine_resources.records[free_slot].handle = handle;
        g_engine_resources.records[free_slot].kind = kind;
    }
    __atomic_store_n(&g_engine_resources.lock, 0, __ATOMIC_RELEASE);
}

/* Called only after the coroutine and every movie worker have stopped. */
static void engine_resources_close(void)
{
    for (size_t i = 0; i < 2048; ++i) {
        obor_resource_record *record = &g_engine_resources.records[i];
        if (record->kind == OBOR_RESOURCE_FILE_OPEN) fclose((FILE *)record->handle);
        else if (record->kind == OBOR_RESOURCE_FD_OPEN) {
#ifdef _WIN32
            _close((int)record->handle);
#else
            close((int)record->handle);
#endif
        }
        record->kind = 0;
    }
}
#endif
