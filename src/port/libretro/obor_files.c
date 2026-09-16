/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdio.h>
#include <string.h>
#include <errno.h>

extern char savesDir[], logsDir[], screenShotsDir[];
extern FILE *__real_fopen(const char *, const char *);

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
        return __real_fopen(mapped, mode);
    }
    return __real_fopen(path, mode);
}
