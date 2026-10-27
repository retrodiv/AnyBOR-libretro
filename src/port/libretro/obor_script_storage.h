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

#ifndef OBOR_SCRIPT_STORAGE_ALLOC
#define OBOR_SCRIPT_STORAGE_ALLOC(n) malloc(n)
#endif
#ifndef OBOR_SCRIPT_STORAGE_FREE
#define OBOR_SCRIPT_STORAGE_FREE(p) free(p)
#endif

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

static inline int obor_script_reference_release(obor_script_reference **slot)
{
    obor_script_reference *reference;
    if(!slot) return 0;
    reference = *slot;
    if(!reference) return 1;
    if(!reference->references) return 0;
    *slot = NULL;
    if(--reference->references == 0)
    {
        reference->destroy(reference->value);
        OBOR_SCRIPT_STORAGE_FREE(reference);
    }
    return 1;
}

#endif
