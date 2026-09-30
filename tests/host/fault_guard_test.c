/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obor_fault.h"
#include "libco/libco.h"
#ifdef _WIN32
#include <windows.h>
#else
#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>
#include <pthread.h>
#endif
extern void obor_co_restore_active(cothread_t);
static cothread_t frontend, engine;
static void *engine_stack;
static const unsigned stack_size = 1024 * 1024;
static volatile uintptr_t bad_address;
static int operation, yielded;
static int user_signal;

#ifdef _WIN32
static LONG CALLBACK previous_handler(EXCEPTION_POINTERS *exception)
{
    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION)
        ExitProcess(73);
    return EXCEPTION_CONTINUE_SEARCH;
}
static DWORD WINAPI worker(LPVOID unused)
{ (void)unused; yielded = *(volatile unsigned *)bad_address; return 0; }
#else
static volatile sig_atomic_t forwarded;
static void previous_handler(int signal)
{ (void)signal; if (user_signal) ++forwarded; else _exit(73); }
static void *worker(void *unused)
{ (void)unused; yielded = *(volatile unsigned *)bad_address; return NULL; }
#endif

static void outside_thread(void *unused)
{
    (void)unused;
#ifdef _WIN32
    HANDLE thread = CreateThread(NULL, 0, worker, NULL, 0, NULL);
    assert(thread); WaitForSingleObject(thread, INFINITE); CloseHandle(thread);
#else
    pthread_t thread;
    assert(pthread_create(&thread, NULL, worker, NULL) == 0);
    assert(pthread_join(thread, NULL) == 0);
#endif
}
#ifndef _WIN32
static void user_generated(void *unused) { (void)unused; raise(SIGSEGV); }
#endif

__attribute__((noinline)) static unsigned overflow(unsigned n)
{
    volatile unsigned char padding[4096];
    padding[n & 4095] = (unsigned char)n;
    return overflow(n + 1) + padding[n & 4095];
}

static void entry(void)
{
    yielded = 1;
    co_switch(frontend); /* Fault on a later call, with a fresh frontend guard. */
    if (operation == 3 || operation == 5) obor_fault_allocator_error(1234);
    else if (operation == 2 || operation == 4) (void)overflow(0);
    else if (operation) *(volatile unsigned *)bad_address = 42;
    else yielded = *(volatile unsigned *)bad_address;
    abort();
}

static void execute(void *unused)
{
    (void)unused;
#ifdef _WIN32
    NT_TIB *tib = (NT_TIB *)NtCurrentTeb();
    void *base = tib->StackBase, *limit = tib->StackLimit;
    tib->StackBase = (char *)engine_stack + stack_size;
    tib->StackLimit = engine_stack;
    co_switch(engine);
    tib->StackBase = base;
    tib->StackLimit = limit;
#else
    co_switch(engine);
#endif
}

static void harmless(void *context) { ++*(int *)context; }

