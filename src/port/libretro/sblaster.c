/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR audio backend.
 *
 * No audio device: the glue pulls one frame's worth of samples per video
 * frame through obor_get_audio, which drains the engine mixer synchronously
 * (update_sample). Single-threaded and deterministic.
 */
#include "libretroport.h"
#include "sblaster.h"
#include "soundmix.h"
#include "obor_abi.h"

#include <string.h>
#ifdef OBOR_HAS_MOVIE_PLAYBACK
#include "obor_threads.h"
/* Recursive ownership mirrors SDL's callback lock. Released locks contain
 * no native handles, and can be restored with the engine's ordinary state. */
static uintptr_t audio_owner;
static unsigned int audio_depth;
void SB_lock_audio_direct(void)
{
    uintptr_t self = obor_thread_identity();
    if(__atomic_load_n(&audio_owner, __ATOMIC_ACQUIRE) == self) {
        ++audio_depth;
        return;
    }
    uintptr_t empty;
    do {
        empty = 0;
        if(__atomic_compare_exchange_n(&audio_owner, &empty, self, 0,
                                       __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) break;
        obor_thread_yield();
    } while(1);
    audio_depth = 1;
}
void SB_unlock_audio_direct(void)
{
    if(--audio_depth == 0)
        __atomic_store_n(&audio_owner, 0, __ATOMIC_RELEASE);
}
#else
void SB_lock_audio_direct(void) {}
void SB_unlock_audio_direct(void) {}
#endif
void SB_lock_audio(void) { SB_lock_audio_direct(); }
void SB_unlock_audio(void) { SB_unlock_audio_direct(); }
static void mix_samples(unsigned char *buffer, int bytes)
{
    SB_lock_audio_direct();
    update_sample(buffer, bytes);
    SB_unlock_audio_direct();
}


int SB_playstart(int bits, int samplerate)
{
    if(bits != 8 && bits != 16 && bits != 24) return 0;
    obor_snd_bits = bits;
    if (samplerate > 0)
        obor_snd_rate = samplerate;
    obor_snd_started = 1;
    return 1;
}

void SB_playstop(void)
{
    obor_snd_started = 0;
}

void SB_setvolume(char dev, char volume)
{
    (void)dev;
    (void)volume;
}

void SB_updatevolume(int volume)
{
    (void)volume;
}

/* ---- ABI: mix and deliver interleaved stereo s16 at 44100 Hz ---- */

int32_t obor_get_audio(int16_t *out, int32_t max_frames)
{
    if (!obor_snd_started) {
        return 0;
    }

    int32_t want = 44100 / 60; /* 735 frames per 60 Hz video frame */
    if (want > max_frames)
        want = max_frames;

    if (obor_snd_rate == 44100 && obor_snd_bits == 16) {
        mix_samples((unsigned char *)out, (int)(want * 2 * sizeof(int16_t)));
        return want;
    }

    /* Engine mixing at another rate/format: pull at engine rate, then
     * convert. 8-bit output mode mixes unsigned 8-bit stereo. */
    static int16_t tmp[8192];
    int32_t src_frames = (obor_snd_rate + 30) / 60;
    if (src_frames > 4000)
        src_frames = 4000;

    if (obor_snd_bits == 16) {
        mix_samples((unsigned char *)tmp, (int)(src_frames * 2 * sizeof(int16_t)));
    } else if(obor_snd_bits == 24) {
        /* Upstream's logical 24-bit mode carries left-aligned signed PCM
         * in 32-bit words, as in the native SDL AUDIO_S32SYS backend. */
        static int32_t tmp32[8192];
        mix_samples((unsigned char *)tmp32, src_frames * 2 * sizeof(int32_t));
        for(int32_t i = 0; i < src_frames * 2; ++i)
            tmp[i] = (int16_t)(tmp32[i] >> 16);
    } else {
        static unsigned char tmp8[8192];
        mix_samples(tmp8, (int)(src_frames * 2));
        for (int32_t i = 0; i < src_frames * 2; i++)
            tmp[i] = (int16_t)((tmp8[i] - 128) << 8);
    }

    /* Nearest-sample resample src_frames@rate -> want@44100. */
    for (int32_t i = 0; i < want; i++) {
        int32_t j = (int32_t)((int64_t)i * src_frames / want);
        out[i * 2] = tmp[j * 2];
        out[i * 2 + 1] = tmp[j * 2 + 1];
    }
    return want;
}
