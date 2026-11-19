/* AnyBOR modification record: 2026-09-30.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve historical random-result magnitudes through build 4323 and raw
 * results from 4324, with identical generator state and defined unsigned
 * arithmetic.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4432.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2014 OpenBOR Team
 */

#include "rand32.h"
#include <stdint.h>

extern uint32_t obor_profile_build;

u64 seed = 1234567890;

unsigned int rand32(void)
{
    u64 t = seed, tl, tr;

    t *= 1103515245ull;
    t += 12345ull;

    tl = tr = t;
    t = rotr64(t,4);

    // less significative part
    tr = (((~tl)>>16)^(0xAC05)) & 0xFFFF;

    // more significative part
    tl = ((tr&0xFFFF)&0x1234)<<16;
    tl = (tl|tr) & 0xFFFFFFFF;
    tl = rotl64(tl,8);

    t *= tl;

    seed = t;

    /* Earlier profiles return the magnitude of the native 32-bit result.
     * Keep the same generator state and calculate that magnitude unsigned. */
    uint32_t result = (uint32_t)((t >> 16) & UINT32_C(0xffffffff));
    if(obor_profile_build >= 4283 && obor_profile_build < 4324 &&
       result > UINT32_C(0x7fffffff))
    {
        result = UINT32_C(0) - result;
    }

    return (unsigned int)result;
}

void srand32(u64 n)
{
    seed = n;
}

float randf(float max)
{
    float f;

    if(max == 0)
    {
        return 0;
    }
    f = (float)(rand32() % 10000);
    f /= (10000 / max);

    return f;
}

/* --- RAND UTILS --- */

u64 getseed()
{
    return seed;
}

u64 rotl64(u64 n, unsigned int c)
{
  const unsigned int mask = (CHAR_BIT*sizeof(n)-1);

  c &= mask;
  return (n<<c) | (n>>( (-c)&mask ));
}

u64 rotr64(u64 n, unsigned int c)
{
  const unsigned int mask = (CHAR_BIT*sizeof(n)-1);

  c &= mask;
  return (n>>c) | (n<<( (-c)&mask ));
}


