/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "obor_paths.h"
#include "obor_loose.h"
#include "obor_runtime.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <sys/stat.h>
#if defined(_WIN32)
#include <windows.h>
#elif defined(__linux__)
#include <linux/magic.h>
#include <sys/vfs.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#else
#include <unistd.h>
#endif

extern int __real_close(int);
extern char savesDir[], logsDir[], screenShotsDir[];
typedef struct {
    char root[4096];
    int local_notifications;
#if defined(_WIN32)
    HANDLE directory;
#else
    int descriptor_plus_one;
#if defined(__linux__)
    char proc_root[64];
#endif
#endif
} obor_path_context;
static obor_path_context paths OBOR_RUNTIME;

int obor_paths_notifications_local(void) { return paths.local_notifications; }

#if defined(__linux__)
static int notifications_local(int fd)
{
    struct statfs filesystem;
    if (fstatfs(fd, &filesystem)) return 0;
    switch ((uint32_t)filesystem.f_type) {
    case EXT2_SUPER_MAGIC: case TMPFS_MAGIC: case BTRFS_SUPER_MAGIC:
    case XFS_SUPER_MAGIC: case F2FS_SUPER_MAGIC: case OVERLAYFS_SUPER_MAGIC:
    case MSDOS_SUPER_MAGIC:
        return 1;
    case FUSE_SUPER_MAGIC: {
        /* fuseblk has a local block filesystem (e.g. NTFS/exFAT). Do not
         * assume a generic FUSE daemon or remote filesystem reports changes
         * made outside this kernel: an accepted inotify watch isn't proof. */
        struct stat st;
        if (fstat(fd, &st)) return 0;
        extern FILE *__real_fopen(const char *, const char *);
        extern int __real_fclose(FILE *);
        FILE *mounts = __real_fopen("/proc/self/mountinfo", "r");
        if (!mounts) return 0;
        char line[8192]; size_t bytes = 0; int local = 0;
        while (fgets(line, sizeof(line), mounts) && (bytes += strlen(line)) <= 262144) {
            unsigned major_id, minor_id;
            if (!strchr(line, '\n')) break;
            if (sscanf(line, "%*u %*u %u:%u", &major_id, &minor_id) == 2 &&
                major_id == major(st.st_dev) && minor_id == minor(st.st_dev) &&
                strstr(line, " - fuseblk ")) { local = 1; break; }
        }
        __real_fclose(mounts);
        return local;
    }
    default:
        /* In particular NFS, SMB and WSL drvfs/9p can change without a
         * notification here. Keep their original lookup semantics. */
        return 0;
    }
}
#endif

void obor_paths_clear(void)
{
    obor_loose_reset();
#if defined(_WIN32)
    if (paths.directory) CloseHandle(paths.directory);
#else
    if (paths.descriptor_plus_one) __real_close(paths.descriptor_plus_one - 1);
#endif
    memset(&paths, 0, sizeof(paths));
}

