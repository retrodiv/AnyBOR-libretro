/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve source-defined drawing property names, numeric IDs, callback
 * results and field ownership with bounded typed access. Select native
 * drawing and palette callbacks, names, copy widths, object tags and typed
 * field access.
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

 // Drawmethod Properties
 // 2019-03-28
 // Caskey, Damon V.

#include "scriptcommon.h"

static const s_property_access_map obor_profile_drawmethod_get_property_map(const void* acting_object_param, const unsigned int property_index_param)
{
	s_property_access_map property_map;
	const s_drawmethod* acting_object = acting_object_param;
	const e_obor_drawmethod_properties property_index = property_index_param;

	switch (property_index)
	{
	case OBOR_DRAWMETHOD_PROPERTY_ALPHA:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->alpha;
		property_map.id_string = "DRAWMETHOD_PROPERTY_ALPHA";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CENTER_X:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->centerx;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CENTER_X";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CENTER_Y:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->centery;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CENTER_Y";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CHANNEL_BLUE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->channelb;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CHANNEL_BLUE";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CHANNEL_GREEN:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->channelg;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CHANNEL_GREEN";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CHANNEL_RED:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->channelr;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CHANNEL_RED";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CLIP_POSITION_X:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->clipx;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CLIP_POSITION_X";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CLIP_POSITION_Y:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->clipy;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CLIP_POSITION_Y";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CLIP_SIZE_X:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->clipw;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CLIP_SIZE_X";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CLIP_SIZE_Y:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->cliph;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CLIP_SIZE_Y";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_COLORSET_INDEX:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->remap;
		property_map.id_string = "DRAWMETHOD_PROPERTY_COLORSET_INDEX";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_COLORSET_TABLE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->table;
		property_map.id_string = "DRAWMETHOD_PROPERTY_COLORSET_TABLE";
		property_map.type = VT_PTR;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_CONFIG:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->config;
		property_map.id_string = "DRAWMETHOD_PROPERTY_CONFIG";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_FILL_COLOR:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->fillcolor;
		property_map.id_string = "DRAWMETHOD_PROPERTY_FILL_COLOR";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_REPEAT_X:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->xrepeat;
		property_map.id_string = "DRAWMETHOD_PROPERTY_REPEAT_X";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_REPEAT_Y:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->yrepeat;
		property_map.id_string = "DRAWMETHOD_PROPERTY_REPEAT_Y";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_ROTATE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->rotate;
		property_map.id_string = "DRAWMETHOD_PROPERTY_ROTATE";
		property_map.type = VT_DECIMAL;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_SCALE_X:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->scalex;
		property_map.id_string = "DRAWMETHOD_PROPERTY_SCALE_X";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_SCALE_Y:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->scaley;
		property_map.id_string = "DRAWMETHOD_PROPERTY_SCALE_Y";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_SPAN_X:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->xspan;
		property_map.id_string = "DRAWMETHOD_PROPERTY_SPAN_X";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_SPAN_Y:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->yspan;
		property_map.id_string = "DRAWMETHOD_PROPERTY_SPAN_Y";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_TINT_COLOR:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->tintcolor;
		property_map.id_string = "DRAWMETHOD_PROPERTY_TINT_COLOR";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_TINT_MODE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->tintmode;
		property_map.id_string = "DRAWMETHOD_PROPERTY_TINT_MODE";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_MODE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.watermode;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_MODE";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_PERSPECTIVE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.perspective;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_PERSPECTIVE";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_SIZE_BEGIN:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.beginsize;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_SIZE_BEGIN";
		property_map.type = VT_DECIMAL;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_SIZE_END:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.endsize;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_SIZE_END";
		property_map.type = VT_DECIMAL;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.amplitude;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_LENGTH:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.wavelength;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE";
		property_map.type = VT_DECIMAL;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_SPEED:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.wavespeed;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_WAVE_SPEED";
		property_map.type = VT_DECIMAL;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_TIME:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_MACRO_DEFAULT;
		property_map.field = &acting_object->water.wavetime;
		property_map.id_string = "DRAWMETHOD_PROPERTY_WATER_WAVE_TIME";
		property_map.type = VT_INTEGER;
		break;

	case OBOR_DRAWMETHOD_PROPERTY_END:
	default:
		property_map.config_flags = PROPERTY_ACCESS_CONFIG_NONE;
		property_map.field = NULL;
		property_map.id_string = "Drawmethod";
		property_map.type = VT_EMPTY;
		break;

	}
	return property_map;
}


