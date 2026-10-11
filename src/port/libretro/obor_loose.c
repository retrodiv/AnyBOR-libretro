/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "obor_loose.h"
#include "obor_paths.h"
#include "obor_runtime.h"
#include <dirent.h>
#include <errno.h>
#include <pthread.h>
#include <string.h>
#if defined(__linux__)
#include <fcntl.h>
#include <sys/inotify.h>
#include <sys/stat.h>
#include <unistd.h>
#elif defined(_WIN32)
#include <windows.h>
#endif

/* This is directory-name metadata, not bytes from a game or rewind history.
 * At most 256 directory entries and 64 exact-spelling absence proofs, each
 * at most 255 bytes (80 KiB of names). Overflow or unavailable notifications
 * preserves the original lookup. Enumeration alone cannot rule out aliases
 * such as DOS short names on NTFS, so each absence needs a native lookup. */
#define LOOSE_ENTRIES 256
#define LOOSE_MISSING 64
#define LOOSE_NAME_BYTES 256
typedef struct {
    int attempted, valid;
    unsigned count, missing_count;
    char names[LOOSE_ENTRIES][LOOSE_NAME_BYTES];
    char missing[LOOSE_MISSING][LOOSE_NAME_BYTES];
#if defined(__linux__)
    int descriptor_plus_one;
#elif defined(_WIN32)
    HANDLE notification;
#endif
} loose_context;
static loose_context loose OBOR_RUNTIME;
static pthread_mutex_t loose_mutex OBOR_RUNTIME = PTHREAD_MUTEX_INITIALIZER;
static int loose_dirty OBOR_RUNTIME;
extern DIR *__real_opendir(const char *);
extern int __real_close(int);

static void lock(void) { pthread_mutex_lock(&loose_mutex); }
static void unlock(void) { pthread_mutex_unlock(&loose_mutex); }

static void stop_watch(void)
{
#if defined(__linux__)
    if (loose.descriptor_plus_one) __real_close(loose.descriptor_plus_one - 1);
    loose.descriptor_plus_one = 0;
#elif defined(_WIN32)
    if (loose.notification) FindCloseChangeNotification(loose.notification);
    loose.notification = NULL;
#endif
    loose.valid = 0;
}

void obor_loose_reset(void)
{
    lock(); stop_watch(); memset(&loose, 0, sizeof(loose));
    __atomic_store_n(&loose_dirty, 0, __ATOMIC_RELAXED); unlock();
}

void obor_loose_invalidate(void)
{
    __atomic_store_n(&loose_dirty, 1, __ATOMIC_RELEASE);
}

static int start_watch(const char *root)
{
#if defined(__linux__)
    int fd = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
    if (fd < 0) return 0;
    int watch = inotify_add_watch(fd, root, IN_CREATE | IN_DELETE | IN_ATTRIB |
        IN_MOVED_FROM | IN_MOVED_TO | IN_DELETE_SELF | IN_MOVE_SELF | IN_ONLYDIR);
    if (watch < 0) { __real_close(fd); return 0; }
    loose.descriptor_plus_one = fd + 1;
    return 1;
#elif defined(_WIN32)
    HANDLE watch = FindFirstChangeNotificationA(root, FALSE,
        FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_DIR_NAME | FILE_NOTIFY_CHANGE_ATTRIBUTES);
    if (watch == INVALID_HANDLE_VALUE) return 0;
    loose.notification = watch;
    return 1;
#else
    (void)root;
    return 0;
#endif
}

/* 0 = unchanged, 1 = dirty, -1 = no trustworthy watcher. Consume only a
 * bounded amount per call. Overflow/busy writers force the original lookup;
 * a storm cannot create an unbounded loop in the engine thread. */
static int watch_changes(void)
{
#if defined(__linux__)
    if (!loose.descriptor_plus_one) return -1;
    union { struct inotify_event alignment; char data[8192]; } buffer;
    int dirty = 0;
    for (unsigned batch = 0; batch < 4; ++batch) {
        ssize_t size = read(loose.descriptor_plus_one - 1, buffer.data, sizeof(buffer.data));
        if (size < 0 && errno == EINTR) continue;
        if (size < 0 && errno == EAGAIN) return dirty;
        if (size <= 0) { stop_watch(); return -1; }
        for (size_t at = 0; at < (size_t)size;) {
            if ((size_t)size - at < sizeof(struct inotify_event)) {
                stop_watch(); return -1;
            }
            struct inotify_event *event = (void *)(buffer.data + at);
            if (event->len > (size_t)size - at - sizeof(*event)) {
                stop_watch(); return -1;
            }
            if (event->mask & (IN_IGNORED | IN_UNMOUNT | IN_DELETE_SELF)) {
                stop_watch(); return -1;
            }
            dirty = 1;
            at += sizeof(*event) + event->len;
        }
    }
    stop_watch(); return -1;
#elif defined(_WIN32)
    if (!loose.notification) return -1;
    DWORD status = WaitForSingleObject(loose.notification, 0);
    if (status == WAIT_TIMEOUT) return 0;
    if (status != WAIT_OBJECT_0 || !FindNextChangeNotification(loose.notification)) {
        stop_watch(); return -1;
    }
    return 1;
#else
    return -1;
#endif
}

