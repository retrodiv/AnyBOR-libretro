/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR threads backend — pthread implementation of
 * source/gamelib/threads.h. Only webmlib (cutscene playback) uses threads;
 * the frame/audio/input path stays single-threaded.
 *
 * Pre-webm engine eras have no threads.h at all — compile to nothing there.
 */
/* Live engine-thread count: obor_state.c refuses to snapshot while any
 * webm thread might be mid-allocation. Defined even for threadless eras. */
int obor_live_threads;

/* NB: probe the engine-relative path — a bare "threads.h" would match the
 * system C11 <threads.h> on modern glibc. */
#if !__has_include("gamelib/threads.h")
typedef int obor_no_threads_in_this_era;
#else

#ifndef _WIN32

#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <time.h>
#include <sched.h>
#include <stdint.h>

#include "gamelib/threads.h"

struct bor_thread {
    pthread_t th;
    int (*fn)(void *);
    void *data;
    int result;
};
struct bor_mutex {
    pthread_mutex_t mtx;
};
struct bor_cond {
    pthread_cond_t cond;
};

static void *trampoline(void *arg)
{
    bor_thread *t = (bor_thread *)arg;
    t->result = t->fn(t->data);
    return NULL;
}

bor_thread *thread_create(int (*fn)(void *), const char *name, void *data)
{
    (void)name;
    bor_thread *t = (bor_thread *)malloc(sizeof(*t));
    if (!t)
        return NULL;
    t->fn = fn;
    t->data = data;
    /* Publish the worker before it can run. pthread_create() may schedule the
     * trampoline immediately, so incrementing afterwards leaves a window in
     * which savestate code can walk an arena that the worker is mutating. */
    __atomic_add_fetch(&obor_live_threads, 1, __ATOMIC_SEQ_CST);
    if (pthread_create(&t->th, NULL, trampoline, t) != 0) {
        __atomic_sub_fetch(&obor_live_threads, 1, __ATOMIC_SEQ_CST);
        free(t);
        return NULL;
    }
    return t;
}

void thread_join(bor_thread *thread)
{
    if (!thread)
        return;
    pthread_join(thread->th, NULL);
    free(thread);
    __atomic_sub_fetch(&obor_live_threads, 1, __ATOMIC_SEQ_CST);
}

bor_mutex *mutex_create(void)
{
    bor_mutex *m = (bor_mutex *)malloc(sizeof(*m));
    if (m)
        pthread_mutex_init(&m->mtx, NULL);
    return m;
}

void mutex_destroy(bor_mutex *mutex)
{
    if (!mutex)
        return;
    pthread_mutex_destroy(&mutex->mtx);
    free(mutex);
}

int mutex_lock(bor_mutex *mutex) { return pthread_mutex_lock(&mutex->mtx); }
int mutex_unlock(bor_mutex *mutex) { return pthread_mutex_unlock(&mutex->mtx); }

bor_cond *cond_create(void)
{
    bor_cond *c = (bor_cond *)malloc(sizeof(*c));
    if (c)
        pthread_cond_init(&c->cond, NULL);
    return c;
}

void cond_destroy(bor_cond *cond)
{
    if (!cond)
        return;
    pthread_cond_destroy(&cond->cond);
    free(cond);
}

int cond_signal(bor_cond *cond) { return pthread_cond_signal(&cond->cond); }
int cond_broadcast(bor_cond *cond) { return pthread_cond_broadcast(&cond->cond); }

int cond_wait(bor_cond *cond, bor_mutex *mutex)
{
    return pthread_cond_wait(&cond->cond, &mutex->mtx);
}

int cond_wait_timed(bor_cond *cond, bor_mutex *mutex, int ms)
{
    struct timeval now;
    struct timespec ts;
    gettimeofday(&now, NULL);
    ts.tv_sec = now.tv_sec + ms / 1000;
    ts.tv_nsec = now.tv_usec * 1000 + (ms % 1000) * 1000000;
    if (ts.tv_nsec >= 1000000000) {
        ts.tv_sec++;
        ts.tv_nsec -= 1000000000;
    }
    return pthread_cond_timedwait(&cond->cond, &mutex->mtx, &ts);
}

/* No decoder workers may exist while these state hooks run. */
void obor_mutex_suspend(bor_mutex *m)
{ if(m) pthread_mutex_destroy(&m->mtx); }
void obor_mutex_resume(bor_mutex *m)
{ if(m) { memset(&m->mtx, 0, sizeof(m->mtx)); pthread_mutex_init(&m->mtx, NULL); } }
int obor_cpu_count(void)
{ long n = sysconf(_SC_NPROCESSORS_ONLN); return n > 0 ? (int)n : 1; }
void obor_thread_high_priority(void) { /* Normal unprivileged scheduling. */ }
uintptr_t obor_thread_identity(void) { return (uintptr_t)pthread_self(); }
void obor_thread_yield(void) { sched_yield(); }
void obor_worker_pause(void) { usleep(1000); }
uint64_t obor_wall_uticks(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000 + t.tv_nsec / 1000;
}