#include "anybor_drawmethod_member.inc"

static HRESULT obor_profile_get_drawmethod_property(const ScriptVariant* const* varlist, ScriptVariant** const pretvar, const int paramCount)
{
	const char* SELF_NAME = "openbor_get_drawmethod_property(void drawmethod, int property)";
	const int ARG_OBJECT = 0;
	const int ARG_PROPERTY = 1;

	/*
	* Clear pass by reference argument used to send
	* property data back to calling script.
	*/
	ScriptVariant_Clear(*pretvar);

	/*
	* Should at least be a pointer to the
	* acting object and a property id.
	*/
	if (paramCount < 2 || !varlist || !varlist[ARG_OBJECT] || !varlist[ARG_PROPERTY]
        || varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER) {
		printf("\n\n Script error: %s. You must provide a valid object pointer and property id.\n\n", SELF_NAME);
		return E_FAIL;
	}

	/*
	* Now let's make sure the object type is
	* correct (ex. drawmethod vs. model) so we
	* can shut down gracefully if there's
	* a mismatch.
	*/

	const s_drawmethod* const acting_object = (const s_drawmethod* const)varlist[ARG_OBJECT]->ptrVal;

	if (!acting_object || acting_object->object_type != OBJECT_TYPE_DRAWMETHOD) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;

	const e_obor_drawmethod_properties property_id = (e_obor_drawmethod_properties)(property_id_param);
	const s_property_access_map property_map = obor_profile_drawmethod_get_property_map(acting_object, property_id);

	/*
	* If property id is in range, we send
	* the property map and return parameter
	* for population, then ext.
	*/

	if (property_id_param >= 0 && property_id_param < OBOR_DRAWMETHOD_PROPERTY_END) {
		obor_drawmethod_get_member(&property_map, property_id, *pretvar);
		return S_OK;
	}

	/*
	* Is this a dump request? If not, then
	* the property id is invalid.
	*/

	if (property_id_param == PROPERTY_ACCESS_DUMP) {
		property_access_dump_members(obor_drawmethod_dump_map, OBOR_DRAWMETHOD_PROPERTY_END, acting_object);
	}
	else {
		printf("\n\nScript error: %s. Unknown property id (%d). \n\n", SELF_NAME, property_id_param);
		return E_FAIL;
	}

	return S_OK;
}


