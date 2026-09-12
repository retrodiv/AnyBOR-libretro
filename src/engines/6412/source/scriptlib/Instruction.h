/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Remove redundant value storage, compact opcode and call-reference
 * bookkeeping, and share parser-only fields with their compiled
 * replacements.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/6412.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2013 OpenBOR Team
 */

#ifndef INSTRUCTION_H
#define INSTRUCTION_H
#include "depends.h"
#include "Lexer.h"
#include "List.h"
#include "ScriptVariant.h"

typedef LPSTR Label;

typedef enum OpCode { CONSTSTR, CONSTDBL, CONSTINT, LOAD, SAVE, INC, DEC, FIELD, CALL, POS, NEG,
                      NOT, MUL, DIV, MOD, ERR, ADD, SUB, SHL, SHR, JUMP, PJUMP, GE, LE, LT, GT, EQ, NE, OR, AND,
                      BIT_OR, XOR, BIT_AND, NOOP, PUSH, POP, Branch_FALSE, Branch_TRUE, Branch_EQUAL, DATA, PARAM,
                      IMMEDIATE, DEFERRED, RET, CHECKARG, CLEAN, JUMPR, FUNCDECL, OPCODE_END
                    } OpCode;

#pragma pack(4)

typedef enum InstructionReferenceStorageType
{
    INSTRUCTION_REFERENCE_LIST,
    INSTRUCTION_REFERENCE_COMPACT
} InstructionReferenceStorageType;

typedef enum InstructionStorageType
{
    INSTRUCTION_SOURCE_TOKEN, INSTRUCTION_SOURCE_LABEL, INSTRUCTION_COMPILED
} InstructionStorageType;

typedef enum InstructionTargetType
{
    INSTRUCTION_TARGET_NONE, INSTRUCTION_TARGET_INDEX,
    INSTRUCTION_TARGET_JUMP, INSTRUCTION_TARGET_FUNCTION
} InstructionTargetType;

typedef struct CallReferenceList
{
    int index;
    int size;
    ScriptVariant *values[];
} CallReferenceList;

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
        struct Instruction *ptheJumpTarget;
        ScriptVariant *theRef;
    };
    ScriptVariant *theVal;
    union
    {
        ScriptVariant *theRef2;
        List *theRefList;
        CallReferenceList *callReferences;
    };
} Instruction;

#pragma pack()

void Instruction_InitViaToken(Instruction *pins, OpCode code, Token *pToken );
void Instruction_InitViaLabel(Instruction *pins, OpCode code, LPCSTR label );
void Instruction_Init(Instruction *pins);
void Instruction_Clear(Instruction *pins);

void Instruction_NewData(Instruction *pins);
void Instruction_ConvertConstant(Instruction *pins);
int Instruction_CompactCallReferences(Instruction *pins);
int Instruction_CallReferenceCount(const Instruction *pins);
ScriptVariant **Instruction_CallReferenceValues(const Instruction *pins);
int *Instruction_CallReferenceIndex(Instruction *pins);
int Instruction_OwnsValue(const Instruction *pins);
ScriptVariant **Instruction_FirstReferenceAddress(Instruction *pins);

void Instruction_ToString(Instruction *pins, LPSTR strRep);
#endif
