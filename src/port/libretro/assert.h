/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Like the C assertion header, this wrapper can be included again after
 * NDEBUG changes. Engine modules that include it after globals.h retain
 * their C-style diagnostic and use the controlled engine stop. */
#include_next <assert.h>

#if defined(OBOR_CONTROLLED_ASSERTIONS) && OBOR_CONTROLLED_ASSERTIONS
#ifdef __cplusplus
extern "C" {
#endif
void obor_port_assert(int value, const char *assertion, const char *func,
                      const char *file, int line);
#ifdef __cplusplus
}
#endif
#undef assert
#ifdef NDEBUG
#define assert(x) ((void)0)
#else
#define assert(x) obor_port_assert((x) ? 1 : 0, #x, __func__, __FILE__, __LINE__)
#endif
#endif
