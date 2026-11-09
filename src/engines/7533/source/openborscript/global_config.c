/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve native global-configuration property names, flags, results and
 * typed field access. Select the native global-config property maps,
 * read/write flags, field conversions and setter results.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved. See LICENSE in OpenBOR root for license details.
 *
 * Copyright (c)  OpenBOR Team
 */

 /* 
 * Global Config Properties
 * 2022-05-10
 * Caskey, Damon V.
 */

#include "scriptcommon.h"

static int obor_profile_global_config_property_end(void)
{
    return obor_profile_build >= 7557 ? 6 : 8;
}

static const s_property_access_map obor_profile_global_config_get_property_map(const void* acting_object_param, const unsigned int property_index_param)
{
	s_property_access_map property_map;
	const s_global_config* acting_object = acting_object_param;
	unsigned int profile_index = property_index_param;
    if(obor_profile_build < 7557 && profile_index >= 8)
    {
        profile_index = GLOBAL_CONFIG_PROPERTY_END;
    }
    else if(obor_profile_build >= 7557)
    {
        profile_index = profile_index == 4 ? GLOBAL_CONFIG_PROPERTY_FLASH
            : profile_index == 5 ? GLOBAL_CONFIG_PROPERTY_SHOW_GO
            : profile_index >= 6 ? GLOBAL_CONFIG_PROPERTY_END : profile_index;
    }
    const e_profile_global_config_properties property_index = profile_index;

	switch (property_index)
	{
	case GLOBAL_CONFIG_PROPERTY_AJSPECIAL:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->ajspecial;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_AJSPECIAL";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_BLOCK_RATIO:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->block_ratio;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_BLOCK_RATIO";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_BLOCK_TYPE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->block_type;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_BLOCK_TYPE";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_CHEATS:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->cheats;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_CHEATS";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_ADJUST:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->flash_layer_adjust;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_ADJUST";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_SOURCE:
		property_map.config_flags = (e_property_access_config_flags)GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_SOURCE;
		property_map.field = &acting_object->flash_layer_source;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_SOURCE";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_FLASH_Z_SOURCE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->flash_z_source;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_FLASH_Z_SOURCE";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_SHOW_GO:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->showgo;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_SHOW_GO";
		property_map.type = VT_INTEGER;
		break;

	case GLOBAL_CONFIG_PROPERTY_FLASH:

		property_map.config_flags = (PROPERTY_ACCESS_CONFIG_READ | PROPERTY_ACCESS_CONFIG_STATIC_POINTER);
		property_map.field = &acting_object->flash;
		property_map.id_string = "GLOBAL_CONFIG_PROPERTY_FLASH";
		property_map.type = VT_PTR;
		break;

	case GLOBAL_CONFIG_PROPERTY_END:
	default:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_NONE;
		property_map.field = NULL;
		property_map.id_string = "Global Config";
		property_map.type = VT_EMPTY;
		break;

	}
	return property_map;
}


