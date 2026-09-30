/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "obor_fault.h"
#include "obor_runtime.h"
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
/* A libco stack has no unwind relationship with the frontend stack. MinGW's
 * non-SEH setjmp supplies a null frame, so longjmp restores registers without
 * asking Windows to unwind across the two unrelated stacks. */
#define __USE_MINGW_SETJMP_NON_SEH
#include <setjmp.h>
#include <windows.h>
typedef struct {
    jmp_buf resume;
    volatile obor_fault fault;
    void *volatile stack_base, *volatile stack_limit;
    uintptr_t stack_alarm;
    volatile unsigned allocator_depth;
} fault_guard;
/* OS TLS avoids MinGW's emutls descriptors, which a snapshot would otherwise
 * restore. Allocate only for this guard's lifetime, then free the slot. */
static struct { volatile LONG busy; DWORD slot; } runtime OBOR_RUNTIME;
static fault_guard *current_guard(void)
{
    return runtime.busy == 2 ? (fault_guard *)TlsGetValue(runtime.slot) : NULL;
}

static void recover(fault_guard *guard)
{
    TlsSetValue(runtime.slot, NULL);
    ((NT_TIB *)NtCurrentTeb())->StackBase = guard->stack_base;
    ((NT_TIB *)NtCurrentTeb())->StackLimit = guard->stack_limit;
    longjmp(guard->resume, 1);
}

void obor_fault_allocator_activity(int entering)
{
    fault_guard *guard = current_guard();
    if (guard) {
        if (entering) ++guard->allocator_depth;
        else --guard->allocator_depth;
    }
}

void obor_fault_abort(uint32_t kind, uintptr_t address)
{
    fault_guard *guard = current_guard();
    if (!guard) abort();
    guard->fault.kind = kind;
    guard->fault.address = address;
    guard->fault.pc = (uintptr_t)__builtin_return_address(0);
    recover(guard);
    abort();
}

static LONG CALLBACK memory_exception(EXCEPTION_POINTERS *exception)
{
    fault_guard *guard = current_guard();
    DWORD code = exception->ExceptionRecord->ExceptionCode;
    uintptr_t address = exception->ExceptionRecord->NumberParameters >= 2 ?
        exception->ExceptionRecord->ExceptionInformation[1] : 0;
    int stack_alarm = guard && guard->stack_alarm &&
        code == EXCEPTION_GUARD_PAGE && address >= guard->stack_alarm &&
        address < guard->stack_alarm + 4096;
    if (!guard || (!stack_alarm && code != EXCEPTION_ACCESS_VIOLATION &&
                   code != EXCEPTION_IN_PAGE_ERROR && code != EXCEPTION_STACK_OVERFLOW))
        return EXCEPTION_CONTINUE_SEARCH;
    guard->fault.kind = stack_alarm || code == EXCEPTION_STACK_OVERFLOW ?
                        OBOR_FAULT_STACK : guard->allocator_depth ?
                        OBOR_FAULT_ALLOCATOR : OBOR_FAULT_MEMORY;
    guard->fault.code = code;
    guard->fault.pc = (uintptr_t)exception->ExceptionRecord->ExceptionAddress;
    guard->fault.address = address;
    recover(guard);
    return EXCEPTION_CONTINUE_SEARCH;
}

int obor_fault_stack_prepare(void *stack, size_t size)
{
    SYSTEM_INFO system;
    DWORD previous;
    GetSystemInfo(&system);
    if (!stack || size <= OBOR_STACK_EMERGENCY_BYTES + system.dwPageSize ||
        (uintptr_t)stack % system.dwPageSize ||
        OBOR_STACK_EMERGENCY_BYTES % system.dwPageSize) return 0;
    return VirtualProtect((char *)stack + OBOR_STACK_EMERGENCY_BYTES,
                          system.dwPageSize, PAGE_READWRITE | PAGE_GUARD, &previous) != 0;
}

