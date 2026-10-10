/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_block_state.h"
#include "obor_block_worker_policy.h"
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int deny_thread, deny_alloc, created, joined, active, maximum_active;
static int deny_cpu_clock;
int __real_clock_gettime(clockid_t, struct timespec *);
int __wrap_clock_gettime(clockid_t clock, struct timespec *value)
{
    if (deny_cpu_clock && clock == CLOCK_THREAD_CPUTIME_ID) { errno = EINVAL; return -1; }
    return __real_clock_gettime(clock, value);
}
static void *(*thread_function)(void *);
static void *thread_argument;
int __real_pthread_create(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
int __real_pthread_join(pthread_t, void **);
static void *observed_thread(void *unused)
{
    (void)unused;
    int count = __atomic_add_fetch(&active, 1, __ATOMIC_SEQ_CST);
    if (count > maximum_active) maximum_active = count;
    void *result = thread_function(thread_argument);
    __atomic_sub_fetch(&active, 1, __ATOMIC_SEQ_CST);
    return result;
}
int __wrap_pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                         void *(*function)(void *), void *argument)
{
    assert(!__atomic_load_n(&active, __ATOMIC_SEQ_CST));
    if (deny_thread) return EAGAIN;
    thread_function = function; thread_argument = argument;
    int result = __real_pthread_create(thread, attr, observed_thread, NULL);
    if (!result) ++created;
    return result;
}
int __wrap_pthread_join(pthread_t thread, void **result)
{
    int error = __real_pthread_join(thread, result);
    if (!error) ++joined;
    return error;
}
static void *alloc(size_t n, size_t s)
{ if (deny_alloc) { deny_alloc = 0; return NULL; } return calloc(n, s); }
static obor_block_allocator allocator = {.calloc=alloc,.realloc=realloc,.free=free};
typedef struct { unsigned char *data; uint32_t length; int scratch; uint32_t fail_at; } input;
static const void *read_source(void *opaque, uint32_t offset, uint32_t size, void *scratch)
{
    input *in = opaque;
    assert(offset <= in->length && size <= in->length - offset);
    if (in->fail_at && offset >= in->fail_at) return NULL;
    if (in->scratch) { memcpy(scratch, in->data + offset, size); return scratch; }
    return in->data + offset;
}
static void equal_images(obor_block_state *a, obor_block_state *b, obor_block_state *cold, input *in)
{
    uint32_t na, nb, nc;
    const void *pa = obor_block_state_image(a, &na), *pb = obor_block_state_image(b, &nb);
    assert(pa && pb && na == nb && !memcmp(pa, pb, na));
    obor_block_state_forget(cold);
    assert(obor_block_state_decode(cold, pb, nb));
    const void *raw = obor_block_state_raw(cold, &nc);
    assert(raw && nc == in->length && !memcmp(raw, in->data, nc));
    assert(!__atomic_load_n(&active, __ATOMIC_SEQ_CST) && created == joined);
}
static uint32_t random_word(uint32_t *s)
{ uint32_t x=*s;x^=x<<13;x^=x>>17;x^=x<<5;return *s=x; }
static uint64_t clock_calls;
static uint64_t test_clock(void) { return ++clock_calls; }

