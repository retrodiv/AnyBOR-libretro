/* AnyBOR modification record: 2026-10-05.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Keep legacy binding IDs and append shared selectors for modern profile
 * properties.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/6391.md
 * at the source repository root. Original notices follow below.
 */


typedef enum
{
    _BINDING_ANIMATION,
    _BINDING_BIND_X,
    _BINDING_BIND_Y,
    _BINDING_BIND_Z,
    _BINDING_DIRECTION,
    _BINDING_OFFSET_X,
    _BINDING_OFFSET_Y,
    _BINDING_OFFSET_Z,
    _BINDING_SORT_ID,
    _BINDING_TARGET,
    _BINDING_LEGACY_END,
    _BINDING_ENABLE = _BINDING_LEGACY_END,
    _BINDING_OFFSET,
    _BINDING_OVERRIDING,
    _BINDING_TAG,
    _BINDING_END,
} e_binding_properties;

// Binding properties.
HRESULT openbor_get_binding_property(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount);
HRESULT openbor_set_binding_property(ScriptVariant **varlist , ScriptVariant **pretvar, int paramCount);

int mapstrings_binding(ScriptVariant **varlist, int paramCount);
