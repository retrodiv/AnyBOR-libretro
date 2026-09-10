/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * AnyBOR adaptations: retrodiv <retrodiv@proton.me>
 * Adapted for AnyBOR: compiler and buffer VM only. */
#ifndef OBOR_TRANSFORM_VM_H
#define OBOR_TRANSFORM_VM_H
#include <stddef.h>
#include <stdint.h>
#define OBOR_TRANSFORM_MAX_CONFIG_BYTES 524288u
#define OBOR_TRANSFORM_MAX_PROGRAM_BYTES 12288u
#define OBOR_TRANSFORM_MAX_PARAMETER_BYTES 4096u
#define OBOR_TRANSFORM_MAX_METADATA_BYTES 256u
#define OBOR_TRANSFORM_MAX_PROGRAMS 16u
#define OBOR_TRANSFORM_MAX_PIPELINE_STEPS 16u
#define OBOR_TRANSFORM_SCRATCH_BYTES 65536u
#define OBOR_TRANSFORM_MAX_INPUT_BYTES UINT64_C(1073741824)
#define OBOR_TRANSFORM_MAX_STEPS (UINT64_C(1000000)+OBOR_TRANSFORM_MAX_INPUT_BYTES*128u)
#define OBOR_TRANSFORM_INSTRUCTION_BYTES 12u

/* The internal instruction representation is twelve bytes: opcode, destination, left, right,
 * followed by an unsigned little-endian 64-bit immediate. See CONTENT_TRANSFORMS.md.
 * None of these instructions performs a format-specific operation. */
enum {
  OBOR_TRANSFORM_RETURN=0, OBOR_TRANSFORM_REJECT=1,
  OBOR_TRANSFORM_CONSTANT=2, OBOR_TRANSFORM_MOVE=3,
  OBOR_TRANSFORM_ADD=4, OBOR_TRANSFORM_SUBTRACT=5,
  OBOR_TRANSFORM_MULTIPLY=6, OBOR_TRANSFORM_DIVIDE=7,
  OBOR_TRANSFORM_REMAINDER=8, OBOR_TRANSFORM_AND=9,
  OBOR_TRANSFORM_OR=10, OBOR_TRANSFORM_XOR=11,
  OBOR_TRANSFORM_SHIFT_LEFT=12, OBOR_TRANSFORM_SHIFT_RIGHT=13,
  OBOR_TRANSFORM_EQUAL=14, OBOR_TRANSFORM_LESS=15,
  OBOR_TRANSFORM_LOAD8=16, OBOR_TRANSFORM_LOAD32=17,
  OBOR_TRANSFORM_LOAD64=18, OBOR_TRANSFORM_STORE8=19,
  OBOR_TRANSFORM_STORE32=20, OBOR_TRANSFORM_STORE64=21,
  OBOR_TRANSFORM_JUMP=22, OBOR_TRANSFORM_JUMP_ZERO=23,
  OBOR_TRANSFORM_JUMP_NONZERO=24
};


#ifdef __cplusplus
extern "C" {
#endif
int obor_content_transform_execute(const void *,size_t,const void *,size_t,const void *,size_t,const void *,size_t,uint64_t,uint8_t **,size_t *,char *,size_t);
int obor_content_transform_compile(const char *,size_t,size_t *,uint8_t **,size_t *,uint8_t **,size_t *,char *,size_t);
#ifdef __cplusplus
}
#endif
#endif