static HRESULT obor_profile_set_drawmethod_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount)
{
	const char* SELF_NAME = "openbor_set_drawmethod_property(void drawmethod, int property, <mixed> value)";
	const int ARG_OBJECT = 0;
	const int ARG_PROPERTY = 1;
	const int ARG_VALUE = 2;
	const int ARG_MINIMUM = 3;

	/*
	* Should at least be a pointer to the
	* acting object, a property id, and
	* a new value.
	*/

	if (paramCount < ARG_MINIMUM || !varlist || !varlist[ARG_OBJECT]
        || !varlist[ARG_PROPERTY] || !varlist[ARG_VALUE]
        || varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER
		|| paramCount < ARG_MINIMUM) {
		printf("\n\n Script error: %s. You must provide a valid object pointer, property id, and new value.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	/*
	* Now let's make sure the object type is
	* correct (ex. drawmethod vs. model) so we
	* can shut down gracefully if there's
	* a mismatch.
	*/

	const s_drawmethod* const acting_object = (const s_drawmethod* const)varlist[ARG_OBJECT]->ptrVal;

	if (!acting_object || acting_object->object_type != OBJECT_TYPE_DRAWMETHOD) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const int property_id_param = (const int)varlist[ARG_PROPERTY]->lVal;
	const e_obor_drawmethod_properties property_id = (e_obor_drawmethod_properties)(property_id_param);

	if (property_id_param < 0 && property_id_param >= OBOR_DRAWMETHOD_PROPERTY_END) {
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

	const s_property_access_map property_map = obor_profile_drawmethod_get_property_map(acting_object, property_id);

	/*
	* Populate the property value on
	* acting object and return OK/FAIL.
	*/

	return obor_drawmethod_set_member(acting_object, &property_map, property_id, varlist[ARG_VALUE]);

	return S_OK;
}


static HRESULT obor_profile_copy_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
	const char* SELF_NAME = "copy_drawmethod(void target, void source)";
	const int ARG_MINIMUM = 2;   // Minimum required arguments.
	const int ARG_TARGET = 0;
	const int ARG_SOURCE = 1;

	// Verify arguments. 
	if (paramCount < ARG_MINIMUM
        || !varlist || !varlist[ARG_SOURCE] || !varlist[ARG_TARGET]
		|| varlist[ARG_SOURCE]->vt != VT_PTR
		|| varlist[ARG_TARGET]->vt != VT_PTR)
	{
		printf("\n\n Script error: %s. You must provide a valid target and source object.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}
	
	// Populate local vars with arguments.
	const s_drawmethod* const source = (const s_drawmethod *)varlist[ARG_SOURCE]->ptrVal;
	s_drawmethod* target = (s_drawmethod *)varlist[ARG_TARGET]->ptrVal;

	/*
	* Default drawmethod (plainmethod) is a const and 
	* therefore cannot be mutated. We'll send a warning 
	* to the log and exit function. Note it's perfectly 
	* fine to use the default drawmethod as a source, 
	* and that's probably what will be done most of the 
	* time anyway.
	*/
	if (target == &plainmethod)
	{
		printf("\n Warning: The default drawmethod and its properties are read only: %s\n\n", SELF_NAME);

		return S_OK;
	}

    if(!target || !source)
    {
        printf("\n\n Script error: %s. You must provide a valid target and source object.\n\n", SELF_NAME);
        *pretvar = NULL;
        return E_FAIL;
    }

	// Copy values into target drawmethod.
	memcpy(target, source, sizeof(*target));

	return S_OK;
}


// Use string property argument to find an
// integer property constant and populate
// varlist->lval.
int mapstrings_drawmethod(ScriptVariant **varlist, int paramCount)
{
#define ARG_MINIMUM     2   // Minimum number of arguments allowed in varlist.
#define ARG_PROPERTY    1   // Varlist element carrying which property is requested.

	char *propname = NULL;  // Placeholder for string property name from varlist.
	int prop;               // Placeholder for integer constant located by string.

	static const char *proplist[] =
	{
		"alpha",
		"background_transparency",
		"center_x",
		"center_y",
		"channel_blue",
		"channel_green",
		"channel_red",
		"clip_position_x",
		"clip_position_y",
		"clip_size_x",
		"clip_size_y",
		"colorset_index",
		"colorset_table",
		"enable",
		"fill_color",
		"flip_x",
		"flip_y",
		"repeat_x",
		"repeat_y",
		"rotate",
		"rotate_flip",
		"scale_x",
		"scale_y",
		"shift_x",
		"span_x",
		"span_y",
		"tag",
		"tint_color",
		"tint_mode",
		"water_mode",
		"water_perspective",
		"water_size_begin",
		"water_size_end",
		"water_wave_amplitude",
		"water_wave_length",
		"water_wave_speed",
		"water_wave_time"
	};

	// If the minimum argument count
	// was not passed, then there is
	// nothing to map. Return true - we'll
	// catch the mistake in property access
	// functions.
	if (paramCount < ARG_MINIMUM)
	{
		return 1;
	}

	// See macro - will return 0 on fail.
	MAPSTRINGS(varlist[ARG_PROPERTY], proplist, DRAWMETHOD_PROPERTY_END,
		"Property name '%s' is not supported by drawmethod.\n");


	// If we made it this far everything should be OK.
	return 1;

#undef ARG_MINIMUM
#undef ARG_PROPERTY
}

// Caskey, Damon  V.
// 2019-04-15
//
// Allocate a new drawmethod and return the pointer.
HRESULT openbor_allocate_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
	extern s_drawmethod *allocate_drawmethod();
	s_drawmethod *drawmethod;

	ScriptVariant_ChangeType(*pretvar, VT_PTR);
	
	if ((drawmethod = allocate_drawmethod()))
	{
		(*pretvar)->ptrVal = (s_drawmethod *)drawmethod;
	}

	return S_OK;
}

// Caskey, Damon  V.
// 2019-04-15
//
// Copy properties of source drawmethod to target drawmethod.
HRESULT openbor_copy_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(obor_profile_build >= 7582) return obor_profile_copy_drawmethod(varlist, pretvar, paramCount);

#define SELF_NAME       "openbor_copy_drawmethod(void source, void target)"
#define ARG_MINIMUM     2   // Minimum required arguments.
#define ARG_SOURCE		0
#define ARG_TARGET		1

	s_drawmethod *source;
	s_drawmethod *target;

	// Verify arguments. 
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_SOURCE]->vt != VT_PTR
		|| varlist[ARG_TARGET]->vt != VT_PTR)
	{
		*pretvar = NULL;
		goto error_local;
	}
	else
	{
		// Populate local vars with arguments.
		source = (s_drawmethod *)varlist[ARG_SOURCE]->ptrVal;
		target = (s_drawmethod *)varlist[ARG_TARGET]->ptrVal;
	}

	// Default drawmethod (plainmethod) is a const and therefore cannot
	// be mutated. If the author tries it's sure to cause a crash or
	// even worse, untracable bugs. We'll send a warning to the log and 
	// exit function. Note it's perfectly fine to use the default 
	// drawmethod as a source, and that's probably what will be done 
	// most of the time anyway.
	if (target == &plainmethod)
	{
		printf("\n Warning: The default drawmethod and its properties are read only: " SELF_NAME "\n");

		return S_OK;
	}

	// Copy values into target drawmethod.
	memcpy(target, source, sizeof(*target));

	return S_OK;

error_local:

	printf("\nYou must provide valid source and target drawmethod pointers: " SELF_NAME "\n");
	*pretvar = NULL;

	return E_FAIL;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_SOURCE
#undef ARG_TARGET
}

