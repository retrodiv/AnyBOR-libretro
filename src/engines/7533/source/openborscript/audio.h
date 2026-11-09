/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the imported 7735music-channel callback interface with its
 * original property numbering.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */


typedef enum e_music_channel_properties
{
	MUSIC_CHANNEL_PROPERTY_ACTIVE,
	MUSIC_CHANNEL_PROPERTY_BUFFER_LIST,
	MUSIC_CHANNEL_PROPERTY_CHANNELS,
	MUSIC_CHANNEL_PROPERTY_PAUSED,
	MUSIC_CHANNEL_PROPERTY_PERIOUD,
	MUSIC_CHANNEL_PROPERTY_PLAY_BUFFER,
	MUSIC_CHANNEL_PROPERTY_PLAY_TO,
	MUSIC_CHANNEL_PROPERTY_SAMPLE_POSITION,
	MUSIC_CHANNEL_PROPERTY_VOLUME_LEFT,
	MUSIC_CHANNEL_PROPERTY_VOLUME_RIGHT,
	MUSIC_CHANNEL_PROPERTY_END,
} e_music_channel_properties;

// Drawmethod properties.
HRESULT openbor_get_music_channel_property(const ScriptVariant* const* varlist, ScriptVariant** const pretvar, const int paramCount);
HRESULT openbor_set_music_channel_property(ScriptVariant** varlist, ScriptVariant** const pretvar, const int paramCount);