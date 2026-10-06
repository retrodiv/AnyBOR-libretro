/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PREPARE_PROGRESS_H
#define OBOR_PREPARE_PROGRESS_H

/* Content helpers also run in standalone tools. A frontend may install a
 * cooperative checkpoint; false requests normal cleanup and cancellation. */
static int (*obor_prepare_progress)(void);
static int obor_prepare_checkpoint(void)
{
    return !obor_prepare_progress || obor_prepare_progress();
}
#endif
