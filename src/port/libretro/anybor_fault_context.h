/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_FAULT_CONTEXT_H
#define OBOR_FAULT_CONTEXT_H
#include <signal.h>
#include <stdint.h>

/* Signal numbers alone cannot distinguish an arena permission write from
 * an alignment, instruction or foreign fault. The caller must also check
 * the saved CPU context and the tracked destination. XNU ARM reports the
 * same BSD code for several different Mach bad-access exceptions. */
static inline int obor_fault_protection_signal(int signal, int code)
{
    if (signal == SIGSEGV && code == SEGV_ACCERR) return 1;
#if defined(__APPLE__)
    if (signal == SIGBUS && (code == BUS_ADRERR || code == BUS_ADRALN)) return 1;
#endif
    return 0;
}

static inline int obor_fault_arm_permission_write(uint32_t esr)
{
    /* EL0 data abort, write, permission fault; exclude cache maintenance. */
    return ((esr >> 26) & 0x3f) == 0x24 && (esr & (1U << 6)) &&
        !(esr & (1U << 8)) && (esr & 0x3c) == 0x0c;
}
#endif
