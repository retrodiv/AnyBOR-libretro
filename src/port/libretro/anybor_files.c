/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _LARGEFILE64_SOURCE
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <fcntl.h>
#include "anybor_abi.h"
#include "anybor_paths.h"
#include "anybor_loose.h"
#include <dirent.h>
#include <sys/stat.h>
#ifdef _WIN32
#include "anybor_file_io.h"
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
#ifdef _WIN32
    FILE *file = obor_fopen(path, mode);
#else
    FILE *file = __real_fopen(path, mode);
#endif
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
#ifdef _WIN32
    int fd = obor_open(path, flags, mode);
#else
    int fd = OBOR_REAL_OPEN(path, flags, mode);
#endif
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

#if defined(__linux__)
/* Target codec archives can be built with large-file redirection. */
FILE *__wrap_fopen64(const char *path, const char *mode)
{
    return tracked_fopen(path, mode);
}
#endif

/* Relative paths belong to the engine session, including metadata and
 * script writes. Only actual I/O resolves a path; yielding a frame does not.
 * The partial-link wrappers are confined to this engine's symbol namespace. */
extern DIR *__real_opendir(const char *);
DIR *__wrap_opendir(const char *path)
{
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
#ifdef _WIN32
    return path ? obor_opendir(path) : NULL;
#else
    return path ? __real_opendir(path) : NULL;
#endif
}

#ifdef _WIN32
struct dirent *__wrap_readdir(DIR *directory)
{
    return obor_readdir(directory);
}

int __wrap_closedir(DIR *directory)
{
    return obor_closedir(directory);
}

static int obor_win_unlink(const char *path)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wunlink(name) : -1;
}
#define OBOR_NATIVE_REMOVE obor_remove
#define OBOR_NATIVE_UNLINK obor_win_unlink
#define OBOR_NATIVE_RMDIR obor_rmdir
#define OBOR_NATIVE_RENAME obor_rename
#else
extern int __real_remove(const char *);
extern int __real_unlink(const char *);
extern int __real_rmdir(const char *);
extern int __real_rename(const char *, const char *);
#define OBOR_NATIVE_REMOVE __real_remove
#define OBOR_NATIVE_UNLINK __real_unlink
#define OBOR_NATIVE_RMDIR __real_rmdir
#define OBOR_NATIVE_RENAME __real_rename
#endif

#define PATH_CALL_ONE(name, native) \
    int __wrap_##name(const char *path) { \
        obor_loose_invalidate(); \
        char mapped[8192]; \
        path = obor_paths_resolve(path, mapped, sizeof(mapped)); \
        return path ? native(path) : -1; \
    }
PATH_CALL_ONE(remove, OBOR_NATIVE_REMOVE)
PATH_CALL_ONE(unlink, OBOR_NATIVE_UNLINK)
PATH_CALL_ONE(rmdir, OBOR_NATIVE_RMDIR)
#ifdef _WIN32
PATH_CALL_ONE(_unlink, OBOR_NATIVE_UNLINK)
PATH_CALL_ONE(_rmdir, OBOR_NATIVE_RMDIR)
#endif

int __wrap_rename(const char *from, const char *to)
{
    obor_loose_invalidate();
    char old_path[8192], new_path[8192];
    from = obor_paths_resolve(from, old_path, sizeof(old_path));
    if (!from) return -1;
    to = obor_paths_resolve(to, new_path, sizeof(new_path));
    return to ? OBOR_NATIVE_RENAME(from, to) : -1;
}

#if defined(_WIN32)
int __wrap_mkdir(const char *path)
{
    obor_loose_invalidate();
    char mapped[8192];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    return path ? obor_mkdir(path, 0755) : -1;
}
int __wrap__mkdir(const char *path) { return __wrap_mkdir(path); }
int __wrap_chmod(const char *path, int mode)
{
    obor_loose_invalidate();
    char mapped[8192];
    wchar_t name[OBOR_WIN_PATH_CAP];
    path = obor_paths_resolve(path, mapped, sizeof(mapped));
    return path && obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wchmod(name, mode) : -1;
}
int __wrap__chmod(const char *path, int mode) { return __wrap_chmod(path, mode); }
/* Each emitted MinGW name encodes the caller's stat buffer ABI. */
#define PATH_STAT(name, native, type) \
    int __wrap_##name(const char *path, struct type *buf) { \
        char mapped[8192]; \
        wchar_t wide[OBOR_WIN_PATH_CAP]; \
        path = obor_paths_resolve(path, mapped, sizeof(mapped)); \
        return path && obor_win_wide(path, wide, OBOR_WIN_PATH_CAP) ? native(wide, buf) : -1; \
    }
