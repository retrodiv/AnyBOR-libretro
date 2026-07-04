/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* token -> minimum engine build that defines it (lower bound).
 * 5 entries. */
typedef struct { const char *tok; int build; } obor_marker;
static const obor_marker kMarkers[] = {
};
/* tokens that DISAPPEARED from the engine after this build: a pak
 * using one very likely targets <= that era (upper bound). */
static const obor_marker kRemovedMarkers[] = {
    { "changebglayerproperty", 3400 },
    { "changefglayerproperty", 3400 },
    { "getbglayerproperty", 3400 },
    { "getfglayerproperty", 3400 },
    { "weaponum", 3400 },
};
