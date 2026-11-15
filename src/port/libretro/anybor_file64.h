/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_FILE64_H
#define OBOR_FILE64_H
#include <stdint.h>
#include <stdio.h>
#if !defined(_WIN32)
#include <sys/types.h>
#endif

/* Windows keeps long at 32 bits even in a 64-bit process. POSIX builds must
 * expose large-file stdio before including their system headers. Refuse a
 * narrow off_t rather than silently truncating a packed-content offset. */
static int obor_file_seek64(FILE *file, int64_t offset, int origin)
{
#if defined(_WIN32)
    return _fseeki64(file, offset, origin);
#else
    typedef char obor_file_requires_large_offsets[(sizeof(off_t) >= 8) ? 1 : -1];
    (void)sizeof(obor_file_requires_large_offsets);
    return fseeko(file, (off_t)offset, origin);
#endif
}

static int64_t obor_file_tell64(FILE *file)
{
#if defined(_WIN32)
    return _ftelli64(file);
#else
    return (int64_t)ftello(file);
#endif
}
#endif
