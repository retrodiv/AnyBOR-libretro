/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_BLOCK_CRC_H
#define OBOR_BLOCK_CRC_H
#include <stdint.h>
#include <string.h>
#include <zlib.h>

/* Optional acceleration of the SAME IEEE CRC stored in OBC1. Baseline ARMv8
 * does not require CRC instructions: isolate them in a target function and
 * ask the kernel before each call. No remembered CPU flag enters a state.
 * Other architectures/toolchains retain zlib's implementation. */
#if defined(__linux__) && defined(__aarch64__) && defined(__GNUC__) && \
    !defined(__clang__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define OBOR_BLOCK_ARM_CRC 1
#include <arm_acle.h>
#include <asm/hwcap.h>
#include <sys/auxv.h>

__attribute__((target("+crc"), noinline))
static uint32_t obor_block_crc_arm(uint32_t seed, const unsigned char *bytes, uint32_t length)
{
    uint32_t crc = ~seed;
    while (length >= 8) {
        uint64_t word;
        memcpy(&word, bytes, sizeof(word));
        crc = __crc32d(crc, word);
        bytes += 8; length -= 8;
    }
    while (length--) crc = __crc32b(crc, *bytes++);
    return ~crc;
}
#endif

static uint32_t obor_block_crc32(uint32_t seed, const void *bytes, uint32_t length)
{
    if (!bytes) return 0; /* Preserve zlib's null-buffer initialization rule. */
#if defined(OBOR_BLOCK_ARM_CRC)
    if (getauxval(AT_HWCAP) & HWCAP_CRC32)
        return obor_block_crc_arm(seed, bytes, length);
#endif
    return (uint32_t)crc32(seed, bytes, length);
}
#endif
