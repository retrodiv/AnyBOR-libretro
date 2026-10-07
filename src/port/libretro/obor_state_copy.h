/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_COPY_H
#define OBOR_STATE_COPY_H

#include <stddef.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#include "obor_state_padding.h"
typedef struct {
    unsigned char *destination;
    const unsigned char *source;
    size_t size;
} obor_win_state_copy_job;

static void CALLBACK obor_win_state_copy_worker(PTP_CALLBACK_INSTANCE instance,
                                                void *context, PTP_WORK work)
{
    obor_win_state_copy_job *job = (obor_win_state_copy_job *)context;
    (void)instance;
    (void)work;
    memcpy(job->destination, job->source, job->size);
}
#endif

#if defined(__linux__) && (defined(__x86_64__) || defined(__ANDROID__))
#include <pthread.h>
#include <unistd.h>

typedef struct {
    unsigned char *destination;
    const unsigned char *source;
    size_t size;
} obor_state_copy_job;

static void *obor_state_copy_worker(void *context)
{
    obor_state_copy_job *job = (obor_state_copy_job *)context;
    memcpy(job->destination, job->source, job->size);
    return NULL;
}
#endif

/* The engine is parked and the module/stack header has already been saved.
 * Large heaps benefit from bounded parallel copies on desktop and Android hosts. Jobs touch
 * disjoint byte ranges and join before returning. No persistent worker,
 * mutex, allocation, buffer identity or omitted bytes enter a snapshot.
 * Non-Android AArch64 uses serial memcpy: Pi 5 measurements found that workers contend
 * for shared memory bandwidth and increase large-copy time.
 * Call only for non-overlapping buffers, exactly like memcpy. */
static void obor_state_copy_heap(void *destination, const void *source, size_t size)
{
#if defined(_WIN32)
    if (size >= (32u << 20)) {
        SYSTEM_INFO info;
        GetSystemInfo(&info);
        unsigned count = info.dwNumberOfProcessors > 4 ? 4 : info.dwNumberOfProcessors;
        if (count > 1) {
            PTP_WORK work[3] = {0};
            obor_win_state_copy_job jobs[4];
            size_t chunk = (size / count) & ~(size_t)4095;
            unsigned i;
            for (i = 0; i < count; ++i) {
                jobs[i].destination = (unsigned char *)destination + i * chunk;
                jobs[i].source = (const unsigned char *)source + i * chunk;
                jobs[i].size = i + 1 == count ? size - i * chunk : chunk;
                if (i + 1 < count) {
                    work[i] = CreateThreadpoolWork(obor_win_state_copy_worker, &jobs[i], NULL);
                    if (work[i]) SubmitThreadpoolWork(work[i]);
                    else obor_win_state_copy_worker(NULL, &jobs[i], NULL);
                } else {
                    obor_win_state_copy_worker(NULL, &jobs[i], NULL);
                }
            }
            for (i = 0; i + 1 < count; ++i) {
                if (work[i]) {
                    WaitForThreadpoolWorkCallbacks(work[i], FALSE);
                    CloseThreadpoolWork(work[i]);
                }
            }
            return;
        }
    }
#endif
#if defined(__linux__) && (defined(__x86_64__) || defined(__ANDROID__))
    if (size >= (64u << 20)) {
        long cpus = sysconf(_SC_NPROCESSORS_ONLN);
        unsigned count = cpus > 4 ? 4 : cpus > 1 ? (unsigned)cpus : 1;
        if (count > 1) {
            pthread_t threads[3] = {0};
            int started[3];
            obor_state_copy_job jobs[4];
            size_t chunk = (size / count) & ~(size_t)4095;
            unsigned i;
            for (i = 0; i < count; ++i) {
                jobs[i].destination = (unsigned char *)destination + i * chunk;
                jobs[i].source = (const unsigned char *)source + i * chunk;
                jobs[i].size = i + 1 == count ? size - i * chunk : chunk;
                if (i + 1 < count) {
                    started[i] = pthread_create(&threads[i], NULL,
                                               obor_state_copy_worker, &jobs[i]) == 0;
                    if (!started[i])
                        obor_state_copy_worker(&jobs[i]);
                } else {
                    obor_state_copy_worker(&jobs[i]);
                }
            }
            for (i = 0; i + 1 < count; ++i)
                if (started[i])
                    pthread_join(threads[i], NULL);
            return;
        }
    }
#endif
    memcpy(destination, source, size);
}

