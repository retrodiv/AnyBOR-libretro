/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_BLOCK_WORKER_POLICY_H
#define OBOR_BLOCK_WORKER_POLICY_H
#include <stdint.h>

/* Consider the pipeline when codec work exceeds 5 ms (30% of a 60 Hz frame)
 * and can fill at least two 32-block batches. A block count alone misses the
 * cost of proving and reading source memory. Use owner plus helper CPU time,
 * excluding waits, so parallel speedup does not itself disable the next call.
 * This is a work estimate, never a content selector or a retention condition.
 * A sudden workload change can use the less efficient encoder once; both
 * encoders produce the same complete image. */
#define OBOR_BLOCK_WORKER_MIN_BLOCKS 64U
#define OBOR_BLOCK_WORKER_MIN_CPU_NS UINT64_C(5000000)
typedef struct {
    uint32_t changed_blocks[2];
    uint64_t cpu_ns[2];
} obor_block_worker_policy;

static inline void obor_block_worker_policy_reset(obor_block_worker_policy *policy)
{
    policy->changed_blocks[0] = policy->changed_blocks[1] = 0;
    policy->cpu_ns[0] = policy->cpu_ns[1] = 0;
}

static inline int obor_block_worker_policy_due(const obor_block_worker_policy *policy,
                                               int preparation)
{
    unsigned phase = preparation != 0;
    return policy->changed_blocks[phase] >= OBOR_BLOCK_WORKER_MIN_BLOCKS &&
           policy->cpu_ns[phase] >= OBOR_BLOCK_WORKER_MIN_CPU_NS;
}

static inline void obor_block_worker_policy_observe(obor_block_worker_policy *policy,
                                                   int preparation, uint32_t blocks,
                                                   uint64_t cpu_ns)
{
    /* The final serialization often changes only its header after early
     * preparation. It must not replace the estimate for the next preparation.
     * A missing clock yields zero cost and selects the complete serial path.
     * These estimates are disposable performance metadata, not history. */
    policy->changed_blocks[preparation != 0] = blocks;
    policy->cpu_ns[preparation != 0] = cpu_ns;
}
#endif
