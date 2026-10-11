/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _LARGEFILE64_SOURCE
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <fcntl.h>
#include "obor_abi.h"
#include "obor_paths.h"
#include "obor_loose.h"
#include <dirent.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

extern FILE *__real_fopen(const char *, const char *);
extern int __real_fclose(FILE *);
extern void (*obor_resource_event)(uint32_t, uintptr_t);

static FILE *tracked_fopen(const char *path, const char *mode)
{
    /* Some engine helpers probe loose input with fopen before consulting
     * the PAK reader. Use the same watched absence proof on this path too.
     * Existing files, output directories and unobservable roots still use
     * the original I/O; no file contents or successful opens are cached. */
    if (mode[0] == 'r' && !strchr(mode, '+') && !obor_loose_may_exist(path)) {
        errno = ENOENT;
        return NULL;
    }
    if (strchr(mode, 'w') || strchr(mode, 'a') || strchr(mode, '+')) obor_loose_invalidate();
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    if (!path) return NULL;
    FILE *file = __real_fopen(path, mode);
    if (file && obor_resource_event)
        obor_resource_event(OBOR_RESOURCE_FILE_OPEN, (uintptr_t)file);
    return file;
}

int __wrap_fclose(FILE *file)
{
    int result = __real_fclose(file);
    if (obor_resource_event)
        obor_resource_event(OBOR_RESOURCE_FILE_CLOSE, (uintptr_t)file);
    return result;
}

#define OBOR_REAL_OPEN __real_open
#define OBOR_WRAP_OPEN __wrap_open
#define OBOR_REAL_CLOSE __real_close
#define OBOR_WRAP_CLOSE __wrap_close
extern int OBOR_REAL_OPEN(const char *, int, ...);
extern int OBOR_REAL_CLOSE(int);
int OBOR_WRAP_OPEN(const char *path, int flags, ...)
{
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    if (!(flags & (O_CREAT | O_TRUNC)) && (flags & O_ACCMODE) == O_RDONLY &&
        !obor_loose_may_exist(path)) { errno = ENOENT; return -1; }
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    if (!path) return -1;
    if (flags & (O_CREAT | O_TRUNC | O_WRONLY | O_RDWR)) obor_loose_invalidate();
    int fd = OBOR_REAL_OPEN(path, flags, mode);
    if (fd >= 0 && obor_resource_event)
        obor_resource_event(OBOR_RESOURCE_FD_OPEN, (uintptr_t)fd);
    return fd;
}
int OBOR_WRAP_CLOSE(int fd)
{
    int result = OBOR_REAL_CLOSE(fd);
    if (obor_resource_event)
        obor_resource_event(OBOR_RESOURCE_FD_CLOSE, (uintptr_t)fd);
    return result;
}
#ifdef _WIN32
/* Engine eras use both POSIX aliases and explicit CRT names. */
int __wrap__open(const char *path, int flags, ...)
{
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    return __wrap_open(path, flags, mode);
}
int __wrap__close(int fd) { return __wrap_close(fd); }
#endif
#if defined(__linux__)
extern int __real_open64(const char *, int, ...);
int __wrap_open64(const char *path, int flags, ...)
{
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    if (!(flags & (O_CREAT | O_TRUNC)) && (flags & O_ACCMODE) == O_RDONLY &&
        !obor_loose_may_exist(path)) { errno = ENOENT; return -1; }
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    if (!path) return -1;
    if (flags & (O_CREAT | O_TRUNC | O_WRONLY | O_RDWR)) obor_loose_invalidate();
    int fd = __real_open64(path, flags, mode);
    if (fd >= 0 && obor_resource_event)
        obor_resource_event(OBOR_RESOURCE_FD_OPEN, (uintptr_t)fd);
    return fd;
}
#endif

FILE *__wrap_fopen(const char *path, const char *mode)
{
    return tracked_fopen(path, mode);
}

/* Relative paths belong to the engine session, including metadata and
 * script writes. Only actual I/O resolves a path; yielding a frame does not.
 * The partial-link wrappers are confined to this engine's symbol namespace. */
extern DIR *__real_opendir(const char *);
DIR *__wrap_opendir(const char *path)
{
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    return path ? __real_opendir(path) : NULL;
}

#define PATH_CALL_ONE(name) \
    extern int __real_##name(const char *); \
    int __wrap_##name(const char *path) { \
        obor_loose_invalidate(); \
        char mapped[8192]; \
        path = obor_paths_resolve(path, mapped, sizeof(mapped)); \
        return path ? __real_##name(path) : -1; \
    }
PATH_CALL_ONE(remove)
PATH_CALL_ONE(unlink)
PATH_CALL_ONE(rmdir)

extern int __real_rename(const char *, const char *);
int __wrap_rename(const char *from, const char *to)
{
    obor_loose_invalidate();
    char old_path[8192], new_path[8192];
    from = obor_paths_resolve(from, old_path, sizeof(old_path));
    if (!from) return -1;
    to = obor_paths_resolve(to, new_path, sizeof(new_path));
    return to ? __real_rename(from, to) : -1;
}

