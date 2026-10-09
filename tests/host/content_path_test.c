/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail_allocate;
static void *test_allocate(size_t n) { return fail_allocate ? NULL : malloc(n); }
#define malloc test_allocate
#include "obor_content_path.h"
#undef malloc
static char *copy(const char *s)
{
    char *p = malloc(strlen(s)+1); assert(p); strcpy(p,s); return p;
}
int main(void)
{
    const char *first = "/session-one/prepared/content.pak";
    const char *second = "/a-longer-session-two/prepared/content.pak";
    const char *third = "/third/content.pak";
    char *sound = copy(first), *handle = copy(first);
    char *other = copy("/session-one/prepared/content.pak.extra");
    char *basename = copy("/other/content.pak"), *empty = NULL;
    char *before = sound;
    fail_allocate = 1;
    assert(obor_content_path_rebind(&sound,first,first) && sound==before);
    assert(!obor_content_path_rebind(&sound,first,second) && sound==before);
    assert(!strcmp(sound,first));
    assert(obor_content_path_rebind(&other,first,second));
    assert(obor_content_path_rebind(&basename,first,second));
    assert(obor_content_path_rebind(&empty,first,second) && !empty);
    fail_allocate = 0;
    assert(obor_content_path_rebind(&sound,first,second));
    assert(obor_content_path_rebind(&handle,first,second));
    assert(sound!=handle && !strcmp(sound,second) && !strcmp(handle,second));
    /* A second cold save/load must not retain aliases to either old session. */
    assert(obor_content_path_rebind(&sound,second,third));
    assert(obor_content_path_rebind(&handle,second,third));
    assert(!strcmp(sound,third) && !strcmp(handle,third));
    assert(!strcmp(other,"/session-one/prepared/content.pak.extra"));
    assert(!strcmp(basename,"/other/content.pak"));
    assert(!obor_content_path_rebind(NULL,first,second));
    assert(!obor_content_path_rebind(&sound,NULL,second));
    assert(!obor_content_path_rebind(&sound,first,NULL));
    free(sound); free(handle); free(other); free(basename);
    puts("cold_path_rebind=1 repeated_session=1 unrelated_paths_preserved=1 allocation_failure=1");
    return 0;
}
