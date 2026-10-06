/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PREPARE_CO_H
#define OBOR_PREPARE_CO_H
#ifdef __cplusplus
extern "C" {
#endif
void *obor_prepare_co_active(void);
void *obor_prepare_co_derive(void *memory, unsigned size, void (*entry)(void));
void obor_prepare_co_switch(void *context);
#ifdef __cplusplus
}
#endif
#endif
