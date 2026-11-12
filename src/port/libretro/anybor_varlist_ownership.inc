/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 *
 * The engine thread owns this registry. Only array and entity constructors
 * register collections. Raw script properties can hold an opaque value.
 */

enum { OBOR_VARLIST_BUCKETS = 256 };
static Varlist *obor_varlist_buckets[OBOR_VARLIST_BUCKETS];

static Varlist **obor_varlist_find_slot(const void *value)
{
    uintptr_t address = (uintptr_t)value;
    size_t bucket = ((address >> 4) ^ (address >> 12)) &
                    (OBOR_VARLIST_BUCKETS - 1);
    Varlist **slot = &obor_varlist_buckets[bucket];
    while(*slot && *slot != value)
        slot = &(*slot)->obor_owner_next;
    return slot;
}

Varlist *obor_varlist_find(const void *value)
{
    Varlist *table = value ? *obor_varlist_find_slot(value) : NULL;
    return table && table->magic == varlist_magic ? table : NULL;
}

static void obor_varlist_reset(void)
{
    memset(obor_varlist_buckets, 0, sizeof(obor_varlist_buckets));
}

void obor_varlist_register(Varlist *value)
{
    Varlist **slot = obor_varlist_find_slot(value);
    value->obor_owner_next = NULL;
    value->obor_owners = 1;
    value->obor_dispose_pending = 0;
    *slot = value;
}

void obor_varlist_retain(const void *value)
{
    Varlist *table = obor_varlist_find(value);
    if(!table) return;
    if(table->obor_owners == SIZE_MAX)
    {
        borExit(1);
        return;
    }
    ++table->obor_owners;
}

void obor_varlist_release(const void *value, int dispose)
{
    if(!value) return;
    Varlist **slot = obor_varlist_find_slot(value);
    Varlist *table = *slot;
    if(!table || !table->obor_owners) return;
    if(dispose) table->obor_dispose_pending = 1;
    if(--table->obor_owners == 0 && table->obor_dispose_pending)
    {
        *slot = table->obor_owner_next;
        if(table->magic == varlist_magic) Varlist_Clear(table);
        free(table);
    }
}

void obor_entity_varlist_set(entity *owner, void *value)
{
    Varlist *table = obor_varlist_find(value);
    if(owner->obor_varlist_owned != table)
    {
        obor_varlist_retain(table);
        /* A detached collection remains accessible through any existing
         * borrowed handle, unless a real owner requested its disposal. */
        obor_varlist_release(owner->obor_varlist_owned, 0);
        owner->obor_varlist_owned = table;
    }
    owner->varlist = value;
}
