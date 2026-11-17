/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Select native allocation admission and preserve call-site metadata by
 * profile. Bound copied string extents.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2015 OpenBOR Team
 */

#ifndef SAFEALLOC_H
#define SAFEALLOC_H

#include <stdlib.h>
#include <limits.h>
#include <stdint.h>
#include <string.h> // for strlen
#include "utils.h" // for checkAlloc

extern unsigned int obor_profile_build;

#define MALLOCLIKE __attribute__((__malloc__))

static inline void *safeRealloc(void *ptr, size_t size, const char *func, const char *file, int line)
{
    return checkAlloc(realloc(ptr, size), size, func, file, line);
}

// attributes can only be declared on function declarations, so declare these before defining them
static inline void *safeMalloc(size_t size, const char *func, const char *file, int line) MALLOCLIKE;
static inline void *safeCalloc(size_t nmemb, size_t size, const char *func, const char *file, int line) MALLOCLIKE;
static inline void *safeStrdup(const char *str, const char *func, const char *file, int line) MALLOCLIKE;

static inline void *safeMalloc(size_t size, const char *func, const char *file, int line)
{
    return checkAlloc(malloc(size), size, func, file, line);
}

static inline void *safeCalloc(size_t nmemb, size_t size, const char *func, const char *file, int line)
{
    return checkAlloc(calloc(nmemb, size), size, func, file, line);
}

static inline void *safeStrdup(const char *str, const char *func, const char *file, int line)
{
    if(obor_profile_build < 4163) return strdup(str);
    size_t length = strlen(str);
    if(length >= INT_MAX)
    {
        checkAlloc(NULL, length == SIZE_MAX ? length : length + 1, func, file, line);
        return NULL;
    }
    size_t size = length + 1;
    char *newString = (char *)checkAlloc(malloc(size), size, func, file, line);
    memcpy(newString, str, size);
    return newString;
}

#define realloc(ptr, size) safeRealloc(ptr, size, __func__, __FILE__, __LINE__)
#define malloc(size) safeMalloc(size, __func__, __FILE__, __LINE__)
#define calloc(nmemb, size) safeCalloc(nmemb, size, __func__, __FILE__, __LINE__)
#define strdup(str) safeStrdup(str, __func__, __FILE__, __LINE__)

#endif // !defined SAFEALLOC_H
