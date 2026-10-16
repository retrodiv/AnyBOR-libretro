/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include "obor_fault.h"
#include "obor_abi.h"
#include "obor_write_watch.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static unsigned char *memory;
static unsigned char *mapping;
static size_t page;
static int operation;
static uint64_t initial;
static pthread_t registered_thread;
static pthread_mutex_t registered_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t registered_condition = PTHREAD_COND_INITIALIZER;
static int registered_ready, registered_go, registered_done;
static int clean(size_t offset, size_t length, uint64_t since)
{ return obor_write_watch_range_unchanged((uintptr_t)memory + offset, length, since); }
static void previous_signal(int signal) { (void)signal; _exit(73); }
static void *foreign_write(void *unused)
{
    (void)unused;
    *(volatile unsigned char *)memory = 1;
    return NULL;
}
static void *registered_write(void *unused)
{
    (void)unused;
    obor_fault_worker_enter();
    assert(!pthread_mutex_lock(&registered_mutex));
    registered_ready = 1;
    assert(!pthread_cond_broadcast(&registered_condition));
    while (!registered_go)
        assert(!pthread_cond_wait(&registered_condition, &registered_mutex));
    assert(!pthread_mutex_unlock(&registered_mutex));
    *(volatile unsigned char *)memory = 0x5a;
    obor_fault_worker_leave();
    assert(!pthread_mutex_lock(&registered_mutex));
    registered_done = 1;
    assert(!pthread_cond_broadcast(&registered_condition));
    assert(!pthread_mutex_unlock(&registered_mutex));
    return NULL;
}
static void exercise(void *unused)
{
    (void)unused;
    if (operation == 1) {
        volatile unsigned char *p = memory;
        p[page - 1] = 0x31;
        p[page] = 0x42;
    } else if (operation == 2) {
        int fd = open("/dev/zero", 0);
        if (fd < 0 || read(fd, memory + page - 3, 6) != 6) exit(11);
        close(fd);
    } else if (operation == 3) {
        FILE *file = fopen("/dev/zero", "rb");
        if (!file || fread(memory + page - 3, 1, 6, file) != 6) exit(12);
        fclose(file);
    } else if (operation == 4) {
        volatile unsigned char *p = memory;
        p[0] ^= 1;
    } else if (operation == 5) {
        volatile unsigned char *p = memory;
        p[page * 3] ^= 1; /* new pages have no earlier protected generation */
    } else if (operation == 6) {
        volatile unsigned char *p = (unsigned char *)(uintptr_t)1;
        *p = 1;
    } else if (operation == 7) {
        errno = 0;
        if (read(-1, memory, 8) != -1 || errno != EBADF) exit(13);
    } else if (operation == 9) {
        assert(obor_fault_worker_acquire());
        assert(!clean(0, page, initial));
        assert(!obor_write_watch_arm(page * 2));
        obor_fault_worker_release();
        assert(clean(0, page, initial));
    } else if (operation == 8) {
        pthread_t thread;
        if (pthread_create(&thread, NULL, foreign_write, NULL)) exit(14);
        pthread_join(thread, NULL);
        exit(15); /* a foreign write must reach the previous signal owner */
    } else if (operation == 10) {
        assert(obor_fault_worker_acquire());
        assert(!pthread_create(&registered_thread, NULL, registered_write, NULL));
        assert(!pthread_mutex_lock(&registered_mutex));
        while (!registered_ready)
            assert(!pthread_cond_wait(&registered_condition, &registered_mutex));
        assert(!pthread_mutex_unlock(&registered_mutex));
    } else if (operation == 11) {
        assert(!pthread_join(registered_thread, NULL));
        assert(obor_fault_worker_leases() == 1);
        obor_fault_worker_release();
        assert(!obor_fault_worker_leases());
    } else if (operation == 12) {
        ((void (*)(void))(uintptr_t)memory)(); /* NX, not a write */
    } else if (operation == 13) {
        ((void (*)(void))(uintptr_t)(memory - 2))(); /* straddling fetch */
    }
}