// Caskey, Damon  V.
// 2019-04-16
//
// Allocate a new drawmethod and return the pointer.
HRESULT openbor_free_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
#define SELF_NAME       "openbor_free_drawmethod(void drawmethod)"
#define ARG_MINIMUM     1   // Minimum required arguments.
#define ARG_TARGET		0

	s_drawmethod *target;

	// Verify arguments.
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_TARGET]->vt != VT_PTR)
	{
		*pretvar = NULL;
		goto error_local;
	}
	else
	{
		// Populate local vars with arguments.
		target = (s_drawmethod *)varlist[ARG_TARGET]->ptrVal;
	}

	// Default drawmethod (plainmethod) is a const and therefore cannot
	// be mutated. If the author tries it's sure to cause a crash or
	// even worse, untracable bugs. We'll send a warning to the log and 
	// exit function.
	if (target == &plainmethod)
	{
		printf("\n Warning: The default drawmethod and its properties are read only: " SELF_NAME "\n");

		return S_OK;
	}

	// Free the drawmethod.
	free(target);

	return S_OK;

error_local:

	printf("\n You must provide a valid drawmethod pointer: " SELF_NAME "\n");
	*pretvar = NULL;

	return E_FAIL;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_TARGET
}

// Caskey, Damon  V.
// 2019-03-28
//
// Return a drawmethod property. Requires
// the pointer from drawmethod property
// and a property to access.
HRESULT openbor_get_drawmethod_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(obor_profile_build >= 7573) return obor_profile_get_drawmethod_property((const ScriptVariant* const*)varlist, pretvar, paramCount);

