/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CONTENT_PATH_H
#define OBOR_CONTENT_PATH_H
#include <stdlib.h>
#include <string.h>

/* Engines identify their separately owned copies of the content path. An
 * exact reference to the saved session's content becomes a reference to the
 * current session's equivalent content. Other packages and loose files keep
 * their own identity; basename or prefix matches are deliberately insufficient.
 * Each slot owns its allocation, as required by the engine's normal teardown.
 * Allocation failure preserves that slot and makes restoration fail. */
static int obor_content_path_rebind(char **owned, const char *saved,
                                    const char *current)
{
    if (!owned || !saved || !current) return 0;
    if (!*owned || !strcmp(saved, current) || strcmp(*owned, saved)) return 1;
    size_t length = strlen(current) + 1;
    char *replacement = malloc(length);
    if (!replacement) return 0;
    memcpy(replacement, current, length);
    free(*owned);
    *owned = replacement;
    return 1;
}
#endif