int main(int argc, char **argv)
{
    deny_thread = argc > 1 && !strcmp(argv[1], "--deny-thread");
    deny_cpu_clock = argc > 1 && !strcmp(argv[1], "--deny-cpu-clock");
    const uint32_t maximum = 4U << 20;
    input in = {malloc(maximum), maximum, 0, 0}; assert(in.data);
    uint32_t seed = 0x735192;
    for (uint32_t i=0;i<maximum;++i) in.data[i]=(unsigned char)((i/71+i/4096)%17);
    obor_block_source source = {&in, read_source, NULL};
    obor_block_state *serial=obor_block_state_create(&allocator);
    obor_block_state *worker=obor_block_state_create(&allocator);
    obor_block_state *cold=obor_block_state_create(&allocator);
    assert(serial && worker && cold);
    obor_block_state_set_worker(worker, 1);
    assert(obor_block_state_encode(serial,&source,in.length));
    assert(obor_block_state_encode(worker,&source,in.length));
    equal_images(serial,worker,cold,&in);
    unsigned char *old_images[4], *old_raw[4];
    uint32_t old_sizes[4], old_lengths[4];
    unsigned saved=0;
    int (*encoders[])(obor_block_state *, const obor_block_source *, uint32_t) = {
        obor_block_state_encode, obor_block_state_encode_fast, obor_block_state_encode_mutable
    };
    unsigned threaded_captures=0;
    for (unsigned round=0;round<24;++round) {
        in.scratch = round % 2;
        in.length = round % 4 == 0 ? maximum - 123457 : maximum;
        for (uint32_t i=0;i<in.length;i+=97) in.data[i]=(unsigned char)random_word(&seed);
        /* First workspace allocation fails: the current frame must still use
         * the complete serial path, without changing state bytes. */
        assert(encoders[round % 3](serial,&source,in.length));
        if (!round) deny_alloc=1;
        assert(encoders[round % 3](worker,&source,in.length));
        equal_images(serial,worker,cold,&in);
        if (round==0 || round==7 || round==15 || round==23) {
            const void *image=obor_block_state_image(worker,old_sizes+saved);
            old_images[saved]=malloc(old_sizes[saved]);old_raw[saved]=malloc(in.length);
            assert(old_images[saved] && old_raw[saved]);
            memcpy(old_images[saved],image,old_sizes[saved]);
            memcpy(old_raw[saved],in.data,in.length);old_lengths[saved]=in.length;++saved;
        }
        obor_block_changes changes; obor_block_state_changes(worker,&changes);
        if (deny_cpu_clock) {
            assert(!changes.owner_cpu_ns && !changes.helper_cpu_ns);
            assert(!obor_block_state_cpu_cost(worker));
        } else {
            assert(changes.owner_cpu_ns);
            assert((changes.helper_cpu_ns != 0) == (changes.worker_threads != 0));
            assert(obor_block_state_cpu_cost(worker) == changes.owner_cpu_ns + changes.helper_cpu_ns);
        }
        assert(changes.worker_threads <= 1);
        if (changes.worker_threads) {
            ++threaded_captures; assert(changes.worker_blocks >= 32);
        }
    }
    assert(deny_thread ? !threaded_captures : threaded_captures >= 20);
    for (unsigned i=saved;i-- > 0;) {
        obor_block_state_forget(cold);
        assert(obor_block_state_decode(cold,old_images[i],old_sizes[i]));
        uint32_t length;const void *raw=obor_block_state_raw(cold,&length);
        assert(length==old_lengths[i] && !memcmp(raw,old_raw[i],length));
        free(old_images[i]);free(old_raw[i]);
    }
    /* An unchanged image spawns no thread. A caller-supplied detailed clock
     * need not be thread safe, so its diagnostic path must stay serial. */
    int before=created;
    assert(obor_block_state_encode(worker,&source,in.length) && created==before);
    for (uint32_t i=0;i<in.length;i+=4096) in.data[i]^=0x7f;
    obor_block_state_set_clock(worker,test_clock);
    assert(obor_block_state_encode(serial,&source,in.length));
    assert(obor_block_state_encode(worker,&source,in.length));
    equal_images(serial,worker,cold,&in);
    assert(created==before && clock_calls);obor_block_state_set_clock(worker,NULL);
    /* Fail a source read after more than a submitted batch. Join first, then
     * invalidate the incomplete cache. Neither old batch nor old raw bytes
     * may make a later cold reconstruction succeed incorrectly. */
    memset(in.data,0,in.length); in.fail_at=1U<<20;
    assert(!obor_block_state_encode(worker,&source,in.length));
    assert(!obor_block_state_image(worker,NULL));
    assert(!obor_block_state_cpu_cost(worker));
    assert(!active && created==joined);
    in.fail_at=0;obor_block_state_forget(serial);
    assert(obor_block_state_encode(serial,&source,in.length));
    assert(obor_block_state_encode(worker,&source,in.length));
    equal_images(serial,worker,cold,&in);
    /* A preparation and its final header update have separate workload
     * estimates. Exercise real encodes across light/heavy/light transitions,
     * checking independent cold decodes and byte identity on both paths. */
    obor_block_worker_policy policy = {0};
    const uint32_t loads[] = {56, 96, 96, 180, 40, 40};
    /* Inject cost estimates to make policy assertions independent of machine
     * speed. Actual encode CPU measurements are checked separately above. */
    const uint64_t costs[] = {3000000, 3000000, 7000000, 7000000, 7000000, 0};
    const int expected[] = {0, 0, 0, 1, 1, 0};
    for (unsigned pass = 0; pass < sizeof(loads) / sizeof(loads[0]); ++pass) {
        for (uint32_t block = 0; block < loads[pass]; ++block)
            in.data[block * OBOR_BLOCK_STATE_BLOCK] ^= 0x5a;
        int due = obor_block_worker_policy_due(&policy, 1);
        assert(due == expected[pass]);
        obor_block_state_set_worker(worker, due);
        assert(obor_block_state_encode(serial, &source, in.length));
        assert(obor_block_state_encode(worker, &source, in.length));
        equal_images(serial, worker, cold, &in);
        assert(obor_block_state_workload(worker) == loads[pass]);
        obor_block_changes work; obor_block_state_changes(worker, &work);
        assert(work.worker_threads == (unsigned)(due && !deny_thread));
        obor_block_worker_policy_observe(&policy, 1, obor_block_state_workload(worker), costs[pass]);

        in.data[0] ^= 1;
        assert(!obor_block_worker_policy_due(&policy, 0));
        obor_block_state_set_worker(worker, 0);
        assert(obor_block_state_encode(serial, &source, in.length));
        assert(obor_block_state_encode(worker, &source, in.length));
        equal_images(serial, worker, cold, &in);
        assert(obor_block_state_workload(worker) == 1);
        obor_block_worker_policy_observe(&policy, 0, obor_block_state_workload(worker), 100000);
        assert(obor_block_worker_policy_due(&policy, 1) == (pass == 2 || pass == 3));
    }
    obor_block_worker_policy_observe(&policy, 1, 256, 0);
    assert(!obor_block_worker_policy_due(&policy, 1));
    obor_block_worker_policy_observe(&policy, 1, 64, 4999999);
    assert(!obor_block_worker_policy_due(&policy, 1));
    obor_block_worker_policy_observe(&policy, 1, 64, 5000000);
    assert(obor_block_worker_policy_due(&policy, 1));
    obor_block_worker_policy_reset(&policy);
    assert(!obor_block_worker_policy_due(&policy, 0) && !obor_block_worker_policy_due(&policy, 1));
    obor_block_state_set_worker(worker, 1);
    /* Slot exhaustion must drain the helper before the bounded repack, and
     * failure of that repack must leave no restorable partial image. */
    obor_block_state *small=obor_block_state_create_sized(&allocator,4U<<20);assert(small);
    obor_block_state_set_worker(small,1);
    assert(obor_block_state_encode(small,&source,in.length));
    for (uint32_t i=0;i<in.length;++i) in.data[i]=(unsigned char)random_word(&seed);
    assert(!obor_block_state_encode(small,&source,in.length));
    assert(!obor_block_state_image(small,NULL) && !active && created==joined);
    assert(!obor_block_state_cpu_cost(small));
    obor_block_state_destroy(small);
    obor_block_state_destroy(serial);obor_block_state_destroy(worker);obor_block_state_destroy(cold);
    free(in.data); assert(maximum_active <= 1 && created==joined);
    printf("equivalent_images=39 cold_decodes=43 adaptive_phases=6 old_independent=4 overflow_drained=1 joined_helpers=%d maximum_active=%d failure_drained=1 denied=%d denied_clock=%d\n",created,maximum_active,deny_thread,deny_cpu_clock);
    return 0;
}
