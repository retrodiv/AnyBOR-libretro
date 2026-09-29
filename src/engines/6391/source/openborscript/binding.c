/* AnyBOR modification record: 2026-09-29.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Map legacy binding properties and the 6412 axis-handle properties to one
 * binding layout according to the logical profile.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/6391.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved. See LICENSE in OpenBOR root for license details.
 *
 * Copyright (c) 2004 - 2017 OpenBOR Team
 */

// Binding Properties
// 2018-03-31
// Caskey, Damon V.

#include "scriptcommon.h"

// Use string property argument to find an
// integer property constant and populate
// varlist->lval.
int mapstrings_binding(ScriptVariant **varlist, int paramCount)
{
    #define ARG_MINIMUM     2   // Minimum number of arguments allowed in varlist.
    #define ARG_PROPERTY    1   // Varlist element carrying which property is requested.

    char *propname = NULL;  // Placeholder for string property name from varlist.
    int prop;               // Placeholder for integer constant located by string.

    static const char *proplist[] =
    {
        "animation",
        "bind_x",
        "bind_y",
        "bind_z",
        "direction",
        "offset_x",
        "offset_y",
        "offset_z",
        "sort_id",
        "target"
    };
    static const char *proplist6412[] =
    {
        "animation", "direction", "enable", "offset", "sort_id", "target", NULL
    };

    // If the minimum argument count
    // was not passed, then there is
    // nothing to map. Return true - we'll
    // catch the mistake in property access
    // functions.
    if(paramCount < ARG_MINIMUM)
    {
        return 1;
    }

    // See macro - will return 0 on fail.
    if(obor_profile_build == 6412)
    {
        MAPSTRINGS(varlist[ARG_PROPERTY], proplist6412, 6,
                   "Property name '%s' is not supported by binding.\n");
    }
    else
    {
        MAPSTRINGS(varlist[ARG_PROPERTY], proplist, _BINDING_LEGACY_END,
                   "Property name '%s' is not supported by binding.\n");
    }


    // If we made it this far everything should be OK.
    return 1;

    #undef ARG_MINIMUM
    #undef ARG_PROPERTY
}

static e_binding_properties profile_binding_property(LONG property)
{
    static const e_binding_properties modern[] = {
        _BINDING_ANIMATION, _BINDING_DIRECTION, _BINDING_ENABLE,
        _BINDING_OFFSET, _BINDING_SORT_ID, _BINDING_TARGET
    };
    if(obor_profile_build == 6412)
        return property >= 0 && property < 6 ? modern[property] : _BINDING_END;
    return property >= 0 && property < _BINDING_LEGACY_END
               ? (e_binding_properties)property : _BINDING_END;
}

// Caskey, Damon  V.
// 2018-03-31
//
// Return a binding property. Requires
// the handle from binding entity
// property and property name to
// access.
HRESULT openbor_get_binding_property(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME       "openbor_get_binding_property(void handle, char property)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_HANDLE      0   // Handle (pointer to property structure).
    #define ARG_PROPERTY    1   // Property to access.

    s_bind                  *handle     = NULL; // Property handle.
    e_binding_properties    property    = 0;    // Property argument.

    // Clear pass by reference argument used to send
    // property data back to calling script.     .
    ScriptVariant_Clear(*pretvar);

    // Map string property name to a
    // matching integer constant.
    mapstrings_binding(varlist, paramCount);

    // Verify arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which property constant is accessed.
    if(paramCount < ARG_MINIMUM
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        // Populate local vars for readability.
        handle      = (s_bind *)varlist[ARG_HANDLE]->ptrVal;
        property    = profile_binding_property((LONG)varlist[ARG_PROPERTY]->lVal);
    }

    printf("\n\n Size entity: %d", sizeof(entity));
    printf("\n Size bind: %d", sizeof(s_bind));

    switch(property)
    {
        case _BINDING_ANIMATION:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->ani_bind;

            break;

        case _BINDING_BIND_X:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->bind_toggle.x;

            break;

        case _BINDING_BIND_Y:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->bind_toggle.y;

            break;

        case _BINDING_BIND_Z:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->bind_toggle.z;

            break;

        case _BINDING_DIRECTION:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->direction;

            break;

        case _BINDING_ENABLE:

            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)&handle->bind_toggle;

            break;

        case _BINDING_OFFSET:

            ScriptVariant_ChangeType(*pretvar, VT_PTR);
            (*pretvar)->ptrVal = (VOID *)&handle->offset;

            break;

        case _BINDING_OFFSET_X:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->offset.x;

            break;

        case _BINDING_OFFSET_Y:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->offset.y;

            break;

        case _BINDING_OFFSET_Z:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->offset.z;

            break;

        case _BINDING_SORT_ID:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)handle->sortid;

            break;

        case _BINDING_TARGET:

            // If there is no entity bound, we just
            // leave the return var empty.
            if(handle->ent)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = (VOID *)handle->ent;
            }

            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;

            break;
    }

    return S_OK;

    error_local:

    printf("You must provide a valid binding handle and property name: " SELF_NAME "\n");
    *pretvar = NULL;

    return E_FAIL;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_INDEX
}