int obor_paths_set_root(const char *path)
{
    size_t length = path ? strnlen(path, sizeof(paths.root)) : 0;
    if (!length || length == sizeof(paths.root)) {
        errno = length ? ENAMETOOLONG : EINVAL;
        return 0;
    }
    if (!strcmp(paths.root, path)) return 1;
    obor_path_context next = {0};
#if defined(_WIN32)
    if (!((path[0] && path[1] == ':' && (path[2] == '/' || path[2] == '\\')) ||
          (path[0] == '\\' && path[1] == '\\'))) { errno = EINVAL; return 0; }
    next.directory = CreateFileA(path, 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
        OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    if (next.directory == INVALID_HANDLE_VALUE) { errno = EACCES; return 0; }
    BY_HANDLE_FILE_INFORMATION information;
    if (!GetFileInformationByHandle(next.directory, &information) ||
        !(information.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
        CloseHandle(next.directory); errno = ENOTDIR; return 0;
    }
    char volume[4096];
    if (GetVolumePathNameA(path, volume, sizeof(volume))) {
        UINT type = GetDriveTypeA(volume);
        next.local_notifications = type == DRIVE_FIXED || type == DRIVE_REMOVABLE || type == DRIVE_RAMDISK;
    }
#else
    if (path[0] != '/') { errno = EINVAL; return 0; }
#if defined(__linux__)
    int fd = openat(AT_FDCWD, path, O_PATH | O_DIRECTORY | O_CLOEXEC);
#else
    extern int __real_open(const char *, int, ...);
    int fd = __real_open(path, O_EVTONLY | O_CLOEXEC);
#endif
    if (fd < 0) return 0;
    next.descriptor_plus_one = fd + 1;
#if defined(__linux__)
    next.local_notifications = notifications_local(fd);
    /* Verify the magic-link provider once. Following this fd for a real I/O
     * keeps directory identity across renames without fchdir/fstat per frame. */
    int proc = openat(AT_FDCWD, "/proc/self/fd", O_PATH | O_DIRECTORY | O_CLOEXEC);
    if (proc >= 0) {
        struct statfs filesystem;
        if (!fstatfs(proc, &filesystem) && filesystem.f_type == PROC_SUPER_MAGIC)
            snprintf(next.proc_root, sizeof(next.proc_root), "/proc/self/fd/%d", fd);
        __real_close(proc);
    }
#endif
#endif
    memcpy(next.root, path, length + 1);
    obor_paths_clear();
    paths = next;
    return 1;
}

static const char *resolve_root(const char *path, char *out, size_t capacity)
{
    if (!path) { errno = EINVAL; return NULL; }
    if (!paths.root[0] || !path[0]) return path;
    const char *root = paths.root;
#if defined(_WIN32)
    if (((path[0] == '\\' || path[0] == '/') &&
         (path[1] == '\\' || path[1] == '/')) ||
        (path[1] == ':' && (path[2] == '\\' || path[2] == '/'))) return path;
    char live_root[4096];
    DWORD length = GetFinalPathNameByHandleA(paths.directory, live_root,
        sizeof(live_root), FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    if (!length || length >= sizeof(live_root)) {
        errno = length ? ENAMETOOLONG : ENOENT; return NULL;
    }
    root = live_root;
    /* Keep the CRT's ordinary drive spelling when possible. UNC and extended
     * paths remain absolute. Root-relative and drive-relative names follow
     * the engine's drive, rather than the frontend's current drive. */
    if (!strncmp(root, "\\\\?\\", 4) && root[4] && root[5] == ':') root += 4;
    char volume_root[4096];
    if (path[0] == '/' || path[0] == '\\') {
        size_t size;
        if (root[1] == ':') size = 2;
        else {
            /* A root-relative name in a UNC session belongs to its share,
             * not the frontend's drive. Keep extended UNC spelling intact. */
            const char *server = !strncmp(root, "\\\\?\\UNC\\", 8) ? root + 8 :
                !strncmp(root, "\\\\", 2) ? root + 2 : NULL;
            const char *share = server ? strpbrk(server, "/\\") : NULL;
            if (!share || share == server || !share[1]) { errno = EINVAL; return NULL; }
            const char *end = strpbrk(share + 1, "/\\");
            size = end ? (size_t)(end - root) : strlen(root);
        }
        if (size >= sizeof(volume_root)) { errno = ENAMETOOLONG; return NULL; }
        memcpy(volume_root, root, size); volume_root[size] = '\0'; root = volume_root;
    } else if (path[1] == ':') {
        if ((path[0] | 32) != (root[0] | 32) || root[1] != ':') return path;
        path += 2;
    }
#else
    if (path[0] == '/') return path;
#if defined(__linux__)
    if (paths.proc_root[0]) root = paths.proc_root;
    else {
        /* No procfs: resolve only real I/O through the remembered pathname,
         * and reject a replaced/renamed root rather than address another
         * directory. There is still no work on entering an engine frame. */
        struct stat live, named;
        if (fstat(paths.descriptor_plus_one - 1, &live) ||
            fstatat(AT_FDCWD, root, &named, 0)) return NULL;
        if (live.st_dev != named.st_dev || live.st_ino != named.st_ino) {
            errno = ESTALE; return NULL;
        }
    }
#elif defined(__APPLE__)
    char live_root[4096];
    if (fcntl(paths.descriptor_plus_one - 1, F_GETPATH, live_root) < 0) return NULL;
    root = live_root;
#endif
#endif
    int n = snprintf(out, capacity, "%s/%s", root, path);
    if (n < 0 || (size_t)n >= capacity) { errno = ENAMETOOLONG; return NULL; }
    return out;
}

static int output_prefix(const char *path, const char **tail)
{
    static const char *const names[] = { "saves", "logs", "screenshots" };
    if (!path) return -1;
    while (path[0] == '.' && (path[1] == '/' || path[1] == '\\')) path += 2;
    for (unsigned i = 0; i < 3; ++i) {
        size_t j = 0;
        while (names[i][j] && path[j]) {
            unsigned char c = (unsigned char)path[j];
            if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
            if (c != names[i][j]) break;
            ++j;
        }
        if (names[i][j] || (path[j] && path[j] != '/' && path[j] != '\\')) continue;
        if (tail) *tail = path + j + (path[j] != '\0');
        return (int)i;
    }
    return -1;
}

int obor_paths_is_output(const char *path) { return output_prefix(path, NULL) >= 0; }

const char *obor_paths_resolve(const char *path, char *out, size_t capacity)
{
    /* Legacy engines create/check output directories before opening files.
     * Apply one policy to all I/O, including reads: bundled settings belong
     * to a different runner layout and must not leak into this session. */
    const char *tail = NULL;
    int index = output_prefix(path, &tail);
    const char *roots[] = { savesDir, logsDir, screenShotsDir };
    if (index < 0 || !roots[index][0]) return resolve_root(path, out, capacity);
    char redirected[8192];
    int size = snprintf(redirected, sizeof(redirected), "%s%s%s", roots[index],
                        *tail ? "/" : "", tail);
    if (size < 0 || (size_t)size >= sizeof(redirected)) { errno = ENAMETOOLONG; return NULL; }
    for (char *p = redirected; *p; ++p) if (*p == '\\') *p = '/';
    const char *resolved = resolve_root(redirected, out, capacity);
    if (resolved != redirected) return resolved;
    /* An absolute output path passes through resolve_root; its temporary
     * buffer must not escape this call. */
    if ((size_t)size >= capacity) { errno = ENAMETOOLONG; return NULL; }
    memcpy(out, redirected, (size_t)size + 1);
    return out;
}
