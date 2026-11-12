/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LOOSE_H
#define OBOR_LOOSE_H

/* Conservative first-component proof for a loose asset lookup. Zero means
 * the watched session root has no such entry, even ignoring ASCII case.
 * One means use the engine's original lookup, not that the file exists. */
int obor_loose_may_exist(const char *path);
void obor_loose_invalidate(void);
void obor_loose_reset(void);

#endif
