/* Allocation boundary for the native import/VM fixture.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef IMPORTS_PROBE_ALLOC_H
#define IMPORTS_PROBE_ALLOC_H
#include <stdlib.h>
#include <string.h>
void *fixture_malloc(size_t bytes);
void *fixture_calloc(size_t count, size_t bytes);
void *fixture_realloc(void *pointer, size_t bytes);
char *fixture_strdup(const char *text);
void fixture_free(void *pointer);
#define malloc fixture_malloc
#define calloc fixture_calloc
#define realloc fixture_realloc
#define strdup fixture_strdup
#define free fixture_free
#endif
