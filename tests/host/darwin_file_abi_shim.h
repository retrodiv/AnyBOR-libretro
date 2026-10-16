/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef ANYBOR_TEST_DARWIN_FILE_ABI_SHIM_H
#define ANYBOR_TEST_DARWIN_FILE_ABI_SHIM_H
/* Load the host declarations before selecting the port's Darwin branch.
 * Only the two directory/status entry points below model a second SDK ABI.
 * These are original minimal records, not copied SDK headers. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>

struct obor_test_stat {
    uint32_t device;
    uint16_t st_mode, links;
    uint64_t inode;
};
int obor_test_stat(const char *, struct obor_test_stat *) __asm__("stat$INODE64");
DIR *opendir(const char *) __asm__("opendir$INODE64");
#define stat obor_test_stat
#undef _LARGEFILE64_SOURCE
#undef __linux__
#define __APPLE__ 1
#define _DARWIN_C_SOURCE 1
#define __DARWIN_SUF_64_BIT_INO_T "$INODE64"
#define __DARWIN_SUF_UNIX03 ""
#define __DARWIN_SUF_NON_CANCELABLE ""
#define __DARWIN_SUF_EXTSN ""
/* This fixture uses the ELF loader, so model process-local storage with its
 * native section spelling. Actual Darwin sections are checked with the SDK. */
#define OBOR_RUNTIME_H
#define OBOR_RUNTIME __attribute__((section("obor_rt")))
#endif
