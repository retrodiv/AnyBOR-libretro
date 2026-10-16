/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "libco/libco.h"
static unsigned char memory[65536] __attribute__((aligned(16)));
static unsigned char snapshot[65536];
static cothread_t frontend;
static int observed;
static void child(void) {
    for(int local=0;;++local) {
        register uint64_t i0 __asm__("s0") = UINT64_C(0x723456789abcdef0) + local + 0;
        register uint64_t i1 __asm__("s1") = UINT64_C(0x723456789abcdef0) + local + 1;
        register uint64_t i2 __asm__("s2") = UINT64_C(0x723456789abcdef0) + local + 2;
        register uint64_t i3 __asm__("s3") = UINT64_C(0x723456789abcdef0) + local + 3;
        register uint64_t i4 __asm__("s4") = UINT64_C(0x723456789abcdef0) + local + 4;
        register uint64_t i5 __asm__("s5") = UINT64_C(0x723456789abcdef0) + local + 5;
        register uint64_t i6 __asm__("s6") = UINT64_C(0x723456789abcdef0) + local + 6;
        register uint64_t i7 __asm__("s7") = UINT64_C(0x723456789abcdef0) + local + 7;
        register uint64_t i8 __asm__("s8") = UINT64_C(0x723456789abcdef0) + local + 8;
        register uint64_t i9 __asm__("s9") = UINT64_C(0x723456789abcdef0) + local + 9;
        register uint64_t i10 __asm__("s10") = UINT64_C(0x723456789abcdef0) + local + 10;
        register uint64_t i11 __asm__("s11") = UINT64_C(0x723456789abcdef0) + local + 11;
        register double f0 __asm__("fs0") = 1.25 + local + 0;
        register double f1 __asm__("fs1") = 1.25 + local + 1;
        register double f2 __asm__("fs2") = 1.25 + local + 2;
        register double f3 __asm__("fs3") = 1.25 + local + 3;
        register double f4 __asm__("fs4") = 1.25 + local + 4;
        register double f5 __asm__("fs5") = 1.25 + local + 5;
        register double f6 __asm__("fs6") = 1.25 + local + 6;
        register double f7 __asm__("fs7") = 1.25 + local + 7;
        register double f8 __asm__("fs8") = 1.25 + local + 8;
        register double f9 __asm__("fs9") = 1.25 + local + 9;
        register double f10 __asm__("fs10") = 1.25 + local + 10;
        register double f11 __asm__("fs11") = 1.25 + local + 11;
        __asm__ volatile("" : "+r"(i0), "+r"(i1), "+r"(i2), "+r"(i3), "+r"(i4), "+r"(i5), "+r"(i6), "+r"(i7), "+r"(i8), "+r"(i9), "+r"(i10), "+r"(i11));
        __asm__ volatile("" : "+f"(f0), "+f"(f1), "+f"(f2), "+f"(f3), "+f"(f4), "+f"(f5), "+f"(f6), "+f"(f7), "+f"(f8), "+f"(f9), "+f"(f10), "+f"(f11));
        observed=local;
        __asm__ volatile("fscsr %0" : : "r"(0x60));
        co_switch(frontend);
        unsigned csr; __asm__ volatile("frcsr %0" : "=r"(csr));
        __asm__ volatile("" : "+r"(i0), "+r"(i1), "+r"(i2), "+r"(i3), "+r"(i4), "+r"(i5), "+r"(i6), "+r"(i7), "+r"(i8), "+r"(i9), "+r"(i10), "+r"(i11));
        __asm__ volatile("" : "+f"(f0), "+f"(f1), "+f"(f2), "+f"(f3), "+f"(f4), "+f"(f5), "+f"(f6), "+f"(f7), "+f"(f8), "+f"(f9), "+f"(f10), "+f"(f11));
        assert(i0 == UINT64_C(0x723456789abcdef0) + local + 0);
        assert(f0 == 1.25 + local + 0);
        assert(i1 == UINT64_C(0x723456789abcdef0) + local + 1);
        assert(f1 == 1.25 + local + 1);
        assert(i2 == UINT64_C(0x723456789abcdef0) + local + 2);
        assert(f2 == 1.25 + local + 2);
        assert(i3 == UINT64_C(0x723456789abcdef0) + local + 3);
        assert(f3 == 1.25 + local + 3);
        assert(i4 == UINT64_C(0x723456789abcdef0) + local + 4);
        assert(f4 == 1.25 + local + 4);
        assert(i5 == UINT64_C(0x723456789abcdef0) + local + 5);
        assert(f5 == 1.25 + local + 5);
        assert(i6 == UINT64_C(0x723456789abcdef0) + local + 6);
        assert(f6 == 1.25 + local + 6);
        assert(i7 == UINT64_C(0x723456789abcdef0) + local + 7);
        assert(f7 == 1.25 + local + 7);
        assert(i8 == UINT64_C(0x723456789abcdef0) + local + 8);
        assert(f8 == 1.25 + local + 8);
        assert(i9 == UINT64_C(0x723456789abcdef0) + local + 9);
        assert(f9 == 1.25 + local + 9);
        assert(i10 == UINT64_C(0x723456789abcdef0) + local + 10);
        assert(f10 == 1.25 + local + 10);
        assert(i11 == UINT64_C(0x723456789abcdef0) + local + 11);
        assert(f11 == 1.25 + local + 11);
        assert(csr==0x60);
    }
}
int main(void) {
    frontend=co_active();
    cothread_t context=co_derive(memory,sizeof(memory),child); assert(context);
    for(int i=0;i<5;++i) {
        __asm__ volatile("fscsr %0" : : "r"(0x40));
        co_switch(context);
        unsigned csr; __asm__ volatile("frcsr %0" : "=r"(csr));
        assert(csr==0x40);assert(observed==i);
        uintptr_t parked = *(uintptr_t *)context;
        assert(parked > (uintptr_t)memory + 224 && parked < (uintptr_t)memory + sizeof(memory));
        if(i==2)memcpy(snapshot,memory,sizeof(memory));
    }
    memcpy(memory,snapshot,sizeof(memory));co_switch(context);assert(observed==3);
    puts("coroutine_integer_fp_fcsr_and_snapshot=PASS");
    return 0;
}
