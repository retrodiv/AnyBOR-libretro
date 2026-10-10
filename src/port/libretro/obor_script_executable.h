/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Private prototype. Run after value compaction and before converting entry
 * and branch indices to pointers. Keep the existing evaluator's anchor and
 * skip semantics. All ScriptVariants remain owned by the complete value pool. */
#ifndef OBOR_SCRIPT_EXECUTABLE_H
#define OBOR_SCRIPT_EXECUTABLE_H
#include <stdint.h>
#include <stdlib.h>

static int obor_script_compile_only(unsigned opcode)
{
    switch (opcode) {
    case DATA: case CLEAN: case NOOP: case PUSH: case POP:
    case CONSTINT: case CONSTDBL: case CONSTSTR:
        return 1;
#if OBOR_ENGINE_BUILD != 3400 && OBOR_ENGINE_BUILD != 3842
    /* These old engines still enforce CHECKARG at runtime. */
    case CHECKARG:
        return 1;
#endif
    default:
        /* In particular, retain FUNCDECL and IMMEDIATE/DEFERRED boundaries. */
        return 0;
    }
}

static int obor_script_value_in_pool(const Interpreter *p, ScriptVariant *v)
{
    uintptr_t start = (uintptr_t)p->valueStorage, address = (uintptr_t)v;
    return !v || (address >= start &&
        (address - start) % sizeof(*v) == 0 &&
        (address - start) / sizeof(*v) < (size_t)p->compactValueCount);
}

/* Returns the number of records removed. Allocation/validation failure leaves
 * every instruction, entry index, export and value untouched. No persistent
 * old-to-new map, alternate instruction history or reconstruction cache. */
static int obor_script_compact_executable(Interpreter *p, List *exports)
{
    Instruction *old = p->instructionStorage, *storage;
    int size = p->theInstructionList.size, count = 0, i, index;
    int *map;
    Node *node;
    if (!old || size < 2 || !p->theInstructionList.solidlist ||
        !p->valueStorage || p->compactValueCount <= 0 ||
        p->pCurrentInstruction || p->pCurrentCall || p->pReturnEntry ||
        (size_t)size > SIZE_MAX / sizeof(*map) ||
        (size_t)size > SIZE_MAX / sizeof(*old))
        return 0;
    map = (int *)malloc((size_t)size * sizeof(*map));
    if (!map) return 0;
    for (i = 0; i < size; ++i)
        map[i] = !obor_script_compile_only(old[i].OpCode);
    /* Preserve the final sentinel, including an inert last instruction. */
    map[size - 1] = 1;
    for (i = 0; i < size; ++i) {
        const Instruction *ins = &old[i];
        unsigned storage_type = ins->storageType;
#if OBOR_ENGINE_BUILD == 3842
        storage_type &= ~INSTRUCTION_REFERENCE_COMPACT_FLAG;
#endif
        if (storage_type != INSTRUCTION_COMPILED ||
            (obor_script_instruction_owns_value(ins) &&
             !obor_script_value_in_pool(p, ins->theVal))) goto unchanged;
#if OBOR_ENGINE_BUILD == 3400
        if (!obor_script_value_in_pool(p, ins->theVal2)) goto unchanged;
#endif
        if (ins->jumpTargetType == INSTRUCTION_TARGET_INDEX) {
            index = ins->theJumpTargetIndex;
            if (index < 0 || index >= size) goto unchanged;
            map[index] = 1;
        } else if (ins->jumpTargetType == INSTRUCTION_TARGET_JUMP) {
            uintptr_t a = (uintptr_t)ins->ptheJumpTarget;
            uintptr_t base = (uintptr_t)old;
            /* Existing direct pointers must be imported, never into this
             * not-yet-resolved pool. Refuse a violated compiler contract. */
            if (a >= base && a - base <= (size_t)size * sizeof(*old))
                goto unchanged;
        }
    }
#define OBOR_KEEP_ENTRY(field) do { \
    index = p->field; \
    if (index >= size || index < -1) goto unchanged; \
    if (index >= 0) map[index] = 1; \
} while (0)
    OBOR_KEEP_ENTRY(mainEntryIndex);
#if OBOR_ENGINE_BUILD != 3400
    OBOR_KEEP_ENTRY(clearEntryIndex);
    OBOR_KEEP_ENTRY(initEntryIndex);
#endif
#undef OBOR_KEEP_ENTRY
    if (exports) {
        if (exports->solidlist) goto unchanged;
        node = exports->first;
        for (i = 0; i < exports->size; ++i) {
            uintptr_t value;
            if (!node) goto unchanged;
            value = (uintptr_t)node->value;
            if (value >= (size_t)size || old[value].OpCode != FUNCDECL)
                goto unchanged;
            map[value] = 1;
            node = node->next;
        }
        if (node) goto unchanged;
    }
    for (i = 0; i < size; ++i)
        map[i] = map[i] ? count++ : -1;
    if (count == size) goto unchanged;
    storage = (Instruction *)malloc((size_t)count * sizeof(*storage));
    if (!storage) goto unchanged;
    for (i = 0; i < size; ++i) {
        if (map[i] < 0) continue;
        storage[map[i]] = old[i];
        if (old[i].jumpTargetType == INSTRUCTION_TARGET_INDEX)
            storage[map[i]].theJumpTargetIndex = map[old[i].theJumpTargetIndex];
    }
    if (exports) {
        List_Reset(exports);
        for (i = 0; i < List_GetSize(exports); ++i) {
            index = (int)(uintptr_t)List_Retrieve(exports);
            List_Update(exports, (void *)(uintptr_t)map[index]);
            List_GotoNext(exports);
        }
    }
    if (p->mainEntryIndex >= 0) p->mainEntryIndex = map[p->mainEntryIndex];
#if OBOR_ENGINE_BUILD != 3400
    if (p->clearEntryIndex >= 0) p->clearEntryIndex = map[p->clearEntryIndex];
    if (p->initEntryIndex >= 0) p->initEntryIndex = map[p->initEntryIndex];
#endif
    for (i = 0; i < size; ++i)
        p->theInstructionList.solidlist[i] = i < count ? &storage[i] : NULL;
    p->instructionStorage = storage;
    p->theInstructionList.size = count;
    free(old);
    free(map);
    return size - count;
unchanged:
    free(map);
    return 0;
}
#endif
