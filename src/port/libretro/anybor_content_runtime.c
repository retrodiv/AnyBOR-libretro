/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "openbor.h"
#if OBOR_ENGINE_BUILD >= 6391
#include "source/openborscript/config.h"
#else
#include "openborscript.h"
#endif
#include "libretroport.h"
#include "anybor_presentation_number.h"

#if OBOR_ENGINE_BUILD >= 4086
ScriptVariant *Varlist_GetByName(Varlist *varlist, char *name);
#endif

/* Numeric script variants have no VM owners. Restore through each native
 * variable table so drawing can safely replace or remove the live value. */
typedef struct {
    char name[OBOR_PRESENTATION_NAME];
    ScriptVariant original;
} obor_saved_global;

typedef struct {
    obor_saved_global entries[OBOR_PRESENTATION_OVERRIDES];
    unsigned count;
} obor_saved_globals;

static obor_saved_globals obor_scoped_globals, obor_draw_globals;
static unsigned obor_drawing_depth;

static ScriptVariant *obor_named_global(char *name)
{
#if OBOR_ENGINE_BUILD < 4086
    return Script_Get_Global_Variant(name);
#else
    return Varlist_GetByName(&global_var_list, name);
#endif
}

static void obor_put_global(char *name, ScriptVariant *value)
{
#if OBOR_ENGINE_BUILD < 4086
    Script_Set_Global_Variant(name, value);
#else
    Varlist_SetByName(&global_var_list, name, value);
#endif
}

static int obor_global_is_numeric(const ScriptVariant *value)
{
    return value && (value->vt == VT_INTEGER || value->vt == VT_DECIMAL);
}

int32_t obor_get_content_number(const char *name, double *number)
{
    const ScriptVariant *value = obor_named_global((char *)name);
    if (!obor_global_is_numeric(value)) return 0;
    *number = value->vt == VT_INTEGER ? (double)value->lVal : value->dblVal;
    return isfinite(*number);
}

static int obor_global_truth(const char *name)
{
    double number;
    return obor_get_content_number(name, &number) && number != 0.0;
}

static void obor_restore_globals(obor_saved_globals *saved,
                                 const obor_numeric_override *const *active, unsigned count)
{
    unsigned kept = 0;
    for (unsigned i = 0; i < saved->count; ++i) {
        obor_saved_global *entry = &saved->entries[i];
        unsigned slot = 0;
        while (slot < count && strcmp(entry->name, active[slot]->name)) ++slot;
        if (slot < count) {
            saved->entries[kept++] = *entry;
        } else {
            obor_put_global(entry->name, &entry->original);
        }
    }
    memset(saved->entries + kept, 0, (saved->count - kept) * sizeof(saved->entries[0]));
    saved->count = kept;
}

static void obor_apply_globals(obor_saved_globals *saved, int drawing)
{
    const obor_numeric_override *rules;
    unsigned scopes;
    unsigned count = obor_presentation_numeric_rules(&rules, &scopes);
    if (!count && !saved->count) return;
    const obor_numeric_override *active[OBOR_PRESENTATION_OVERRIDES] = {0};
    double values[OBOR_PRESENTATION_OVERRIDES];
    unsigned found = 0;
    for (unsigned i = 0; i < count; ++i) {
        const obor_numeric_override *rule = &rules[i];
        if (rule->target != (drawing ? OBOR_TARGET_DRAW : OBOR_TARGET_GLOBAL) || !(scopes & (1u << rule->scope)) ||
            (rule->condition[0] && !obor_global_truth(rule->condition))) continue;
        double value;
        if (!obor_presentation_number(rule->expression, obor_get_content_number, &value))
            continue;
        unsigned slot = 0;
        while (slot < found && strcmp(active[slot]->name, rule->name)) ++slot;
        if (slot == found) ++found;
        active[slot] = rule;
        values[slot] = value;
    }
    obor_restore_globals(saved, active, found);
    for (unsigned i = 0; i < found; ++i) {
        const obor_numeric_override *rule = active[i];
        ScriptVariant *global = obor_named_global((char *)rule->name);
        if (!obor_global_is_numeric(global)) continue;
        unsigned slot = 0;
        while (slot < saved->count && strcmp(saved->entries[slot].name, rule->name)) ++slot;
        if (slot == saved->count) {
            obor_saved_global *entry = &saved->entries[saved->count++];
            memcpy(entry->name, rule->name, sizeof(entry->name));
            entry->original = *global;
        }

        double value = values[i];
        if (value >= INT32_MIN && value <= INT32_MAX && value == (int32_t)value) {
            ScriptVariant_ChangeType(global, VT_INTEGER);
            global->lVal = (int32_t)value;
        } else {
            ScriptVariant_ChangeType(global, VT_DECIMAL);
            global->dblVal = value;
        }
    }
}

void obor_content_update(void)
{
    if (!obor_drawing_depth) obor_apply_globals(&obor_scoped_globals, 0);
}

void obor_content_draw(void (*draw)(void))
{
    obor_content_update();
    if (!obor_drawing_depth++) obor_apply_globals(&obor_draw_globals, 1);
    draw();
    if (!--obor_drawing_depth) obor_restore_globals(&obor_draw_globals, NULL, 0);
}

void obor_content_draw_suspend(void)
{
    if (obor_drawing_depth) obor_restore_globals(&obor_draw_globals, NULL, 0);
}

void obor_content_draw_resume(void)
{
    if (obor_drawing_depth) obor_apply_globals(&obor_draw_globals, 1);
}