#else /* _WIN32: minimal Win32 implementation */

#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "gamelib/threads.h"

struct bor_thread {
    HANDLE th;
    int (*fn)(void *);
    void *data;
};
struct bor_mutex {
    CRITICAL_SECTION cs;
};
struct bor_cond {
    CONDITION_VARIABLE cv;
};

static DWORD WINAPI trampoline(LPVOID arg)
{
    bor_thread *t = (bor_thread *)arg;
    t->fn(t->data);
    return 0;
}

bor_thread *thread_create(int (*fn)(void *), const char *name, void *data)
{
    (void)name;
    bor_thread *t = (bor_thread *)malloc(sizeof(*t));
    if (!t)
        return NULL;
    t->fn = fn;
    t->data = data;
    /* CreateThread() may execute the trampoline before returning. Mark the
     * arena as threaded first so serialization can never race worker startup. */
    __atomic_add_fetch(&obor_live_threads, 1, __ATOMIC_SEQ_CST);
    t->th = CreateThread(NULL, 0, trampoline, t, 0, NULL);
    if (!t->th) {
        __atomic_sub_fetch(&obor_live_threads, 1, __ATOMIC_SEQ_CST);
        free(t);
        return NULL;
    }
    return t;
}

void thread_join(bor_thread *thread)
{
    if (!thread)
        return;
    WaitForSingleObject(thread->th, INFINITE);
    CloseHandle(thread->th);
    free(thread);
    __atomic_sub_fetch(&obor_live_threads, 1, __ATOMIC_SEQ_CST);
}

bor_mutex *mutex_create(void)
{
    bor_mutex *m = (bor_mutex *)malloc(sizeof(*m));
    if (m)
        InitializeCriticalSection(&m->cs);
    return m;
}

void mutex_destroy(bor_mutex *mutex)
{
    if (!mutex)
        return;
    DeleteCriticalSection(&mutex->cs);
    free(mutex);
}

int mutex_lock(bor_mutex *mutex)
{
    EnterCriticalSection(&mutex->cs);
    return 0;
}

int mutex_unlock(bor_mutex *mutex)
{
    LeaveCriticalSection(&mutex->cs);
    return 0;
}

bor_cond *cond_create(void)
{
    bor_cond *c = (bor_cond *)malloc(sizeof(*c));
    if (c)
        InitializeConditionVariable(&c->cv);
    return c;
}

void cond_destroy(bor_cond *cond) { free(cond); }

int cond_signal(bor_cond *cond)
{
    WakeConditionVariable(&cond->cv);
    return 0;
}

int cond_broadcast(bor_cond *cond)
{
    WakeAllConditionVariable(&cond->cv);
    return 0;
}

int cond_wait(bor_cond *cond, bor_mutex *mutex)
{
    return SleepConditionVariableCS(&cond->cv, &mutex->cs, INFINITE) ? 0 : -1;
}

int cond_wait_timed(bor_cond *cond, bor_mutex *mutex, int ms)
{
    return SleepConditionVariableCS(&cond->cv, &mutex->cs, (DWORD)ms) ? 0 : -1;
}

void obor_mutex_suspend(bor_mutex *m)
{ if(m) DeleteCriticalSection(&m->cs); }
void obor_mutex_resume(bor_mutex *m)
{ if(m) { memset(&m->cs, 0, sizeof(m->cs)); InitializeCriticalSection(&m->cs); } }
int obor_cpu_count(void)
{ SYSTEM_INFO info; GetSystemInfo(&info); return (int)info.dwNumberOfProcessors; }
void obor_thread_high_priority(void)
{ SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL); }
uintptr_t obor_thread_identity(void) { return (uintptr_t)GetCurrentThreadId(); }
void obor_thread_yield(void) { SwitchToThread(); }
void obor_worker_pause(void) { Sleep(1); }
uint64_t obor_wall_uticks(void)
{
    LARGE_INTEGER count, frequency;
    QueryPerformanceCounter(&count); QueryPerformanceFrequency(&frequency);
    return (uint64_t)(count.QuadPart / frequency.QuadPart) * 1000000 +
        (uint64_t)(count.QuadPart % frequency.QuadPart) * 1000000 / frequency.QuadPart;
}

#endif /* _WIN32 */
#endif /* __has_include("threads.h") */
