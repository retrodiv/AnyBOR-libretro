/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_BUILD_IDENTITY_H
#define OBOR_BUILD_IDENTITY_H
#include <stdint.h>

/* The builder fills bytes 32..63 after the final strip/normalization step,
 * before Android embedding or platform signing. Never use a version string
 * as a promise that saved instruction/data pointers have the same layout. */
static const unsigned char obor_build_stamp[64] __attribute__((used)) =
    "AnyBOR-state-build-identity-v1";

static int obor_build_identity_read(uint8_t out[32])
{
    /* Volatile access prevents constant folding of the linked placeholder.
     * The object itself is const and remains in the read-only image. */
    const volatile unsigned char *source = obor_build_stamp + 32;
    unsigned present = 0;
    for (unsigned i = 0; i < 32; ++i) {
        out[i] = source[i];
        present |= out[i];
    }
    return present != 0;
}
#endif
