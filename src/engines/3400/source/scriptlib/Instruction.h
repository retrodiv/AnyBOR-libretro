/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#ifndef INSTRUCTION_H
#define INSTRUCTION_H
#include "depends.h"
#include "Lexer.h"
#include "List.h"
#include "ScriptVariant.h"

typedef LPCSTR Label;

typedef enum OpCode{ CONSTSTR, CONSTDBL, CONSTINT, LOAD, SAVE, INC, DEC, FIELD, CALL, POS, NEG,
			 NOT, MUL, DIV,MOD, ERR, ADD, SUB, JUMP, GE, LE, LT, GT, EQ, NE, OR,
			 AND, NOOP, PUSH, POP, Branch_FALSE, Branch_TRUE, DATA, PARAM,
			 IMMEDIATE, DEFERRED, RET, CHECKARG, CLEAN, JUMPR, FUNCDECL, OPCODE_END
}OpCode;

typedef enum InstructionReferenceStorageType {
   INSTRUCTION_REFERENCE_LIST,
   INSTRUCTION_REFERENCE_COMPACT
} InstructionReferenceStorageType;

typedef enum InstructionStorageType {
   INSTRUCTION_SOURCE_TOKEN, INSTRUCTION_SOURCE_LABEL, INSTRUCTION_COMPILED
} InstructionStorageType;

typedef enum InstructionTargetType {
   INSTRUCTION_TARGET_NONE, INSTRUCTION_TARGET_INDEX,
   INSTRUCTION_TARGET_JUMP, INSTRUCTION_TARGET_FUNCTION
} InstructionTargetType;

typedef struct CallReferenceList {
   int index;
   int size;
   ScriptVariant *values[];
} CallReferenceList;

typedef struct Instruction{
   unsigned char OpCode;
   unsigned char jumpTargetType;
   unsigned char storageType;
   unsigned char referenceStorageType;
   union {
      Token* theToken;
      CHAR* Label;//[MAX_STR_LEN+1];
      HRESULT (*functionRef)(ScriptVariant**, ScriptVariant**, int);
      int theJumpTargetIndex;
      struct Instruction* ptheJumpTarget;
      ScriptVariant* theRef;
   };
   ScriptVariant* theVal;
   ScriptVariant* theVal2;
   union {
      ScriptVariant* theRef2;
      List* theRefList;
      CallReferenceList* callReferences;
   };
}Instruction;


void Instruction_InitViaToken(Instruction* pins, OpCode code, Token* pToken );
void Instruction_InitViaLabel(Instruction* pins, OpCode code, LPCSTR label );
void Instruction_Init(Instruction* pins);
void Instruction_Clear(Instruction* pins);

void Instruction_NewData(Instruction* pins);
void Instruction_NewData2(Instruction* pins);
void Instruction_ConvertConstant(Instruction* pins);
int Instruction_CompactCallReferences(Instruction* pins);
int Instruction_CallReferenceCount(const Instruction* pins);
ScriptVariant** Instruction_CallReferenceValues(const Instruction* pins);
int* Instruction_CallReferenceIndex(Instruction* pins);
int Instruction_OwnsValue(const Instruction* pins);
ScriptVariant** Instruction_FirstReferenceAddress(Instruction* pins);

void Instruction_ToString(Instruction* pins, LPSTR strRep);
#endif
