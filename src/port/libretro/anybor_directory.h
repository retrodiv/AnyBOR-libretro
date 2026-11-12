/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_DIRECTORY_H
#define OBOR_DIRECTORY_H

/* Linux O_PATH preserves search-only directory permissions. The caller must
 * enable GNU declarations before including libc headers. This is process
 * state: place persistent instances in OBOR_RUNTIME, never in a savestate. */
#if defined(__linux__)
#include <errno.h>
#include <fcntl.h>
#include <linux/magic.h>
#include <string.h>
#include <sys/vfs.h>
#include <unistd.h>

typedef struct {
    /* Zero initialization owns no descriptor; fd 0 is still representable. */
    int descriptor_plus_one;
    char path[4096];
} obor_directory_cache;

static void obor_directory_clear(obor_directory_cache *cache)
{
    if (cache->descriptor_plus_one)
        close(cache->descriptor_plus_one - 1);
    cache->descriptor_plus_one = 0;
    cache->path[0] = '\0';
}

static int obor_directory_current(void)
{
    /* Use the calling thread's actual directory identity, including renamed
     * directories. Ordinary lookup of "." can ask a userspace filesystem for
     * permissions even when we only need an O_PATH handle. Procfs' magic link
     * avoids that pathname walk. Verify procfs before trusting the link; keep
     * ordinary lookup on systems without this procfs entry. */
    struct statfs filesystem;
    int flags = O_PATH | O_DIRECTORY | O_CLOEXEC;
    int proc = open("/proc/thread-self", flags);
    if (proc >= 0) {
        if (fstatfs(proc, &filesystem) == 0 && filesystem.f_type == PROC_SUPER_MAGIC) {
            int saved = openat(proc, "cwd", flags);
            int error = errno;
            close(proc);
            if (saved >= 0) return saved;
            if (error != ENOENT && error != ENOTDIR && error != EACCES &&
                error != EPERM && error != ENOSYS && error != ELOOP) {
                errno = error;
                return -1;
            }
        } else close(proc);
    } else if (errno != ENOENT && errno != ENOTDIR && errno != EACCES &&
               errno != EPERM && errno != ENOSYS && errno != ELOOP) {
        return -1;
    }
    return open(".", flags);
}

static int obor_directory_enter(obor_directory_cache *cache,
                                const char *path, int *previous)
{
    size_t length;
    int descriptor, saved, error, replacement;
    *previous = -1;
    length = strnlen(path, sizeof(cache->path));
    if (!length || length == sizeof(cache->path)) {
        errno = length ? ENAMETOOLONG : ENOENT;
        return 0;
    }
    if (path[0] != '/') {
        errno = EINVAL;
        return 0;
    }
    replacement = !cache->descriptor_plus_one || strcmp(path, cache->path);
    if (replacement) {
        descriptor = open(path, O_PATH | O_DIRECTORY | O_CLOEXEC);
        if (descriptor < 0) return 0;
    } else descriptor = cache->descriptor_plus_one - 1;
    /* Capture the live frontend directory every time: it may have changed
     * since the preceding frame. This handle exists only on its own stack. */
    saved = obor_directory_current();
    if (saved < 0) {
        error = errno;
        if (replacement) close(descriptor);
        errno = error;
        return 0;
    }
    if (fchdir(descriptor) != 0) {
        error = errno;
        close(saved);
        if (replacement) close(descriptor);
        errno = error;
        return 0;
    }
    if (replacement) {
        obor_directory_clear(cache);
        cache->descriptor_plus_one = descriptor + 1;
        memcpy(cache->path, path, length + 1);
    }
    *previous = saved;
    return 1;
}

static int obor_directory_leave(int previous)
{
    int status = fchdir(previous);
    int error = errno;
    close(previous);
    if (status != 0) errno = error;
    return status == 0;
}
#endif
#endif
