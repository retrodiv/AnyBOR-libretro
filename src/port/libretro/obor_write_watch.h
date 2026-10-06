/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_WRITE_WATCH_H
#define OBOR_WRITE_WATCH_H
#include <stddef.h>
#include <stdint.h>

/* The fault guard owns the current thread. Worker creation suspends protection
 * before publishing a worker; captures are refused while workers are alive. */
#if defined(__linux__) && !defined(__ANDROID__) && \
    (defined(__aarch64__) || defined(OBOR_WRITE_WATCH_TEST))
#define OBOR_WRITE_WATCH_ENABLED 1
int obor_write_watch_start(void *base, size_t length, size_t maximum);
int obor_write_watch_extend(size_t length);
int obor_write_watch_arm(size_t length);
int obor_write_watch_stop(void);
/* Only after the allocator has replaced/released the complete arena map. */
void obor_write_watch_abandon(void);
int obor_write_watch_fault(uintptr_t address);
int obor_write_watch_prepare_io(void *buffer, size_t length);
uint64_t obor_write_watch_epoch(void);
uint64_t obor_write_watch_page_epoch(size_t page);
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
static inline int obor_write_watch_prepare_io(void *p, size_t n)
{ (void)p; (void)n; return 1; }
static inline uint64_t obor_write_watch_epoch(void) { return 0; }
static inline uint64_t obor_write_watch_page_epoch(size_t p)
{ (void)p; return UINT64_MAX; }
static inline size_t obor_write_watch_page_size(void) { return 0; }
#endif
#endif