int obor_fault_run_stack(void (*execute)(void *), void *context,
                         obor_fault *fault, void *stack, size_t size)
{
    fault_guard guard;
    NT_TIB *tib = (NT_TIB *)NtCurrentTeb();
    PVOID handler;
    int returned;
    memset(&guard, 0, sizeof(guard));
    memset(fault, 0, sizeof(*fault));
    guard.stack_base = tib->StackBase;
    guard.stack_limit = tib->StackLimit;
    guard.stack_alarm = stack && size > OBOR_STACK_EMERGENCY_BYTES + 4096 ?
                        (uintptr_t)stack + OBOR_STACK_EMERGENCY_BYTES : 0;
    if (InterlockedCompareExchange(&runtime.busy, 1, 0)) return -1;
    runtime.slot = TlsAlloc();
    if (runtime.slot == TLS_OUT_OF_INDEXES) { runtime.busy = 0; return -1; }
    handler = AddVectoredExceptionHandler(1, memory_exception);
    if (!handler) { TlsFree(runtime.slot); runtime.busy = 0; return -1; }
    returned = setjmp(guard.resume) == 0;
    if (returned) {
        /* Installing the handler can commit another frontend stack page. */
        guard.stack_base = tib->StackBase;
        guard.stack_limit = tib->StackLimit;
        if (TlsSetValue(runtime.slot, &guard)) {
            InterlockedExchange(&runtime.busy, 2);
            execute(context);
        }
        else returned = -1;
    }
    TlsSetValue(runtime.slot, NULL);
    tib->StackBase = guard.stack_base;
    tib->StackLimit = guard.stack_limit;
    RemoveVectoredExceptionHandler(handler);
    InterlockedExchange(&runtime.busy, 1);
    TlsFree(runtime.slot);
    InterlockedExchange(&runtime.busy, 0);
    if (!returned) *fault = guard.fault;
    return returned;
}

#else
#include <signal.h>
#include <setjmp.h>
/* Darwin requires _XOPEN_SOURCE to expose the machine context. */
#if defined(__APPLE__) && !defined(_XOPEN_SOURCE)
#define _XOPEN_SOURCE 600
#endif
#include <ucontext.h>

typedef struct {
    sigjmp_buf resume;
    volatile sig_atomic_t code;
    volatile uintptr_t address, pc;
    volatile sig_atomic_t kind;
    volatile unsigned allocator_depth;
} fault_guard;
#if defined(__APPLE__)
/* Mach-O compiler TLS makes dyld retain the whole core after dlclose. */
#define OBOR_FAULT_PTHREAD_TLS 1
#endif
#if defined(OBOR_FAULT_PTHREAD_TLS)
#include <pthread.h>
#endif
static struct {
    int busy;
    struct sigaction previous[2];
#if defined(OBOR_FAULT_PTHREAD_TLS)
    pthread_key_t slot;
    pthread_t owner;
    int slot_live;
#endif
} runtime OBOR_RUNTIME;
static const int memory_signals[2] = {SIGSEGV, SIGBUS};

#if defined(OBOR_FAULT_PTHREAD_TLS)
/* Darwin's get/set operations access existing per-thread slots without
 * allocation. Create/delete the key outside the signal handler, and keep
 * its identity outside snapshots just like the installed signal actions. */
static int guard_thread_prepare(void)
{
    int result = pthread_key_create(&runtime.slot, NULL);
    if (!result) {
        __atomic_store_n(&runtime.owner, pthread_self(), __ATOMIC_RELAXED);
        __atomic_store_n(&runtime.slot_live, 1, __ATOMIC_RELEASE);
    }
    return result;
}
static void guard_thread_finish(void)
{
    __atomic_store_n(&runtime.slot_live, 0, __ATOMIC_RELEASE);
    pthread_key_delete(runtime.slot);
}
static fault_guard *current_guard(void)
{
    /* Only the owner may look up this short-lived key. Workers must not race
     * its deletion/reuse, and idle allocator hooks must not read another
     * client's value after the key has been returned to libpthread. */
    if (!__atomic_load_n(&runtime.slot_live, __ATOMIC_ACQUIRE) ||
        !pthread_equal(pthread_self(),
                       __atomic_load_n(&runtime.owner, __ATOMIC_RELAXED))) return NULL;
    return (fault_guard *)pthread_getspecific(runtime.slot);
}
static int set_guard(fault_guard *guard)
{ return pthread_setspecific(runtime.slot, guard); }
#else
static __thread fault_guard *active_guard;
static int guard_thread_prepare(void) { return 0; }
static void guard_thread_finish(void) {}
static fault_guard *current_guard(void) { return active_guard; }
static int set_guard(fault_guard *guard) { active_guard = guard; return 0; }
#endif

void obor_fault_allocator_activity(int entering)
{
    fault_guard *guard = current_guard();
    if (guard) {
        if (entering) ++guard->allocator_depth;
        else --guard->allocator_depth;
    }
}

