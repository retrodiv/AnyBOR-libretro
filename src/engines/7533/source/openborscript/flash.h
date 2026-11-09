/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the imported 7735flash property namespace and callbacks.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

typedef enum
{
	FLASH_PROPERTY_LAYER_ADJUST,
	FLASH_PROPERTY_LAYER_SOURCE,
	FLASH_PROPERTY_MODEL_BLOCK,
	FLASH_PROPERTY_MODEL_HIT,
	FLASH_PROPERTY_Z_SOURCE,
	FLASH_PROPERTY_END,
} e_flash_properties;

// Binding properties.
HRESULT openbor_get_flash_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount);
HRESULT openbor_set_flash_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount);
