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
#define OBOR_NATIVE_IO_STAT "stat" __DARWIN_SUF_64_BIT_INO_T
#define OBOR_NATIVE_IO_OPENDIR "opendir" __DARWIN_SUF_64_BIT_INO_T __DARWIN_SUF_UNIX03
#define OBOR_NATIVE_IO_REMOVE "remove"
#define OBOR_NATIVE_IO_UNLINK "unlink"
#define OBOR_NATIVE_IO_RMDIR "rmdir"
#define OBOR_NATIVE_IO_RENAME "rename"
#define OBOR_NATIVE_IO_MKDIR "mkdir"
#define OBOR_NATIVE_IO_CHMOD "chmod" __DARWIN_SUF_UNIX03
#endif

#endif
