/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include <sys/stat.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <dirent.h>
#include <dlfcn.h>
#include <assert.h>

/* Equal-sized records deliberately put mode at different offsets. A lookup
 * of the legacy name must not fill a caller's current-layout buffer. */
struct current_status { uint32_t device; uint16_t mode, links; uint64_t inode; };
struct legacy_status { uint32_t device, inode; uint16_t mode, links; uint32_t spare; };
static unsigned legacy_stats, current_stats, legacy_dirs, current_dirs;

static int native_stat(const char *path, struct stat *buffer)
{
    static int (*function)(const char *, struct stat *);
    if (!function) *(void **)&function = dlsym(RTLD_NEXT, "stat");
    assert(function);
    return function(path, buffer);
}

int legacy_status_call(const char *, void *) __asm__("stat");
int legacy_status_call(const char *path, void *buffer)
{
    struct stat live;
    int result = native_stat(path, &live);
    ++legacy_stats;
    if (!result) {
        struct legacy_status old = {0};
        old.mode = live.st_mode;
        memcpy(buffer, &old, sizeof(old));
    }
    return result;
}

int current_status_call(const char *, void *) __asm__("stat$INODE64");
int current_status_call(const char *path, void *buffer)
{
    struct stat live;
    int result = native_stat(path, &live);
    ++current_stats;
    if (!result) {
        struct current_status current = {0};
        current.mode = live.st_mode;
        memcpy(buffer, &current, sizeof(current));
    }
    return result;
}

static DIR *native_opendir(const char *path)
{
    static DIR *(*function)(const char *);
    if (!function) *(void **)&function = dlsym(RTLD_NEXT, "opendir");
    assert(function);
    return function(path);
}
DIR *legacy_directory_call(const char *) __asm__("opendir");
DIR *legacy_directory_call(const char *path)
{
    ++legacy_dirs;
    return native_opendir(path);
}
DIR *current_directory_call(const char *) __asm__("opendir$INODE64");
DIR *current_directory_call(const char *path)
{
    ++current_dirs;
    return native_opendir(path);
}
int provider_abi_correct(void)
{
    assert(offsetof(struct current_status, mode) == 4);
    assert(offsetof(struct legacy_status, mode) == 8);
    return current_stats && current_dirs && !legacy_stats && !legacy_dirs;
}
