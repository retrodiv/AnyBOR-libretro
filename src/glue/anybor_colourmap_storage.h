/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Ownership of palette tables and shared palette payloads. Entry pointers keep
 * their identities when a table is copied. The engine's logical count remains
 * separate from this allocation extent.
 */
#ifndef OBOR_COLOURMAP_STORAGE_H
#define OBOR_COLOURMAP_STORAGE_H

#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifndef OBOR_COLOURMAP_ALLOC
#define OBOR_COLOURMAP_ALLOC(n) realloc(NULL, (n))
#endif
#ifndef OBOR_COLOURMAP_FREE
#define OBOR_COLOURMAP_FREE(p) free(p)
#endif

typedef struct obor_colourmap_payload {
    unsigned char *data;
    unsigned int refs;
} obor_colourmap_payload;

typedef struct obor_colourmap_retired {
    obor_colourmap_payload *entry;
    struct obor_colourmap_retired *next;
} obor_colourmap_retired;

typedef struct obor_colourmap_storage {
    unsigned char **table;
    obor_colourmap_payload **entries;
    unsigned int capacity;
    unsigned int refs;
    obor_colourmap_retired *retired;
    struct obor_colourmap_storage *next;
} obor_colourmap_storage;

static obor_colourmap_storage *obor_colourmap_tables;

/* A by-value temporary model snapshot borrows its table. Only registered
 * model/entity addresses own a reference; copying the structure alone does
 * not create another owner. */
typedef struct obor_colourmap_owner {
    const void *address;
    unsigned char **table;
    struct obor_colourmap_owner *next;
} obor_colourmap_owner;

static obor_colourmap_owner *obor_colourmap_owners;

static obor_colourmap_owner *obor_colourmap_owner_find(const void *address)
{
    obor_colourmap_owner *owner;
    for(owner = obor_colourmap_owners; owner; owner = owner->next)
        if(owner->address == address) return owner;
    return NULL;
}

static obor_colourmap_owner *obor_colourmap_owner_new(const void *address)
{
    obor_colourmap_owner *owner;
    if(!address || obor_colourmap_owner_find(address)) return NULL;
    owner = OBOR_COLOURMAP_ALLOC(sizeof(*owner));
    if(!owner) return NULL;
    owner->address = address;
    owner->table = NULL;
    owner->next = obor_colourmap_owners;
    obor_colourmap_owners = owner;
    return owner;
}

static obor_colourmap_storage *obor_colourmap_find(unsigned char **table)
{
    obor_colourmap_storage *record;
    for(record = obor_colourmap_tables; record; record = record->next)
        if(record->table == table) return record;
    return NULL;
}

static void obor_colourmap_drop_payload(obor_colourmap_payload *entry)
{
    if(entry && --entry->refs == 0)
    {
        OBOR_COLOURMAP_FREE(entry->data);
        OBOR_COLOURMAP_FREE(entry);
    }
}

/* Unknown tables are refused: their allocation and ownership are not known. */
static int obor_colourmap_release(unsigned char **table)
{
    obor_colourmap_storage **link = &obor_colourmap_tables, *record;
    obor_colourmap_retired *retired;
    unsigned int i;
    if(!table) return 1;
    while(*link && (*link)->table != table) link = &(*link)->next;
    record = *link;
    if(!record) return 0;
    if(--record->refs) return 1;
    *link = record->next;
    for(i = 0; i < record->capacity; ++i)
        obor_colourmap_drop_payload(record->entries[i]);
    while((retired = record->retired))
    {
        record->retired = retired->next;
        obor_colourmap_drop_payload(retired->entry);
        OBOR_COLOURMAP_FREE(retired);
    }
    OBOR_COLOURMAP_FREE(record->entries);
    OBOR_COLOURMAP_FREE(record->table);
    OBOR_COLOURMAP_FREE(record);
    return 1;
}

static int obor_colourmap_owner_release(const void *address)
{
    obor_colourmap_owner **link = &obor_colourmap_owners, *owner;
    while(*link && (*link)->address != address) link = &(*link)->next;
    owner = *link;
    if(!owner) return 0;
    *link = owner->next;
    obor_colourmap_release(owner->table);
    OBOR_COLOURMAP_FREE(owner);
    return 1;
}

static obor_colourmap_storage *obor_colourmap_new(unsigned int count)
{
    obor_colourmap_storage *record;
    size_t table_bytes = (size_t)count * sizeof(*record->table);
    size_t entry_bytes = (size_t)count * sizeof(*record->entries);
    if(!count || table_bytes / count != sizeof(*record->table) ||
        entry_bytes / count != sizeof(*record->entries)) return NULL;
    record = OBOR_COLOURMAP_ALLOC(sizeof(*record));
    if(!record) return NULL;
    memset(record, 0, sizeof(*record));
    record->table = OBOR_COLOURMAP_ALLOC(table_bytes);
    record->entries = OBOR_COLOURMAP_ALLOC(entry_bytes);
    if(!record->table || !record->entries)
    {
        OBOR_COLOURMAP_FREE(record->table);
        OBOR_COLOURMAP_FREE(record->entries);
        OBOR_COLOURMAP_FREE(record);
        return NULL;
    }
    memset(record->table, 0, table_bytes);
    memset(record->entries, 0, entry_bytes);
    record->capacity = count;
    record->refs = 1;
    record->next = obor_colourmap_tables;
    obor_colourmap_tables = record;
    return record;
}

