/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Interpreter.h"
#undef printf
#include <assert.h>

#if OBOR_ENGINE_BUILD == 3842
uint32_t obor_profile_build = OBOR_ENGINE_BUILD;
#endif

static int fail_allocation, allocations, cleared;
static ScriptVariant *clear_base;
static size_t clear_count;
static unsigned char seen[64];
static void *limited_malloc(size_t size)
{
    if (fail_allocation && ++allocations == fail_allocation) return NULL;
    return malloc(size);
}
void ScriptVariant_Clear(ScriptVariant *value)
{
    size_t index;
    assert(value >= clear_base && value < clear_base + clear_count);
    index = (size_t)(value - clear_base);
    assert(!seen[index]);
    seen[index] = 1;
    ++cleared;
}
#define malloc limited_malloc
#include "obor_script_compact.h"
#include "obor_script_executable.h"
#undef malloc

static ScriptVariant *value(Instruction *ins, int number)
{
    ScriptVariant *v = calloc(1, sizeof(*v));
    assert(v);
    v->vt = VT_INTEGER;
    v->lVal = number;
    ins->theVal = v;
    return v;
}

static void setup(Interpreter *p, List *exports, ScriptVariant *external,
                  Instruction *imported)
{
    static const unsigned ops[] = {FUNCDECL, CONSTSTR, DATA, LOAD, CHECKARG,
        Branch_FALSE, CALL, CONSTINT, POP, JUMPR, NOOP, CONSTINT, NOOP, CLEAN,
        FUNCDECL, IMMEDIATE, DATA, DEFERRED, RET, NOOP};
    Instruction *ins;
    int i;
    memset(p, 0, sizeof(*p));
    List_Init(&p->theInstructionList);
    p->theInstructionList.size = 20;
    p->theInstructionList.solidlist = calloc(20, sizeof(void *));
    ins = p->instructionStorage = calloc(20, sizeof(*ins));
    assert(ins && p->theInstructionList.solidlist);
    for (i = 0; i < 20; ++i) {
        ins[i].OpCode = ops[i];
        ins[i].storageType = INSTRUCTION_COMPILED;
        p->theInstructionList.solidlist[i] = &ins[i];
    }
    value(&ins[1], 11); value(&ins[2], 22); value(&ins[3], 33);
    value(&ins[4], 2); value(&ins[6], 66); value(&ins[7], 77);
    value(&ins[11], 111); value(&ins[16], 161);
    ins[3].theRef = ins[1].theVal;
    ins[3].theRef2 = external;
#if OBOR_ENGINE_BUILD != 3400
    ins[5].theVal = ins[3].theVal;
#else
    ins[3].theVal2 = calloc(1, sizeof(ScriptVariant));
    assert(ins[3].theVal2);
    ins[3].theVal2->lVal = 333;
#endif
    ins[5].jumpTargetType = INSTRUCTION_TARGET_INDEX;
    ins[5].theJumpTargetIndex = 12;
    ins[9].jumpTargetType = INSTRUCTION_TARGET_INDEX;
    ins[9].theJumpTargetIndex = 14;
    ins[6].jumpTargetType = INSTRUCTION_TARGET_JUMP;
    ins[6].ptheJumpTarget = imported;
#if OBOR_ENGINE_BUILD == 3842
    ins[6].storageType |= INSTRUCTION_REFERENCE_COMPACT_FLAG;
#else
    ins[6].referenceStorageType = INSTRUCTION_REFERENCE_COMPACT;
#endif
    ins[6].callReferences = malloc(sizeof(CallReferenceList) + 3 * sizeof(ScriptVariant *));
    assert(ins[6].callReferences);
    ins[6].callReferences->index = 0;
    ins[6].callReferences->size = 3;
    ins[6].callReferences->values[0] = ins[1].theVal;
    ins[6].callReferences->values[1] = external;
    ins[6].callReferences->values[2] = ins[1].theVal;
    p->mainEntryIndex = 0;
#if OBOR_ENGINE_BUILD != 3400
    p->clearEntryIndex = p->initEntryIndex = 14;
#endif
    List_Init(exports);
    List_InsertAfter(exports, (void *)(uintptr_t)0, "entry");
    List_InsertAfter(exports, (void *)(uintptr_t)14, "helper");
    obor_script_compact_values(p);
    assert(p->compactValueCount == (OBOR_ENGINE_BUILD == 3400 ? 9 : 8));
    assert(ins[3].theRef == ins[1].theVal);
    assert(ins[6].callReferences->values[0] == ins[1].theVal);
}

static void teardown(Interpreter *p, List *exports)
{
    int i;
    clear_base = p->valueStorage; clear_count = p->compactValueCount;
    cleared = 0; memset(seen, 0, sizeof(seen));
    for (i = 0; i < p->theInstructionList.size; ++i) {
        Instruction *ins = &p->instructionStorage[i];
        obor_script_clear_compact_values(p, ins);
        Instruction_Clear(ins);
    }
    obor_script_release_value_pool(p);
    assert(cleared == (int)clear_count);
    free(p->instructionStorage);
    free(p->theInstructionList.solidlist);
    List_Clear(exports);
}

