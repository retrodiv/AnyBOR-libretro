/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * AnyBOR adaptations: retrodiv <retrodiv@proton.me>
 * Adapted for AnyBOR: standalone bounded byte-buffer interpreter. */
#include "obor_transform_vm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail(char *error,size_t size,const char *message){
  if(error && size) snprintf(error,size,"content transform: %s",message);
  return 0;
}

static uint64_t read_le(const uint8_t *p,unsigned width){
  uint64_t value=0;
  for(unsigned i=0;i<width;i++) value|=(uint64_t)p[i]<<(8u*i);
  return value;
}

static int valid_program(const uint8_t *code,size_t size){
  if(!code || !size || size>OBOR_TRANSFORM_MAX_PROGRAM_BYTES ||
     size%OBOR_TRANSFORM_INSTRUCTION_BYTES) return 0;
  size_t count=size/OBOR_TRANSFORM_INSTRUCTION_BYTES;
  for(size_t i=0;i<count;i++){
    const uint8_t *p=code+i*OBOR_TRANSFORM_INSTRUCTION_BYTES;
    unsigned op=p[0],d=p[1],a=p[2],b=p[3];
    uint64_t imm=read_le(p+4,8);
    if(op>OBOR_TRANSFORM_JUMP_NONZERO || d>=32 || a>=32 || b>=32) return 0;
    if(op==OBOR_TRANSFORM_CONSTANT){ if(a || b) return 0; }
    else if(op>=OBOR_TRANSFORM_LOAD8 && op<=OBOR_TRANSFORM_STORE64){
      if(b>=5 || (op>=OBOR_TRANSFORM_STORE8 && b!=1 && b!=3)) return 0;
    } else if(op>=OBOR_TRANSFORM_JUMP){
      if(imm>=count || d || b || (op==OBOR_TRANSFORM_JUMP && a)) return 0;
    } else {
      if(imm) return 0;
      if(op==OBOR_TRANSFORM_REJECT && (d || a || b)) return 0;
      if(op==OBOR_TRANSFORM_RETURN && d>1u) return 0;
      if(op==OBOR_TRANSFORM_MOVE && b) return 0;
    }
  }
  return 1;
}