static obor_colourmap_storage *obor_colourmap_clone(
    obor_colourmap_storage *source, unsigned int count)
{
    obor_colourmap_storage *record;
    unsigned int i;
    if(!source || count < source->capacity) return NULL;
    /* This conservative margin also covers repeated payloads in one table. */
    for(i = 0; i < source->capacity; ++i)
        if(source->entries[i] &&
            source->entries[i]->refs > UINT_MAX - source->capacity) return NULL;
    record = obor_colourmap_new(count);
    if(!record) return NULL;
    for(i = 0; i < source->capacity; ++i)
    {
        record->table[i] = source->table[i];
        record->entries[i] = source->entries[i];
        if(record->entries[i]) ++record->entries[i]->refs;
    }
    return record;
}

/* Allocate a fresh extent before releasing the previous reference. Appending
 * to a shared dynamic table detaches it; the original realloc invalidated the
 * borrowed vector in that case. Existing entry pointers remain unchanged. */
static int obor_colourmap_table_reserve(unsigned char ***table,
    unsigned int *capacity, unsigned int count)
{
    obor_colourmap_storage *old, *replacement;
    if(!table || !capacity) return 0;
    if(!*table)
    {
        if(!count) { *capacity = 0; return 1; }
        replacement = obor_colourmap_new(count);
    }
    else
    {
        old = obor_colourmap_find(*table);
        if(!old || old->capacity != *capacity) return 0;
        if(count <= old->capacity) return 1;
        replacement = obor_colourmap_clone(old, count);
    }
    if(!replacement) return 0;
    obor_colourmap_release(*table);
    *table = replacement->table;
    *capacity = replacement->capacity;
    return 1;
}

/* A successful replacement takes ownership of data. Refusal leaves ownership
 * with the caller and preserves both the old slot and all other references. */
static int obor_colourmap_replace(unsigned char **table, unsigned int index,
    unsigned char *data)
{
    obor_colourmap_storage *record = obor_colourmap_find(table), *candidate;
    obor_colourmap_payload *entry = NULL;
    obor_colourmap_retired *retired = NULL;
    obor_colourmap_retired *previous;
    unsigned int i;
    if(!record || index >= record->capacity) return 0;
    if(record->table[index] == data) return 1;
    /* A live borrower may still have cached the previous entry pointer. */
    if(record->refs > 1 && record->entries[index])
    {
        retired = OBOR_COLOURMAP_ALLOC(sizeof(*retired));
        if(!retired) return 0;
    }
    if(data)
    {
        for(candidate = obor_colourmap_tables; candidate && !entry;
            candidate = candidate->next)
        {
            for(i = 0; i < candidate->capacity; ++i)
                if(candidate->entries[i] && candidate->entries[i]->data == data)
                { entry = candidate->entries[i]; break; }
            for(previous = candidate->retired; previous && !entry; previous = previous->next)
                if(previous->entry->data == data) entry = previous->entry;
        }
        if(entry)
        {
            if(entry->refs == UINT_MAX)
            { OBOR_COLOURMAP_FREE(retired); return 0; }
            ++entry->refs;
        }
        else
        {
            entry = OBOR_COLOURMAP_ALLOC(sizeof(*entry));
            if(!entry) { OBOR_COLOURMAP_FREE(retired); return 0; }
            entry->data = data;
            entry->refs = 1;
        }
    }
    if(retired)
    {
        retired->entry = record->entries[index];
        retired->next = record->retired;
        record->retired = retired;
    }
    else obor_colourmap_drop_payload(record->entries[index]);
    record->entries[index] = entry;
    record->table[index] = data;
    return 1;
}

/* Independent copies reproduce embedded-array value copying; shared copies
 * reproduce pointer tables. Both retain the exact original entry pointers. */
static int obor_colourmap_copy(unsigned char **table, unsigned int capacity,
    int independent, unsigned char ***result)
{
    obor_colourmap_storage *source, *copy;
    if(!result) return 0;
    if(!table && !capacity) { *result = NULL; return 1; }
    source = obor_colourmap_find(table);
    if(!source || source->capacity != capacity) return 0;
    if(independent)
    {
        copy = obor_colourmap_clone(source, capacity);
        if(!copy) return 0;
        *result = copy->table;
    }
    else
    {
        if(source->refs == UINT_MAX) return 0;
        ++source->refs;
        *result = table;
    }
    return 1;
}

#endif
