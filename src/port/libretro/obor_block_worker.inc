/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Private synchronous encoder pipeline; included after the serial helpers. */
#if defined(__linux__)
#include <pthread.h>
#include <unistd.h>

#define BW_BATCH 32U
typedef struct {
    uint32_t index, length, codec, crc;
    int stored;
    unsigned char raw[BS_BLOCK], encoded[BS_BLOCK + 1024];
} block_worker_job;
typedef struct {
    uint32_t count;
    block_worker_job jobs[BW_BATCH];
} block_worker_batch;
typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    pthread_t thread;
    obor_block_state *state;
    block_worker_batch *pending;
    int stop, active, attempted;
    uint64_t cpu_ns;
    block_worker_batch batches[2];
} block_worker;

/* Only the helper uses the deflater while it exists. Source callbacks, pool
 * mutation, index publication and decoded-cache writes stay on the owner.
 * Every input is copied before submission: source scratch/direct views never
 * cross threads. The two batches use less than 2.1 MiB, independent of content
 * size. They are scratch, not a snapshot cache: counts are invalidated before
 * return, and no restore ever consults them. */
static void block_worker_compress(block_worker *worker, block_worker_batch *batch)
{
    for (uint32_t i = 0; i < batch->count; ++i) {
        block_worker_job *job = batch->jobs + i;
        job->stored = job->codec == BS_RAW ? (int)job->length :
            job->codec == BS_LZ4 ? LZ4_compress_default((const char *)job->raw,
                (char *)job->encoded, (int)job->length, sizeof(job->encoded)) :
            block_deflate(worker->state, job->raw, job->length,
                job->encoded, sizeof(job->encoded));
        if (job->stored <= 0) continue;
        if ((uint32_t)job->stored >= job->length) {
            job->stored = (int)job->length;
            job->codec = BS_RAW;
            memcpy(job->encoded, job->raw, job->length);
        }
        job->crc = obor_block_crc32(0, job->raw, job->length);
    }
}

static void *block_worker_main(void *opaque)
{
    block_worker *worker = opaque;
    uint64_t begin = block_cpu_now();
    pthread_mutex_lock(&worker->mutex);
    for (;;) {
        while (!worker->pending && !worker->stop)
            pthread_cond_wait(&worker->condition, &worker->mutex);
        if (worker->stop) break;
        block_worker_batch *batch = worker->pending;
        pthread_mutex_unlock(&worker->mutex);
        block_worker_compress(worker, batch);
        pthread_mutex_lock(&worker->mutex);
        worker->pending = NULL;
        pthread_cond_broadcast(&worker->condition);
    }
    pthread_mutex_unlock(&worker->mutex);
    worker->cpu_ns = block_cpu_elapsed(begin);
    return NULL;
}

static void block_worker_wait(block_worker *worker)
{
    if (!worker->active) return;
    pthread_mutex_lock(&worker->mutex);
    while (worker->pending)
        pthread_cond_wait(&worker->condition, &worker->mutex);
    pthread_mutex_unlock(&worker->mutex);
}

static void block_worker_submit(block_worker *worker, block_worker_batch *batch)
{
    if (!worker->attempted && batch->count == BW_BATCH) {
        worker->attempted = 1;
        worker->active = pthread_create(&worker->thread, NULL,
                                         block_worker_main, worker) == 0;
        if (worker->active) ++worker->state->work.worker_threads;
    }
    if (!worker->active) {
        block_worker_compress(worker, batch);
        return;
    }
    /* The caller drained the previous batch before submitting this one. */
    pthread_mutex_lock(&worker->mutex);
    worker->pending = batch;
    worker->state->work.worker_blocks += batch->count;
    pthread_cond_broadcast(&worker->condition);
    pthread_mutex_unlock(&worker->mutex);
}

static void block_worker_finish(block_worker *worker)
{
    block_worker_wait(worker);
    if (worker->active) {
        pthread_mutex_lock(&worker->mutex);
        worker->stop = 1;
        pthread_cond_broadcast(&worker->condition);
        pthread_mutex_unlock(&worker->mutex);
        pthread_join(worker->thread, NULL);
        worker->state->work.helper_cpu_ns = worker->cpu_ns;
    }
    worker->active = 0;
    worker->pending = NULL;
    worker->batches[0].count = worker->batches[1].count = 0;
    pthread_cond_destroy(&worker->condition);
    pthread_mutex_destroy(&worker->mutex);
}

/* Preserve serial block order, slot placement and bytes. Completion order can
 * never perturb the frontend's delta stream. Return -1 for the existing
 * bounded DEFLATE repack, 0 for failure, 1 for success. */
