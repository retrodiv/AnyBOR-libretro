/* Historical script-file traversal over explicit 32-bit fields.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Included after the engine's variable tables and ScriptVariant declarations.
 */
#include <limits.h>
#include "obor_script_record32.h"
#include "obor_resources.h"

extern char *obor_arena_base(void);

static size_t obor_script32_target_variant_size(void)
{
    /* The historical Darwin build uses i386. The ARM/RISC-V ports retain
     * their 32-bit architecture's double alignment; Windows uses its ABI. */
#if defined(__APPLE__)
    return 12;
#elif defined(_WIN32) || defined(__arm__) || defined(__aarch64__) || defined(__arm64__) || defined(__riscv)
    return 16;
#else
    return 12;
#endif
}

static int obor_script32_tables(size_t *named, size_t *indexed)
{
    size_t bytes, pointers;
    *named = *indexed = 0;
    if(max_global_vars < 0 || max_indexed_vars < 0) return 0;
    if(max_global_vars > 0) {
        if(!global_var_list) return 0;
        bytes = obor_allocation_size(global_var_list);
        if((size_t)max_global_vars > bytes / sizeof(*global_var_list)) return 0;
        pointers = (size_t)max_global_vars * sizeof(*global_var_list);
        if((size_t)max_global_vars > (bytes - pointers) / sizeof(**global_var_list)) return 0;
        *named = (size_t)max_global_vars;
    }
    if(max_indexed_vars > 0) {
        if(!indexed_var_list) return 0;
        bytes = obor_allocation_size(indexed_var_list);
        *indexed = (size_t)max_indexed_vars + (obor_profile_build >= 3039);
        if(*indexed > bytes / sizeof(*indexed_var_list)) return 0;
    }
    return 1;
}

static int obor_script32_pack_variant(obor_script32_variant *to,
        const ScriptVariant *from, int strict)
{
    uintptr_t address, base;
    memset(to, 0, sizeof(*to));
    to->type = (uint32_t)from->vt;
    switch(from->vt) {
    case VT_EMPTY: return 1;
    case VT_INTEGER:
        obor_script32_put_u32(to->value, (uint32_t)from->lVal);
        return 1;
    case VT_DECIMAL:
        memcpy(to->value, &from->dblVal, 8);
        return 1;
    case VT_STR:
        if(strict && !StrCache_GetIfPresent(from->strVal)) return 0;
        obor_script32_put_u32(to->value, (uint32_t)from->strVal);
        return 1;
    case VT_PTR:
        if(!from->ptrVal) return 1;
        address = (uintptr_t)from->ptrVal;
        base = (uintptr_t)obor_arena_base();
        /* Every engine arena is 4 GiB aligned and smaller than 4 GiB.
         * Its low pointer word uniquely identifies an interior reference. */
        if(strict && ((base & UINT32_MAX) || address < base ||
           address - base > UINT32_MAX || !obor_allocation_contains(from->ptrVal, 1))) return 0;
        obor_script32_put_u32(to->value, (uint32_t)address);
        return 1;
    default:
        if(strict) return 0;
        to->type = VT_EMPTY;
        return 1;
    }
}

static int obor_script32_unpack_variant(ScriptVariant *to,
        const obor_script32_variant *from)
{
    ScriptVariant value;
    uint32_t word = obor_script32_u32(from->value);
    int32_t integer;
    uintptr_t base;
    memset(&value, 0, sizeof(value));
    value.vt = (VARTYPE)from->type;
    switch(from->type) {
    case VT_EMPTY: break;
    case VT_INTEGER:
        memcpy(&integer, &word, sizeof(integer));
        value.lVal = integer;
        break;
    case VT_DECIMAL:
        memcpy(&value.dblVal, from->value, 8);
        break;
    case VT_STR:
        if(word > INT_MAX || !StrCache_GetIfPresent((int)word)) return 0;
        value.strVal = (int)word;
        break;
    case VT_PTR:
        if(!word) break;
        base = (uintptr_t)obor_arena_base();
        if((base & UINT32_MAX) || word > UINTPTR_MAX - base) return 0;
        value.ptrVal = (void *)(base + word);
        if(!obor_allocation_contains(value.ptrVal, 1)) return 0;
        break;
    default: return 0;
    }
    /* The original assigns cache indices, rather than cloning strings or
     * collecting the overwritten slot. Keep that observable cache behavior. */
    *to = value;
    return 1;
}

static int obor_script32_pack_node(obor_script32_node *to,
        const s_variantnode *from, int strict)
{
    size_t length = from->key ? strlen(from->key) : 0;
    memset(to, 0, sizeof(*to));
    if(length >= sizeof(to->key)) {
        if(strict) return 0;
    } else if(length) memcpy(to->key, from->key, length);
    to->owner = (uint32_t)(uintptr_t)from->owner;
    return obor_script32_pack_variant(&to->variant, &from->value, strict);
}

