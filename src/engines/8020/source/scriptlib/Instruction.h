/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c)  OpenBOR Team
 */

#ifndef INSTRUCTION_H
#define INSTRUCTION_H
#include "depends.h"
#include "Lexer.h"
#include "List.h"
#include "ScriptVariant.h"

typedef LPSTR Label;

typedef enum OpCode { CONSTSTR, CONSTDBL, CONSTINT, LOAD, SAVE, INC, DEC, FIELD, CALL, POS, NEG,
                      NOT, BIT_NOT, MUL, DIV, MOD, ERR, ADD, SUB, SHL, SHR, JUMP, PJUMP, GE, LE, LT, GT, EQ, NE, OR, AND,
                      BIT_OR, XOR, BIT_AND, NOOP, PUSH, POP, Branch_FALSE, Branch_TRUE, Branch_EQUAL, DATA, PARAM,
                      IMMEDIATE, DEFERRED, RET, CHECKARG, CLEAN, JUMPR, FUNCDECL, OPCODE_END
                    } OpCode;

typedef enum InstructionStorageType {
    INSTRUCTION_SOURCE_TOKEN, INSTRUCTION_SOURCE_LABEL, INSTRUCTION_COMPILED
} InstructionStorageType;

typedef enum InstructionTargetType {
    INSTRUCTION_TARGET_NONE, INSTRUCTION_TARGET_INDEX,
    INSTRUCTION_TARGET_JUMP, INSTRUCTION_TARGET_FUNCTION
} InstructionTargetType;

typedef enum InstructionReferenceStorageType {
    INSTRUCTION_REFERENCE_LIST,
    INSTRUCTION_REFERENCE_COMPACT
} InstructionReferenceStorageType;

typedef struct CallReferenceList {
    int index;
    int size;
    ScriptVariant *values[];
} CallReferenceList;

#pragma pack(4)

typedef struct Instruction
{
    unsigned step;
    unsigned char OpCode;
    unsigned char jumpTargetType;
    unsigned char storageType;
    unsigned char referenceStorageType;
    union
    {
        Token *theToken;
        CHAR *Label;//[MAX_STR_LEN+1];
        HRESULT (*functionRef)(ScriptVariant **, ScriptVariant **, int);
        int theJumpTargetIndex;
        struct Instruction **ptheJumpTarget;
    };
    ScriptVariant *theVal;
    ScriptVariant *theRef;
    union
    {
        ScriptVariant *theRef2;
        List *theRefList;
        CallReferenceList *callReferences;
    };
} Instruction;

#pragma pack()

HRESULT Instruction_InitViaToken(Instruction *pins, OpCode code, Token *pToken );
void Instruction_InitViaLabel(Instruction *pins, OpCode code, LPCSTR label );
void Instruction_Init(Instruction *pins);
void Instruction_Clear(Instruction *pins);

void Instruction_NewData(Instruction *pins);
HRESULT Instruction_ConvertConstant(Instruction *pins);
int Instruction_CompactCallReferences(Instruction *pins);
int Instruction_CallReferenceCount(const Instruction *pins);
ScriptVariant **Instruction_CallReferenceValues(const Instruction *pins);
int *Instruction_CallReferenceIndex(Instruction *pins);

void Instruction_ToString(Instruction *pins, LPSTR strRep);
#endif
