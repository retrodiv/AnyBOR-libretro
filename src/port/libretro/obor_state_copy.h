/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_COPY_H
#define OBOR_STATE_COPY_H

#include <stddef.h>
#include <string.h>

#if defined(__linux__) && !defined(__ANDROID__)
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
 * Large heaps benefit from bounded parallel copies on Linux. Jobs touch
 * disjoint byte ranges and join before returning. No persistent worker,
 * mutex, allocation, buffer identity or omitted bytes enter a snapshot.
 * Call only for non-overlapping buffers, exactly like memcpy. */
static void obor_state_copy_heap(void *destination, const void *source, size_t size)
{
#if defined(__linux__) && !defined(__ANDROID__)
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

#endif
