/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PORT_DIRENT_H
#define OBOR_PORT_DIRENT_H
#ifdef _WIN32
#include "anybor_win_directory.h"

typedef obor_path_directory DIR;
#define dirent obor_path_entry

/* The engine linker redirects these functions to the session-path wrappers. */
DIR *opendir(const char *path);
struct dirent *readdir(DIR *directory);
int closedir(DIR *directory);
#else
#include_next <dirent.h>
#endif
#endif
