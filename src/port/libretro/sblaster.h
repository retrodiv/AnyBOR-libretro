/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* AnyBOR audio backend — API mirror of sdl/sblaster.h. */
#ifndef SBLASTER_H
#define SBLASTER_H

#define MAXDMABUFSIZE 0x10000
#define MONO 0
#define STEREO 1
#define LOWQ 0
#define HIGHQ 2
#define SBDETECT -1
#define SB_MASTERVOL 0x22
#define SB_VOICEVOL 0x04
#define SB_CDVOL 0x28

int SB_playstart(int bits, int samplerate);
void SB_playstop(void);
void SB_lock_audio(void);
void SB_unlock_audio(void);
void SB_lock_audio_direct(void);
void SB_unlock_audio_direct(void);
void SB_setvolume(char dev, char volume);
void SB_updatevolume(int volume);

#endif
