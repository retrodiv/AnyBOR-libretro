/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PATHS_H
#define OBOR_PATHS_H
#include <stddef.h>

/* Per-engine live filesystem context. Never serialized, and never changes
 * the frontend's process cwd. Rebinding the same session is a memory-only
 * operation, including during rewind. Call set/clear with workers stopped. */
int obor_paths_set_root(const char *path);
void obor_paths_clear(void);
const char *obor_paths_resolve(const char *path, char *out, size_t capacity);
int obor_paths_notifications_local(void);
/* Reserved mutable-output prefixes are resolved outside an unpacked mod. */
int obor_paths_is_output(const char *path);

#endif
