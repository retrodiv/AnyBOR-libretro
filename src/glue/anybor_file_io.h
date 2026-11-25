/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_FILE_IO_H
#define OBOR_FILE_IO_H

/* Paths inside the core are UTF-8. Convert at the Windows filesystem boundary. */
#include <stdio.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#include <errno.h>
#include <fcntl.h>
#include <io.h>
#include <stdarg.h>
#include <stdlib.h>
#include <windows.h>
#include "anybor_win_directory.h"

#define OBOR_WIN_PATH_CAP 8192

static inline int obor_win_path_error(DWORD error)
{
    switch (error) {
    case ERROR_FILE_NOT_FOUND:
    case ERROR_PATH_NOT_FOUND:
        return ENOENT;
    case ERROR_DIRECTORY:
        return ENOTDIR;
    case ERROR_INSUFFICIENT_BUFFER:
    case ERROR_FILENAME_EXCED_RANGE:
        return ENAMETOOLONG;
    case ERROR_NO_UNICODE_TRANSLATION:
        return EILSEQ;
    case ERROR_INVALID_PARAMETER:
    case ERROR_INVALID_NAME:
        return EINVAL;
    default:
        return EACCES;
    }
}

static inline int obor_win_wide(const char *text, wchar_t *out, int capacity)
{
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, out, capacity);
    if (!length) errno = obor_win_path_error(GetLastError());
    return length;
}

static inline int obor_win_utf8(const wchar_t *text, char *out, int capacity)
{
    int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, -1,
                                    out, capacity, NULL, NULL);
    if (!length) errno = obor_win_path_error(GetLastError());
    return length;
}

static inline FILE *obor_fopen(const char *path, const char *mode)
{
    wchar_t name[OBOR_WIN_PATH_CAP], flags[32];
    if (!obor_win_wide(path, name, OBOR_WIN_PATH_CAP) || !obor_win_wide(mode, flags, 32))
        return NULL;
    return _wfopen(name, flags);
}

static inline int obor_open(const char *path, int flags, ...)
{
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, int);
        va_end(args);
    }
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wopen(name, flags, mode) : -1;
}

static inline int obor_stat(const char *path, struct stat *status)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? wstat(name, status) : -1;
}

static inline int obor_win_stat64(const char *path, struct _stat64 *status)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wstat64(name, status) : -1;
}

static inline int obor_remove(const char *path)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wremove(name) : -1;
}

static inline int obor_rmdir(const char *path)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wrmdir(name) : -1;
}

static inline int obor_mkdir(const char *path, int mode)
{
    (void)mode;
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wmkdir(name) : -1;
}

static inline int obor_rename(const char *from, const char *to)
{
    wchar_t old_name[OBOR_WIN_PATH_CAP], new_name[OBOR_WIN_PATH_CAP];
    if (!obor_win_wide(from, old_name, OBOR_WIN_PATH_CAP) ||
        !obor_win_wide(to, new_name, OBOR_WIN_PATH_CAP))
        return -1;
    return _wrename(old_name, new_name);
}

static inline char *obor_getcwd(char *path, int capacity)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return _wgetcwd(name, OBOR_WIN_PATH_CAP) && obor_win_utf8(name, path, capacity) ?
        path : NULL;
}

static inline int obor_chdir(const char *path)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ? _wchdir(name) : -1;
}

static inline DWORD obor_win_attributes(const char *path)
{
    wchar_t name[OBOR_WIN_PATH_CAP];
    return obor_win_wide(path, name, OBOR_WIN_PATH_CAP) ?
        GetFileAttributesW(name) : INVALID_FILE_ATTRIBUTES;
}

static inline int obor_win_absolute(const char *path, char *out, int capacity)
{
    wchar_t input[OBOR_WIN_PATH_CAP], absolute[OBOR_WIN_PATH_CAP];
    if (!obor_win_wide(path, input, OBOR_WIN_PATH_CAP)) return 0;
    DWORD size = GetFullPathNameW(input, OBOR_WIN_PATH_CAP, absolute, NULL);
    return size && size < OBOR_WIN_PATH_CAP && obor_win_utf8(absolute, out, capacity);
}

struct obor_path_directory {
    HANDLE handle;
    WIN32_FIND_DATAW data;
    int first;
    obor_path_entry entry;
};

static inline obor_path_directory *obor_opendir(const char *path)
{
    wchar_t pattern[OBOR_WIN_PATH_CAP];
    int length = obor_win_wide(path, pattern, OBOR_WIN_PATH_CAP - 2) - 1;
    if (length <= 0) {
        if (length == 0) errno = ENOENT;
        return NULL;
    }
    DWORD attributes = GetFileAttributesW(pattern);
    if (attributes == INVALID_FILE_ATTRIBUTES || !(attributes & FILE_ATTRIBUTE_DIRECTORY)) {
        errno = attributes == INVALID_FILE_ATTRIBUTES ? obor_win_path_error(GetLastError()) : ENOTDIR;
        return NULL;
    }
    if (pattern[length - 1] != L'/' && pattern[length - 1] != L'\\' &&
        !(length == 2 && pattern[1] == L':'))
        pattern[length++] = L'\\';
    pattern[length++] = L'*';
    pattern[length] = 0;
    obor_path_directory *dir = (obor_path_directory *)malloc(sizeof(*dir));
    if (!dir) return NULL;
    dir->handle = FindFirstFileW(pattern, &dir->data);
    dir->first = 1;
    if (dir->handle == INVALID_HANDLE_VALUE && GetLastError() != ERROR_FILE_NOT_FOUND) {
        errno = obor_win_path_error(GetLastError());
        free(dir);
        return NULL;
    }
    return dir;
}

static inline obor_path_entry *obor_readdir(obor_path_directory *dir)
{
    if (dir->handle == INVALID_HANDLE_VALUE) return NULL;
    if (!dir->first && !FindNextFileW(dir->handle, &dir->data)) {
        DWORD error = GetLastError();
        if (error != ERROR_NO_MORE_FILES) errno = obor_win_path_error(error);
        return NULL;
    }
    dir->first = 0;
    if (!obor_win_utf8(dir->data.cFileName, dir->entry.d_name, sizeof(dir->entry.d_name)))
        return NULL;
    dir->entry.attributes = dir->data.dwFileAttributes;
    return &dir->entry;
}

static inline int obor_closedir(obor_path_directory *dir)
{
    BOOL ok = dir->handle == INVALID_HANDLE_VALUE || FindClose(dir->handle);
    if (!ok) errno = obor_win_path_error(GetLastError());
    free(dir);
    return ok ? 0 : -1;
}

#else
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>

typedef DIR obor_path_directory;
typedef struct dirent obor_path_entry;
#define obor_fopen fopen
#define obor_open open
#define obor_stat stat
#define obor_remove remove
#define obor_rmdir rmdir
#define obor_mkdir mkdir
#define obor_rename rename
#define obor_getcwd getcwd
#define obor_chdir chdir
#define obor_opendir opendir
#define obor_readdir readdir
#define obor_closedir closedir
#endif
#endif