// Caskey, Damon  V.
// 2018-04-01
//
// Mutate a binding property. Requires
// the handle from binding entity
// property, property name to modify,
// and the new value.
HRESULT openbor_set_binding_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    #define SELF_NAME           "set_binding_property(void handle, char property, value)"
    #define ARG_MINIMUM         3   // Minimum required arguments.
    #define ARG_HANDLE          0   // Handle (pointer to property structure).
    #define ARG_PROPERTY        1   // Property to access.
    #define ARG_VALUE           2   // New value to apply.

    int                     result      = S_OK; // Success or error?
    s_bind                  *handle     = NULL; // Property handle.
    e_binding_properties    property    = 0;    // Property to access.

    // Value carriers to apply on properties after
    // taken from argument.
    LONG         temp_int;

    // Map string property name to a
    // matching integer constant.
    mapstrings_binding(varlist, paramCount);

    // Verify incoming arguments. There should at least
    // be a pointer for the property handle and an integer
    // to determine which property is accessed.
    if(paramCount < ARG_MINIMUM
       || varlist[ARG_HANDLE]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }

    // Populate local handle and property vars.
    handle      = (s_bind *)varlist[ARG_HANDLE]->ptrVal;
    property    = profile_binding_property((LONG)varlist[ARG_PROPERTY]->lVal);

    // Which property to modify?
    switch(property)
    {

        case _BINDING_ANIMATION:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->ani_bind = temp_int;
            }

            break;

        case _BINDING_BIND_X:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->bind_toggle.x = temp_int;

            }

            break;

        case _BINDING_BIND_Y:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->bind_toggle.y = temp_int;
            }

            break;

        case _BINDING_BIND_Z:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->bind_toggle.z = temp_int;
            }

            break;

        case _BINDING_DIRECTION:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->direction = temp_int;
            }

            break;

        case _BINDING_ENABLE:
        case _BINDING_OFFSET:

            // Modern axis handles are changed through axis properties.
            break;

        case _BINDING_OFFSET_X:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->offset.x = temp_int;
            }

            break;

        case _BINDING_OFFSET_Y:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->offset.y = temp_int;
            }

            break;

        case _BINDING_OFFSET_Z:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->offset.z = temp_int;
            }

            break;

        case _BINDING_SORT_ID:

            if(SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
            {
                handle->sortid = temp_int;
            }

            break;

        case _BINDING_TARGET:

            handle->ent = (entity *)varlist[ARG_VALUE]->ptrVal;

            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;

            break;
    }

    return result;

    // Error trapping.
    error_local:

    printf("You must provide a valid binding handle, property, and new value: " SELF_NAME "\n");

    result = E_FAIL;
    return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_HANDLE
    #undef ARG_PROPERTY
    #undef ARG_VALUE
}
