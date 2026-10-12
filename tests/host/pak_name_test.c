/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_pak_name.h"
#include <assert.h>
#include <stdio.h>

int main(void)
{
    static const char *suffixes[] = {".sav", ".hi", ".scr", ".inp", ".cfg", ".controls"};
    char path[4096], result[128], expected[128], joined[128];
    /* Includes POSIX, drive and UNC separators and a parent much longer than
     * the former256byte temporary, with the same short archive basename. */
    memset(path, 'd', sizeof(path));
    memcpy(path, "\\\\server\\share\\", 15);
    path[sizeof(path)-30] = '/';
    strcpy(path + sizeof(path)-29, "fixture.pak");
    for (int type = 0; type < 6; ++type) {
        snprintf(expected, sizeof(expected), "fixture%s", suffixes[type]);
        assert(obor_pak_name(result, sizeof(result), path, type));
        assert(!strcmp(result, expected));
        assert(obor_pak_name(result, strlen(expected)+1, "C:\\data\\fixture.pak", type));
        assert(!strcmp(result, expected));
        result[strlen(expected)] = 'G';
        assert(!obor_pak_name(result, strlen(expected), path, type));
        assert(result[0] == 0 && result[strlen(expected)] == 'G');
    }
    assert(obor_pak_name(result, sizeof(result), "fixture.pak", -1));
    assert(!strcmp(result, "fixture"));
    assert(obor_pak_name(result, sizeof(result), "/root/fixture.PAK", 99));
    assert(!strcmp(result, "fixture"));
    assert(obor_pak_name(result, sizeof(result), "x", 4));
    assert(!strcmp(result, "x.cfg"));
    assert(!obor_pak_name(result, sizeof(result), "", 0));
    assert(!obor_pak_name(result, sizeof(result), "/root/", 0));
    assert(!obor_pak_name(result, sizeof(result), ".pak", 0));
    assert(!obor_pak_name(result, 0, "fixture.pak", 0));
    assert(!obor_pak_name(NULL, 0, "fixture.pak", 0));
    memset(path, 'x', 300); strcpy(path + 300, ".pak");
    assert(!obor_pak_name(result, sizeof(result), path, 4));
    strcpy(joined, "Saves/");
    assert(obor_pak_path_append(joined, sizeof(joined), "fixture.cfg"));
    assert(!strcmp(joined, "Saves/fixture.cfg"));
    strcpy(result, joined);
    assert(!obor_pak_path_append(joined, strlen(joined)+1, "x"));
    assert(!strcmp(joined, result));
    memset(joined, 'x', sizeof(joined));
    assert(!obor_pak_path_append(joined, sizeof(joined), "x"));
    assert(joined[127] == 'x');
    puts("long_parent=1 extensions=1 exact_capacity=1 rejection=1 bounded_join=1");
    return 0;
}