#if defined(_WIN32)

/* Caller buffers are arbitrary and may have been modified since the last
 * save. Compare every byte before omitting an equal block; pointer identity
 * never substitutes for checking its contents. This reduces write traffic
 * for resource-heavy heaps without requiring frontend buffer ownership. */
static void obor_win_state_copy_checked(unsigned char *destination,
                                        const unsigned char *source, size_t size)
{
#if defined(__SSE2__)
    while (size >= 512) {
        __m128i a = _mm_setzero_si128(), b = a;
        size_t i;
        for (i = 0; i < 512; i += 32) {
            a = _mm_or_si128(a, _mm_xor_si128(
                _mm_loadu_si128((const __m128i *)(source + i)),
                _mm_loadu_si128((const __m128i *)(destination + i))));
            b = _mm_or_si128(b, _mm_xor_si128(
                _mm_loadu_si128((const __m128i *)(source + i + 16)),
                _mm_loadu_si128((const __m128i *)(destination + i + 16))));
        }
        if (_mm_movemask_epi8(_mm_cmpeq_epi8(
            _mm_or_si128(a, b), _mm_setzero_si128())) != 0xffff)
            memcpy(destination, source, 512);
        destination += 512;
        source += 512;
        size -= 512;
    }
#endif
    memcpy(destination, source, size);
}

static void CALLBACK obor_win_state_copy_and_pad_worker(PTP_CALLBACK_INSTANCE instance,
                                                        void *context, PTP_WORK work)
{
    obor_win_state_copy_job *job = (obor_win_state_copy_job *)context;
    (void)instance;
    (void)work;
    if (job->source)
        obor_win_state_copy_checked(job->destination, job->source, job->size);
    else
        obor_state_clear_padding_serial(job->destination, job->size);
}

/* Two disjoint operations share one bounded batch. The engine is parked;
 * all workers finish before returning, including on partial creation failure.
 * Return whether padding was also cleared. Smaller hosts/ranges retain the
 * ordinary copy and let the caller clear the tail separately. */
static int obor_win_state_copy_and_pad(void *destination, const void *source,
                                       size_t size, void *padding, size_t padding_size)
{
    if (size >= (32u << 20) && padding_size >= (16u << 20)) {
        SYSTEM_INFO info;
        GetSystemInfo(&info);
        if (info.dwNumberOfProcessors >= 8) {
            PTP_WORK work[7] = {0};
            obor_win_state_copy_job jobs[8];
            size_t chunk = (size / 4) & ~(size_t)4095;
            size_t pad_chunk = (padding_size / 4) & ~(size_t)511;
            unsigned i;
            for (i = 0; i < 8; ++i) {
                if (i < 4) {
                    jobs[i].destination = (unsigned char *)destination + i * chunk;
                    jobs[i].source = (const unsigned char *)source + i * chunk;
                    jobs[i].size = i == 3 ? size - i * chunk : chunk;
                } else {
                    unsigned at = i - 4;
                    jobs[i].destination = (unsigned char *)padding + at * pad_chunk;
                    jobs[i].source = NULL;
                    jobs[i].size = at == 3 ? padding_size - at * pad_chunk : pad_chunk;
                }
                if (i < 7) {
                    work[i] = CreateThreadpoolWork(obor_win_state_copy_and_pad_worker,
                                                   &jobs[i], NULL);
                    if (work[i]) SubmitThreadpoolWork(work[i]);
                    else obor_win_state_copy_and_pad_worker(NULL, &jobs[i], NULL);
                } else {
                    obor_win_state_copy_and_pad_worker(NULL, &jobs[i], NULL);
                }
            }
            for (i = 0; i < 7; ++i) {
                if (work[i]) {
                    WaitForThreadpoolWorkCallbacks(work[i], FALSE);
                    CloseThreadpoolWork(work[i]);
                }
            }
            return 1;
        }
    }
    obor_state_copy_heap(destination, source, size);
    return 0;
}

#endif

#endif