static int read_names(const char *root)
{
    loose.valid = 0; loose.count = 0; loose.missing_count = 0;
    DIR *directory = __real_opendir(root);
    if (!directory) return 0;
    struct dirent *entry;
    int ok = 1;
    errno = 0;
    while ((entry = readdir(directory))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        size_t length = strlen(entry->d_name);
        if (length >= LOOSE_NAME_BYTES || loose.count == LOOSE_ENTRIES) { ok = 0; break; }
        memcpy(loose.names[loose.count++], entry->d_name, length + 1);
    }
    if (!entry && errno) ok = 0;
    if (closedir(directory)) ok = 0;
    loose.valid = ok;
    return ok;
}

static int equal_component(const char *name, const char *part, size_t length)
{
    for (size_t i = 0; i < length; ++i) {
        unsigned char a = (unsigned char)name[i], b = (unsigned char)part[i];
        if (!a) return 0;
        if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
        if (b >= 'A' && b <= 'Z') b += 'a' - 'A';
        if (a != b) return 0;
    }
    return !name[length];
}

static int native_absent(const char *part)
{
    char mapped[8192];
    const char *path = obor_paths_resolve(part, mapped, sizeof(mapped));
    if (!path) return 0;
#if defined(__linux__)
    struct stat entry;
    /* A dangling symlink is still an entry: do not follow its target. */
    return fstatat(AT_FDCWD, path, &entry, AT_SYMLINK_NOFOLLOW) < 0 && errno == ENOENT;
#elif defined(_WIN32)
    DWORD attributes = GetFileAttributesA(path);
    if (attributes != INVALID_FILE_ATTRIBUTES) return 0;
    DWORD error = GetLastError();
    return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND;
#else
    return 0;
#endif
}

static int may_exist(const char *path)
{
    if (!path) return 1;
    /* Output paths can resolve outside this watched content/session root. */
    if (obor_paths_is_output(path)) return 1;
#if !defined(_WIN32)
    /* A backslash can be a literal filename byte on POSIX; the original
     * engine also has its own separator conversion rules. */
    if (strchr(path, '\\')) return 1;
#endif
    while (path[0] == '.' && (path[1] == '/' || path[1] == '\\')) path += 2;
    size_t length = 0;
    while (path[length] && path[length] != '/' && path[length] != '\\') {
        unsigned char c = (unsigned char)path[length];
        /* The engines' locale-aware case search can match beyond ASCII.
         * Such names and Windows drive names never take a negative proof. */
        if (c >= 128 || c == ':' || ++length >= LOOSE_NAME_BYTES) return 1;
    }
    if (!length || (length == 1 && path[0] == '.') ||
        (length == 2 && path[0] == '.' && path[1] == '.')) return 1;
#if defined(_WIN32)
    /* Leave Win32 device names and trailing-dot/space normalization to the
     * original I/O. In particular NUL need not appear in a directory list. */
    if (!path[length] || path[length - 1] == '.' || path[length - 1] == ' ') return 1;
#endif
    int result = 1;
    lock();
    char mapped[8192];
    const char *root = NULL;
    int dirty = __atomic_exchange_n(&loose_dirty, 0, __ATOMIC_ACQUIRE);
    if (!loose.attempted) {
        loose.attempted = 1;
        if (!obor_paths_notifications_local()) goto done;
        root = obor_paths_resolve(".", mapped, sizeof(mapped));
        /* Inactive context cannot cache the frontend's changing cwd. */
        if (!root || !strcmp(root, ".") || !start_watch(root)) goto done;
        dirty = 1;
    }
    int changed = watch_changes();
    if (changed < 0) goto done;
    if (dirty || changed) {
        if (!root) root = obor_paths_resolve(".", mapped, sizeof(mapped));
        if (!root || !read_names(root)) goto done;
        /* Watch started before enumeration. A concurrent mutation invalidates
         * this sample instead of publishing a potentially stale absence. */
        if (watch_changes() != 0 || __atomic_load_n(&loose_dirty, __ATOMIC_ACQUIRE)) {
            loose.valid = 0; obor_loose_invalidate(); goto done;
        }
    }
    if (!loose.valid) goto done;
    for (unsigned i = 0; i < loose.count; ++i) {
        /* Non-ASCII filesystem names also require the original locale rules. */
        const unsigned char *name = (const unsigned char *)loose.names[i];
        for (unsigned j = 0; name[j]; ++j) if (name[j] >= 128) { result = 1; goto done; }
        if (equal_component(loose.names[i], path, length)) goto done;
    }
    char component[LOOSE_NAME_BYTES];
    memcpy(component, path, length); component[length] = '\0';
    for (unsigned i = 0; i < loose.missing_count; ++i) {
        if (!strcmp(loose.missing[i], component)) { result = 0; goto done; }
    }
    if (loose.missing_count == LOOSE_MISSING || !native_absent(component)) goto done;
    if (watch_changes() != 0 || __atomic_load_n(&loose_dirty, __ATOMIC_ACQUIRE)) {
        loose.valid = 0; obor_loose_invalidate(); goto done;
    }
    memcpy(loose.missing[loose.missing_count++], component, length + 1);
    result = 0;
done:
    unlock();
    return result;
}

int obor_loose_may_exist(const char *path)
{
    int saved_errno = errno;
#if defined(_WIN32)
    DWORD saved_error = GetLastError();
#endif
    int result = may_exist(path);
    errno = saved_errno;
#if defined(_WIN32)
    SetLastError(saved_error);
#endif
    return result;
}
