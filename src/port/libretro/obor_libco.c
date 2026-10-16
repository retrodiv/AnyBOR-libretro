/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * The included libco implementation retains its upstream license. */
#if defined(__riscv) && __riscv_xlen == 64
#include "obor_libco_riscv64.inc"
#else
#include "libco/libco.c"
#endif

/* A fault jumps directly to the frontend stack instead of co_switch().
 * Repair libco's TLS identity before another engine can be derived/run.
 * Every selected backend uses this internal handle. */
void obor_co_restore_active(cothread_t frontend)
{
    co_active_handle = frontend;
}