#define SELF_NAME       "openbor_get_drawmethod_property(void drawmethod, char property)"
#define ARG_MINIMUM     2   // Minimum required arguments.
#define ARG_OBJECT      0   // Handle (pointer to property structure).
#define ARG_PROPERTY    1   // Property to access.

	s_drawmethod				*handle = NULL;		// Property handle.
	e_drawmethod_properties		property = 0;		// Property argument.

	// Clear pass by reference argument used to send
	// property data back to calling script.     .
	ScriptVariant_Clear(*pretvar);

	// Verify arguments. There should at least
	// be a pointer for the property handle and an integer
	// to determine which property constant is accessed.
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}
	else
	{
		// Populate local vars for readability.
		handle = (s_drawmethod *)varlist[ARG_OBJECT]->ptrVal;
		property = (LONG)varlist[ARG_PROPERTY]->lVal;

    /* This intermediate source removed these switch cases before renumbering. */
    if(obor_profile_build >= 7567 &&
        (property == DRAWMETHOD_PROPERTY_BACKGROUND_TRANSPARENCY ||
         property == DRAWMETHOD_PROPERTY_ENABLE ||
         property == DRAWMETHOD_PROPERTY_FLIP_X ||
         property == DRAWMETHOD_PROPERTY_FLIP_Y ||
         property == DRAWMETHOD_PROPERTY_ROTATE_FLIP))
    {
        property = DRAWMETHOD_PROPERTY_END;
    }

	}

	switch (property)
	{		
	case DRAWMETHOD_PROPERTY_ALPHA:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->alpha;

		break;

	case DRAWMETHOD_PROPERTY_BACKGROUND_TRANSPARENCY:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->transbg;

		break;

	case DRAWMETHOD_PROPERTY_CENTER_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->centerx;

		break;

	case DRAWMETHOD_PROPERTY_CENTER_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->centery;

		break;

	case DRAWMETHOD_PROPERTY_CHANNEL_BLUE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->channelb;

		break;

	case DRAWMETHOD_PROPERTY_CHANNEL_GREEN:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->channelg;

		break;

	case DRAWMETHOD_PROPERTY_CHANNEL_RED:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->channelr;

		break;

	case DRAWMETHOD_PROPERTY_CLIP_POSITION_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->clipx;

		break;

	case DRAWMETHOD_PROPERTY_CLIP_POSITION_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->clipy;

		break;

	case DRAWMETHOD_PROPERTY_CLIP_SIZE_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->clipw;

		break;

	case DRAWMETHOD_PROPERTY_CLIP_SIZE_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->cliph;

		break;

	case DRAWMETHOD_PROPERTY_COLORSET_INDEX:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->remap;

		break;

	case DRAWMETHOD_PROPERTY_COLORSET_TABLE:

		ScriptVariant_ChangeType(*pretvar, VT_PTR);
		(*pretvar)->ptrVal = (VOID *)(handle->table);

		break;

	case DRAWMETHOD_PROPERTY_ENABLE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->flag;

		break;
	
	case DRAWMETHOD_PROPERTY_FILL_COLOR:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->fillcolor;

		break;

	case DRAWMETHOD_PROPERTY_FLIP_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->flipx;

		break;

	case DRAWMETHOD_PROPERTY_FLIP_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->flipy;

		break;

	case DRAWMETHOD_PROPERTY_REPEAT_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->xrepeat;

		break;

	case DRAWMETHOD_PROPERTY_REPEAT_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->yrepeat;

		break;

	case DRAWMETHOD_PROPERTY_ROTATE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->rotate;

		break;

	case DRAWMETHOD_PROPERTY_ROTATE_FLIP:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->fliprotate;

		break;

	case DRAWMETHOD_PROPERTY_SCALE_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->scalex;

		break;

	case DRAWMETHOD_PROPERTY_SCALE_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->scaley;

		break;

	case DRAWMETHOD_PROPERTY_SHIFT_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->shiftx;

		break;

	case DRAWMETHOD_PROPERTY_SPAN_X:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->xspan;

		break;

	case DRAWMETHOD_PROPERTY_SPAN_Y:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->yspan;

		break;

	case DRAWMETHOD_PROPERTY_TAG:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->tag;

		break;

	case DRAWMETHOD_PROPERTY_TINT_COLOR:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->tintcolor;

		break;

	case DRAWMETHOD_PROPERTY_TINT_MODE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->tintmode;

		break;

	case DRAWMETHOD_PROPERTY_WATER_MODE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.watermode;

		break;

	case DRAWMETHOD_PROPERTY_WATER_PERSPECTIVE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.perspective;

		break;

	case DRAWMETHOD_PROPERTY_WATER_SIZE_BEGIN:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.beginsize;

		break;

	case DRAWMETHOD_PROPERTY_WATER_SIZE_END:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.endsize;

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.amplitude;

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_LENGTH:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.wavelength;

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_SPEED:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.wavespeed;

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_TIME:

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
		(*pretvar)->lVal = (LONG)handle->water.wavetime;

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

// Caskey, Damon  V.
// 2019-03-28
//
// Mutate a drawmethod property. Requires
// the pointer from drawmethod property
// and a property to access.
HRESULT openbor_set_drawmethod_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount)
{
    if(obor_profile_build >= 7573) return obor_profile_set_drawmethod_property(varlist, pretvar, paramCount);

#define SELF_NAME			"set_drawmethod_property(void drawmethod, char property, mixed value)"
#define ARG_MINIMUM         3   // Minimum required arguments.
#define ARG_OBJECT          0   // Handle (pointer to property structure).
#define ARG_PROPERTY        1   // Property to access.
#define ARG_VALUE           2   // New value to apply.

	s_drawmethod			*handle = NULL;	// Property handle.
	e_drawmethod_properties	property = 0;	// Property to access.

	// Value carriers to apply on properties after
	// taken from argument.
	LONG         temp_int;

	// Verify incoming arguments. There should at least
	// be a pointer for the property handle and an integer
	// to determine which property is accessed.
	if (paramCount < ARG_MINIMUM
		|| varlist[ARG_OBJECT]->vt != VT_PTR
		|| varlist[ARG_PROPERTY]->vt != VT_INTEGER)
	{
		*pretvar = NULL;
		goto error_local;
	}

	// Populate local handle and property vars.
	handle = (s_drawmethod *)varlist[ARG_OBJECT]->ptrVal;
	property = (LONG)varlist[ARG_PROPERTY]->lVal;

    /* This intermediate source removed these switch cases before renumbering. */
    if(obor_profile_build >= 7567 &&
        (property == DRAWMETHOD_PROPERTY_BACKGROUND_TRANSPARENCY ||
         property == DRAWMETHOD_PROPERTY_ENABLE ||
         property == DRAWMETHOD_PROPERTY_FLIP_X ||
         property == DRAWMETHOD_PROPERTY_FLIP_Y ||
         property == DRAWMETHOD_PROPERTY_ROTATE_FLIP))
    {
        property = DRAWMETHOD_PROPERTY_END;
    }


	// Default drawmethod (plainmethod) is a const and therefore cannot
	// be mutated. If the author tries it's sure to cause a crash or
	// even worse, untracable bugs. We'll send a warning to the log and 
	// exit function.
	if (handle == &plainmethod)
	{
		printf("\n Warning: The default drawmethod and its properties are read only: " SELF_NAME "\n");
		
		return S_OK;
	}		

	// Which property to modify?
	switch (property)
	{
	
	case DRAWMETHOD_PROPERTY_ALPHA:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->alpha = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_BACKGROUND_TRANSPARENCY:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->transbg = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CENTER_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->centerx = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CENTER_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->centery = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CHANNEL_BLUE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->channelb = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CHANNEL_GREEN:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->channelg = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CHANNEL_RED:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->channelr = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CLIP_POSITION_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->clipx = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CLIP_POSITION_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->clipy = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CLIP_SIZE_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->clipw = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_CLIP_SIZE_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->cliph = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_COLORSET_INDEX:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->remap = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_COLORSET_TABLE:

		handle->table = (VOID *)varlist[ARG_VALUE]->ptrVal;

		break;

	case DRAWMETHOD_PROPERTY_ENABLE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->flag = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_FILL_COLOR:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->fillcolor = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_FLIP_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->flipx = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_FLIP_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->flipy = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_REPEAT_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->xrepeat = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_REPEAT_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->yrepeat = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_ROTATE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->rotate = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_ROTATE_FLIP:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->fliprotate = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_SCALE_X:
		
		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->scalex = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_SCALE_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->scaley = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_SHIFT_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->shiftx = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_SPAN_X:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->xspan = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_SPAN_Y:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->yspan = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_TAG:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->tag = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_TINT_COLOR:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->tintcolor = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_TINT_MODE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->tintmode = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_WATER_MODE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.watermode = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_WATER_PERSPECTIVE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.perspective = temp_int;
		}

	case DRAWMETHOD_PROPERTY_WATER_SIZE_BEGIN:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.beginsize = temp_int;
		}

	case DRAWMETHOD_PROPERTY_WATER_SIZE_END:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.endsize = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.amplitude = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_LENGTH:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.wavelength = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_SPEED:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.wavespeed = temp_int;
		}

		break;

	case DRAWMETHOD_PROPERTY_WATER_WAVE_TIME:

		if (SUCCEEDED(ScriptVariant_IntegerValue(varlist[ARG_VALUE], &temp_int)))
		{
			handle->water.wavetime = temp_int;
		}

		break;

	default:

		printf("Unsupported property.\n");
		goto error_local;

		break;
	}

	return S_OK;

	// Error trapping.
