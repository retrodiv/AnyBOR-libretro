/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Expose the native media mixer layout to the cutscene decoder. Declare the
 * selected audio fields and property adapters used by scripts and media
 * callers.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c)  OpenBOR Team
 */

#ifndef SOUNDMIX_H
#define SOUNDMIX_H

#include "types.h"
#include <stdint.h>
extern uint32_t obor_profile_build;

/*
**	Sound mixer.
**	Now supports ADPCM instead of MP3 (costs less CPU time).
**
**	Also plays WAV files (unsigned, mono, both 8-bit and 16-bit).
*/

// 20:12 fixed-point conversion macros.
// The maximum size of a sound is linked directly
// to the range of the fixed-point variables!
#define OBOR_AUDIO_FRACTION_BITS (obor_profile_build >= 7597 ? 4u : obor_profile_build >= 7587 ? 1u : obor_profile_build >= 7557 ? 8u : 12u)
#define INT_TO_FIX(i) ((unsigned int)(i) << OBOR_AUDIO_FRACTION_BITS)
#define FIX_TO_INT(f) ((unsigned int)(f) >> OBOR_AUDIO_FRACTION_BITS)
unsigned int sound_profile_sample_limit(void);
uint32_t sound_profile_sample_play_id(void);
#define MAX_SOUND_LEN sound_profile_sample_limit()
#define		CHANNEL_PLAYING		1
#define		CHANNEL_LOOPING		2
#define		MUSIC_NUM_BUFFERS	4
#define		MUSIC_BUF_SIZE		(16*1024)	// In samples
#define		SOUND_MONO			1
#define		SOUND_STEREO		2

typedef enum e_sound_file_type { SOUND_FILE_TYPE_NONE=-1, SOUND_FILE_TYPE_ADPCM=0, SOUND_FILE_TYPE_VORBIS=1 } e_sound_file_type;
typedef enum e_channel_type { CHANNEL_TYPE_MONO=1, CHANNEL_TYPE_STEREO=2 } e_channel_type;
typedef enum e_sound_spatial_channel { SOUND_SPATIAL_CHANNEL_LEFT=0, SOUND_SPATIAL_CHANNEL_RIGHT=1, SOUND_SPATIAL_CHANNEL_MAX=2 } e_channel_index;

typedef struct
{
    int            active;
    int            paused;
    short 		   *buf[MUSIC_NUM_BUFFERS];
    unsigned int   fp_playto[MUSIC_NUM_BUFFERS];
    unsigned int   fp_samplepos;  // Position (fixed-point)
    unsigned int   fp_period;	  // Period (fixed-point)
    int			   playing_buffer;
    int            volume[2];
    e_channel_type channels;
    e_object_type object_type;
} musicchannelstruct;

void sound_music_channel_clear(musicchannelstruct *const music_channel);

extern musicchannelstruct musicchannel;
extern int playfrequency;

void sound_stop_playback();
int sound_start_playback();
void sound_exit();
int sound_init(int channels);

extern int sample_play_id;

// Returns interval in milliseconds
u32 sound_getinterval();
int sound_load_sample(char *filename, char *packfilename, int iLog);
int sound_reload_sample(int index);
void sound_unload_sample(int index);
void sound_unload_all_samples();
int sound_query_channel(int playid);
int sound_id(int channel);
int sound_is_active(int channel);
int sound_play_sample(int samplenum, unsigned int priority, int lvolume, int rvolume, unsigned int speed);
int sound_loop_sample(int samplenum, unsigned int priority, int lvolume, int rvolume, unsigned int speed);
void sound_stop_sample(int channel);
void sound_stopall_sample();
void sound_pause_sample(int toggle);
void sound_pause_single_sample(int toggle, int channel);
void sound_volume_sample(int channel, int lvolume, int rvolume);
int sound_getpos_sample(int channel);

#ifdef DC
int sound_was_music_opened();
#endif

int sound_open_music(char *filename, char *packname, int volume, int loop, u32 music_offset);
void sound_close_music();
void sound_update_music();
void sound_volume_music(int left, int right);
void sound_music_tempo(int music_tempo);
int sound_query_music(char *artist, char *title);
void sound_pause_music(int toggle);

void update_sample(unsigned char *buf, int size);

int maxchannels(void);

#endif
