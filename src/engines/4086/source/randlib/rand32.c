/* AnyBOR modification record: 2026-11-08.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve each profile's native generator, seed initialization and
 * unsigned-long storage, including clock-based libc seeding and engine-owned
 * libc random state.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
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
#include "types.h"
#include <time.h>
#include "libretroport.h"

unsigned long seed = 1234567890;
static int obor_rand32_profile_ready;

static int obor_rand32_uses_libc(void)
{
    return obor_profile_build >= 4081 && obor_profile_build < 4084;
}

static void obor_rand32_prepare(void)
{
    if(!obor_rand32_profile_ready)
    {
        if(obor_rand32_uses_libc()) seed = 0;
        obor_rand32_profile_ready = 1;
    }
}


unsigned int rand32(void)
{
    obor_rand32_prepare();
    if(obor_rand32_uses_libc())
    {
        if(!seed) srand32((unsigned long)time(NULL));
        return (unsigned int)obor_rand();
    }
    u64 t = seed;
    t *= 1103515245ull;
    t += 12345ull;
    seed = t;
    return (t >> 16) & 0xFFFFFFFF;
}

void srand32(unsigned long n)
{
    obor_rand32_prepare();
    if(obor_rand32_uses_libc())
    {
        seed = n;
        obor_srand((unsigned int)n);
    }
    else
    {
        /* The original int argument sign-extends before unsigned-long storage. */
        uint32_t low = (uint32_t)n;
        int64_t value = low <= INT32_MAX ? (int64_t)low :
                        (int64_t)low - INT64_C(4294967296);
        seed = (unsigned long)value;
    }
}
