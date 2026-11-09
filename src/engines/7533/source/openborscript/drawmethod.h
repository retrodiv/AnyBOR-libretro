/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare shared drawing-property selectors and the native callback
 * interface. Declare the source-defined drawing/palette interfaces and
 * shared selector domain.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

typedef enum
{
	DRAWMETHOD_PROPERTY_ALPHA,
	DRAWMETHOD_PROPERTY_BACKGROUND_TRANSPARENCY,
	DRAWMETHOD_PROPERTY_CENTER_X,
	DRAWMETHOD_PROPERTY_CENTER_Y,
	DRAWMETHOD_PROPERTY_CHANNEL_BLUE,
	DRAWMETHOD_PROPERTY_CHANNEL_GREEN,
	DRAWMETHOD_PROPERTY_CHANNEL_RED,
	DRAWMETHOD_PROPERTY_CLIP_POSITION_X,
	DRAWMETHOD_PROPERTY_CLIP_POSITION_Y,
	DRAWMETHOD_PROPERTY_CLIP_SIZE_X,
	DRAWMETHOD_PROPERTY_CLIP_SIZE_Y,
	DRAWMETHOD_PROPERTY_COLORSET_INDEX,
	DRAWMETHOD_PROPERTY_COLORSET_TABLE,
	DRAWMETHOD_PROPERTY_ENABLE,
	DRAWMETHOD_PROPERTY_FILL_COLOR,
	DRAWMETHOD_PROPERTY_FLIP_X,
	DRAWMETHOD_PROPERTY_FLIP_Y,
	DRAWMETHOD_PROPERTY_REPEAT_X,
	DRAWMETHOD_PROPERTY_REPEAT_Y,
	DRAWMETHOD_PROPERTY_ROTATE,
	DRAWMETHOD_PROPERTY_ROTATE_FLIP,
	DRAWMETHOD_PROPERTY_SCALE_X,
	DRAWMETHOD_PROPERTY_SCALE_Y,
	DRAWMETHOD_PROPERTY_SHIFT_X,
	DRAWMETHOD_PROPERTY_SPAN_X,
	DRAWMETHOD_PROPERTY_SPAN_Y,
	DRAWMETHOD_PROPERTY_TAG,
	DRAWMETHOD_PROPERTY_TINT_COLOR,
	DRAWMETHOD_PROPERTY_TINT_MODE,	
	DRAWMETHOD_PROPERTY_WATER_MODE,
	DRAWMETHOD_PROPERTY_WATER_PERSPECTIVE,
	DRAWMETHOD_PROPERTY_WATER_SIZE_BEGIN,
	DRAWMETHOD_PROPERTY_WATER_SIZE_END,
	DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE,
	DRAWMETHOD_PROPERTY_WATER_WAVE_LENGTH,
	DRAWMETHOD_PROPERTY_WATER_WAVE_SPEED,
	DRAWMETHOD_PROPERTY_WATER_WAVE_TIME,
	DRAWMETHOD_PROPERTY_END,
} e_drawmethod_properties;

// Drawmethod properties.
HRESULT openbor_allocate_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);
HRESULT openbor_copy_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);
HRESULT openbor_free_drawmethod(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);
HRESULT openbor_get_drawmethod_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);
HRESULT openbor_set_drawmethod_property(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);

int mapstrings_drawmethod(ScriptVariant **varlist, int paramCount);

/* Newer property numbering coexists with the legacy namespace. */
typedef enum
{
	OBOR_DRAWMETHOD_PROPERTY_ALPHA,
	OBOR_DRAWMETHOD_PROPERTY_CENTER_X,
	OBOR_DRAWMETHOD_PROPERTY_CENTER_Y,
	OBOR_DRAWMETHOD_PROPERTY_CHANNEL_BLUE,
	OBOR_DRAWMETHOD_PROPERTY_CHANNEL_GREEN,
	OBOR_DRAWMETHOD_PROPERTY_CHANNEL_RED,
	OBOR_DRAWMETHOD_PROPERTY_CLIP_POSITION_X,
	OBOR_DRAWMETHOD_PROPERTY_CLIP_POSITION_Y,
	OBOR_DRAWMETHOD_PROPERTY_CLIP_SIZE_X,
	OBOR_DRAWMETHOD_PROPERTY_CLIP_SIZE_Y,
	OBOR_DRAWMETHOD_PROPERTY_COLORSET_INDEX,
	OBOR_DRAWMETHOD_PROPERTY_COLORSET_TABLE,
	OBOR_DRAWMETHOD_PROPERTY_CONFIG,
	OBOR_DRAWMETHOD_PROPERTY_FILL_COLOR,
	OBOR_DRAWMETHOD_PROPERTY_REPEAT_X,
	OBOR_DRAWMETHOD_PROPERTY_REPEAT_Y,
	OBOR_DRAWMETHOD_PROPERTY_ROTATE,
	OBOR_DRAWMETHOD_PROPERTY_SCALE_X,
	OBOR_DRAWMETHOD_PROPERTY_SCALE_Y,
	OBOR_DRAWMETHOD_PROPERTY_SHIFT_X,
	OBOR_DRAWMETHOD_PROPERTY_SPAN_X,
	OBOR_DRAWMETHOD_PROPERTY_SPAN_Y,
	OBOR_DRAWMETHOD_PROPERTY_TAG,
	OBOR_DRAWMETHOD_PROPERTY_TINT_COLOR,
	OBOR_DRAWMETHOD_PROPERTY_TINT_MODE,	
	OBOR_DRAWMETHOD_PROPERTY_WATER_MODE,
	OBOR_DRAWMETHOD_PROPERTY_WATER_PERSPECTIVE,
	OBOR_DRAWMETHOD_PROPERTY_WATER_SIZE_BEGIN,
	OBOR_DRAWMETHOD_PROPERTY_WATER_SIZE_END,
	OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_AMPLITUDE,
	OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_LENGTH,
	OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_SPEED,
	OBOR_DRAWMETHOD_PROPERTY_WATER_WAVE_TIME,
	OBOR_DRAWMETHOD_PROPERTY_END,
} e_obor_drawmethod_properties;

HRESULT openbor_allocate_palette(ScriptVariant** varlist, ScriptVariant** pretvar, const int paramCount);
HRESULT openbor_copy_palette(ScriptVariant** varlist, ScriptVariant** pretvar, const int paramCount);
HRESULT openbor_load_palette(ScriptVariant** varlist, ScriptVariant** pretvar, const int paramCount);
HRESULT openbor_get_palette_property (const ScriptVariant* const* varlist, ScriptVariant** const pretvar, const int paramCount);
HRESULT openbor_set_palette_property(ScriptVariant** varlist, ScriptVariant** pretvar, const int paramCount);
