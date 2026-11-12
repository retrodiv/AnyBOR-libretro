/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_DIRECTORY_WINDOWS_H
#define OBOR_DIRECTORY_WINDOWS_H

#if defined(_WIN32)
#include <direct.h>
#include <errno.h>
#include <string.h>

/* These hooks are used only by the standalone component tests. */
#ifndef OBOR_DIRECTORY_GETCWD
#define OBOR_DIRECTORY_GETCWD _getcwd
#endif
#ifndef OBOR_DIRECTORY_CHDIR
#define OBOR_DIRECTORY_CHDIR _chdir
#endif

typedef struct {
    char previous[4096];
} obor_windows_directory_scope;

static int obor_windows_directory_enter(const char *path,
                                         obor_windows_directory_scope *scope)
{
    scope->previous[0] = '\0';
    if (!path || !path[0]) {
        errno = EINVAL;
        return 0;
    }
    /* Observe the frontend's current directory on every entry. A saved path
     * from the preceding frame is not evidence of the current process cwd. */
    if (!OBOR_DIRECTORY_GETCWD(scope->previous, sizeof(scope->previous)))
        return 0;
    /* Exact equality is sufficient. Do not case-fold, resolve aliases or
     * normalize away distinctions merely to take this fast path. */
    return !strcmp(scope->previous, path) || OBOR_DIRECTORY_CHDIR(path) == 0;
}

static int obor_windows_directory_leave(const obor_windows_directory_scope *scope)
{
    char current[4096];
    if (!scope->previous[0]) {
        errno = EINVAL;
        return 0;
    }
    /* The engine may itself have changed cwd, even if enter skipped chdir.
     * Query it again; on query failure still attempt the required restore. */
    if (OBOR_DIRECTORY_GETCWD(current, sizeof(current)) &&
        !strcmp(current, scope->previous)) return 1;
    return OBOR_DIRECTORY_CHDIR(scope->previous) == 0;
}
#endif
#endif
