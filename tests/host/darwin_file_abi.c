/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_paths.h"
#include <assert.h>
#include <stdint.h>

char savesDir[4096] = "Saves", logsDir[4096] = "Logs";
char screenShotsDir[4096] = "ScreenShots";
void (*obor_resource_event)(uint32_t, uintptr_t);
int provider_abi_correct(void);

/* The runner inserts the exact current obor_make_dir() implementation here. */
/* ANYBOR_DIRECTORY_HELPER */

int main(int argc, char **argv)
{
    assert(argc == 2);
    char before[4096], after[4096];
    assert(getcwd(before, sizeof(before)));
    assert(obor_make_dir(argv[1]));
    /* As at engine boot, the frontend has already created this root. */
    assert(obor_make_dir(argv[1]));
    assert(obor_paths_set_root(argv[1]));
    assert(obor_make_dir("Saves"));
    assert(obor_make_dir("Saves"));
    FILE *file = fopen("Saves/session", "wb");
    assert(file); assert(fputs("session", file) >= 0); assert(!fclose(file));
    DIR *directory = opendir("Saves");
    assert(directory);
    struct dirent *entry;
    int found = 0;
    while ((entry = readdir(directory))) if (!strcmp(entry->d_name, "session")) found = 1;
    assert(found); assert(!closedir(directory));
    struct stat status;
    assert(!stat("Saves", &status) && S_ISDIR(status.st_mode));
    assert(provider_abi_correct());
    assert(getcwd(after, sizeof(after)) && !strcmp(before, after));
    obor_paths_clear();
    puts("SDK-selected stat/directory ABI, existing save root and relative I/O: OK");
    return 0;
}
