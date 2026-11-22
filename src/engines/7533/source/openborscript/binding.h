/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Keep legacy binding IDs and append shared selectors for modern profile
 * properties. Declare the shared binding selectors used by the native
 * profile maps.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */


typedef enum
{
	BIND_PROPERTY_ANIMATION_FRAME,
	BIND_PROPERTY_ANIMATION_ID,
	BIND_PROPERTY_CONFIG,
	BIND_PROPERTY_DIRECTION_ADJUST,
	BIND_PROPERTY_META_DATA,
	BIND_PROPERTY_META_TAG,
	BIND_PROPERTY_OFFSET_X,
	BIND_PROPERTY_OFFSET_Y,
	BIND_PROPERTY_OFFSET_Z,
	BIND_PROPERTY_SORT_ID,
	BIND_PROPERTY_TARGET,
	BIND_PROPERTY_END,
} e_bind_properties;

// Binding properties.
int mapstrings_bind_property(ScriptVariant **varlist, int paramCount);
HRESULT openbor_get_bind_property(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount);
HRESULT openbor_set_bind_property(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount);
HRESULT openbor_update_bind(ScriptVariant **varlist, ScriptVariant **pretvar, int paramCount);

