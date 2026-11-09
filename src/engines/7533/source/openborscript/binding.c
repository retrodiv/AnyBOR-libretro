/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Map native legacy, 6412 and 6510 binding property names and IDs to the
 * shared layout. Select native binding fields, initialization, object tags,
 * argument conversions and property results.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved. See LICENSE in OpenBOR root for license details.
 *
 * Copyright (c) 2004 OpenBOR Team
 */

// Binding Properties
// 2018-03-31
// Caskey, Damon V.

#include "scriptcommon.h"

static const s_property_access_map obor_profile_bind_get_property_map(const void* acting_object_param, const unsigned int property_index_param)
{
    s_property_access_map property_map;
    const s_bind* acting_object = acting_object_param;
    const e_bind_properties property_index = property_index_param;

    switch (property_index)
    {
    case BIND_PROPERTY_ANIMATION_FRAME:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->frame;
        property_map.id_string = "BIND_PROPERTY_ANIMATION_FRAME";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_ANIMATION_ID:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->animation;
        property_map.id_string = "BIND_PROPERTY_ANIMATION_ID";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_CONFIG:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->config;
        property_map.id_string = "BIND_PROPERTY_CONFIG";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_DIRECTION_ADJUST:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->direction_adjust;
        property_map.id_string = "BIND_PROPERTY_DIRECTION_ADJUST";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_META_DATA:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->meta_data;
        property_map.id_string = "BIND_PROPERTY_META_DATA";
        property_map.type = VT_PTR;
        break;

    case BIND_PROPERTY_META_TAG:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->meta_tag;
        property_map.id_string = "BIND_PROPERTY_META_TAG";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_OFFSET_X:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->offset.x;
        property_map.id_string = "BIND_PROPERTY_OFFSET_X";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_OFFSET_Y:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->offset.y;
        property_map.id_string = "BIND_PROPERTY_OFFSET_Y";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_OFFSET_Z:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->offset.z;
        property_map.id_string = "BIND_PROPERTY_OFFSET_Z";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_SORT_ID:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->sortid;
        property_map.id_string = "BIND_PROPERTY_SORT_ID";
        property_map.type = VT_INTEGER;
        break;

    case BIND_PROPERTY_TARGET:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
        property_map.field = &acting_object->target;
        property_map.id_string = "BIND_PROPERTY_TARGET";
        property_map.type = VT_PTR;
        break;

    case BIND_PROPERTY_END:
    default:
        property_map.config_flags = PROPERTY_ACCESS_CONFIG_NONE;
        property_map.field = NULL;
        property_map.id_string = "Bind";
        property_map.type = VT_EMPTY;
        break;

    }
    return property_map;
}

static HRESULT obor_profile_get_bind_property(const ScriptVariant* const* varlist, ScriptVariant** const pretvar, const int paramCount)
{
    const char* SELF_NAME = "openbor_get_bind_property(void bind, int property)";
    const unsigned int ARG_OBJECT = 0; // Handle (pointer to property structure).
    const unsigned int ARG_PROPERTY = 1; // Property to access.

    /*
    * Clear pass by reference argument used to send
    * property data back to calling script.
    */
    ScriptVariant_Clear(*pretvar);

    /*
    * Should at least be a pointer to the
    * acting object and a  property id.
    */
    if (paramCount < 2
        || varlist[ARG_OBJECT]->vt != VT_PTR
        || varlist[ARG_PROPERTY]->vt != VT_INTEGER) {
        printf("\n\n Script error: %s. You must provide a valid object pointer and property id.\n\n", SELF_NAME);
        return E_FAIL;
    }

    /*
    * Now let's make sure the object type is
    * correct (ex. entity vs. model) so we
    * can shut down gracefully if there's
    * a mismatch.
    */

    const s_bind* const acting_object = (const s_bind* const)varlist[ARG_OBJECT]->ptrVal;

    if (acting_object->object_type != OBJECT_TYPE_BIND) {
        printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
        *pretvar = NULL;
        return E_FAIL;
    }

    const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;
    const e_bind_properties property_id = (e_bind_properties)(property_id_param);
    const s_property_access_map property_map = obor_profile_bind_get_property_map(acting_object, property_id);

    /*
    * If property id is in range, we send
    * the property map and return parameter
    * for population, then ext.
    */

    if (property_id_param >= 0 && property_id_param < BIND_PROPERTY_END) {
        property_access_get_member(&property_map, *pretvar);
        return S_OK;
    }

    /*
    * Is this a dump request? If not, then
    * the property id is invalid.
    */

    if (property_id_param == PROPERTY_ACCESS_DUMP) {
        property_access_dump_members(obor_profile_bind_get_property_map, BIND_PROPERTY_END, acting_object);
    }
    else {
        printf("\n\nScript error: %s. Unknown property id (%d). \n\n", SELF_NAME, property_id_param);
        return E_FAIL;
    }

    return S_OK;
}