error_local:

	printf("\nYou must provide a valid pointer, property name, and new value: " SELF_NAME "\n");
	
	return E_FAIL;

#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_OBJECT
#undef ARG_PROPERTY
#undef ARG_VALUE
}

/* Source-specific palette script APIs. */
HRESULT openbor_allocate_palette(ScriptVariant **varlist, ScriptVariant **pretvar, const int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

	unsigned char* acting_object = NULL; 

	ScriptVariant_ChangeType(*pretvar, VT_PTR);
	
	if ((acting_object = malloc(PAL_BYTES)))
	{
		memset(acting_object, 0, MAX_PAL_SIZE);

		(*pretvar)->ptrVal = (unsigned char *)acting_object;
	}

	return S_OK;
}

HRESULT openbor_copy_palette(ScriptVariant** varlist, ScriptVariant** pretvar, const int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

	const char* SELF_NAME = "openbor_copy_palette(void target, void source)";
	const int ARG_MINIMUM = 2;   // Minimum required arguments.
	const int ARG_SOURCE = 1;
	const int ARG_TARGET = 0;

	// Verify arguments. 
	if (paramCount < ARG_MINIMUM || !varlist || !varlist[ARG_SOURCE] || !varlist[ARG_TARGET]
        || varlist[ARG_SOURCE]->vt != VT_PTR || varlist[ARG_TARGET]->vt != VT_PTR || !varlist[ARG_SOURCE]->ptrVal || !varlist[ARG_TARGET]->ptrVal) {

		printf("\n\n Script error: %s. You must provide a valid target object and source object.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	// Populate local vars with arguments.
	const unsigned char* const source = (const unsigned char* const)varlist[ARG_SOURCE]->ptrVal;
	unsigned char* target = (unsigned char*)varlist[ARG_TARGET]->ptrVal;

	// Copy values into target object.
	memmove(target, source, sizeof(*target));

	return S_OK;
}

HRESULT openbor_load_palette(ScriptVariant** varlist, ScriptVariant** pretvar, const int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

	const char* SELF_NAME = "openbor_load_palette(void target, char path)";
	const int ARG_MINIMUM = 2;   // Minimum required arguments.
	const int ARG_SOURCE = 1;
	const int ARG_TARGET = 0;

	// Verify arguments. 
	if (paramCount < ARG_MINIMUM || !varlist || !varlist[ARG_SOURCE] || !varlist[ARG_TARGET]
        || varlist[ARG_SOURCE]->vt != VT_STR || varlist[ARG_TARGET]->vt != VT_PTR) {

		printf("\n\n Script error: %s. You must provide a valid target object and source path.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	// Populate local vars with arguments.
	char* source = (char*)StrCache_Get(varlist[ARG_SOURCE]->strVal);
	unsigned char* target = (unsigned char*)varlist[ARG_TARGET]->ptrVal;

	if (!target) {
		printf("\n\nScript error: %s. Missing or invalid target pointer.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	/*
	* Clear pass by reference argument used to send
	* property data back to calling script.
	*/
	ScriptVariant_Clear(*pretvar);
	ScriptVariant_ChangeType(*pretvar, VT_INTEGER);

	/* Read file and populate palette with values. */
	(*pretvar)->lVal = load_palette(target, source);

	return S_OK;
}

HRESULT openbor_get_palette_property(const ScriptVariant* const* varlist, ScriptVariant** const pretvar, const int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

	const char* SELF_NAME = (obor_profile_build < 7582 ? "openbor_set_color_component(void drawmethod, int color_index, int color_component)" : "openbor_set_palette_property(void drawmethod, int color_index, int color_component)");
	const int ARG_OBJECT = 0;
	const int ARG_COLOR_INDEX = 1;
	const int ARG_COLOR_COMPONENT = 2;
	const int ARG_MINIMUM = 3;

	/*
	* Verify parameters.
	*/
	if (paramCount < ARG_MINIMUM || !varlist || !varlist[ARG_OBJECT] || !varlist[ARG_COLOR_INDEX] || !varlist[ARG_COLOR_COMPONENT]
        || varlist[ARG_OBJECT]->vt != VT_PTR || varlist[ARG_COLOR_INDEX]->vt != VT_INTEGER || varlist[ARG_COLOR_COMPONENT]->vt != VT_INTEGER) {
		printf("\n\n Script error: %s. You must provide a valid object pointer, color index, and color component.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	/*
	* Verify we don't have a NULL pointer.
	* Our target object is an array, not
	* a structure, so there's no really
	* good way to verify type.
	*/

	unsigned char* acting_object = (unsigned char*)varlist[ARG_OBJECT]->ptrVal;

	if (!acting_object) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	/*
	* Clear pass by reference argument used to send
	* property data back to calling script.
	*/
	ScriptVariant_Clear(*pretvar);

	const unsigned char color_index_param = (unsigned char)varlist[ARG_COLOR_INDEX]->lVal;
	const e_color_components color_component_param = (e_color_components)varlist[ARG_COLOR_COMPONENT]->lVal;

	const uint32_t component_id = (uint32_t)COLOR_COMPONENT_END * color_index_param + (uint32_t)color_component_param;

	/*
	* If property id is in range, we send
	* the property map and return parameter
	* for population, then ext.
	*/

	if (component_id < MAX_PAL_SIZE) {		

		ScriptVariant_ChangeType(*pretvar, VT_INTEGER);
			
		(*pretvar)->lVal = acting_object[component_id];

		return S_OK;
	}

	/*
	* Is this a dump request? If not, then
	* the property id is invalid.
	*/

	//if (color_index_param == PROPERTY_ACCESS_DUMP) {
		
	//}
	//else {
	//	printf("\n\nScript error: %s. Unknown color index (%d) or component (%d). \n\n", SELF_NAME, color_index_param, color_component_param);
	//	return E_FAIL;
	//}

    /* The original7580getter reports unknown final byte positions. */
    if(obor_profile_build < 7581)
    {
        printf("\n\nScript error: %s. Unknown color index (%d) or component (%d). \n\n", SELF_NAME, color_index_param, (int)color_component_param);
        return E_FAIL;
    }

	return S_OK;
}

HRESULT openbor_set_palette_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount)
{
    if(!pretvar || !*pretvar) return E_FAIL;

	const char* SELF_NAME = (obor_profile_build < 7582 ? "openbor_set_color_component(void drawmethod, int color_index, int color_component, int value)" : "openbor_set_palette_property(void drawmethod, int color_index, int color_component, int value)");
	const int ARG_OBJECT = 0;
	const int ARG_COLOR_INDEX = 1;
	const int ARG_COLOR_COMPONENT = 2;
	const int ARG_VALUE = 3;
	const int ARG_MINIMUM = 4;

	/*
	* Verify parameters.
	*/
	if (paramCount < ARG_MINIMUM || !varlist || !varlist[ARG_OBJECT] || !varlist[ARG_COLOR_INDEX] || !varlist[ARG_COLOR_COMPONENT] || !varlist[ARG_VALUE]
        || varlist[ARG_OBJECT]->vt != VT_PTR || varlist[ARG_COLOR_INDEX]->vt != VT_INTEGER || varlist[ARG_COLOR_COMPONENT]->vt != VT_INTEGER) {
		printf("\n\n Script error: %s. You must provide a valid object pointer, color index, color component, and new value.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	/*
	* Verify we don't have a NULL pointer. 
	* Our target object is an array, not 
	* a structure, so there's no really
	* good way to verify type.
	*/

	unsigned char* acting_object = (unsigned char*)varlist[ARG_OBJECT]->ptrVal;

	if (!acting_object) {
		printf("\n\nScript error: %s. Object pointer is not correct type.\n\n", SELF_NAME);
		*pretvar = NULL;
		return E_FAIL;
	}

	const unsigned char color_index_param = (unsigned char)varlist[ARG_COLOR_INDEX]->lVal;
	const e_color_components color_component_param = (e_color_components)varlist[ARG_COLOR_COMPONENT]->lVal;
	
	
	const uint32_t component_id = (uint32_t)COLOR_COMPONENT_END * color_index_param + (uint32_t)color_component_param;
	
	/* Keep the source flattened index, including defined neighboring entries. */
    if(component_id < MAX_PAL_SIZE)
    {
        acting_object[component_id] = (unsigned int)varlist[ARG_VALUE]->lVal;
    }

	return S_OK;
}
