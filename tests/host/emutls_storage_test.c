/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

volatile int captured_game_counter = 73;
char captured_game_bss[64];
__thread uintptr_t guard = 11;
__thread uintptr_t other;
typedef struct {
    uintptr_t size, alignment, object, value;
} control;
/* Refer from assembler so no C declaration shadows LLVM's generated globals. */
static control *control_guard(void)
{
    control *value;
    __asm__("leaq __emutls_v.guard(%%rip),%0" : "=r"(value));
    return value;
}
static control *control_other(void)
{
    control *value;
    __asm__("leaq __emutls_v.other(%%rip),%0" : "=r"(value));
    return value;
}
#define guard_control (*control_guard())
#define other_control (*control_other())
static __attribute__((noinline)) volatile uintptr_t *read_guard(void) { return &guard; }
static __attribute__((noinline)) volatile uintptr_t *read_other(void) { return &other; }

int main(int argc, char **argv)
{
    assert(argc == 3 && captured_game_counter == 73);
    captured_game_bss[0] = 1;
    control saved[2];
    if (!strcmp(argv[1], "save")) {
        guard = 11;
        other = 22;
        saved[0] = guard_control;
        saved[1] = other_control;
        FILE *f = fopen(argv[2], "wb");
        assert(f && fwrite(saved, sizeof(saved), 1, f) == 1 && !fclose(f));
        printf("saved guard_index=%lu other_index=%lu guard=%lu other=%lu\n",
               (unsigned long)guard_control.object, (unsigned long)other_control.object,
               (unsigned long)guard, (unsigned long)other);
        return 0;
    }
    other = 22;
    guard = 11;
    printf("live guard_index=%lu other_index=%lu guard=%lu other=%lu\n",
           (unsigned long)guard_control.object, (unsigned long)other_control.object,
           (unsigned long)guard, (unsigned long)other);
    FILE *f = fopen(argv[2], "rb");
    assert(f && fread(saved, sizeof(saved), 1, f) == 1 && !fclose(f));
    if (!strcmp(argv[1], "restore")) {
        guard_control = saved[0];
        other_control = saved[1];
    } else assert(!strcmp(argv[1], "exclude"));
    /* Force fresh TLS address resolution after restoring module storage. */
    __asm__ __volatile__("" ::: "memory");
    volatile uintptr_t *observed_guard = read_guard();
    volatile uintptr_t *observed_other = read_other();
    printf("continued guard_index=%lu other_index=%lu guard=%lu other=%lu\n",
           (unsigned long)guard_control.object, (unsigned long)other_control.object,
           (unsigned long)*observed_guard, (unsigned long)*observed_other);
    if (!strcmp(argv[1], "restore"))
        assert(*observed_guard == 22 && *observed_other == 11);
    else assert(*observed_guard == 11 && *observed_other == 22);
    return 0;
}
