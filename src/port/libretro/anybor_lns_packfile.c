/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
#if OBOR_ENGINE_BUILD == 6391
/* Must precede every system header, in particular on Windows. */
#ifdef _FILE_OFFSET_BITS
#undef _FILE_OFFSET_BITS
#endif
#define _FILE_OFFSET_BITS 64
#define OBOR_LNS_PAK_IMPL 1
#include "source/gamelib/packfile.c"
#endif