int obor_content_transform_execute(const void *program,size_t program_size,
                                     const void *parameters,size_t parameter_size,
                                     const void *input,size_t input_size,
                                     const void *metadata,size_t metadata_size,uint64_t step_limit,
                                     uint8_t **output,size_t *output_size,
                                     char *error,size_t error_size){
  if(error && error_size) error[0]=0;
  if(output) *output=NULL;
  if(output_size) *output_size=0;
  if(!output || !output_size || (input_size && !input) ||
     (parameter_size && !parameters) || input_size>OBOR_TRANSFORM_MAX_INPUT_BYTES ||
     (metadata_size && !metadata) || metadata_size>OBOR_TRANSFORM_MAX_METADATA_BYTES ||
     parameter_size>OBOR_TRANSFORM_MAX_PARAMETER_BYTES ||
     !valid_program((const uint8_t*)program,program_size))
    return fail(error,error_size,"invalid program or buffer");
  uint8_t *work=(uint8_t*)malloc(input_size?input_size:1u);
  uint8_t *scratch=(uint8_t*)calloc(OBOR_TRANSFORM_SCRATCH_BYTES,1u);
  if(!work || !scratch){ free(work); free(scratch); return fail(error,error_size,"allocation failed"); }
  if(input_size) memcpy(work,input,input_size);
  const uint8_t *memory[5]={(const uint8_t*)input,work,(const uint8_t*)parameters,scratch,metadata};
  size_t lengths[5]={input_size,input_size,parameter_size,OBOR_TRANSFORM_SCRATCH_BYTES,metadata_size};
  uint64_t registers[32]={0};
  registers[0]=input_size; registers[1]=parameter_size;
  registers[2]=metadata_size;
  uint64_t budget=UINT64_C(1000000)+(uint64_t)input_size*128u;
  if(budget>OBOR_TRANSFORM_MAX_STEPS) budget=OBOR_TRANSFORM_MAX_STEPS;
  if(step_limit && step_limit<budget) budget=step_limit;
  size_t pc=0,count=program_size/OBOR_TRANSFORM_INSTRUCTION_BYTES;
  const char *reason="instruction budget exhausted";
  while(budget--){
    if(pc>=count){ reason="program ended without a result"; break; }
    const uint8_t *p=(const uint8_t*)program+pc++*OBOR_TRANSFORM_INSTRUCTION_BYTES;
    unsigned op=p[0],d=p[1],a=p[2],b=p[3];
    uint64_t imm=read_le(p+4,8),left=registers[a],right=registers[b];
    switch(op){
      case OBOR_TRANSFORM_RETURN: {
        uint8_t *result=d?scratch:work;
        size_t capacity=d?OBOR_TRANSFORM_SCRATCH_BYTES:input_size;
        if(left>capacity || right>capacity-left){ reason="invalid result slice"; goto rejected; }
        if(right) memmove(result,result+(size_t)left,(size_t)right);
        free(d?work:scratch); *output=result; *output_size=(size_t)right; return 1;
      }
      case OBOR_TRANSFORM_REJECT: reason="program rejected input"; goto rejected;
      case OBOR_TRANSFORM_CONSTANT: registers[d]=imm; break;
      case OBOR_TRANSFORM_MOVE: registers[d]=left; break;
      case OBOR_TRANSFORM_ADD: registers[d]=left+right; break;
      case OBOR_TRANSFORM_SUBTRACT: registers[d]=left-right; break;
      case OBOR_TRANSFORM_MULTIPLY: registers[d]=left*right; break;
      case OBOR_TRANSFORM_DIVIDE:
      case OBOR_TRANSFORM_REMAINDER:
        if(!right){ reason="division by zero"; goto rejected; }
        registers[d]=op==OBOR_TRANSFORM_DIVIDE?left/right:left%right; break;
      case OBOR_TRANSFORM_AND: registers[d]=left&right; break;
      case OBOR_TRANSFORM_OR: registers[d]=left|right; break;
      case OBOR_TRANSFORM_XOR: registers[d]=left^right; break;
      case OBOR_TRANSFORM_SHIFT_LEFT:
      case OBOR_TRANSFORM_SHIFT_RIGHT:
        if(right>=64){ reason="invalid shift"; goto rejected; }
        registers[d]=op==OBOR_TRANSFORM_SHIFT_LEFT?left<<right:left>>right; break;
      case OBOR_TRANSFORM_EQUAL: registers[d]=left==right; break;
      case OBOR_TRANSFORM_LESS: registers[d]=left<right; break;
      case OBOR_TRANSFORM_LOAD8:
      case OBOR_TRANSFORM_LOAD32:
      case OBOR_TRANSFORM_LOAD64:
      case OBOR_TRANSFORM_STORE8:
      case OBOR_TRANSFORM_STORE32:
      case OBOR_TRANSFORM_STORE64: {
        unsigned width=(op-OBOR_TRANSFORM_LOAD8)%3u;
        width=width==0?1u:width==1?4u:8u;
        uint64_t address=left+imm;
        if(address<left || address>lengths[b] || width>lengths[b]-address){
          reason="buffer access out of bounds"; goto rejected;
        }
        if(op<=OBOR_TRANSFORM_LOAD64) registers[d]=read_le(memory[b]+(size_t)address,width);
        else {
          uint8_t *destination=b==1?work:scratch;
          for(unsigned i=0;i<width;i++) destination[(size_t)address+i]=(uint8_t)(registers[d]>>(8u*i));
        }
        break;
      }
      case OBOR_TRANSFORM_JUMP: pc=(size_t)imm; break;
      case OBOR_TRANSFORM_JUMP_ZERO: if(!left) pc=(size_t)imm; break;
      case OBOR_TRANSFORM_JUMP_NONZERO: if(left) pc=(size_t)imm; break;
    }
  }
rejected:
  free(work); free(scratch); return fail(error,error_size,reason);
}
