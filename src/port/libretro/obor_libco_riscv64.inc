/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#if !defined(__riscv) || __riscv_xlen != 64 || !defined(__riscv_float_abi_double)
#error AnyBOR RISC-V coroutines require the LP64D ABI
#endif
#define LIBCO_C
#include "libco/libco.h"
#include "libco/settings.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

/* The integer and floating-point preserved registers occupy fixed slots.
 * gp and tp belong to the hosting OS thread and never change here. */
typedef struct {
    uint64_t integer[14]; /* sp, ra, s0..s11; snapshot readers expect sp first */
    uint64_t floating[12];
    uint64_t fcsr;
    void (*entry)(void);
} obor_co_riscv_context;
typedef char obor_co_riscv_layout[
    offsetof(obor_co_riscv_context, floating) == 112 &&
    offsetof(obor_co_riscv_context, fcsr) == 208 &&
    sizeof(obor_co_riscv_context) == 224 ? 1 : -1];

static thread_local obor_co_riscv_context co_active_buffer;
static thread_local cothread_t co_active_handle;

static __attribute__((naked, noinline)) void obor_co_riscv_swap(
    cothread_t next __attribute__((unused)), cothread_t previous __attribute__((unused)))
{
    __asm__ volatile(
        "sd sp, 0(a1)\n sd ra, 8(a1)\n"
        "sd s0, 16(a1)\n sd s1, 24(a1)\n sd s2, 32(a1)\n sd s3, 40(a1)\n"
        "sd s4, 48(a1)\n sd s5, 56(a1)\n sd s6, 64(a1)\n sd s7, 72(a1)\n"
        "sd s8, 80(a1)\n sd s9, 88(a1)\n sd s10, 96(a1)\n sd s11, 104(a1)\n"
        "fsd fs0, 112(a1)\n fsd fs1, 120(a1)\n fsd fs2, 128(a1)\n fsd fs3, 136(a1)\n"
        "fsd fs4, 144(a1)\n fsd fs5, 152(a1)\n fsd fs6, 160(a1)\n fsd fs7, 168(a1)\n"
        "fsd fs8, 176(a1)\n fsd fs9, 184(a1)\n fsd fs10, 192(a1)\n fsd fs11, 200(a1)\n"
        "frcsr t0\n sd t0, 208(a1)\n"
        "ld sp, 0(a0)\n ld ra, 8(a0)\n"
        "ld s0, 16(a0)\n ld s1, 24(a0)\n ld s2, 32(a0)\n ld s3, 40(a0)\n"
        "ld s4, 48(a0)\n ld s5, 56(a0)\n ld s6, 64(a0)\n ld s7, 72(a0)\n"
        "ld s8, 80(a0)\n ld s9, 88(a0)\n ld s10, 96(a0)\n ld s11, 104(a0)\n"
        "fld fs0, 112(a0)\n fld fs1, 120(a0)\n fld fs2, 128(a0)\n fld fs3, 136(a0)\n"
        "fld fs4, 144(a0)\n fld fs5, 152(a0)\n fld fs6, 160(a0)\n fld fs7, 168(a0)\n"
        "fld fs8, 176(a0)\n fld fs9, 184(a0)\n fld fs10, 192(a0)\n fld fs11, 200(a0)\n"
        "ld t0, 208(a0)\n fscsr t0\n ret\n");
}

static void obor_co_riscv_enter(void)
{
    ((obor_co_riscv_context *)co_active_handle)->entry();
    abort();
}

cothread_t co_active(void)
{
    if (!co_active_handle) co_active_handle = &co_active_buffer;
    return co_active_handle;
}

cothread_t co_derive(void *memory, unsigned int size, void (*entry)(void))
{
    uintptr_t begin = (uintptr_t)memory, end = begin + size;
    obor_co_riscv_context *context = memory;
    if (!memory || !entry || begin % 16 || end < begin ||
        size < sizeof(*context) + 256) return NULL;
    co_active();
    memset(context, 0, sizeof(*context));
    context->integer[0] = end & ~(uintptr_t)15;
    context->integer[1] = (uintptr_t)obor_co_riscv_enter;
    context->entry = entry;
    __asm__ volatile("frcsr %0" : "=r"(context->fcsr));
    return context;
}

cothread_t co_create(unsigned int size, void (*entry)(void))
{
    void *memory = LIBCO_MALLOC(size);
    cothread_t result = co_derive(memory, size, entry);
    if (!result) LIBCO_FREE(memory);
    return result;
}

void co_delete(cothread_t handle) { LIBCO_FREE(handle); }
void co_switch(cothread_t handle)
{
    cothread_t previous = co_active();
    co_active_handle = handle;
    obor_co_riscv_swap(handle, previous);
}
int co_serializable(void) { return 1; }
