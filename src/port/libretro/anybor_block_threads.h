/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_BLOCK_THREADS_H
#define OBOR_BLOCK_THREADS_H
#include <stdlib.h>

/* One bounded encoder helper. These objects are process-local scratch and
 * are destroyed only after its final input batch has been drained. */
#ifdef _WIN32
#include <windows.h>
typedef CRITICAL_SECTION bw_mutex;
typedef CONDITION_VARIABLE bw_condition;
typedef HANDLE bw_thread;
static int bw_mutex_init(bw_mutex *mutex)
{ return InitializeCriticalSectionEx(mutex, 0, 0) ? 0 : -1; }
static void bw_mutex_destroy(bw_mutex *mutex) { DeleteCriticalSection(mutex); }
static void bw_mutex_lock(bw_mutex *mutex) { EnterCriticalSection(mutex); }
static void bw_mutex_unlock(bw_mutex *mutex) { LeaveCriticalSection(mutex); }
static int bw_condition_init(bw_condition *condition)
{ InitializeConditionVariable(condition); return 0; }
static void bw_condition_destroy(bw_condition *condition) { (void)condition; }
static void bw_condition_wait(bw_condition *condition, bw_mutex *mutex)
{ if (!SleepConditionVariableCS(condition, mutex, INFINITE)) abort(); }
static void bw_condition_signal(bw_condition *condition)
{ WakeAllConditionVariable(condition); }
static int bw_cpu_count(void)
{ SYSTEM_INFO system; GetSystemInfo(&system); return (int)system.dwNumberOfProcessors; }
static void bw_thread_join(bw_thread thread)
{
    if (WaitForSingleObject(thread, INFINITE) != WAIT_OBJECT_0 ||
        !CloseHandle(thread)) abort();
}
#else
#include <pthread.h>
#include <unistd.h>
typedef pthread_mutex_t bw_mutex;
typedef pthread_cond_t bw_condition;
typedef pthread_t bw_thread;
static int bw_mutex_init(bw_mutex *mutex) { return pthread_mutex_init(mutex, NULL); }
static void bw_mutex_destroy(bw_mutex *mutex) { pthread_mutex_destroy(mutex); }
static void bw_mutex_lock(bw_mutex *mutex) { pthread_mutex_lock(mutex); }
static void bw_mutex_unlock(bw_mutex *mutex) { pthread_mutex_unlock(mutex); }
static int bw_condition_init(bw_condition *condition)
{ return pthread_cond_init(condition, NULL); }
static void bw_condition_destroy(bw_condition *condition) { pthread_cond_destroy(condition); }
static void bw_condition_wait(bw_condition *condition, bw_mutex *mutex)
{ if (pthread_cond_wait(condition, mutex)) abort(); }
static void bw_condition_signal(bw_condition *condition) { pthread_cond_broadcast(condition); }
static int bw_cpu_count(void) { return (int)sysconf(_SC_NPROCESSORS_ONLN); }
static void bw_thread_join(bw_thread thread)
{ if (pthread_join(thread, NULL)) abort(); }
#endif
#endif