static int block_worker_commit(obor_block_state *state, block_worker_batch *batch)
{
    block_entry *entries = (block_entry *)(state->image + sizeof(block_header));
    for (uint32_t i = 0; i < batch->count; ++i) {
        block_worker_job *job = batch->jobs + i;
        block_entry *entry = entries + job->index;
        if (job->stored <= 0) return 0;
        uint32_t capacity = ((uint32_t)job->stored + BS_ALIGN - 1) / BS_ALIGN * BS_ALIGN;
        if (entry->capacity < capacity) {
            if (!block_release_slot(state, entry)) return 0;
            entry->offset = block_reserve_slot(state, capacity);
            if (!entry->offset) return -1;
            entry->capacity = capacity;
        }
        memcpy(state->image + entry->offset, job->encoded, (size_t)job->stored);
        memset(state->image + entry->offset + job->stored, 0,
                entry->capacity - (uint32_t)job->stored);
        entry->stored = (uint32_t)job->stored;
        entry->raw = job->length;
        entry->codec = job->codec;
        entry->crc = job->crc;
        memcpy(state->raw + job->index * BS_BLOCK, job->raw, job->length);
        block_mark_changed(state, job->index);
    }
    batch->count = 0;
    return 1;
}

/* -1 means no attempt: use the ordinary serial encoder. Once work starts,
 * every exit drains and joins the sole helper before touching engine state,
 * invalidating/repacking the cache, or returning to the caller. */
static int block_encode_worker(obor_block_state *state,
    const obor_block_source *source, uint32_t raw_size, int initial_codec, int update_codec)
{
    if (sysconf(_SC_NPROCESSORS_ONLN) < 2) return -1;
    if (!state->worker_workspace)
        state->worker_workspace = state->allocator.calloc(1, sizeof(block_worker));
    block_worker *worker = state->worker_workspace;
    if (!worker) return -1;
    worker->state = state;
    worker->pending = NULL;
    worker->stop = worker->active = worker->attempted = 0;
    worker->cpu_ns = 0;
    worker->batches[0].count = worker->batches[1].count = 0;
    if (pthread_mutex_init(&worker->mutex, NULL)) return -1;
    if (pthread_cond_init(&worker->condition, NULL)) {
        pthread_mutex_destroy(&worker->mutex);
        return -1;
    }
    int result = 0, pending = -1;
    unsigned current = 0;
    memset(&state->work, 0, sizeof(state->work));
    memset(&state->timing, 0, sizeof(state->timing));
    if (!block_reserve_raw(state, raw_size)) goto finish;
    uint32_t count = (raw_size + BS_BLOCK - 1) / BS_BLOCK;
    uint32_t old_count = (state->raw_size + BS_BLOCK - 1) / BS_BLOCK;
    block_entry *entries = (block_entry *)(state->image + sizeof(block_header));
    unsigned char scratch[BS_BLOCK];
    memset(state->changed, 0, sizeof(state->changed));
    for (uint32_t i = count; i < old_count; ++i) {
        if (!block_release_slot(state, entries + i)) goto finish;
        block_mark_changed(state, i);
    }
    for (uint32_t i = 0; i < count; ++i) {
        uint32_t proven_group = block_proven_group(state, source, i, raw_size);
        if (proven_group) { i += proven_group - 1; continue; }
        uint32_t offset = i * BS_BLOCK, length = raw_size - offset;
        if (length > BS_BLOCK) length = BS_BLOCK;
        block_entry *entry = entries + i;
        int existing = state->valid && entry->raw == length &&
                       offset + length <= state->raw_size;
        if (existing && source->unchanged &&
            source->unchanged(source->context, offset, length)) {
            ++state->work.proven_blocks;
            continue;
        }
        const void *raw = source->read(source->context, offset, length, scratch);
        if (!raw) { result = 0; goto finish; }
        ++state->work.read_blocks;
        state->work.read_bytes += length;
        if (existing && !memcmp(raw, state->raw + offset, length)) {
            ++state->work.equal_blocks;
            continue;
        }
        block_worker_batch *batch = worker->batches + current;
        block_worker_job *job = batch->jobs + batch->count++;
        job->index = i; job->length = length;
        job->codec = (uint32_t)(existing ? update_codec : initial_codec);
        memcpy(job->raw, raw, length);
        if (batch->count == BW_BATCH) {
            if (pending >= 0) {
                block_worker_wait(worker);
                result = block_worker_commit(state, worker->batches + pending);
                if (result != 1) goto finish;
            }
            block_worker_submit(worker, batch);
            pending = (int)current;
            current ^= 1;
        }
    }
    if (pending >= 0) {
        block_worker_wait(worker);
        result = block_worker_commit(state, worker->batches + pending);
        if (result != 1) goto finish;
    }
    if (worker->batches[current].count) {
        block_worker_submit(worker, worker->batches + current);
        block_worker_wait(worker);
        result = block_worker_commit(state, worker->batches + current);
        if (result != 1) goto finish;
    }
    result = block_compact(state, count);
    if (result) {
        block_header header = {OBOR_BLOCK_STATE_MAGIC, BS_VERSION, BS_BLOCK,
                               count, raw_size, state->high, {0, 0}};
        memcpy(state->image, &header, sizeof(header));
        state->raw_size = raw_size;
        state->valid = 1;
    }
finish:
    block_worker_finish(worker);
    if (result == 1) return 1;
    obor_block_state_forget(state);
    if (result == -1) {
        ++state->work.repacks;
        return block_encode(state, source, raw_size, 0, BS_DEFLATE, update_codec);
    }
    return 0;
}
#endif
