/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdio.h>
#include "obor_capture_cadence.h"
int main(void)
{
    obor_capture_cadence c;
    obor_capture_cadence_reset(&c);
    assert(!obor_capture_cadence_due(&c,10));
    obor_capture_cadence_observe(&c,10);
    obor_capture_cadence_observe(&c,10); /* Repeated manual request. */
    obor_capture_cadence_observe(&c,20);
    assert(!obor_capture_cadence_due(&c,30));
    obor_capture_cadence_observe(&c,30);
    assert(!obor_capture_cadence_due(&c,39));
    assert(obor_capture_cadence_due(&c,40));
    assert(!obor_capture_cadence_due(&c,40));
    assert(!obor_capture_cadence_due(&c,50)); /* Captures stopped. */
    obor_capture_cadence_observe(&c,50); /* Interval changed. */
    assert(!obor_capture_cadence_due(&c,70));
    obor_capture_cadence_observe(&c,70);
    assert(!obor_capture_cadence_due(&c,91)); /* A missed prediction expires. */
    obor_capture_cadence_observe(&c,90);
    assert(obor_capture_cadence_due(&c,110));
    obor_capture_cadence_observe(&c,5); /* Reset/backward frame count. */
    assert(!obor_capture_cadence_due(&c,25));
    obor_capture_cadence_observe(&c,1000); /* Long manual-save gap. */
    assert(!obor_capture_cadence_due(&c,1995));
    obor_capture_cadence_reset(&c);
    for(uint64_t f=1; f<=4; ++f) obor_capture_cadence_observe(&c,f);
    assert(obor_capture_cadence_due(&c,5)); /* g1 remains valid. */
    obor_capture_cadence_reset(&c);
    obor_capture_cadence_observe(&c,UINT64_MAX-21);
    obor_capture_cadence_observe(&c,UINT64_MAX-11);
    obor_capture_cadence_observe(&c,UINT64_MAX-1);
    assert(!obor_capture_cadence_due(&c,UINT64_MAX));
    puts("period_changes=1 repeated_requests=1 missed_prediction=1 reset=1 overflow=1");
    return 0;
}
