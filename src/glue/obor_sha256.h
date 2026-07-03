/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* Small streaming SHA-256 implementation used only to key extracted ZIPs.
 * It has no allocation and no dependency on platform crypto libraries. */
#ifndef OBOR_SHA256_H
#define OBOR_SHA256_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    uint32_t h[8];
    uint64_t bits;
    uint8_t block[64];
    size_t used;
} obor_sha256_ctx;

static uint32_t obor_sha_rotr(uint32_t x, unsigned n)
{
    return (x >> n) | (x << (32 - n));
}

static void obor_sha256_transform(obor_sha256_ctx *c, const uint8_t *p)
{
    static const uint32_t k[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    uint32_t w[64], a, b, d, e, f, g, h, t1, t2;
    uint32_t cc;
    for (unsigned i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[i * 4] << 24) | ((uint32_t)p[i * 4 + 1] << 16) |
               ((uint32_t)p[i * 4 + 2] << 8) | p[i * 4 + 3];
    for (unsigned i = 16; i < 64; i++) {
        uint32_t s0 = obor_sha_rotr(w[i - 15], 7) ^
                      obor_sha_rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = obor_sha_rotr(w[i - 2], 17) ^
                      obor_sha_rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = c->h[0]; b = c->h[1]; cc = c->h[2]; d = c->h[3];
    e = c->h[4]; f = c->h[5]; g = c->h[6]; h = c->h[7];
    for (unsigned i = 0; i < 64; i++) {
        uint32_t s1 = obor_sha_rotr(e, 6) ^ obor_sha_rotr(e, 11) ^ obor_sha_rotr(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        t1 = h + s1 + ch + k[i] + w[i];
        uint32_t s0 = obor_sha_rotr(a, 2) ^ obor_sha_rotr(a, 13) ^ obor_sha_rotr(a, 22);
        uint32_t maj = (a & b) ^ (a & cc) ^ (b & cc);
        t2 = s0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = cc; cc = b; b = a; a = t1 + t2;
    }
    c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d;
    c->h[4] += e; c->h[5] += f; c->h[6] += g; c->h[7] += h;
}

static void obor_sha256_init(obor_sha256_ctx *c)
{
    static const uint32_t init[8] = {
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    };
    memcpy(c->h, init, sizeof(init));
    c->bits = 0;
    c->used = 0;
}

static void obor_sha256_update(obor_sha256_ctx *c, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    c->bits += (uint64_t)len * 8;
    while (len) {
        size_t take = 64 - c->used;
        if (take > len) take = len;
        memcpy(c->block + c->used, p, take);
        c->used += take; p += take; len -= take;
        if (c->used == 64) {
            obor_sha256_transform(c, c->block);
            c->used = 0;
        }
    }
}

static void obor_sha256_final(obor_sha256_ctx *c, uint8_t out[32])
{
    c->block[c->used++] = 0x80;
    if (c->used > 56) {
        memset(c->block + c->used, 0, 64 - c->used);
        obor_sha256_transform(c, c->block);
        c->used = 0;
    }
    memset(c->block + c->used, 0, 56 - c->used);
    for (unsigned i = 0; i < 8; i++)
        c->block[63 - i] = (uint8_t)(c->bits >> (i * 8));
    obor_sha256_transform(c, c->block);
    for (unsigned i = 0; i < 8; i++) {
        out[i * 4] = (uint8_t)(c->h[i] >> 24);
        out[i * 4 + 1] = (uint8_t)(c->h[i] >> 16);
        out[i * 4 + 2] = (uint8_t)(c->h[i] >> 8);
        out[i * 4 + 3] = (uint8_t)c->h[i];
    }
}

static int obor_sha256_file(const char *path, char hex[65])
{
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    obor_sha256_ctx c;
    uint8_t buf[64 * 1024], digest[32];
    obor_sha256_init(&c);
    for (;;) {
        size_t n = fread(buf, 1, sizeof(buf), f);
        if (n) obor_sha256_update(&c, buf, n);
        if (n != sizeof(buf)) {
            if (ferror(f)) { fclose(f); return 0; }
            break;
        }
    }
    fclose(f);
    obor_sha256_final(&c, digest);
    for (unsigned i = 0; i < 32; i++)
        snprintf(hex + i * 2, 3, "%02x", digest[i]);
    hex[64] = '\0';
    return 1;
}

#endif
