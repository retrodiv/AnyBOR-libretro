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
static size_t page;
static int operation;
static uint64_t initial;
static int clean(size_t offset, size_t length, uint64_t since)
{ return obor_write_watch_range_unchanged((uintptr_t)memory + offset, length, since); }
static void previous_signal(int signal) { (void)signal; _exit(73); }
static void *foreign_write(void *unused)
{
    (void)unused;
    *(volatile unsigned char *)memory = 1;
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
    }
}

static void guarded(int op, int expect_success)
{
    operation = op;
    obor_fault fault;
    int result = obor_fault_run(exercise, NULL, &fault);
    if ((result == 1) != expect_success) exit(20);
    if (!expect_success && fault.address != 1) exit(21);
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    page = (size_t)sysconf(_SC_PAGESIZE);
#if defined(__aarch64__) && !defined(OBOR_WRITE_WATCH_TEST)
    void *wanted = (void *)(uintptr_t)(OBOR_ARENA_BASE_VA + (16UL << 20));
    memory = mmap(wanted, page * 4, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (memory != wanted) return 3;
#else
    memory = mmap(NULL, page * 4, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
#endif
    if (memory == MAP_FAILED) return 3;
    memset(memory, 0x77, page * 4);
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
    } else if (!strcmp(argv[1], "errno")) {
        guarded(7, 1);
    } else if (!strcmp(argv[1], "lease")) {
        guarded(9, 1);
    } else if (!strcmp(argv[1], "worker")) {
        struct sigaction previous = {0};
        previous.sa_handler = previous_signal;
        sigemptyset(&previous.sa_mask);
        if (sigaction(SIGSEGV, &previous, NULL)) return 17;
        guarded(8, 1);
    } else return 2;
    if (!obor_write_watch_stop() || !obor_write_watch_stop() ||
        obor_write_watch_epoch() || obor_write_watch_page_size()) return 15;
    assert(!clean(0, page, initial));
    /* No stale signal handler, metadata or protection after shutdown. */
    memset(memory, 0x99, page * 4);
    if (!obor_write_watch_start(memory, page * 2, page * 4) ||
        obor_write_watch_epoch() != 1 || !obor_write_watch_stop()) return 16;
    munmap(memory, page * 4);
    puts("write_watch_passed=1");
    return 0;
}