void obor_fault_abort(uint32_t kind, uintptr_t address)
{
    fault_guard *guard = current_guard();
    if (!guard) abort();
    guard->kind = kind;
    guard->address = address;
    guard->pc = (uintptr_t)__builtin_return_address(0);
    set_guard(NULL);
    siglongjmp(guard->resume, 1);
}

static void memory_signal(int signal, siginfo_t *info, void *context)
{
    fault_guard *guard = current_guard();
    if (guard && info && info->si_code > 0) {
        ucontext_t *machine = (ucontext_t *)context;
        guard->code = signal;
        guard->kind = guard->allocator_depth ? OBOR_FAULT_ALLOCATOR : OBOR_FAULT_MEMORY;
        guard->address = (uintptr_t)info->si_addr;
#if defined(__APPLE__) && defined(__x86_64__)
        guard->pc = machine->uc_mcontext->__ss.__rip;
#elif defined(__APPLE__) && (defined(__aarch64__) || defined(__arm64__))
        guard->pc = machine->uc_mcontext->__ss.__pc;
#elif defined(__x86_64__)
        guard->pc = machine->uc_mcontext.gregs[REG_RIP];
#elif defined(__aarch64__)
        guard->pc = machine->uc_mcontext.pc;
#endif
        set_guard(NULL);
        /* Do not allocate, log, inspect the arena or run engine cleanup here. */
        siglongjmp(guard->resume, 1);
    }
    /* Frontend/worker/user-generated signals belong to the previous owner. */
    struct sigaction *old = &runtime.previous[signal == SIGBUS];
    if (old->sa_handler == SIG_IGN) return;
    if (old->sa_handler != SIG_DFL) {
        if (old->sa_flags & SA_SIGINFO) old->sa_sigaction(signal, info, context);
        else old->sa_handler(signal);
        return;
    }
    sigaction(signal, old, NULL);
    raise(signal);
}

int obor_fault_stack_prepare(void *stack, size_t size)
{ (void)stack; (void)size; return 1; }

int obor_fault_run_stack(void (*execute)(void *), void *context,
                         obor_fault *fault, void *stack, size_t size)
{
    fault_guard guard;
    struct sigaction action;
    stack_t alternate, saved_stack;
    unsigned char signal_stack[64 * 1024];
    int installed = 0, returned;
    (void)stack; (void)size;
    memset(&guard, 0, sizeof(guard));
    memset(fault, 0, sizeof(*fault));
    if (__atomic_exchange_n(&runtime.busy, 1, __ATOMIC_ACQUIRE)) return -1;
    if (guard_thread_prepare() != 0) {
        __atomic_store_n(&runtime.busy, 0, __ATOMIC_RELEASE); return -1;
    }
    memset(&alternate, 0, sizeof(alternate));
    alternate.ss_sp = signal_stack;
    alternate.ss_size = sizeof(signal_stack);
    if (sigaltstack(&alternate, &saved_stack) != 0) {
        guard_thread_finish();
        __atomic_store_n(&runtime.busy, 0, __ATOMIC_RELEASE); return -1;
    }
    memset(&action, 0, sizeof(action));
    sigemptyset(&action.sa_mask);
    action.sa_sigaction = memory_signal;
    action.sa_flags = SA_SIGINFO | SA_ONSTACK;
    for (; installed < 2; ++installed)
        if (sigaction(memory_signals[installed], &action, &runtime.previous[installed]) != 0)
            break;
    if (installed != 2) {
        while (installed) { --installed; sigaction(memory_signals[installed], &runtime.previous[installed], NULL); }
        sigaltstack(&saved_stack, NULL);
        guard_thread_finish();
        __atomic_store_n(&runtime.busy, 0, __ATOMIC_RELEASE);
        return -1;
    }
    returned = sigsetjmp(guard.resume, 1) == 0;
    if (returned) {
        if (set_guard(&guard) == 0) execute(context);
        else returned = -1;
    }
    set_guard(NULL);
    for (installed = 0; installed < 2; ++installed)
        sigaction(memory_signals[installed], &runtime.previous[installed], NULL);
    sigaltstack(&saved_stack, NULL);
    guard_thread_finish();
    __atomic_store_n(&runtime.busy, 0, __ATOMIC_RELEASE);
    if (!returned) {
        fault->code = guard.code;
        fault->kind = guard.kind;
        fault->address = guard.address;
        fault->pc = guard.pc;
    }
    return returned;
}
#endif

int obor_fault_run(void (*execute)(void *), void *context, obor_fault *fault)
{
    return obor_fault_run_stack(execute, context, fault, NULL, 0);
}
