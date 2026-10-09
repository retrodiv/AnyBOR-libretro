/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include "obor_fault.h"
#include "obor_write_watch.h"
#include "gamelib/threads.h"
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

enum { WORKERS = 8 };
static unsigned char *memory;
static size_t page;
static bor_thread *workers[WORKERS];
static pthread_barrier_t ready;
static volatile sig_atomic_t forwarded;
static int action, fail_create, suspended;
static unsigned cycle;
static unsigned completed;
static int fallback;
extern int obor_live_threads;
extern int __real_pthread_create(pthread_t *, const pthread_attr_t *,
                                 void *(*)(void *), void *);
int __wrap_pthread_create(pthread_t *thread, const pthread_attr_t *attributes,
                         void *(*entry)(void *), void *data)
{
    return fail_create ? EAGAIN : __real_pthread_create(thread, attributes, entry, data);
}
void obor_state_owned_suspend(void)
{
    ++suspended;
    assert(obor_write_watch_stop());
}
static void previous_signal(int signal)
{
    (void)signal;
    if (action == 5) { ++forwarded; return; }
    _exit(73);
}
static int worker(void *argument)
{
    size_t index = (size_t)(uintptr_t)argument;
    pthread_barrier_wait(&ready);
    if (action == 1) *(volatile unsigned char *)(uintptr_t)1 = 0;
    if (action == 2) ((void (*)(void))(uintptr_t)memory)(); /* NX, not a write */
    /* Separate bytes on the same page avoid a data race while stressing
     * simultaneous protected-page faults and the already-dirty retry. */
    memory[index] = (unsigned char)cycle;
    memory[page + index] = (unsigned char)(cycle + 1);
    if (index == 0) {
        FILE *file = fopen("/dev/zero", "rb");
        assert(file && fread(memory + page * 2, 1, 16, file) == 16);
        fclose(file);
    }
    __atomic_add_fetch(&completed, 1, __ATOMIC_RELEASE);
    return 0;
}
static void spawn(void *unused)
{
    (void)unused;
    for (size_t i = 0; i < WORKERS; ++i) {
        workers[i] = thread_create(worker, "watch-test", (void *)(uintptr_t)i);
        assert(workers[i]);
    }
    assert(obor_fault_worker_leases() == (fallback ? 0 : WORKERS) &&
           obor_live_threads == WORKERS);
}
static void join(void *unused)
{
    (void)unused;
    for (size_t i = 0; i < WORKERS; ++i) thread_join(workers[i]);
    assert(!obor_fault_worker_leases() && !obor_live_threads);
}
static void failed_spawn(void *unused)
{
    (void)unused;
    fail_create = 1;
    assert(!thread_create(worker, "failed-test", NULL));
    fail_create = 0;
    assert(!obor_fault_worker_leases() && !obor_live_threads);
}
static void owner_fault(void *unused)
{ (void)unused; *(volatile unsigned char *)(uintptr_t)1 = 0; }
static void *foreign(void *unused)
{ (void)unused; memory[page * 3] = 0; return NULL; }
static void run(void (*execute)(void *))
{
    obor_fault fault;
    assert(obor_fault_run(execute, NULL, &fault) == 1);
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    if (!strcmp(argv[1], "worker-fault")) action = 1;
    else if (!strcmp(argv[1], "worker-execute")) action = 2;
    else if (!strcmp(argv[1], "foreign")) action = 3;
    else if (!strcmp(argv[1], "frontend")) action = 4;
    else if (!strcmp(argv[1], "user")) action = 5;
    else if (!strcmp(argv[1], "fallback") || !strcmp(argv[1], "disabled")) fallback = 1;
    else if (!strcmp(argv[1], "inactive")) fallback = 2;
    else assert(!strcmp(argv[1], "lifetime") || !strcmp(argv[1], "default"));
    struct sigaction handler = {0}, after;
    handler.sa_handler = previous_signal;
    sigemptyset(&handler.sa_mask);
    assert(!sigaction(SIGSEGV, &handler, NULL));
    assert(!setenv("OBOR_STATE_WORKER_WATCH", "1", 1));
    if (!strcmp(argv[1], "default") || !strcmp(argv[1], "inactive"))
        assert(!unsetenv("OBOR_STATE_WORKER_WATCH"));
    if (!strcmp(argv[1], "disabled")) assert(!setenv("OBOR_STATE_WORKER_WATCH", "0", 1));
    assert(!obor_fault_worker_acquire()); /* no dispatch outside a guard */
    page = (size_t)sysconf(_SC_PAGESIZE);
    memory = mmap(NULL, page * 4, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(memory != MAP_FAILED);
    memset(memory, 0x77, page * 4);
    if (fallback != 2) assert(obor_write_watch_start(memory, page * 4, page * 4));
    if (fallback) {
        if (fallback != 2) assert(obor_write_watch_arm(page * 4) == 1);
        assert(!pthread_barrier_init(&ready, NULL, WORKERS + 1));
        run(spawn);
        assert(!obor_write_watch_epoch());
        pthread_barrier_wait(&ready);
        while (__atomic_load_n(&completed, __ATOMIC_ACQUIRE) != WORKERS) sched_yield();
        run(join);
        assert(!pthread_barrier_destroy(&ready) && suspended == WORKERS);
        assert(!sigaction(SIGSEGV, NULL, &after) && after.sa_handler == previous_signal);
        munmap(memory, page * 4);
        puts("worker_watch_fallback_passed=1");
        return 0;
    }
    for (cycle = 1; cycle <= 64; ++cycle) {
        assert(obor_write_watch_arm(page * 4) == 1);
        uint64_t epoch = obor_write_watch_epoch();
        run(failed_spawn);
        assert(obor_write_watch_epoch() == epoch);
        assert(!pthread_barrier_init(&ready, NULL, WORKERS + 1));
        run(spawn);
        assert(!obor_write_watch_arm(page * 4) && !obor_write_watch_stop() &&
               !obor_write_watch_extend(page * 4));
        /* Owner recovery expires each callback, but worker dispatch survives.
         * Repeated owner faults must not detach dispatch from live workers. */
        obor_fault fault;
        assert(obor_fault_run(owner_fault, NULL, &fault) == 0 && fault.address == 1);
        if (action == 3) {
            pthread_t thread;
            assert(!pthread_create(&thread, NULL, foreign, NULL));
            pthread_join(thread, NULL);
            abort();
        }
        if (action == 4) { memory[page * 3] = 0; abort(); }
        if (action == 5) { raise(SIGSEGV); assert(forwarded == (int)cycle); }
        /* Writes happen with no owner callback on the stack. */
        __atomic_store_n(&completed, 0, __ATOMIC_RELEASE);
        pthread_barrier_wait(&ready);
        while (__atomic_load_n(&completed, __ATOMIC_ACQUIRE) != WORKERS) sched_yield();
        run(join);
        assert(!pthread_barrier_destroy(&ready));
        assert(!sigaction(SIGSEGV, NULL, &after) && after.sa_handler == previous_signal);
        assert(obor_write_watch_epoch() == epoch);
        for (size_t i = 0; i < WORKERS; ++i)
            assert(memory[i] == cycle && memory[page + i] == cycle + 1);
        for (size_t i = 0; i < 16; ++i) assert(memory[page * 2 + i] == 0);
        for (size_t i = 0; i < 3; ++i)
            assert(obor_write_watch_page_epoch(i) == epoch);
        assert(obor_write_watch_page_epoch(3) < epoch);
    }
    assert(!suspended);
    assert(obor_write_watch_stop());
    memset(memory, 0x99, page * 4);
    munmap(memory, page * 4);
    puts("worker_watch_passed=1 cycles=64 workers=8");
    return 0;
}
