/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _LARGEFILE64_SOURCE
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <fcntl.h>
#include "obor_abi.h"
#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

extern char savesDir[], logsDir[], screenShotsDir[];
extern FILE *__real_fopen(const char *, const char *);
extern int __real_fclose(FILE *);
extern void (*obor_resource_event)(uint32_t, uintptr_t);

static FILE *tracked_fopen(const char *path, const char *mode)
{
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
    int fd = __real_open64(path, flags, mode);
    if (fd >= 0 && obor_resource_event)
        obor_resource_event(OBOR_RESOURCE_FD_OPEN, (uintptr_t)fd);
    return fd;
}
#endif

/* Legacy engines use literal relative output paths even when the port's
 * directory globals are absolute. Redirect reads too: a loose game's bundled
 * settings belong to its original runner, not this engine's binary layout. */
FILE *__wrap_fopen(const char *path, const char *mode)
{
    static const char *const names[] = { "saves", "logs", "screenshots" };
    const char *roots[] = { savesDir, logsDir, screenShotsDir };
    const char *part = path;
    char mapped[4096];
    while (part[0] == '.' && (part[1] == '/' || part[1] == '\\')) part += 2;
    for (unsigned i = 0; i < 3; ++i) {
        size_t j = 0;
        while (names[i][j] && part[j]) {
            unsigned char c = (unsigned char)part[j];
            if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
            if (c != names[i][j]) break;
            ++j;
        }
        if (names[i][j] || (part[j] != '/' && part[j] != '\\')) continue;
        int n = snprintf(mapped, sizeof(mapped), "%s/%s", roots[i], part + j + 1);
        if (n < 0 || (size_t)n >= sizeof(mapped)) { errno = ENAMETOOLONG; return NULL; }
        for (char *p = mapped; *p; ++p) if (*p == '\\') *p = '/';
        return tracked_fopen(mapped, mode);
    }
    return tracked_fopen(path, mode);
}

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
#endif
