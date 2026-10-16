/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_WRITE_WATCH_H
#define OBOR_WRITE_WATCH_H
#include <stddef.h>
#include <stdint.h>

/* The fault guard owns the current thread. Explicitly registered engine
 * workers can retain protection with pinned dispatch; captures, rearming and
 * destruction are refused until join. Other workers require suspension. */
#if (defined(__linux__) || defined(__APPLE__)) && \
    (defined(__aarch64__) || defined(__x86_64__) || \
     (defined(__riscv) && __riscv_xlen == 64) || defined(OBOR_WRITE_WATCH_TEST))
#define OBOR_WRITE_WATCH_ENABLED 1
int obor_write_watch_start(void *base, size_t length, size_t maximum);
int obor_write_watch_extend(size_t length);
int obor_write_watch_arm(size_t length);
int obor_write_watch_stop(void);
/* Only after the allocator has replaced/released the complete arena map. */
void obor_write_watch_abandon(void);
int obor_write_watch_fault(uintptr_t address);
/* Dispatcher-only entry: learning records actual CPU writes, never kernel-IO
 * preparation or synthetic always-dirty pages. */
int obor_write_watch_cpu_fault(uintptr_t address);
/* Access-kind-free signal contexts must exclude instruction fetches before
 * treating a permission fault on our readable data as a CPU write. */
int obor_write_watch_instruction_outside(uintptr_t pc);
int obor_write_watch_prepare_io(void *buffer, size_t length);
uint64_t obor_write_watch_epoch(void);
uint64_t obor_write_watch_page_epoch(size_t page);
/* Call while tracked engine workers are parked, as for state capture. A
 * missing/inactive watch, invalid range or unarmed generation is not proof. */
int obor_write_watch_range_unchanged(uintptr_t begin, size_t length, uint64_t since);
size_t obor_write_watch_page_size(void);
#else
#define OBOR_WRITE_WATCH_ENABLED 0
static inline int obor_write_watch_start(void *p, size_t n, size_t m)
{ (void)p; (void)n; (void)m; return 0; }
static inline int obor_write_watch_extend(size_t n) { (void)n; return 0; }
static inline int obor_write_watch_arm(size_t n) { (void)n; return 0; }
static inline int obor_write_watch_stop(void) { return 1; }
static inline void obor_write_watch_abandon(void) {}
static inline int obor_write_watch_fault(uintptr_t p) { (void)p; return 0; }
static inline int obor_write_watch_cpu_fault(uintptr_t p) { (void)p; return 0; }
static inline int obor_write_watch_instruction_outside(uintptr_t p)
{ (void)p; return 0; }
static inline int obor_write_watch_prepare_io(void *p, size_t n)
{ (void)p; (void)n; return 1; }
static inline uint64_t obor_write_watch_epoch(void) { return 0; }
static inline uint64_t obor_write_watch_page_epoch(size_t p)
{ (void)p; return UINT64_MAX; }
static inline int obor_write_watch_range_unchanged(uintptr_t p, size_t n, uint64_t e)
{ (void)p; (void)n; (void)e; return 0; }
static inline size_t obor_write_watch_page_size(void) { return 0; }
#endif
#endif