static HRESULT obor_profile_set_bind_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount)
{
    const char* SELF_NAME = "openbor_set_bind_property(void bind, int property, <mixed> value)";
    const unsigned int ARG_OBJECT = 0;
    const unsigned int ARG_PROPERTY = 1;
    const unsigned int ARG_VALUE = 2;
    const unsigned int ARG_MINIMUM = 3;

    /*
    * Should at least be a pointer to the
    * acting object, a property id, and
    * a new value.
    */

    if (paramCount < (int)ARG_MINIMUM
        || varlist[ARG_OBJECT]->vt != VT_PTR
        || varlist[ARG_PROPERTY]->vt != VT_INTEGER) {
        printf("\n\n Script error: %s. You must provide a valid object pointer, property id, and new value.\n\n", SELF_NAME);
        *pretvar = NULL;
        return E_FAIL;
    }

    /*
    * Now let's make sure the object type is
    * correct (ex. entity vs. model) so we
    * can shut down gracefully if there's
    * a mismatch.
    */

    const s_bind* const acting_object = (const s_bind* const)varlist[ARG_OBJECT]->ptrVal;

    if (acting_object->object_type != OBJECT_TYPE_BIND) {
        printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
        *pretvar = NULL;
        return E_FAIL;
    }

    const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;
    const e_bind_properties property_id = (e_bind_properties)(property_id_param);

    if (property_id_param < 0 && property_id_param >= BIND_PROPERTY_END) {
        printf("\n\nScript error: %s. Unknown property id (%d). \n\n", SELF_NAME, property_id_param);
        return E_FAIL;
    }

    /*
    * Get map of property. This is a struct
    * that contains the property variable
    * type, reference to the acting object's
    * appropriate data member, text name,
    * read only, etc.
    */

    const s_property_access_map property_map = obor_profile_bind_get_property_map(acting_object, property_id);

    /*
    * Populate the property value on
    * acting object and return OK/FAIL.
    */

    return property_access_set_member(acting_object, &property_map, varlist[ARG_VALUE]);
}


/*
* Caskey, Damon  V.
* 2018-03-31
*
* Return a binding property. Requires
* the object from binding entity
* property and property name to
* access.
*/
HRESULT openbor_get_bind_property(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount)
{
    if(obor_profile_build >= 7555)
    {
        return obor_profile_get_bind_property((const ScriptVariant* const*)varlist, pretvar, paramCount);
    }

    #define SELF_NAME       "openbor_get_bind_property(void bind, int property)"
    #define ARG_MINIMUM     2   // Minimum required arguments.
    #define ARG_OBJECT      0   // Handle (pointer to property structure).
    #define ARG_PROPERTY    1   // Property to access.

    s_bind              *object     = NULL; // Property object.
    e_bind_properties	property    = 0;    // Property argument.

    /* 
	* Clear pass by reference argument used to send
    * property data back to calling script.     .
    */
	ScriptVariant_Clear(*pretvar);

	/*
    * Verify arguments. There should at least
    * be a pointer for the property object and an integer
    * to determine which property constant is accessed.
    */
	if(paramCount < ARG_MINIMUM
       || varlist[ARG_OBJECT]->vt != VT_PTR
       || varlist[ARG_PROPERTY]->vt != VT_INTEGER)
    {
        *pretvar = NULL;
        goto error_local;
    }
    else
    {
        /* Populate local vars for readability. */
        object      = (s_bind *)varlist[ARG_OBJECT]->ptrVal;
        property    = (LONG)varlist[ARG_PROPERTY]->lVal;
    }

    switch(property)
    {
		case BIND_PROPERTY_ANIMATION_FRAME:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (LONG)object->frame;

			break;

		case BIND_PROPERTY_ANIMATION_ID:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (LONG)object->animation;

			break;

		case BIND_PROPERTY_CONFIG:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (e_bind_config)object->config;

			break;

        case BIND_PROPERTY_DIRECTION_ADJUST:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (e_direction_adjust)object->direction_adjust;

            break;

		case BIND_PROPERTY_META_DATA:

			ScriptVariant_ChangeType(*pretvar, VT_PTR);
			(*pretvar)->ptrVal = (s_meta_data*)object->meta_data;

			break;

		case BIND_PROPERTY_META_TAG:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (LONG)object->meta_tag;

			break;		

        case BIND_PROPERTY_OFFSET_X:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (LONG)object->offset.x;

			break;

		case BIND_PROPERTY_OFFSET_Y:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (LONG)object->offset.y;

			break;

		case BIND_PROPERTY_OFFSET_Z:

			ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			(*pretvar)->lVal = (LONG)object->offset.z;

			break;			       

        case BIND_PROPERTY_SORT_ID:

            ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
            (*pretvar)->lVal = (LONG)object->sortid;

            break;

        case BIND_PROPERTY_TARGET:

            // If there is no entity bound, we just
            // leave the return var empty.
            if(object->target)
            {
                ScriptVariant_ChangeType(*pretvar, VT_PTR);
                (*pretvar)->ptrVal = (entity *)object->target;
            }

            break;

        default:

            printf("Unsupported property.\n");
            goto error_local;

            break;
    }

    return S_OK;

    error_local:

    printf("\nYou must provide a valid pointer and property constant: " SELF_NAME "\n");
    *pretvar = NULL;

    return E_FAIL;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_OBJECT
    #undef ARG_INDEX
}

