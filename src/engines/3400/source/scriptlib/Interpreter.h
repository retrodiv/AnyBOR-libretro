/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Own the exact contiguous storage used by compiled instructions and their
 * values. Store parser state indirectly so compiled interpreters do not
 * retain it.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#ifndef INTERPRETER_H
#define INTERPRETER_H
#include "depends.h"
#include "StackedSymbolTable.h"
#include "Instruction.h"
#include "Parser.h"

typedef HRESULT (*SCRIPTFUNCTION)(ScriptVariant** varlist , ScriptVariant** pretvar, int paramCount);

typedef struct Interpreter {
   StackedSymbolTable theSymbolTable;
   List* ptheFunctionList;               //external functionlist, to save some memory
   List theImportList;
   List theInstructionList;
   Instruction* instructionStorage;
   ScriptVariant *valueStorage;
   List paramList;
   Stack theDataStack;
   Stack theLabelStack;
   Parser *theParser;
   pp_context theContext;

   Instruction* pCurrentInstruction;
   Instruction* pCurrentCall;
   Instruction* pReturnEntry;
   union { // we have to use the index before solidifying the instruction list
	  Instruction* pMainEntry;
	  int mainEntryIndex;
   };
   int bHasImmediateCode;

   BOOL bCallCompleted;
   BOOL bMainCompleted;
}Interpreter;

void Interpreter_Init(Interpreter* pinterpreter, LPCSTR name, List* pflist);
void Interpreter_Clear(Interpreter* pinterpreter);
HRESULT Interpreter_ParseText(Interpreter* pinterpreter, LPSTR scriptText,
						   ULONG startingLineNumber, LPCSTR path);
HRESULT Interpreter_PutValue(Interpreter* pinterpreter, LPCSTR variable, ScriptVariant* pValue, int refFlag );
HRESULT Interpreter_GetValue(Interpreter* pinterpreter, LPCSTR variable, ScriptVariant* pValue);
HRESULT Interpreter_GetValueByRef(Interpreter* pinterpreter, LPCSTR variable, ScriptVariant** pValue);
HRESULT Interpreter_EvaluateImmediate(Interpreter* pinterpreter);
HRESULT Interpreter_EvaluateCall(Interpreter* pinterpreter);
HRESULT Interpreter_CompileInstructions(Interpreter* pinterpreter);
HRESULT Interpreter_Call(Interpreter* pinterpreter);
HRESULT Interpreter_EvalInstruction(Interpreter* pinterpreter);
void Interpreter_Reset(Interpreter* pinterpreter);
void Interpreter_ClearImports(Interpreter* pinterpreter);


#endif
