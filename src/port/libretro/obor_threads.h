/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* OS helpers for asynchronous movie and audio workers. */
#ifndef OBOR_THREADS_H
#define OBOR_THREADS_H
#include <stdint.h>
#include "gamelib/threads.h"
typedef struct { int value; } obor_atomic_int;
static inline int obor_atomic_get(obor_atomic_int *p)
{ return __atomic_load_n(&p->value, __ATOMIC_SEQ_CST); }
static inline int obor_atomic_set(obor_atomic_int *p, int value)
{ return __atomic_exchange_n(&p->value, value, __ATOMIC_SEQ_CST); }
int obor_cpu_count(void);
void obor_thread_high_priority(void);
uint64_t obor_wall_uticks(void);
uintptr_t obor_thread_identity(void);
void obor_thread_yield(void);
void obor_mutex_suspend(bor_mutex *mutex);
void obor_mutex_resume(bor_mutex *mutex);
#endif
