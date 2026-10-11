/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE 1
#include <dirent.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

/* Linux diagnostic interposer. No probing or sleeping outside the requested
 * retro_run window. Calls into libc, rather than every internal libc syscall,
 * are counted; opendir covers its internal open/fstat/getdents setup too.
 * There is no file output in the timed window. */
#define MAX_FRAMES 4096
enum { C_CHDIR, C_FCHDIR, C_GETCWD, C_STAT, C_FSTAT, C_OPEN, C_OPENDIR, C_READDIR, C_COUNT };
static const char *names[] = {"chdir", "fchdir", "getcwd", "stat", "fstat", "open", "opendir", "readdir"};
typedef struct { uint64_t ns, calls[C_COUNT]; } frame_record;
static frame_record records[MAX_FRAMES];
static unsigned first_frame, last_frame, delay_ms, frame_now, active;
static uint64_t start_ns;
static __thread int entering;
static FILE *output;

static uint64_t now(void)
{
    struct timespec value; clock_gettime(CLOCK_MONOTONIC, &value);
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}

static void account(unsigned kind)
{
    int saved = errno;
    if (__atomic_load_n(&active, __ATOMIC_ACQUIRE) && !entering) {
        entering = 1;
        __atomic_fetch_add(&records[frame_now].calls[kind], 1, __ATOMIC_RELAXED);
        if (delay_ms) {
            struct timespec wait = {0, (long)delay_ms * 1000000L};
            while (nanosleep(&wait, &wait) && errno == EINTR) {}
        }
        entering = 0;
    }
    errno = saved;
}

__attribute__((constructor)) static void initialize(void)
{
    const char *path = getenv("OBOR_TEST_FS_REPORT");
    if (!path) return;
    first_frame = (unsigned)strtoul(getenv("OBOR_TEST_FS_FIRST") ?: "600", NULL, 10);
    last_frame = (unsigned)strtoul(getenv("OBOR_TEST_FS_LAST") ?: "900", NULL, 10);
    delay_ms = (unsigned)strtoul(getenv("OBOR_TEST_FS_DELAY_MS") ?: "0", NULL, 10);
    if (first_frame > last_frame || last_frame >= MAX_FRAMES || delay_ms > 200) abort();
    output = fopen(path, "wx"); if (!output) abort();
}

void obor_fs_probe_begin(unsigned frame)
{
    if (!output || frame < first_frame || frame > last_frame) return;
    frame_now = frame; start_ns = now();
    __atomic_store_n(&active, 1, __ATOMIC_RELEASE);
}

void obor_fs_probe_end(unsigned frame)
{
    if (!__atomic_exchange_n(&active, 0, __ATOMIC_ACQ_REL)) return;
    if (frame != frame_now) abort();
    records[frame].ns = now() - start_ns;
}

__attribute__((destructor)) static void finish(void)
{
    if (!output) return;
    __atomic_store_n(&active, 0, __ATOMIC_RELEASE);
    fprintf(output, "frame,ns");
    for (unsigned kind = 0; kind < C_COUNT; ++kind) fprintf(output, ",%s", names[kind]);
    fputc('\n', output);
    for (unsigned frame = first_frame; frame <= last_frame; ++frame) {
        fprintf(output, "%u,%llu", frame, (unsigned long long)records[frame].ns);
        for (unsigned kind = 0; kind < C_COUNT; ++kind)
            fprintf(output, ",%llu", (unsigned long long)records[frame].calls[kind]);
        fputc('\n', output);
    }
    fclose(output);
}

#define RESOLVE(name, type) \
    static type cached; \
    type original = __atomic_load_n(&cached, __ATOMIC_ACQUIRE); \
    if (!original) { *(void **)(&original) = dlsym(RTLD_NEXT, #name); if (!original) abort(); \
        __atomic_store_n(&cached, original, __ATOMIC_RELEASE); }
#define PATH_ONE(name, kind) \
    int name(const char *path) { typedef int (*function)(const char *); \
        RESOLVE(name, function); account(kind); return original(path); }
PATH_ONE(chdir, C_CHDIR)
int fchdir(int fd) { typedef int (*function)(int); RESOLVE(fchdir, function); account(C_FCHDIR); return original(fd); }
char *getcwd(char *buffer, size_t size) { typedef char *(*function)(char *, size_t); RESOLVE(getcwd, function); account(C_GETCWD); return original(buffer, size); }
#define PATH_STAT(name, record) \
    int name(const char *path, record *buf) { typedef int (*function)(const char *, record *); \
        RESOLVE(name, function); account(C_STAT); return original(path, buf); }
PATH_STAT(stat, struct stat)
PATH_STAT(stat64, struct stat64)
PATH_STAT(lstat, struct stat)
PATH_STAT(lstat64, struct stat64)
#define FD_STAT(name, record) \
    int name(int fd, record *buf) { typedef int (*function)(int, record *); \
        RESOLVE(name, function); account(C_FSTAT); return original(fd, buf); }
FD_STAT(fstat, struct stat)
FD_STAT(fstat64, struct stat64)
#define AT_STAT(name, record) \
    int name(int fd, const char *path, record *buf, int flags) { \
        typedef int (*function)(int, const char *, record *, int); \
        RESOLVE(name, function); account(C_STAT); return original(fd, path, buf, flags); }
AT_STAT(fstatat, struct stat)
AT_STAT(fstatat64, struct stat64)
#define OPEN(name) \
    int name(const char *path, int flags, ...) { typedef int (*function)(const char *, int, ...); \
        RESOLVE(name, function); int mode = 0; \
        if ((flags & O_CREAT) || (flags & O_TMPFILE) == O_TMPFILE) { \
            va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args); } \
        account(C_OPEN); return original(path, flags, mode); }
OPEN(open)
OPEN(open64)
#define FOPEN(name) \
    FILE *name(const char *path, const char *mode) { \
        typedef FILE *(*function)(const char *, const char *); RESOLVE(name, function); \
        account(C_OPEN); return original(path, mode); }
FOPEN(fopen)
FOPEN(fopen64)
int openat(int fd, const char *path, int flags, ...)
{
    typedef int (*function)(int, const char *, int, ...); RESOLVE(openat, function);
    int mode = 0;
    if ((flags & O_CREAT) || (flags & O_TMPFILE) == O_TMPFILE) {
        va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    account(C_OPEN); return original(fd, path, flags, mode);
}
DIR *opendir(const char *path)
{
    typedef DIR *(*function)(const char *); RESOLVE(opendir, function);
    account(C_OPENDIR); return original(path);
}
struct dirent *readdir(DIR *directory)
{
    typedef struct dirent *(*function)(DIR *); RESOLVE(readdir, function);
    account(C_READDIR); return original(directory);
}
struct dirent64 *readdir64(DIR *directory)
{
    typedef struct dirent64 *(*function)(DIR *); RESOLVE(readdir64, function);
    account(C_READDIR); return original(directory);
}
