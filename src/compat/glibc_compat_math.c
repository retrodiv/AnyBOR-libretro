/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* Compatibility wrappers for Linux cores built on a newer glibc than the
   target frontend. glibc 2.41+ re-versioned selected float libm symbols;
   References to a newer version of acosf (for example GLIBC_2.43) can
   make dlopen fail on older hosts before libretro starts. The optional
   build-time glibc ceiling checks the resulting binary's requirements.

   The build links this object into Linux cores together with --wrap flags.
   The wrappers deliberately call the base symbol version available on the
   target architecture. */
#if defined(__linux__) && !defined(__ANDROID__)
# ifndef _GNU_SOURCE
#  define _GNU_SOURCE 1
# endif
# include <features.h>
# if defined(__GLIBC__)
#  if defined(__x86_64__)
#   define OBOR_GLIBC_MATH_VER "GLIBC_2.2.5"
#  elif defined(__aarch64__)
#   define OBOR_GLIBC_MATH_VER "GLIBC_2.17"
#  elif defined(__arm__)
#   define OBOR_GLIBC_MATH_VER "GLIBC_2.4"
#  elif defined(__riscv) && __riscv_xlen == 64
#   define OBOR_GLIBC_MATH_VER "GLIBC_2.27"
#  endif
#  ifdef OBOR_GLIBC_MATH_VER
extern float obor_glibc_acosf(float);
extern float obor_glibc_asinf(float);
extern float obor_glibc_sqrtf(float);

__asm__(".symver obor_glibc_acosf,acosf@" OBOR_GLIBC_MATH_VER);
__asm__(".symver obor_glibc_asinf,asinf@" OBOR_GLIBC_MATH_VER);
__asm__(".symver obor_glibc_sqrtf,sqrtf@" OBOR_GLIBC_MATH_VER);

float __wrap_acosf(float x) { return obor_glibc_acosf(x); }
float __wrap_asinf(float x) { return obor_glibc_asinf(x); }
float __wrap_sqrtf(float x) { return obor_glibc_sqrtf(x); }
#  endif
# endif
#endif
