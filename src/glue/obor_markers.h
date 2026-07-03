/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* token -> minimum engine build that defines it (lower bound).
 * 0 entries. */
typedef struct { const char *tok; int build; } obor_marker;
static const obor_marker kMarkers[] = {
};
/* tokens that DISAPPEARED from the engine after this build: a pak
 * using one very likely targets <= that era (upper bound). */
static const obor_marker kRemovedMarkers[] = {
};