#if !defined(_WIN64)
PATH_STAT(stat32, _wstat32, _stat32)
PATH_STAT(_stat32, _wstat32, _stat32)
PATH_STAT(stat32i64, _wstat32i64, _stat32i64)
PATH_STAT(_stat32i64, _wstat32i64, _stat32i64)
#endif
PATH_STAT(stat64i32, _wstat64i32, _stat64i32)
PATH_STAT(_stat64i32, _wstat64i32, _stat64i32)
PATH_STAT(stat64, _wstat64, _stat64)
PATH_STAT(_stat64, _wstat64, _stat64)
PATH_STAT(stat, _wstat, _stat)
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
/* Matching the allocator interposers in anybor_alloc.c: the Darwin engine build
 * renames every symbol an engine defines, so this fopen() only captures the
 * engine's own calls while the glue keeps libSystem's. */
#if defined(__APPLE__)
#include <dlfcn.h>
#include "anybor_native_io.h"
#include "anybor_runtime.h"

FILE *__real_fopen(const char *path, const char *mode)
{
    OBOR_DARWIN_NATIVE(__real_fopen, OBOR_NATIVE_IO_FOPEN);
    if (!original) {
        errno = ENOSYS;
        return NULL;
    }
    return original(path, mode);
}

FILE *fopen(const char *path, const char *mode) { return __wrap_fopen(path, mode); }
int __real_fclose(FILE *file)
{
    OBOR_DARWIN_NATIVE(__real_fclose, OBOR_NATIVE_IO_FCLOSE);
    return original ? original(file) : EOF;
}
int fclose(FILE *file) { return __wrap_fclose(file); }
int __real_open(const char *path, int flags, ...)
{
    OBOR_DARWIN_NATIVE(__real_open, OBOR_NATIVE_IO_OPEN);
    va_list args; int mode;
    va_start(args, flags); mode = va_arg(args, int); va_end(args);
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
    OBOR_DARWIN_NATIVE(__real_close, OBOR_NATIVE_IO_CLOSE);
    return original ? original(fd) : -1;
}
int close(int fd) { return __wrap_close(fd); }
#define DARWIN_PATH_ONE(name, native_name) \
    int __real_##name(const char *path) { \
        OBOR_DARWIN_NATIVE(__real_##name, native_name); \
        if (!original) { errno = ENOSYS; return -1; } \
        return original(path); \
    } \
    int name(const char *path) { return __wrap_##name(path); }
DARWIN_PATH_ONE(remove, OBOR_NATIVE_IO_REMOVE)
DARWIN_PATH_ONE(unlink, OBOR_NATIVE_IO_UNLINK)
DARWIN_PATH_ONE(rmdir, OBOR_NATIVE_IO_RMDIR)
#define DARWIN_PATH_TWO(name, type, native_name) \
    int __real_##name(const char *path, type value) { \
        OBOR_DARWIN_NATIVE(__real_##name, native_name); \
        if (!original) { errno = ENOSYS; return -1; } \
        return original(path, value); \
    } \
    int name(const char *path, type value) { return __wrap_##name(path, value); }
DARWIN_PATH_TWO(rename, const char *, OBOR_NATIVE_IO_RENAME)
DARWIN_PATH_TWO(mkdir, mode_t, OBOR_NATIVE_IO_MKDIR)
DARWIN_PATH_TWO(chmod, mode_t, OBOR_NATIVE_IO_CHMOD)
DARWIN_PATH_TWO(stat, struct stat *, OBOR_NATIVE_IO_STAT)
DIR *__real_opendir(const char *path)
{
    OBOR_DARWIN_NATIVE(__real_opendir, OBOR_NATIVE_IO_OPENDIR);
    if (!original) { errno = ENOSYS; return NULL; }
    return original(path);
}
DIR *opendir(const char *path) { return __wrap_opendir(path); }
#endif