#if defined(_WIN32)
extern int __real_mkdir(const char *);
int __wrap_mkdir(const char *path)
{
    obor_loose_invalidate();
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    return path ? __real_mkdir(path) : -1;
}
/* MinGW's stat spellings depend on both time_t and _FILE_OFFSET_BITS in
 * each caller. Forward its buffer unchanged to the matching CRT ABI. */
#define PATH_STAT(name) \
    extern int __real_##name(const char *, void *); \
    int __wrap_##name(const char *path, void *buf) { \
        char mapped[8192]; \
        path = obor_paths_resolve(path, mapped, sizeof(mapped)); \
        return path ? __real_##name(path, buf) : -1; \
    }
#if !defined(_WIN64)
PATH_STAT(stat32)
PATH_STAT(stat32i64)
#endif
PATH_STAT(stat64i32)
PATH_STAT(stat64)
#else
#define PATH_MODE(name) \
    extern int __real_##name(const char *, mode_t); \
    int __wrap_##name(const char *path, mode_t mode) { \
        obor_loose_invalidate(); \
        char mapped[8192]; \
        path = obor_paths_resolve(path, mapped, sizeof(mapped)); \
        return path ? __real_##name(path, mode) : -1; \
    }
PATH_MODE(mkdir)
PATH_MODE(chmod)
#define PATH_STAT(name, type) \
    extern int __real_##name(const char *, type *); \
    int __wrap_##name(const char *path, type *buf) { \
        char mapped[8192]; \
        path = obor_paths_resolve(path, mapped, sizeof(mapped)); \
        return path ? __real_##name(path, buf) : -1; \
    }
PATH_STAT(stat, struct stat)
#if defined(__linux__)
PATH_STAT(stat64, struct stat64)
#endif
#endif

/* ------------------------------------------------------------- Darwin ---- */
/* Matching the allocator interposers in obor_alloc.c: the Darwin engine build
 * renames every symbol an engine defines, so this fopen() only captures the
 * engine's own calls while the glue keeps libSystem's. */
#if defined(__APPLE__)
#include <dlfcn.h>

FILE *__real_fopen(const char *path, const char *mode)
{
    static FILE *(*original)(const char *, const char *);
    if (!original) {
        *(void **)(&original) = dlsym(RTLD_NEXT, "fopen");
        if (!original) {
            errno = ENOSYS;
            return NULL;
        }
    }
    return original(path, mode);
}

FILE *fopen(const char *path, const char *mode) { return __wrap_fopen(path, mode); }
int __real_fclose(FILE *file)
{
    static int (*original)(FILE *);
    if (!original) *(void **)(&original) = dlsym(RTLD_NEXT, "fclose");
    return original ? original(file) : EOF;
}
int fclose(FILE *file) { return __wrap_fclose(file); }
int __real_open(const char *path, int flags, ...)
{
    static int (*original)(const char *, int, ...);
    va_list args; int mode;
    va_start(args, flags); mode = va_arg(args, int); va_end(args);
    if (!original) *(void **)(&original) = dlsym(RTLD_NEXT, "open");
    return original ? original(path, flags, mode) : -1;
}
int open(const char *path, int flags, ...)
{
    va_list args; int mode = 0;
    if (flags & O_CREAT) {
        va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    return __wrap_open(path, flags, mode);
}
int __real_close(int fd)
{
    static int (*original)(int);
    if (!original) *(void **)(&original) = dlsym(RTLD_NEXT, "close");
    return original ? original(fd) : -1;
}
int close(int fd) { return __wrap_close(fd); }
#define DARWIN_PATH_ONE(name) \
    int __real_##name(const char *path) { \
        static int (*original)(const char *); \
        if (!original) *(void **)(&original) = dlsym(RTLD_NEXT, #name); \
        if (!original) { errno = ENOSYS; return -1; } \
        return original(path); \
    } \
    int name(const char *path) { return __wrap_##name(path); }
DARWIN_PATH_ONE(remove)
DARWIN_PATH_ONE(unlink)
DARWIN_PATH_ONE(rmdir)
#define DARWIN_PATH_TWO(name, type) \
    int __real_##name(const char *path, type value) { \
        static int (*original)(const char *, type); \
        if (!original) *(void **)(&original) = dlsym(RTLD_NEXT, #name); \
        if (!original) { errno = ENOSYS; return -1; } \
        return original(path, value); \
    } \
    int name(const char *path, type value) { return __wrap_##name(path, value); }
DARWIN_PATH_TWO(rename, const char *)
DARWIN_PATH_TWO(mkdir, mode_t)
DARWIN_PATH_TWO(chmod, mode_t)
DARWIN_PATH_TWO(stat, struct stat *)
DIR *__real_opendir(const char *path)
{
    static DIR *(*original)(const char *);
    if (!original) *(void **)(&original) = dlsym(RTLD_NEXT, "opendir");
    if (!original) { errno = ENOSYS; return NULL; }
    return original(path);
}
DIR *opendir(const char *path) { return __wrap_opendir(path); }
#endif