static void success(void)
{
    Interpreter p;
    List exports;
    Instruction imported = {0}, *ins;
    ScriptVariant external = {0};
    ScriptVariant *values;
    int removed, count, i, load = -1, call = -1, branch = -1, jump = -1;
    setup(&p, &exports, &external, &imported);
    values = p.valueStorage;
    removed = obor_script_compact_executable(&p, &exports);
    assert(removed == (OBOR_ENGINE_BUILD == 3400 || OBOR_ENGINE_BUILD == 3842 ? 8 : 9));
    assert(p.valueStorage == values);
    count = p.theInstructionList.size;
    ins = p.instructionStorage;
    for (i = 0; i < count; ++i) {
        assert(p.theInstructionList.solidlist[i] == &ins[i]);
        if (ins[i].OpCode == LOAD) load = i;
        if (ins[i].OpCode == CALL) call = i;
        if (ins[i].OpCode == Branch_FALSE) branch = i;
        if (ins[i].OpCode == JUMPR) jump = i;
    }
    assert(load >= 0 && call >= 0 && branch >= 0 && jump >= 0);
    assert(ins[load].theRef->lVal == 11 && ins[load].theRef2 == &external);
    assert(ins[call].ptheJumpTarget == &imported);
    assert(ins[call].callReferences->values[0] == ins[load].theRef);
    assert(ins[call].callReferences->values[2] == ins[load].theRef);
    assert(ins[call].callReferences->values[1] == &external);
    assert(ins[ins[branch].theJumpTargetIndex].OpCode == NOOP);
    assert(ins[ins[jump].theJumpTargetIndex].OpCode == FUNCDECL);
    assert(ins[p.mainEntryIndex].OpCode == FUNCDECL);
    assert(ins[(uintptr_t)exports.first->next->value].OpCode == FUNCDECL);
    assert(ins[count - 1].OpCode == NOOP);
#if OBOR_ENGINE_BUILD == 3400
    assert(ins[load].theVal2->lVal == 333);
#else
    assert(ins[branch].theVal == ins[load].theVal);
    assert(p.clearEntryIndex == (int)(uintptr_t)exports.first->next->value);
    assert(p.initEntryIndex == p.clearEntryIndex);
#endif
    assert(obor_script_compact_executable(&p, &exports) == 0);
    teardown(&p, &exports);
}

static void failure(int scenario)
{
    Interpreter p, before;
    List exports, before_exports;
    Instruction imported = {0}, *original;
    ScriptVariant external = {0};
    unsigned char instructions[20 * sizeof(Instruction)];
    setup(&p, &exports, &external, &imported);
    if (scenario == 3) p.instructionStorage[5].theJumpTargetIndex = 21;
    if (scenario == 4) p.instructionStorage[3].storageType = INSTRUCTION_SOURCE_TOKEN;
    if (scenario == 5) p.instructionStorage[6].ptheJumpTarget = &p.instructionStorage[14];
    if (scenario == 6) exports.first->next->value = (void *)(uintptr_t)3;
    if (scenario == 7) p.pCurrentInstruction = p.instructionStorage;
    before = p; before_exports = exports; original = p.instructionStorage;
    memcpy(instructions, original, sizeof(instructions));
    fail_allocation = scenario <= 2 ? scenario : 0; allocations = 0;
    assert(obor_script_compact_executable(&p, &exports) == 0);
    fail_allocation = 0;
    assert(memcmp(&p, &before, sizeof(p)) == 0);
    assert(memcmp(&exports, &before_exports, sizeof(exports)) == 0);
    assert(memcmp(original, instructions, sizeof(instructions)) == 0);
    /* Undo the deliberately malformed source tag before normal destruction. */
    p.instructionStorage[3].storageType = INSTRUCTION_COMPILED;
    teardown(&p, &exports);
}

int main(void)
{
    int i;
#if OBOR_ENGINE_BUILD == 3842
    obor_profile_build = 3830;
    assert(!obor_script_compile_only(CONSTINT));
    assert(!obor_script_compile_only(CONSTDBL));
    assert(!obor_script_compile_only(CONSTSTR));
    obor_profile_build = 3831;
    assert(obor_script_compile_only(CONSTINT));
    assert(obor_script_compile_only(CONSTDBL));
    assert(obor_script_compile_only(CONSTSTR));
    obor_profile_build = OBOR_ENGINE_BUILD;
#endif
    success();
    for (i = 1; i <= 7; ++i) failure(i);
    printf("engine=%d compact_aliases_exports_anchors_values=1 failures_atomic=7\n", OBOR_ENGINE_BUILD);
    return 0;
}
