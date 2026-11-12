/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Width-correct staging for the source-owned drawing property map.
 */
#include <float.h>

typedef union obor_drawmethod_member_value
{
    LONG integer;
    DOUBLE decimal;
    void *pointer;
} obor_drawmethod_member_value;

static int obor_drawmethod_byte_member(unsigned int property)
{
    return property == OBOR_DRAWMETHOD_PROPERTY_CHANNEL_BLUE
        || property == OBOR_DRAWMETHOD_PROPERTY_CHANNEL_GREEN
        || property == OBOR_DRAWMETHOD_PROPERTY_CHANNEL_RED;
}

static s_property_access_map obor_drawmethod_staged_map(
    s_property_access_map map, unsigned int property,
    obor_drawmethod_member_value *value)
{
    if(!map.field) return map;
    switch(map.type)
    {
    case VT_INTEGER:
        if(obor_drawmethod_byte_member(property))
        {
            unsigned char field;
            memcpy(&field, map.field, sizeof(field));
            value->integer = field;
        }
        else
        {
            memcpy(&value->integer, map.field, sizeof(value->integer));
        }
        map.field = &value->integer;
        break;
    case VT_DECIMAL:
    {
        float field;
        memcpy(&field, map.field, sizeof(field));
        value->decimal = field;
        map.field = &value->decimal;
        break;
    }
    case VT_PTR:
        memcpy(&value->pointer, map.field, sizeof(value->pointer));
        map.field = &value->pointer;
        break;
    default:
        break;
    }
    return map;
}

static HRESULT obor_drawmethod_get_member(const s_property_access_map *map,
    unsigned int property, ScriptVariant *result)
{
    obor_drawmethod_member_value value = {0};
    s_property_access_map staged = obor_drawmethod_staged_map(*map, property, &value);
    return property_access_get_member(&staged, result);
}

static HRESULT obor_drawmethod_set_member(const void *object,
    const s_property_access_map *map, unsigned int property, ScriptVariant *input)
{
    obor_drawmethod_member_value value = {0};
    s_property_access_map staged = *map;
    HRESULT result;
    if(object == &plainmethod)
        staged.config_flags &= ~PROPERTY_ACCESS_CONFIG_WRITE;
    if(!(staged.config_flags & PROPERTY_ACCESS_CONFIG_WRITE) || !staged.field)
        return property_access_set_member(object, &staged, input);
    staged = obor_drawmethod_staged_map(staged, property, &value);
    result = property_access_set_member(object, &staged, input);
    if(FAILED(result)) return result;
    switch(map->type)
    {
    case VT_INTEGER:
        if(input->vt != VT_INTEGER && input->vt != VT_DECIMAL) break;
        if(obor_drawmethod_byte_member(property))
        {
            unsigned char field = (unsigned char)value.integer;
            memcpy((void*)map->field, &field, sizeof(field));
        }
        else
        {
            memcpy((void*)map->field, &value.integer, sizeof(value.integer));
        }
        break;
    case VT_DECIMAL:
        if(input->vt == VT_INTEGER || input->vt == VT_DECIMAL)
        {
            float field;
            if(value.decimal > FLT_MAX || value.decimal < -FLT_MAX) break;
            field = (float)value.decimal;
            memcpy((void*)map->field, &field, sizeof(field));
        }
        break;
    case VT_PTR:
        memcpy((void*)map->field, &value.pointer, sizeof(value.pointer));
        break;
    default:
        break;
    }
    return result;
}

static const s_property_access_map obor_drawmethod_dump_map(
    const void *object, unsigned int property)
{
    /* The dump consumes each returned value before requesting the next row. */
    static obor_drawmethod_member_value value;
    return obor_drawmethod_staged_map(
        obor_profile_drawmethod_get_property_map(object, property), property, &value);
}
