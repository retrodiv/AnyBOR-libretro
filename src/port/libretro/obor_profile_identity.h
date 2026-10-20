/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PROFILE_IDENTITY_H
#define OBOR_PROFILE_IDENTITY_H

#include "obor_sha256.h"

#define OBOR_PROFILE_KEY_CAPACITY 48u

/* A profile key is one bounded filename component. This checks storage
 * safety; the generated profile table defines which keys actually exist. */
static inline size_t obor_profile_key_length(const char *key)
{
    if (!key) return 0;
    for (size_t i = 0; i < OBOR_PROFILE_KEY_CAPACITY; ++i) {
        unsigned char c = (unsigned char)key[i];
        if (!c) return i;
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') ||
              (c >= 'A' && c <= 'Z') || c == '-' || c == '_')) return 0;
    }
    return 0;
}

/* Bind a snapshot to its linked module and selected profile. This digest is
 * an identity guard only; it never selects compatibility from content. The
 * fixed-width fields use little endian independently of the host ABI. */
static inline int obor_profile_state_identity(const uint8_t binary[32],
                                              uint32_t build, uint32_t features,
                                              const char *key, uint8_t out[32])
{
    static const unsigned char domain[] = "AnyBOR state profile identity";
    size_t length = obor_profile_key_length(key);
    if (!binary || !out || !build || !length) return 0;
    uint32_t fields[3] = {build, features, (uint32_t)length};
    uint8_t encoded[12];
    for (unsigned i = 0; i < 3; ++i)
        for (unsigned j = 0; j < 4; ++j)
            encoded[i * 4 + j] = (uint8_t)(fields[i] >> (8 * j));
    obor_sha256_ctx hash;
    obor_sha256_init(&hash);
    obor_sha256_update(&hash, domain, sizeof(domain));
    obor_sha256_update(&hash, binary, 32);
    obor_sha256_update(&hash, encoded, sizeof(encoded));
    obor_sha256_update(&hash, key, length);
    obor_sha256_final(&hash, out);
    return 1;
}

#endif
