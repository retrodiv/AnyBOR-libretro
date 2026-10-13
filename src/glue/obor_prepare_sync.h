/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PREPARE_SYNC_H
#define OBOR_PREPARE_SYNC_H
#include <errno.h>
#include <stdio.h>
#include "obor_prepare_progress.h"
#if defined(_WIN32)
#include <windows.h>
#include <io.h>
#else
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#endif

/* A newly written input can still have dirty pages when the engine starts
 * streaming it. On a slow filesystem, writeback can then block gameplay
 * reads. Complete only this file's writes during preparation. One transient
 * worker keeps cooperative loading responsive; it owns no content buffer,
 * state history or engine data and is joined before the descriptor is closed.
 * Cancellation must also join: an in-flight filesystem call cannot safely
 * outlive the loading stack or the core module. */
typedef struct {
    int fd, result, error, done;
    int (*operation)(int);
} obor_prepare_sync_job;

static int obor_prepare_sync_native(int fd)
{
#if defined(_WIN32)
    return _commit(fd);
#else
    return fsync(fd);
#endif
}

#if defined(_WIN32)
static DWORD WINAPI obor_prepare_sync_worker(void *opaque)
#else
static void *obor_prepare_sync_worker(void *opaque)
#endif
{
    obor_prepare_sync_job *job = (obor_prepare_sync_job *)opaque;
    do { job->result = job->operation(job->fd); }
    while (job->result < 0 && errno == EINTR);
    job->error = job->result ? errno : 0;
    __atomic_store_n(&job->done, 1, __ATOMIC_RELEASE);
    return 0;
}

static int obor_prepare_sync_fd(int fd, int (*operation)(int))
{
    obor_prepare_sync_job job = { fd, -1, 0, 0, operation };
    if (fd < 0 || !operation) { errno = EINVAL; return 0; }
    if (!obor_prepare_checkpoint()) { errno = ECANCELED; return 0; }
    /* Standalone preparation tools have no frontend to keep repainting. */
    if (!obor_prepare_progress) {
        obor_prepare_sync_worker(&job);
        errno = job.error;
        return job.result == 0;
    }
#if defined(_WIN32)
    HANDLE thread = CreateThread(NULL, 256u << 10, obor_prepare_sync_worker,
                                  &job, STACK_SIZE_PARAM_IS_A_RESERVATION, NULL);
    if (!thread) { errno = EAGAIN; return 0; }
#else
    pthread_t thread;
    pthread_attr_t attr;
    int error = pthread_attr_init(&attr);
    if (error) { errno = error; return 0; }
    error = pthread_attr_setstacksize(&attr, 256u << 10);
    if (!error) error = pthread_create(&thread, &attr, obor_prepare_sync_worker, &job);
    pthread_attr_destroy(&attr);
    if (error) { errno = error; return 0; }
#endif
    int cancelled = 0;
    while (!__atomic_load_n(&job.done, __ATOMIC_ACQUIRE)) {
        if (!obor_prepare_checkpoint()) cancelled = 1;
#if defined(_WIN32)
        Sleep(1);
#else
        struct timespec delay = { 0, 1000000 };
        nanosleep(&delay, NULL);
#endif
    }
#if defined(_WIN32)
    int joined = WaitForSingleObject(thread, INFINITE) == WAIT_OBJECT_0;
    CloseHandle(thread);
#else
    int joined = pthread_join(thread, NULL) == 0;
#endif
    if (!obor_prepare_checkpoint()) cancelled = 1;
    errno = cancelled ? ECANCELED : !joined ? EIO : job.error;
    return !cancelled && joined && job.result == 0;
}

static int obor_prepare_sync_file(FILE *file)
{
    if (!file || fflush(file)) return 0;
    return obor_prepare_sync_fd(fileno(file), obor_prepare_sync_native);
}
#endif
