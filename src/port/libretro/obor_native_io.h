/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_NATIVE_IO_H
#define OBOR_NATIVE_IO_H

#if defined(__APPLE__)
/* The SDK selects the ABI of each declaration. Native dynamic lookups must
 * select that same ABI: an undecorated stat/opendir can be the legacy layout
 * even though the compiler bound our interposer to the current SDK layout.
 * Use the SDK's suffixes, which also cover targets with no alternate ABI.
 * Supported deployment floors are newer than the stdio 10.6 alias switch. */
#if defined(_DARWIN_UNLIMITED_STREAMS) || defined(_DARWIN_C_SOURCE)
#define OBOR_NATIVE_IO_FOPEN "fopen" __DARWIN_SUF_EXTSN
#else
#define OBOR_NATIVE_IO_FOPEN "fopen" __DARWIN_SUF_UNIX03
#endif
#define OBOR_NATIVE_IO_FCLOSE "fclose"
#define OBOR_NATIVE_IO_OPEN "open" __DARWIN_SUF_NON_CANCELABLE __DARWIN_SUF_UNIX03
#define OBOR_NATIVE_IO_CLOSE "close" __DARWIN_SUF_NON_CANCELABLE __DARWIN_SUF_UNIX03
#define OBOR_NATIVE_IO_READ "read" __DARWIN_SUF_NON_CANCELABLE __DARWIN_SUF_UNIX03
#define OBOR_NATIVE_IO_FREAD "fread"
#define OBOR_NATIVE_IO_STAT "stat" __DARWIN_SUF_64_BIT_INO_T
#define OBOR_NATIVE_IO_OPENDIR "opendir" __DARWIN_SUF_64_BIT_INO_T __DARWIN_SUF_UNIX03
#define OBOR_NATIVE_IO_REMOVE "remove"
#define OBOR_NATIVE_IO_UNLINK "unlink"
#define OBOR_NATIVE_IO_RMDIR "rmdir"
#define OBOR_NATIVE_IO_RENAME "rename"
#define OBOR_NATIVE_IO_MKDIR "mkdir"
#define OBOR_NATIVE_IO_CHMOD "chmod" __DARWIN_SUF_UNIX03

/* Native code addresses belong to this process, not an engine snapshot.
 * Workers may race their first lookup; publish only the complete pointer. */
#define OBOR_DARWIN_NATIVE(symbol, lookup) \
    static __typeof__(&symbol) original_storage OBOR_RUNTIME; \
    __typeof__(&symbol) original = __atomic_load_n(&original_storage, __ATOMIC_ACQUIRE); \
    if (!original) { \
        void *resolved = dlsym(RTLD_NEXT, lookup); \
        _Static_assert(sizeof(original) == sizeof(resolved), "Darwin function address width"); \
        memcpy(&original, &resolved, sizeof(original)); \
        if (original) __atomic_store_n(&original_storage, original, __ATOMIC_RELEASE); \
    }
#endif

#endif
