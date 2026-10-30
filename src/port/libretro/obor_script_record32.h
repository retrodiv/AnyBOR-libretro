/* Explicit fields of the historical 32-bit script save records.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef OBOR_SCRIPT_RECORD32_H
#define OBOR_SCRIPT_RECORD32_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* These are wire fields, not live ScriptVariant or s_variantnode objects.
 * References remain opaque here; the engine must resolve them before use. */
typedef struct {
    unsigned char value[8];
    uint32_t type;
} obor_script32_variant;

typedef struct {
    obor_script32_variant variant;
    char key[24];
    uint32_t owner;
} obor_script32_node;

static inline uint32_t obor_script32_u32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static inline void obor_script32_put_u32(unsigned char *p, uint32_t value)
{
    p[0] = (unsigned char)value;
    p[1] = (unsigned char)(value >> 8);
    p[2] = (unsigned char)(value >> 16);
    p[3] = (unsigned char)(value >> 24);
}

static inline size_t obor_script32_node_size(size_t variant_size)
{
    return variant_size == 12 ? 40 : variant_size == 16 ? 48 : 0;
}

static inline int obor_script32_type_valid(uint32_t type)
{
    return type == 0 || type == 1 || type == 2 || type == 5 || type == 6;
}

static inline int obor_script32_read_variant(obor_script32_variant *out,
        const unsigned char *bytes, size_t available, size_t variant_size)
{
    uint32_t type;
    if(!out || !bytes || !obor_script32_node_size(variant_size) ||
       available < variant_size) return 0;
    type = obor_script32_u32(bytes + 8);
    if(!obor_script32_type_valid(type)) return 0;
    memcpy(out->value, bytes, sizeof(out->value));
    out->type = type;
    return 1;
}

static inline int obor_script32_write_variant(unsigned char *bytes,
        size_t available, size_t variant_size, const obor_script32_variant *in)
{
    if(!in || !bytes || !obor_script32_node_size(variant_size) ||
       available < variant_size || !obor_script32_type_valid(in->type)) return 0;
    memset(bytes, 0, variant_size);
    memcpy(bytes, in->value, sizeof(in->value));
    obor_script32_put_u32(bytes + 8, in->type);
    return 1;
}

static inline int obor_script32_read_node(obor_script32_node *out,
        const unsigned char *bytes, size_t available, size_t variant_size)
{
    obor_script32_node node;
    size_t size = obor_script32_node_size(variant_size);
    if(!out || !bytes || !size || available < size ||
       !memchr(bytes + variant_size, 0, sizeof(node.key)) ||
       !obor_script32_read_variant(&node.variant, bytes, available, variant_size))
        return 0;
    memcpy(node.key, bytes + variant_size, sizeof(node.key));
    node.owner = obor_script32_u32(bytes + variant_size + sizeof(node.key));
    *out = node;
    return 1;
}

static inline int obor_script32_write_node(unsigned char *bytes,
        size_t available, size_t variant_size, const obor_script32_node *in)
{
    size_t size = obor_script32_node_size(variant_size);
    if(!in || !bytes || !size || available < size ||
       !memchr(in->key, 0, sizeof(in->key)) ||
       !obor_script32_type_valid(in->variant.type)) return 0;
    memset(bytes, 0, size);
    obor_script32_write_variant(bytes, available, variant_size, &in->variant);
    memcpy(bytes + variant_size, in->key, sizeof(in->key));
    obor_script32_put_u32(bytes + variant_size + sizeof(in->key), in->owner);
    return 1;
}

#endif
