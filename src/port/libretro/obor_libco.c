/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * The included libco implementation retains its upstream license. */
#include "libco/libco.c"

/* A fault jumps directly to the frontend stack instead of co_switch().
 * Repair libco's TLS identity before another engine can be derived/run.
 * Both supported backends (amd64 and aarch64) use this internal handle. */
void obor_co_restore_active(cothread_t frontend)
{
    co_active_handle = frontend;
}
