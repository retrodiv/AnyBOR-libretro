/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_FAULT_H
#define OBOR_FAULT_H
#include <stdint.h>
#include <stddef.h>
enum { OBOR_FAULT_MEMORY = 1, OBOR_FAULT_ALLOCATOR, OBOR_FAULT_STACK, OBOR_FAULT_STATE };
#define OBOR_STACK_EMERGENCY_BYTES (64U * 1024U)
typedef struct {
    uint32_t code;
    uint32_t kind;
    uintptr_t address;
    uintptr_t pc;
} obor_fault;
/* 1 = returned, 0 = synchronous memory fault, -1 = guard unavailable.
 * The recovery point lives on the frontend stack, outside the engine arena.
 * Only the calling thread and the lifetime of the callback are protected.
 * This is containment of typical engine faults, not memory isolation. */
int obor_fault_run(void (*execute)(void *), void *context, obor_fault *fault);
/* Arm a Windows stack alarm above a committed emergency reserve. The libco
 * handle at the bottom remains accessible; healthy snapshots omit this gap. */
int obor_fault_stack_prepare(void *stack, size_t size);
int obor_fault_run_stack(void (*execute)(void *), void *context,
                         obor_fault *fault, void *stack, size_t size);
/* dlmalloc's fatal corruption/usage hooks call this before entering CRT abort.
 * A worker/out-of-scope call retains the ordinary abort behaviour. */
void obor_fault_abort(uint32_t kind, uintptr_t address) __attribute__((noreturn));
void obor_fault_allocator_activity(int entering);
static inline __attribute__((noreturn)) void obor_fault_allocator_error(uintptr_t address)
{ obor_fault_abort(OBOR_FAULT_ALLOCATOR, address); }
#endif
