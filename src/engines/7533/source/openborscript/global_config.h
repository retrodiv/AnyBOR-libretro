/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the shared global-configuration property selectors and callbacks.
 * Declare the shared global-config property domain and profile adapters.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

typedef enum
{
	_GLOBAL_CONFIG_AJSPECIAL,
	_GLOBAL_CONFIG_BLOCK_RATIO,
	_GLOBAL_CONFIG_BLOCK_TYPE,
	_GLOBAL_CONFIG_CHEATS,
	_GLOBAL_CONFIG_FLASH_LAYER_ADJUST,
	_GLOBAL_CONFIG_FLASH_LAYER_SOURCE,
	_GLOBAL_CONFIG_FLASH_Z_SOURCE,
	_GLOBAL_CONFIG_FLASH_STATIC_Z_PRIORITY,
	_GLOBAL_CONFIG_SHOW_GO,
	_GLOBAL_CONFIG_END,
} e_global_config_properties;

// Binding properties.
HRESULT openbor_get_global_config_property(ScriptVariant** varlist, ScriptVariant** pretvar, int paramCount);
HRESULT openbor_set_global_config_property(ScriptVariant** varlist, ScriptVariant** pretvar, int paramCount);

int mapstrings_global_config_property(ScriptVariant** varlist, int paramCount);

typedef enum
{
	GLOBAL_CONFIG_PROPERTY_AJSPECIAL,
	GLOBAL_CONFIG_PROPERTY_BLOCK_RATIO,
	GLOBAL_CONFIG_PROPERTY_BLOCK_TYPE,
	GLOBAL_CONFIG_PROPERTY_CHEATS,
	GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_ADJUST,
	GLOBAL_CONFIG_PROPERTY_FLASH_LAYER_SOURCE,
	GLOBAL_CONFIG_PROPERTY_FLASH_Z_SOURCE,
	GLOBAL_CONFIG_PROPERTY_SHOW_GO,
	GLOBAL_CONFIG_PROPERTY_FLASH,
	GLOBAL_CONFIG_PROPERTY_END,
} e_profile_global_config_properties;
