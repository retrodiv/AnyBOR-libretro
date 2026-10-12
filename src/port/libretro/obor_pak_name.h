/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PAK_NAME_H
#define OBOR_PAK_NAME_H

#include <stddef.h>
#include <string.h>

/* Engine output names come from the basename, never from a copy of the
 * entire content path. Keep the engines' four-character extension convention
 * for normal archive names. Reject insufficient destinations without silently
 * changing the name (and therefore possibly opening another save file). */
static inline int obor_pak_name(char *out, size_t capacity,
                                const char *path, int type)
{
    const char *base, *p, *suffix = "";
    size_t length, extra;
    if (!out || !capacity || !path) return 0;
    base = path;
    for (p = path; *p; ++p)
        if (*p == '/' || *p == '\\') base = p + 1;
    length = (size_t)(p - base);
    if (length >= 4) length -= 4;
    switch (type) {
    case 0: suffix = ".sav"; break;
    case 1: suffix = ".hi"; break;
    case 2: suffix = ".scr"; break;
    case 3: suffix = ".inp"; break;
    case 4: suffix = ".cfg"; break;
    case 5: suffix = ".controls"; break;
    default: break;
    }
    extra = strlen(suffix);
    if (!length || length >= capacity || extra >= capacity - length) {
        out[0] = '\0';
        return 0;
    }
    memmove(out, base, length);
    memcpy(out + length, suffix, extra + 1);
    return 1;
}

/* Callers also compose an output directory and possibly a script filename.
 * The destination stays intact on failure; no truncated alias is produced. */
static inline int obor_pak_path_append(char *out, size_t capacity,
                                     const char *tail)
{
    size_t used = 0, extra;
    if (!out || !capacity || !tail) return 0;
    while (used < capacity && out[used]) ++used;
    if (used == capacity) return 0;
    extra = strlen(tail);
    if (extra >= capacity - used) return 0;
    memmove(out + used, tail, extra + 1);
    return 1;
}
#endif
