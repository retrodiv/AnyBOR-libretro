/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_REWIND_H
#define OBOR_REWIND_H
#include "obor_abi.h"

/* Optional AnyBOR extension, not a standard libretro environment command.
 * Version and structure size must both match. Unsupported hosts return NULL.
 * The frontend must explicitly enforce this lifetime contract:
 * - exactly two caller-owned, nonoverlapping complete core-state buffers;
 * - no changes to either image except through capture, until end succeeds;
 * - no direct writes through cheat/debugger memory maps until end succeeds;
 * - end before free, core unload/change or reset, including error paths.
 * Any load attempt ends the session, including a rejected input. Begin again
 * after load/reset/change. The first capture fully initializes the advertised
 * size. Normal save/load APIs still work.
 * Range offsets are core-payload-relative; frontend envelope bytes need their
 * own hints. On capture failure, never push a partially written image.
 */
#define OBOR_REWIND_INTERFACE_VERSION 1u
#define OBOR_REWIND_EXCLUSIVE_BUFFERS_AND_MEMORY 1u
typedef struct {
    int32_t (*begin)(void *, void *, uint32_t, uint32_t);
    uint32_t (*capture)(void *, uint32_t, obor_state_ranges *);
    int32_t (*end)(void);
} obor_rewind_interface;

#ifdef __cplusplus
extern "C" {
#endif
OBOR_API const obor_rewind_interface *retro_anybor_rewind_interface(uint32_t version,
                                                                   uint32_t size);
#ifdef __cplusplus
}
#endif
#endif
