/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 *
 * Raw level properties can redirect the visible table. Only tables allocated
 * for this level contain native text records and own their strings.
 */

struct obor_text_table
{
    s_textobj *objects;
    size_t slots;
    struct obor_text_table *next;
};

static struct obor_text_table *obor_text_table_find(const s_level *lv,
                                                    size_t *offset)
{
    if(!lv || !lv->textobjs) return NULL;
    uintptr_t view = (uintptr_t)lv->textobjs;
    for(struct obor_text_table *table = lv->obor_text_tables; table;
        table = table->next)
    {
        uintptr_t base = (uintptr_t)table->objects;
        if(view < base) continue;
        uintptr_t delta = view - base;
        if(delta % sizeof(*table->objects)) continue;
        size_t index = delta / sizeof(*table->objects);
        if(index >= table->slots) continue;
        *offset = index;
        return table;
    }
    return NULL;
}

int obor_textobjs_count(const s_level *lv)
{
    if(!lv || lv->numtextobjs <= 0) return 0;
    size_t offset;
    struct obor_text_table *table = obor_text_table_find(lv, &offset);
    if(!table) return 0;
    size_t slots = table->slots - offset;
    return slots < (size_t)lv->numtextobjs ? (int)slots : lv->numtextobjs;
}

int obor_textobj_index(s_level *lv, int index, int grow)
{
    if(!lv || index < 0) return -1;
    int count = lv->numtextobjs;
    if(index >= count && !grow) return 0;
    size_t offset = 0;
    struct obor_text_table *table = obor_text_table_find(lv, &offset);
    size_t slots = table ? table->slots - offset : 0;
    if(index < count) return (size_t)index < slots ? 1 : -1;
    if(count < 0 || index == INT_MAX ||
       (size_t)(index + 1) > SIZE_MAX / sizeof(s_textobj) ||
       (lv->textobjs && (!table || offset))) return -1;

    size_t initialized = (size_t)count < slots ? (size_t)count : slots;
    size_t removed = slots - initialized;
    char **retired = NULL;
    if(removed)
    {
        retired = malloc(removed * sizeof(*retired));
        if(!retired) return -1;
        for(size_t i = 0; i < removed; ++i)
            retired[i] = table->objects[initialized + i].text;
    }
    int created = !table;
    if(created)
    {
        table = malloc(sizeof(*table));
        if(!table) return -1;
    }
    size_t capacity = (size_t)index + 1;
    s_textobj *grown = realloc(lv->textobjs, capacity * sizeof(*grown));
    if(!grown)
    {
        if(created) free(table);
        free(retired);
        return -1;
    }
    for(size_t i = 0; i < removed; ++i) free(retired[i]);
    free(retired);
    memset(grown + initialized, 0, (capacity - initialized) * sizeof(*grown));
    if(created)
    {
        table->next = lv->obor_text_tables;
        lv->obor_text_tables = table;
    }
    table->objects = grown;
    table->slots = capacity;
    lv->textobjs = grown;
    lv->numtextobjs = index + 1;
    return 1;
}

static void obor_textobjs_release_range(s_textobj *objects, size_t count)
{
    for(size_t i = 0; i < count; ++i)
    {
        free(objects[i].text);
        objects[i].text = NULL;
    }
}

void obor_textobjs_release_visible(s_level *lv)
{
    size_t offset = 0;
    if(!obor_text_table_find(lv, &offset) || offset) return;
    obor_textobjs_release_range(lv->textobjs, (size_t)obor_textobjs_count(lv));
}

void obor_textobjs_release_all(s_level *lv)
{
    struct obor_text_table *table = lv->obor_text_tables;
    while(table)
    {
        struct obor_text_table *next = table->next;
        obor_textobjs_release_range(table->objects, table->slots);
        free(table->objects);
        free(table);
        table = next;
    }
    lv->obor_text_tables = NULL;
    lv->textobjs = NULL;
}
