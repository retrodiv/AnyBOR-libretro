/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stddef.h>
#include <stdlib.h>
typedef union { size_t size; long double alignment; void *pointer; } header;
static size_t attempts, failure, live, peak;
void image_test_reset(size_t fail_at)
{ assert(!live); attempts = peak = 0; failure = fail_at; }
size_t image_test_attempts(void) { return attempts; }
size_t image_test_live(void) { return live; }
size_t image_test_peak(void) { return peak; }
void *image_test_allocate(size_t size)
{
    if (++attempts == failure) return NULL;
    header *p = malloc(sizeof(*p) + size);
    if (!p) return NULL;
    p->size = size;
    live += size;
    if (live > peak) peak = live;
    return p + 1;
}
void image_test_release(void *memory)
{
    if (!memory) return;
    header *p = (header *)memory - 1;
    assert(p->size <= live);
    live -= p->size;
    free(p);
}
