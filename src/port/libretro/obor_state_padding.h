/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_PADDING_H
#define OBOR_STATE_PADDING_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#if defined(_WIN32)
#include <windows.h>
#endif
#if defined(_WIN32) && defined(__SSE2__)
#include <emmintrin.h>
#endif

/* The transport tail must be deterministic, even for a dirty caller-owned
 * buffer or a shrinking heap. Avoid writing already-zero reserve pages:
 * frontends commonly allocate zero-filled buffers, whose untouched pages
 * can stay physically shared. No remembered buffer pointers or sizes are
 * needed, so alternating, recycled and unaligned buffers are safe. */
static inline void obor_state_clear_padding_serial(void *data, size_t size)
{
    unsigned char *p = (unsigned char *)data;
    while (size >= 512) {
#if defined(_WIN32) && defined(__SSE2__)
        /* MinGW's -O2 vector cost model leaves the unaligned scalar loop
         * below unvectorized. Large games can have tens of MiB of reserve:
         * scanning that on every snapshot outweighed the saved BSS copy.
         * SSE2 is baseline on x86-64; unaligned loads also cover arbitrary
         * frontend buffers without reading beyond this complete block. */
        __m128i a = _mm_setzero_si128(), b = a;
        size_t i;
        for (i = 0; i < 512; i += 32) {
            a = _mm_or_si128(a, _mm_loadu_si128((const __m128i *)(p + i)));
            b = _mm_or_si128(b, _mm_loadu_si128((const __m128i *)(p + i + 16)));
        }
        int dirty = _mm_movemask_epi8(_mm_cmpeq_epi8(
            _mm_or_si128(a, b), _mm_setzero_si128())) != 0xffff;
#else
        uint64_t dirty = 0;
        size_t i;
        for (i = 0; i < 512; i += 8) {
            uint64_t word;
            memcpy(&word, p + i, sizeof(word));
            dirty |= word;
        }
#endif
        if (dirty)
            memset(p, 0, 512);
        p += 512;
        size -= 512;
    }
    while (size--) {
        if (*p) *p = 0;
        ++p;
    }
}

#if defined(_WIN32)
typedef struct {
    unsigned char *data;
    size_t size;
} obor_padding_job;

static void CALLBACK obor_padding_worker(PTP_CALLBACK_INSTANCE instance,
                                        void *context, PTP_WORK work)
{
    obor_padding_job *job = (obor_padding_job *)context;
    (void)instance;
    (void)work;
    obor_state_clear_padding_serial(job->data, job->size);
}
#endif

static inline void obor_state_clear_padding(void *data, size_t size)
{
#if defined(_WIN32)
    /* Large Windows games retain tens of MiB of growth reserve. A serial
     * scan evicts the engine's working set and dominates write-watch saves.
     * Split only that transport tail, after the engine snapshot is complete.
     * Jobs share no state, touch disjoint ranges and finish before returning:
     * no handles, threads or remembered buffers enter the snapshot format. */
    if (size >= (16u << 20)) {
        SYSTEM_INFO info;
        obor_padding_job jobs[7];
        PTP_WORK work[7] = {0};
        unsigned count = (unsigned)(size / (8u << 20));
        unsigned i;
        size_t chunk;
        GetSystemInfo(&info);
        if (count > 8) count = 8;
        if (count > info.dwNumberOfProcessors) count = info.dwNumberOfProcessors;
        if (count >= 2) {
            chunk = (size / count) & ~(size_t)511;
            for (i = 0; i < count - 1; ++i) {
                jobs[i].data = (unsigned char *)data + i * chunk;
                jobs[i].size = chunk;
                work[i] = CreateThreadpoolWork(obor_padding_worker, &jobs[i], NULL);
                if (work[i])
                    SubmitThreadpoolWork(work[i]);
                else
                    obor_state_clear_padding_serial(jobs[i].data, jobs[i].size);
            }
            obor_state_clear_padding_serial((unsigned char *)data + i * chunk,
                                            size - i * chunk);
            for (i = 0; i < count - 1; ++i) {
                if (work[i]) {
                    WaitForThreadpoolWorkCallbacks(work[i], FALSE);
                    CloseThreadpoolWork(work[i]);
                }
            }
            return;
        }
    }
#endif
    obor_state_clear_padding_serial(data, size);
}
#endif
