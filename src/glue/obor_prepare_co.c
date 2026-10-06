/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * The included pinned libco implementation retains its upstream license. */
/* Independent of engine-local contexts; destroyed before engine boot. */
#define co_active obor_prepare_co_active
#define co_derive obor_prepare_co_derive
#define co_switch obor_prepare_co_switch
#define co_create obor_prepare_co_create
#define co_delete obor_prepare_co_delete
#define co_serializable obor_prepare_co_serializable
#include "libco/libco.c"