static int obor_script32_unpack_node(s_variantnode *to,
        const obor_script32_node *from, int owner_untouched)
{
    ScriptVariant value;
    char *name;
    size_t length;
    if(!obor_script32_unpack_variant(&value, &from->variant) ||
       (!owner_untouched && from->owner &&
        from->owner != (uint32_t)(uintptr_t)to->owner)) return 0;
    length = strlen(from->key);
    name = malloc(length + 1);
    if(!name) return 0;
    memcpy(name, from->key, length + 1);
    free(to->key);
    to->key = name;
    to->value = value;
    if(!owner_untouched && !from->owner) to->owner = NULL;
    return 1;
}

static int obor_script_file32_write(FILE *stream, size_t variant_size)
{
    unsigned char bytes[48];
    obor_script32_node node;
    obor_script32_variant value;
    size_t named, indexed, active, count = 0, i, available;
    size_t node_size = obor_script32_node_size(variant_size);
    if(!stream || !node_size || !obor_script32_tables(&named, &indexed) ||
       max_global_var_index < -1) return 0;
    active = max_global_var_index < 0 ? 0 : (size_t)max_global_var_index + 1;
    if(active > named) return 0;
    for(i = 0; i < active; ++i) {
        if(!global_var_list[i]) return 0;
        if(!global_var_list[i]->owner) ++count;
    }
    if(count > INT32_MAX) return 0;
    obor_script32_put_u32(bytes, (uint32_t)count);
    if(fwrite(bytes, 1, 4, stream) != 4) return 0;
    for(i = 0; i < active; ++i) if(!global_var_list[i]->owner) {
        if(!obor_script32_pack_node(&node, global_var_list[i], 1) ||
           !obor_script32_write_node(bytes, sizeof(bytes), variant_size, &node) ||
           fwrite(bytes, 1, node_size, stream) != node_size) return 0;
    }
    if(!indexed) return 1;
    /* The original carries the named loop index into this write. Its actual
     * indexed allocation contains one extra slot. Preserve defined reads. */
    available = active < indexed ? indexed - active : 0;
    if(available > (size_t)max_indexed_vars) available = (size_t)max_indexed_vars;
    for(i = 0; i < available; ++i) {
        if(!obor_script32_pack_variant(&value, indexed_var_list + active + i, 1) ||
           !obor_script32_write_variant(bytes, sizeof(bytes), variant_size, &value) ||
           fwrite(bytes, 1, variant_size, stream) != variant_size) return 0;
    }
    return available == (size_t)max_indexed_vars;
}

static int obor_script_file32_read(FILE *stream, size_t variant_size)
{
    unsigned char bytes[48];
    obor_script32_node node;
    obor_script32_variant wire;
    ScriptVariant value;
    size_t named, indexed, iterations, i, received, wanted, maximum;
    size_t node_size = obor_script32_node_size(variant_size);
    uint32_t count, remaining;
    long position;
    if(!stream || !node_size || !obor_script32_tables(&named, &indexed)) return 0;
    if(fread(bytes, 1, 4, stream) != 4) return 0;
    count = obor_script32_u32(bytes);
    if(count > INT32_MAX) return 0;
    if(!named) max_global_var_index = -1;
    else max_global_var_index = count >= named ? (int)named - 1 : (int)count;
    iterations = max_global_var_index < 0 ? 0 : (size_t)max_global_var_index + 1;
    for(i = 0; i < iterations; ++i) {
        if(!global_var_list[i] || !obor_script32_pack_node(&node, global_var_list[i], 0) ||
           !obor_script32_write_node(bytes, sizeof(bytes), variant_size, &node)) return 0;
        received = fread(bytes, 1, node_size, stream);
        if(received && (!obor_script32_read_node(&node, bytes, node_size, variant_size) ||
                       !obor_script32_unpack_node(global_var_list[i], &node,
                                                received <= variant_size + 24))) return 0;
    }
    if(!indexed) return !ferror(stream);
    position = ftell(stream);
    if(position < 0 || (unsigned long)position > UINT32_MAX ||
       (size_t)max_indexed_vars > UINT32_MAX / variant_size) return 0;
    /* Both original reader eras subtract the file position from the named
     * loop counter. Reproduce its 32-bit unsigned comparison and clamp. */
    remaining = (uint32_t)iterations - (uint32_t)position;
    maximum = (size_t)max_indexed_vars * variant_size;
    if(remaining > maximum) remaining = (uint32_t)maximum;
    for(i = 0; remaining; ++i) {
        wanted = remaining < variant_size ? remaining : variant_size;
        if(!obor_script32_pack_variant(&wire, indexed_var_list + i, 0) ||
           !obor_script32_write_variant(bytes, sizeof(bytes), variant_size, &wire)) return 0;
        received = fread(bytes, 1, wanted, stream);
        if(received && (!obor_script32_read_variant(&wire, bytes, variant_size, variant_size) ||
                       !obor_script32_unpack_variant(&value, &wire))) return 0;
        if(received) indexed_var_list[i] = value;
        remaining -= (uint32_t)wanted;
        if(received < wanted) break;
    }
    return !ferror(stream);
}
