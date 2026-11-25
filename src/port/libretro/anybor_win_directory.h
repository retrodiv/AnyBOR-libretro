/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_WIN_DIRECTORY_H
#define OBOR_WIN_DIRECTORY_H

/* Keep the directory ABI usable from legacy sources with their own Win32 types. */
typedef struct obor_path_directory obor_path_directory;
typedef struct obor_path_entry {
    /* One Windows filename component can occupy 765 bytes in UTF-8. */
    char d_name[3 * 256];
    unsigned long attributes;
} obor_path_entry;

#endif
