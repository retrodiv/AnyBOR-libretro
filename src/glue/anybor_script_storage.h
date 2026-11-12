/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Shared script values keep their identities until their final reference ends.
 * Interpreter and comment references are independent: replacing an interpreter
 * need not replace its diagnostic comment.
 */
#ifndef OBOR_SCRIPT_STORAGE_H
#define OBOR_SCRIPT_STORAGE_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifndef OBOR_SCRIPT_STORAGE_ALLOC
#define OBOR_SCRIPT_STORAGE_ALLOC(n) malloc(n)
#endif
#ifndef OBOR_SCRIPT_STORAGE_FREE
#define OBOR_SCRIPT_STORAGE_FREE(p) free(p)
#endif

typedef struct obor_script_cleanup {
    const void *script;
    struct obor_script_cleanup *previous;
} obor_script_cleanup;

/* The engine thread owns the chain. Reset it when starting a new engine
 * because a controlled stop can abandon an active callback. */
static inline obor_script_cleanup **obor_script_cleanup_chain(void)
{
    static obor_script_cleanup *active;
    return &active;
}

static inline int obor_script_cleanup_active(const void *script)
{
    const obor_script_cleanup *active = *obor_script_cleanup_chain();
    for(; active; active = active->previous)
        if(active->script == script) return 1;
    return 0;
}

typedef struct obor_script_reference {
    void *value;
    size_t references;
    void (*destroy)(void *);
} obor_script_reference;

static inline obor_script_reference *obor_script_reference_new(
    void *value, void (*destroy)(void *))
{
    obor_script_reference *reference;
    if(!value || !destroy) return NULL;
    reference = (obor_script_reference *)OBOR_SCRIPT_STORAGE_ALLOC(sizeof(*reference));
    if(!reference) return NULL;
    reference->value = value;
    reference->references = 1;
    reference->destroy = destroy;
    return reference;
}

static inline int obor_script_reference_retain(obor_script_reference *reference)
{
    if(!reference || !reference->references || reference->references == SIZE_MAX)
        return 0;
    ++reference->references;
    return 1;
}

static inline int obor_script_reference_release(void *slot)
{
    obor_script_reference *reference;
    if(!slot) return 0;
    /* Pointer slots can belong to packed engine records. */
    memcpy(&reference, (const void *)slot, sizeof(reference));
    if(!reference) return 1;
    if(!reference->references) return 0;
    {
        obor_script_reference *empty = NULL;
        memcpy((void *)slot, &empty, sizeof(empty));
    }
    if(--reference->references == 0)
    {
        reference->destroy(reference->value);
        OBOR_SCRIPT_STORAGE_FREE(reference);
    }
    return 1;
}

#endif