/*
* Caskey, Damon  V.
* 2018-04-01
*
* Mutate a binding property. Requires
* the object from binding entity
* property, property name to modify,
* and the new value.
*/
HRESULT openbor_set_bind_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(obor_profile_build >= 7555)
    {
        return obor_profile_set_bind_property(varlist, pretvar, paramCount);
    }

    #define SELF_NAME           "set_bind_property(void bind, int property, mixed value)"
    #define ARG_MINIMUM         3   // Minimum required arguments.
    #define ARG_OBJECT          0   // Handle (pointer to property structure).
    #define ARG_PROPERTY        1   // Property to access.
    #define ARG_VALUE           2   // New value to apply.

	int                     result = S_OK; // Success or error?
	s_bind                  *object = NULL; // Property object.
	e_bind_properties    property = 0;    // Property to access.

	/*
	* Value carriers to apply on properties after
	* taken from argument.
	*/
	LONG         temp_int;
	
	/*
	* Verify incoming arguments. There should at least
	* be a pointer for the property object and an integer
	* to determine which property is accessed.
	*/
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}

	/* Populate local objectand property vars. */
	object = (s_bind *)varlist[ARG_OBJECT]->ptrVal;
	property = (LONG)varlist[ARG_PROPERTY]->lVal;

	/* Which property to modify ? */
	switch (property)
	{

		case BIND_PROPERTY_ANIMATION_FRAME:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->frame = temp_int;
			}

			break;

		case BIND_PROPERTY_ANIMATION_ID:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->animation = temp_int;
			}

			break;

		case BIND_PROPERTY_CONFIG:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->config = temp_int;
			}

			break;

		case BIND_PROPERTY_DIRECTION_ADJUST:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->direction_adjust = temp_int;
			}

			break;

		case BIND_PROPERTY_META_DATA:

			object->meta_data = (s_meta_data*)varlist[ARG_VALUE]->ptrVal;

			break;

		case BIND_PROPERTY_META_TAG:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->meta_tag = temp_int;
			}

			break;

		case BIND_PROPERTY_OFFSET_X:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->offset.x = temp_int;
			}

			break;

		case BIND_PROPERTY_OFFSET_Y:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->offset.y = temp_int;
			}

			break;

		case BIND_PROPERTY_OFFSET_Z:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->offset.z = temp_int;
			}

			break;

		case BIND_PROPERTY_SORT_ID:

			if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
			{
				object->sortid = temp_int;
			}

			break;

		case BIND_PROPERTY_TARGET:

			object->target = (entity *)varlist[ARG_VALUE]->ptrVal;

			break;

		default:

			printf("Unsupported property.\n");
			goto error_local;

			break;
	}

	return result;

	// Error trapping.
    error_local:

	printf("\nYou must provide a valid pointer, property name, and new value: " SELF_NAME "\n");

	result = E_FAIL;
	return result;

    #undef SELF_NAME
    #undef ARG_MINIMUM
    #undef ARG_OBJECT
    #undef ARG_PROPERTY
    #undef ARG_VALUE
}

/*
* Caskey, Damon  V.
* 2018-10-11
*
* Run engine's native bind update function.
*/
HRESULT openbor_update_bind(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
#define SELF_NAME           "update_bind(void entity)"
#define ARG_MINIMUM         1   // Minimum required arguments.
#define ARG_ENTITY          0   // Target entity.

	int		result	= S_OK;	// Success or error?
	entity	*ent	= NULL; // Target entity.

	// Verify incoming arguments.
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_ENTITY]->vt != VT_PTR)
	{
		*pretvar = NULL;
		goto error_local;
	}

	// Populate local object and property vars.
	ent = (entity *)varlist[ARG_ENTITY]->ptrVal;

	adjust_bind(ent);

	return result;

	// Error trapping.
error_local:

	printf("You must provide a valid entity: " SELF_NAME "\n");

	result = E_FAIL;
	return result;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_ENTITY
}