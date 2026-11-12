/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Fixed-width byte-order helpers for the OpenBOR interfaces. */
#ifndef OBOR_ENDIAN_H
#define OBOR_ENDIAN_H
#include <stdint.h>
typedef int8_t SInt8;
typedef uint8_t UInt8;
typedef int16_t SInt16;
typedef uint16_t UInt16;
typedef int32_t SInt32;
typedef uint32_t UInt32;
typedef int64_t SInt64;
typedef uint64_t UInt64;
static inline UInt16 Swap16(UInt16 x)
{ return (UInt16)((x >> 8) | ((UInt16)(x & 255u) << 8)); }
static inline UInt32 Swap32(UInt32 x)
{
    return ((x & UINT32_C(0xff)) << 24) | ((x & UINT32_C(0xff00)) << 8) |
           ((x >> 8) & UINT32_C(0xff00)) | (x >> 24);
}
static inline UInt64 Swap64(UInt64 x)
{ return ((UInt64)Swap32((UInt32)x) << 32) | Swap32((UInt32)(x >> 32)); }
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
#ifndef BOR_BIG_ENDIAN
#define BOR_BIG_ENDIAN
#endif
#endif
#ifdef BOR_BIG_ENDIAN
#define SwapLSB16(x) Swap16(x)
#define SwapLSB32(x) Swap32(x)
#define SwapLSB64(x) Swap64(x)
#define SwapMSB16(x) ((UInt16)(x))
#define SwapMSB32(x) ((UInt32)(x))
#define SwapMSB64(x) ((UInt64)(x))
#else
#define SwapLSB16(x) ((UInt16)(x))
#define SwapLSB32(x) ((UInt32)(x))
#define SwapLSB64(x) ((UInt64)(x))
#define SwapMSB16(x) Swap16(x)
#define SwapMSB32(x) Swap32(x)
#define SwapMSB64(x) Swap64(x)
#endif
#endif