static void guarded(int op, int expect_success)
{
    operation = op;
    obor_fault fault;
    int result = obor_fault_run(exercise, NULL, &fault);
    if ((result == 1) != expect_success) exit(20);
    if (!expect_success) {
        uintptr_t expected = op == 12 || op == 13 ? (uintptr_t)memory : 1;
        if (fault.address != expected) exit(21);
        assert(fault.kind == OBOR_FAULT_MEMORY);
        if (op == 12 || op == 13)
            assert(fault.pc == (uintptr_t)memory - (op == 13 ? 2 : 0));
    }
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    page = (size_t)sysconf(_SC_PAGESIZE);
#if (defined(__aarch64__) || (defined(__riscv) && __riscv_xlen == 64)) && !defined(OBOR_WRITE_WATCH_TEST)
    void *wanted = (void *)(uintptr_t)(OBOR_ARENA_BASE_VA + (16UL << 20) - page);
    mapping = mmap(wanted, page * 5, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (mapping != wanted) return 3;
#else
    mapping = mmap(NULL, page * 5, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
#endif
    if (mapping == MAP_FAILED) return 3;
    memory = mapping + page;
    memset(memory, 0x77, page * 4);
    assert(!obor_write_watch_instruction_outside((uintptr_t)exercise));
    if (!strcmp(argv[1], "execute-boundary")) {
#if defined(__riscv) && __riscv_xlen == 64
        /* A 32-bit ADDI spans an executable page and the NX tracked page. */
        memory[-2] = 0x13; memory[-1] = memory[0] = memory[1] = 0;
        __builtin___clear_cache((char *)memory - 2, (char *)memory + 2);
        assert(!mprotect(mapping, page, PROT_READ | PROT_EXEC));
#else
        return 2;
#endif
    }
    if (obor_write_watch_start(memory + 1, page, page * 4) ||
        obor_write_watch_start(memory, page + 1, page * 4) ||
        obor_write_watch_start(memory, page * 5, page * 4) ||
        obor_write_watch_start(memory, page, SIZE_MAX) ||
        !obor_write_watch_start(memory, page * 2, page * 4) ||
        obor_write_watch_start(memory, page * 2, page * 4)) return 4;
    initial = obor_write_watch_epoch();
    assert(!clean(0, page, initial)); /* not protected yet */
    errno = EDOM;
    if (!obor_write_watch_arm(page * 2) || errno != EDOM) return 5;
    uint64_t first = obor_write_watch_epoch();
    if (first <= initial || obor_write_watch_page_epoch(0) > initial) return 6;
    assert(clean(0, page * 2, initial));
    assert(obor_write_watch_instruction_outside((uintptr_t)exercise));
    assert(!obor_write_watch_instruction_outside(0));
    assert(!obor_write_watch_instruction_outside((uintptr_t)memory));
    assert(!obor_write_watch_instruction_outside((uintptr_t)memory + page * 2 - 1));
    assert(!obor_write_watch_instruction_outside((uintptr_t)memory - 2));
    assert(clean(page - 1, 2, initial));
    assert(!clean(0, 0, initial) && !clean(0, 1, 0));
    assert(!clean(0, 1, first) && !clean(0, 1, UINT64_MAX));
    assert(!clean(page * 2, 1, initial));
    assert(!clean(page * 2 - 1, 2, initial));
    assert(!clean(1, SIZE_MAX, initial));
    assert(!obor_write_watch_range_unchanged((uintptr_t)memory - 1, 1, initial));
    assert(!obor_write_watch_range_unchanged(UINTPTR_MAX, 1, initial));
    if (!strcmp(argv[1], "cpu")) {
        guarded(1, 1);
        if (memory[page-1] != 0x31 || memory[page] != 0x42 ||
            obor_write_watch_page_epoch(0) != first ||
            obor_write_watch_page_epoch(1) != first) return 7;
        assert(!clean(0, page, initial) && !clean(page, page, initial));
        assert(!clean(page - 1, 2, initial));
        if (!obor_write_watch_arm(page * 2)) return 8;
        assert(clean(0, page * 2, first));
        guarded(4, 1);
        if (obor_write_watch_page_epoch(0) != obor_write_watch_epoch() ||
            obor_write_watch_page_epoch(1) != first) return 9;
        assert(!clean(0, page, first));
        assert(clean(page, page, first)); /* dirty outside queried range */
        assert(!clean(page - 1, 2, first));
    } else if (!strcmp(argv[1], "read") || !strcmp(argv[1], "fread")) {
        guarded(!strcmp(argv[1], "read") ? 2 : 3, 1);
        for (size_t i=page-3; i<page+3; ++i) if (memory[i]) return 10;
        if (memory[page-4] != 0x77 || memory[page+3] != 0x77 ||
            obor_write_watch_page_epoch(0) != first ||
            obor_write_watch_page_epoch(1) != first) return 11;
        assert(!clean(0, page * 2, initial));
        assert(!clean(page - 3, 6, initial));
        assert(!clean(page + 20, 1, initial)); /* conservative page proof */
    } else if (!strcmp(argv[1], "growth")) {
        guarded(5, 1);
        if (!obor_write_watch_extend(page * 4) ||
            obor_write_watch_page_epoch(2) != first ||
            obor_write_watch_page_epoch(3) != first ||
            obor_write_watch_extend(page) || obor_write_watch_arm(page * 5)) return 12;
        assert(clean(0, page * 2, initial));
        assert(!clean(page * 2, page * 2, initial));
        if (!obor_write_watch_arm(page * 4)) return 13;
        assert(clean(0, page * 4, first));
        guarded(5, 1);
        if (obor_write_watch_page_epoch(3) != obor_write_watch_epoch()) return 14;
        assert(clean(0, page * 3, first));
        assert(!clean(page * 3, 1, first));
    } else if (!strcmp(argv[1], "fault")) {
        guarded(6, 0);
        guarded(1, 1); /* recovery must not poison the active monitor */
    } else if (!strcmp(argv[1], "execute") || !strcmp(argv[1], "execute-boundary")) {
        guarded(!strcmp(argv[1], "execute") ? 12 : 13, 0);
        /* A fetch fault must not consume a dirty epoch or unprotect data. */
        assert(obor_write_watch_page_epoch(0) <= initial);
        assert(clean(0, page * 2, initial));
        guarded(1, 1);
        assert(obor_write_watch_page_epoch(0) == first);
    } else if (!strcmp(argv[1], "errno")) {
        guarded(7, 1);
    } else if (!strcmp(argv[1], "lease")) {
        guarded(9, 1);
    } else if (!strcmp(argv[1], "worker")) {
        struct sigaction previous = {0};
        previous.sa_handler = previous_signal;
        sigemptyset(&previous.sa_mask);
        if (sigaction(SIGSEGV, &previous, NULL) ||
            sigaction(SIGBUS, &previous, NULL)) return 17;
        guarded(8, 1);
    } else if (!strcmp(argv[1], "registered")) {
        /* Complete the write between owner calls, with no active owner guard.
         * Only the worker lease and its own identity may handle this fault. */
        guarded(10, 1);
        assert(obor_fault_worker_leases() == 1);
        assert(!pthread_mutex_lock(&registered_mutex));
        registered_go = 1;
        assert(!pthread_cond_broadcast(&registered_condition));
        while (!registered_done)
            assert(!pthread_cond_wait(&registered_condition, &registered_mutex));
        assert(!pthread_mutex_unlock(&registered_mutex));
        guarded(11, 1);
        assert(memory[0] == 0x5a && obor_write_watch_page_epoch(0) == first);
        assert(!clean(0, page, initial));
        assert(clean(page, page, initial));
    } else return 2;
    if (!obor_write_watch_stop() || !obor_write_watch_stop() ||
        obor_write_watch_epoch() || obor_write_watch_page_size()) return 15;
    assert(!clean(0, page, initial));
    /* No stale signal handler, metadata or protection after shutdown. */
    memset(memory, 0x99, page * 4);
    if (!obor_write_watch_start(memory, page * 2, page * 4) ||
        obor_write_watch_epoch() != 1 || !obor_write_watch_stop()) return 16;
    munmap(mapping, page * 5);
    puts("write_watch_passed=1");
    return 0;
}