static HRESULT obor_profile_get_global_config_property(const ScriptVariant* const* varlist, ScriptVariant** const pretvar, const int paramCount)
{
	const char* SELF_NAME = "openbor_get_global_config_property(void global_config, int property)";
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
	if (paramCount < 2 || varlist[ARG_OBJECT]->vt != VT_PTR
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

	const s_global_config* const acting_object = (const s_global_config* const)varlist[ARG_OBJECT]->ptrVal;

	if (acting_object->object_type != OBJECT_TYPE_GLOBAL_CONFIG) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;
	const e_profile_global_config_properties property_id = (e_profile_global_config_properties)(property_id_param);
	const s_property_access_map property_map = obor_profile_global_config_get_property_map(acting_object, property_id);

	/*
	* If property id is in range, we send
	* the property map and return parameter
	* for population, then ext.
	*/

	if (property_id_param >= 0 && property_id_param < obor_profile_global_config_property_end()) {
		property_access_get_member(&property_map, *pretvar);
		return S_OK;
	}

	/*
	* Is this a dump request? If not, then
	* the property id is invalid.
	*/

	if (property_id_param == PROPERTY_ACCESS_DUMP) {
		property_access_dump_members(obor_profile_global_config_get_property_map, obor_profile_global_config_property_end(), acting_object);
	}
	else {
		printf("\n\nScript error: %s. Unknown property id (%d). \n\n", SELF_NAME, property_id_param);
		return E_FAIL;
	}

	return S_OK;
}


static HRESULT obor_profile_set_global_config_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount)
{
	const char* SELF_NAME = "openbor_set_global_config_property(void global_config, int property, <mixed> value)";
	const unsigned int ARG_OBJECT = 0;
	const unsigned int ARG_PROPERTY = 1;
	const unsigned int ARG_VALUE = 2;
	const unsigned int ARG_MINIMUM = 3;

	/*
	* Should at least be a pointer to the
	* acting object, a property id, and
	* a new value.
	*/

	if (paramCount < (int)ARG_MINIMUM || varlist[ARG_OBJECT]->vt != VT_PTR
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

	const s_global_config* const acting_object = (const s_global_config* const)varlist[ARG_OBJECT]->ptrVal;

	if (acting_object->object_type != OBJECT_TYPE_GLOBAL_CONFIG) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;
	const e_profile_global_config_properties property_id = (e_profile_global_config_properties)(property_id_param);

	if (property_id_param < 0 && property_id_param >= obor_profile_global_config_property_end()) {
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

	const s_property_access_map property_map = obor_profile_global_config_get_property_map(acting_object, property_id);

	/*
	* Populate the property value on
	* acting object and return OK/FAIL.
	*/

	return property_access_set_member(acting_object, &property_map, varlist[ARG_VALUE]);
}




/* 
* Use string property argument to find an
* integer property constant and populate
* varlist->lval.
*/ 
int mapstrings_global_config_property(ScriptVariant** varlist, int paramCount)
{
#define ARG_MINIMUM     2   // Minimum number of arguments allowed in varlist.
#define ARG_PROPERTY    1   // Varlist element carrying which property is requested.

	char* propname = NULL;  // Placeholder for string property name from varlist.
	int prop = 0;           // Placeholder for integer constant located by string.

	static const char* proplist[] =
	{
		"ajspecial",
		"block_ratio",
		"block_type",
		"cheats",
		"flash_layer_adjust",
		"flash_layer_source",
		"flash_z_source",
		"show_go"
	};

	//printf("\n\n mapstrings_global_config_property(%s)", varlist[ARG_PROPERTY]);

	/*
	* If the minimum argument count
	* was not passed, then there is
	* nothing to map. Return true - we'll
	* catch the mistake in property access
	* functions.
	*/
	if (paramCount < ARG_MINIMUM)
	{
		return 1;
	}

	/* See macro - will return 0 on fail. */
	MAPSTRINGS(varlist[ARG_PROPERTY], proplist, (int)(sizeof(proplist) / sizeof(*proplist)),
		"Property name '%s' is not supported by global config.\n");

	//const char *eps = (varlist[ARG_PROPERTY]->lVal < _GLOBAL_CONFIG_END && varlist[ARG_PROPERTY]->lVal >= 0) ? proplist[varlist[ARG_PROPERTY]->lVal] : "";
	//printf("\Global Config arg: %s\n", eps);

	/* If we made it this far everything should be OK. */
	return 1;

#undef ARG_MINIMUM
#undef ARG_PROPERTY
}

/*
* Caskey, Damon  V.
* 2022-05-10
*
* Return a global config property. 
* Requires the handle from global 
* config variant and property name 
* to access.
*/
HRESULT openbor_get_global_config_property(ScriptVariant** varlist, ScriptVariant** pretvar, int paramCount)
{
    if(obor_profile_build >= 7556)
    {
        return obor_profile_get_global_config_property((const ScriptVariant* const*)varlist, pretvar, paramCount);
    }

#define SELF_NAME       "get_global_config_property(void global_config, char property)"
#define ARG_MINIMUM     2   // Minimum required arguments.
#define ARG_OBJECT      0   // Handle (pointer to property structure).
#define ARG_PROPERTY    1   // Property to access.

	s_global_config* handle = NULL; // Property handle.
	e_global_config_properties	property = 0;    // Property argument.

	/*
	* Clear pass by reference argument used to send
	* property data back to calling script.     .
	*/
	ScriptVariant_Clear(*pretvar);

	/*
	* Map string property name to a
	* matching integer constant.
	*/
	mapstrings_global_config_property(varlist, paramCount);

	/*
	* Verify arguments. There should at least
	* be a pointer for the property handle and an integer
	* to determine which property constant is accessed.
	*/
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}
	else
	{
		/* Populate local vars for readability. */
		handle = (s_global_config*)varlist[ARG_OBJECT]->ptrVal;
		property = (e_global_config_properties)varlist[ARG_PROPERTY]->lVal;
	}

	switch (property)
	{
	case _GLOBAL_CONFIG_AJSPECIAL:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (e_ajspecial_config)handle->ajspecial;

		break;

	case _GLOBAL_CONFIG_BLOCK_RATIO:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = handle->block_ratio;

		break;

	case _GLOBAL_CONFIG_BLOCK_TYPE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = handle->block_type;

		break;

	case _GLOBAL_CONFIG_CHEATS:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (e_cheat_options)handle->cheats;

		break;

	case _GLOBAL_CONFIG_FLASH_LAYER_ADJUST:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (int)handle->flash_layer_adjust;

		break;

	case _GLOBAL_CONFIG_FLASH_LAYER_SOURCE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (int)handle->flash_layer_source;

		break;	

	case _GLOBAL_CONFIG_FLASH_Z_SOURCE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (int)handle->flash_z_source;

		break;

	case _GLOBAL_CONFIG_SHOW_GO:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (int)handle->showgo;

		break;

	default:

		printf("Unsupported property.\n");
		goto error_local;

		break;
	}

	return S_OK;

error_local:

	printf("\nYou must provide a valid pointer and property name: " SELF_NAME "\n");
	*pretvar = NULL;

	return E_FAIL;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_OBJECT
#undef ARG_INDEX
}

/*
* Caskey, Damon  V.
* 2022-05-10
*
* Mutate a global config property. 
* Requires the handle from global 
* config, property name to modify,
* and the new value.
*/
HRESULT openbor_set_global_config_property(ScriptVariant** varlist, ScriptVariant** pretvar, int paramCount)
{
    if(obor_profile_build >= 7556)
    {
        return obor_profile_set_global_config_property(varlist, pretvar, paramCount);
    }

#define SELF_NAME           "set_global_config_property(void global_config, char property, mixed value)"
#define ARG_MINIMUM         3   // Minimum required arguments.
#define ARG_OBJECT          0   // Handle (pointer to property structure).
#define ARG_PROPERTY        1   // Property to access.
#define ARG_VALUE           2   // New value to apply.

	int                     result = S_OK; // Success or error?
	s_global_config* handle = NULL; // Property handle.
	e_global_config_properties    property = 0;    // Property to access.

	/*
	* Value carriers to apply on properties after
	* taken from argument.
	*/
	LONG         temp_int;

	/*
	* Map string property name to a
	* matching integer constant.
	*/
	mapstrings_global_config_property(varlist, paramCount);

	/*
	* Verify incoming arguments. There should at least
	* be a pointer for the property handle and an integer
	* to determine which property is accessed.
	*/
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}

	/* Populate local handleand property vars. */
	handle = (s_global_config*)varlist[ARG_OBJECT]->ptrVal;
	property = (e_global_config_properties)varlist[ARG_PROPERTY]->lVal;

	/* Which property to modify ? */
	switch (property)
	{

	case _GLOBAL_CONFIG_AJSPECIAL:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->ajspecial = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_BLOCK_RATIO:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->block_ratio = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_BLOCK_TYPE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->block_type = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_CHEATS:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->cheats = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_FLASH_LAYER_ADJUST:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->flash_layer_adjust = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_FLASH_LAYER_SOURCE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->flash_layer_source = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_FLASH_Z_SOURCE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->flash_z_source = temp_int;
		}

		break;

	case _GLOBAL_CONFIG_SHOW_GO:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->showgo = temp_int;
		}

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