int main(int argc, char **argv)
{
    setbuf(stdout, NULL);
    obor_fault fault;
    int value = 0;
#ifdef _WIN32
    SYSTEM_INFO system;
    GetSystemInfo(&system);
    size_t page = system.dwPageSize;
    char *mapping = VirtualAlloc(NULL, stack_size + page, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    DWORD old;
    assert(mapping && VirtualProtect(mapping, page, PAGE_NOACCESS, &old));
    bad_address = (uintptr_t)mapping;
    assert(AddVectoredExceptionHandler(0, previous_handler));
    NT_TIB *tib = (NT_TIB *)NtCurrentTeb();
    void *base = tib->StackBase, *limit = tib->StackLimit;
#else
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    char *mapping = mmap(NULL, stack_size + page, PROT_READ | PROT_WRITE,
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(mapping != MAP_FAILED && mprotect(mapping, page, PROT_NONE) == 0);
    bad_address = (uintptr_t)mapping;
    user_signal = argc > 1 && !strcmp(argv[1], "user");
    signal(SIGSEGV, previous_handler);
    if (argc > 1 && !strcmp(argv[1], "sigbus")) {
        FILE *file = tmpfile();
        assert(file && ftruncate(fileno(file), (off_t)page) == 0);
        void *file_mapping = mmap(NULL, page, PROT_READ | PROT_WRITE,
                                  MAP_SHARED, fileno(file), 0);
        assert(file_mapping != MAP_FAILED && ftruncate(fileno(file), 0) == 0);
        bad_address = (uintptr_t)file_mapping;
        fclose(file);
    }
    struct sigaction segv_before, segv_after, bus_before, bus_after;
    stack_t stack_before, stack_after;
    sigset_t mask_before, mask_after;
    sigaction(SIGSEGV, NULL, &segv_before);
    sigaction(SIGBUS, NULL, &bus_before);
    sigaltstack(NULL, &stack_before);
    sigprocmask(SIG_SETMASK, NULL, &mask_before);
#endif
    engine_stack = mapping + page;
    frontend = co_active();
    const int operations = 6;
    for (operation = 0; operation < operations; ++operation) {
        printf("testing operation=%d\n", operation);
        assert(obor_fault_stack_prepare(engine_stack, stack_size));
        engine = co_derive(engine_stack, stack_size, entry);
        yielded = 0;
        assert(obor_fault_run_stack(execute, NULL, &fault, engine_stack, stack_size) == 1 && yielded == 1);
        assert(co_active() == frontend);
        assert(obor_fault_run_stack(execute, NULL, &fault, engine_stack, stack_size) == 0);
        obor_co_restore_active(frontend);
        assert(co_active() == frontend && fault.kind && fault.pc);
        if (operation == 3 || operation == 5) assert(fault.kind == OBOR_FAULT_ALLOCATOR && fault.address == 1234);
#ifdef _WIN32
        if (operation == 2 || operation == 4) assert(fault.kind == OBOR_FAULT_STACK);
#endif
        printf("captured operation=%d code=%x address=%llx pc=%llx\n", operation,
               fault.code, (unsigned long long)fault.address, (unsigned long long)fault.pc);
        assert(obor_fault_run(harmless, &value, &fault) == 1);
#ifdef _WIN32
        /* Windows may commit an additional frontend stack page during a
         * library call. Its limit must still belong to the frontend stack. */
        assert(tib->StackBase == base && (uintptr_t)tib->StackLimit <= (uintptr_t)limit &&
               (uintptr_t)tib->StackLimit < (uintptr_t)&value &&
               (uintptr_t)&value < (uintptr_t)tib->StackBase);
#else
        sigaction(SIGSEGV, NULL, &segv_after);
        sigaction(SIGBUS, NULL, &bus_after);
        sigaltstack(NULL, &stack_after);
        sigprocmask(SIG_SETMASK, NULL, &mask_after);
        assert(segv_before.sa_handler == segv_after.sa_handler &&
               bus_before.sa_handler == bus_after.sa_handler);
        assert(stack_before.ss_sp == stack_after.ss_sp && stack_before.ss_flags == stack_after.ss_flags);
        for (int s = 1; s < NSIG; ++s)
            assert(sigismember(&mask_before, s) == sigismember(&mask_after, s));
#endif
    }
    assert(value == operations);
    if (argc > 1 && !strcmp(argv[1], "worker")) {
        (void)obor_fault_run(outside_thread, NULL, &fault);
        abort(); /* Must have reached the previous handler on the worker. */
    }
    if (argc > 1 && !strcmp(argv[1], "frontend")) {
        yielded = *(volatile unsigned *)bad_address;
        abort(); /* Previous handler must own faults outside execution. */
    }
#ifndef _WIN32
    if (user_signal) {
        assert(obor_fault_run(user_generated, NULL, &fault) == 1);
        assert(forwarded == 1);
        puts("user_signal_forwarded=1");
    }
#endif
    puts("fault_guard_passed=1");
    return 0;
}
