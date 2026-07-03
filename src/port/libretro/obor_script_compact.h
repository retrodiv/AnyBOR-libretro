/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Compact the heap-owned ScriptVariant values of one compiled interpreter.
 * Include after Interpreter.h; OBOR_ENGINE_BUILD selects historical layouts. */
#ifndef OBOR_SCRIPT_COMPACT_H
#define OBOR_SCRIPT_COMPACT_H

#include <stdint.h>
#include <stdlib.h>

typedef struct obor_script_value_move {
    ScriptVariant *old_value;
    ScriptVariant *new_value;
} obor_script_value_move;

static int obor_script_instruction_owns_value(const Instruction *instruction)
{
#if OBOR_ENGINE_BUILD == 3842 || OBOR_ENGINE_BUILD == 4086 || \
    OBOR_ENGINE_BUILD == 4432 || OBOR_ENGINE_BUILD == 6412
    return Instruction_OwnsValue(instruction);
#else
    return 1;
#endif
}

static ScriptVariant **obor_script_first_reference(Instruction *instruction)
{
#if OBOR_ENGINE_BUILD == 3842 || OBOR_ENGINE_BUILD == 4086 || \
    OBOR_ENGINE_BUILD == 4432 || OBOR_ENGINE_BUILD == 6412
    return Instruction_FirstReferenceAddress(instruction);
#else
    return &instruction->theRef;
#endif
}

static int obor_script_compare_value_moves(const void *left, const void *right)
{
    uintptr_t a = (uintptr_t)((const obor_script_value_move *)left)->old_value;
    uintptr_t b = (uintptr_t)((const obor_script_value_move *)right)->old_value;
    return (a > b) - (a < b);
}

static ScriptVariant *obor_script_find_moved_value(
    const obor_script_value_move *moves, int count, ScriptVariant *value)
{
    uintptr_t target = (uintptr_t)value;
    int lo = 0;
    int hi = count;

    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        uintptr_t candidate = (uintptr_t)moves[mid].old_value;
        if (candidate < target)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo < count && moves[lo].old_value == value
               ? moves[lo].new_value : NULL;
}

static void obor_script_compact_values(Interpreter *interpreter)
{
    obor_script_value_move *moves;
    ScriptVariant *storage;
    int count = 0;
    int i;
    int size = interpreter->theInstructionList.size;

    if (interpreter->valueStorage ||
        !interpreter->theInstructionList.solidlist)
        return;

    for (i = 0; i < size; i++) {
        Instruction *instruction =
            (Instruction *)interpreter->theInstructionList.solidlist[i];
        if (obor_script_instruction_owns_value(instruction) && instruction->theVal)
            count++;
#if OBOR_ENGINE_BUILD == 3400
        if (instruction->theVal2)
            count++;
#endif
    }
    if (!count)
        return;

    moves = (obor_script_value_move *)malloc((size_t)count * sizeof(*moves));
    storage = (ScriptVariant *)malloc((size_t)count * sizeof(*storage));
    if (!moves || !storage) {
        free(moves);
        free(storage);
        return;
    }

    count = 0;
    for (i = 0; i < size; i++) {
        Instruction *instruction =
            (Instruction *)interpreter->theInstructionList.solidlist[i];
        if (obor_script_instruction_owns_value(instruction) && instruction->theVal)
            moves[count++].old_value = instruction->theVal;
#if OBOR_ENGINE_BUILD == 3400
        if (instruction->theVal2)
            moves[count++].old_value = instruction->theVal2;
#endif
    }
    qsort(moves, (size_t)count, sizeof(*moves),
          obor_script_compare_value_moves);
    for (i = 1; i < count; i++) {
        if (moves[i - 1].old_value == moves[i].old_value) {
            free(moves);
            free(storage);
            return;
        }
    }
    for (i = 0; i < count; i++) {
        storage[i] = *moves[i].old_value;
        moves[i].new_value = &storage[i];
    }

    for (i = 0; i < size; i++) {
        Instruction *instruction =
            (Instruction *)interpreter->theInstructionList.solidlist[i];
        ScriptVariant *moved;

        if (obor_script_instruction_owns_value(instruction) && instruction->theVal)
            instruction->theVal =
                obor_script_find_moved_value(moves, count,
                                             instruction->theVal);
#if OBOR_ENGINE_BUILD == 3400
        if (instruction->theVal2)
            instruction->theVal2 =
                obor_script_find_moved_value(moves, count,
                                             instruction->theVal2);
#endif
        {
            ScriptVariant **reference =
                obor_script_first_reference(instruction);
            moved = reference
                ? obor_script_find_moved_value(moves, count, *reference)
                : NULL;
            if (moved)
                *reference = moved;
        }

#if OBOR_ENGINE_BUILD == 3842
        if (instruction->OpCode != CALL) {
            moved = obor_script_find_moved_value(moves, count,
                                                 instruction->theRef2);
            if (moved)
                instruction->theRef2 = moved;
        }
#else
        moved = obor_script_find_moved_value(moves, count,
                                             instruction->theRef2);
        if (moved)
            instruction->theRef2 = moved;
#endif

        if (instruction->OpCode == CALL && instruction->theRefList) {
            ScriptVariant **references;
            int reference_count;
            int j;
            references = Instruction_CallReferenceValues(instruction);
            reference_count = Instruction_CallReferenceCount(instruction);
            for (j = 0; references && j < reference_count; j++) {
                moved = obor_script_find_moved_value(
                    moves, count, references[j]);
                if (moved)
                    references[j] = moved;
            }
        }
    }

    for (i = 0; i < count; i++)
        free(moves[i].old_value);
    free(moves);
    interpreter->valueStorage = storage;
}

static void obor_script_clear_compact_values(Interpreter *interpreter,
                                             Instruction *instruction)
{
    if (!interpreter->valueStorage)
        return;
    if (obor_script_instruction_owns_value(instruction) && instruction->theVal) {
        ScriptVariant_Clear(instruction->theVal);
        instruction->theVal = NULL;
    }
#if OBOR_ENGINE_BUILD == 3400
    if (instruction->theVal2) {
        ScriptVariant_Clear(instruction->theVal2);
        instruction->theVal2 = NULL;
    }
#endif
}

#endif
