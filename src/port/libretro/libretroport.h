/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR platform layer — port header.
 * Included by source/globals.h under #ifdef LIBRETRO (patch 01).
 * Mirrors the role of sdl/sdlport.h without any SDL.
 */
#ifndef LIBRETROPORT_H
#define LIBRETROPORT_H

#include <stdlib.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
#include "obor_abi.h"

/* mingw ships a unistd.h too — include it before the usleep macro below so
 * later includes are guard-stopped and never see the macro as a prototype */
#include <unistd.h>
#ifndef _WIN32
#define stricmp strcasecmp
#define strnicmp strncasecmp
#endif

#include "globals.h"

/* Older eras (< ~4700) hardcode 128-byte path buffers and never define
 * MAX_FILENAME_LEN; every engine reference to these globals goes through
 * this header, so one consistent size works across eras. */
#ifndef MAX_FILENAME_LEN
#define MAX_FILENAME_LEN 512
#endif
#ifndef MAX_BUFFER_LEN
#define MAX_BUFFER_LEN 512
#endif

/* All engine sleeps advance the emulated clock (and yield if they pile up
 * past a frame) instead of blocking the frontend thread. */
void obor_port_sleep_us(unsigned long long us);
#undef usleep
#define usleep(us) obor_port_sleep_us((unsigned long long)(us))

void borExit(int reset);
void openborMain(int argc, char **argv);

extern char packfile[MAX_FILENAME_LEN];
extern char paksDir[MAX_FILENAME_LEN];
extern char savesDir[MAX_FILENAME_LEN];
extern char logsDir[MAX_FILENAME_LEN];
extern char screenShotsDir[MAX_FILENAME_LEN];

/* ---- internal hooks between the libretro platform files ---- */

/* Emulated clock (microseconds). Advanced by frame yields and sleeps. */
extern unsigned long long obor_clock_us;

/* Yield one frame to the frontend (called by video_copy_screen / the
 * sleep-liveness path). Never returns until the frontend asks for the
 * next frame. */
void obor_yield_frame(void);

/* Let the frontend consume audio while the coroutine awaits decoded video. */
void obor_wait_frame(void);
void obor_worker_pause(void);

/* Liveness for input-poll loops: engines wait on button state in tight
 * loops without sleeping or rendering, but pad state only changes when the
 * frontend runs between frames. control.c calls this per poll; after many
 * polls without a yield it re-presents the last frame. Count-based, so
 * still deterministic. */
void obor_poll_tick(void);

/* Sleep replacement: advances the emulated clock; yields duplicate frames
 * if the engine sleeps past a frame's worth without rendering. */
void obor_port_sleep_us(unsigned long long us);

/* Held-button state pushed by the glue through the ABI. */
extern unsigned char obor_pad[4][16];

/* Present a finished frame (XRGB8888) to the ABI side. Called by video.c. */
void obor_port_submit_frame(const unsigned int *px, int w, int h, int pitch_px);

/* Mixer parameters recorded by sblaster.c. */
extern int obor_snd_bits, obor_snd_rate, obor_snd_started;

/* Number of live engine-created threads (webm playback); snapshots are
 * refused while nonzero. Maintained by threads.c. */
extern int obor_live_threads;


/* Bind snapshot bookkeeping to the frontend's absolute save directory. */
int obor_state_set_save_dir(const char *dir);
int obor_state_set_regions(const obor_boot_info *info);

/* Snapshot arena (obor_alloc.c). */
int obor_arena_init(void);
char *obor_arena_base(void);
char *obor_stack_ptr(void);
size_t obor_stack_size(void);

/* Saved stack pointer of the parked engine coroutine (only meaningful
 * between frames, which is when serialize runs). Everything below it is
 * ABI-dead: snapshots save just [sp-redzone, stack top]. */
void *obor_engine_sp(void);

/* Some mods verify their own archive through a relative Paks/<original>.pak
 * name. Frontends are free to rename content, so a missing basename-only PAK
 * probe may read the active prepared archive without creating a second copy. */
int obor_buffer_content_alias(const char *requested, char **buffer,
                              size_t *size);

/* Does any file inside the .pak start with this prefix? (case-insensitive,
 * slashes normalized). Used by era patches to drop video.txt overrides that
 * point at files a template line invented (v2-era paks). */
int obor_pak_has_prefix(const char *pakpath, const char *prefix);

#endif /* LIBRETROPORT_H */
