/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * obor_abi.h — the stable C ABI between the AnyBOR glue core and
 * an engine runtime (one runtime per pinned OpenBOR build).
 *
 * This header is shared by the core and the prepared engine port layer.
 *
 * Runtime interface:
 *   video is PULL  — obor_get_video returns a pointer to the runtime's own
 *                    XRGB8888 buffer, dimensions can change per frame
 *   audio is PULL  — obor_get_audio mixes and writes interleaved stereo s16
 *   input is PUSH  — obor_set_button sets held state per (player, button)
 *   one frame      = one obor_run_frame() call
 */
#ifndef OBOR_ABI_H
#define OBOR_ABI_H

#include <stdint.h>

#if UINTPTR_MAX < UINT64_MAX
#error AnyBOR requires a 64-bit target
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define OBOR_ABI_VERSION 1u

/* Snapshot-arena fixed virtual address, shared by the glue (which CLAIMS
 * the range in a load-time constructor, before the frontend allocates its
 * own high mappings) and every engine's allocator (which ADOPTS it). The
 * base must be a compile-time constant identical across processes: save
 * states carry absolute dlmalloc chunk pointers into it, so cross-process
 * state load / netplay only work when the base matches. ARM kernels often
 * run 39-bit user VA (512 GiB) where the x86 base would not fit. */
#if defined(__aarch64__) || defined(__arm__)
#define OBOR_ARENA_BASE_VA 0x2A00000000ULL    /* 168 GiB */
#else
#define OBOR_ARENA_BASE_VA 0x2A000000000ULL   /* ~2.6 TiB */
#endif
#define OBOR_ARENA_MAX_SZ (1536ULL * 1024 * 1024)

/* Runtimes build with -fvisibility=hidden; the ABI surface is the only
 * export. The glue only consumes declarations, where this is harmless. */
#if defined(_WIN32)
#define OBOR_API __declspec(dllexport)
#else
#define OBOR_API __attribute__((visibility("default")))
#endif

/* Buttons per player. Maps onto OpenBOR's default control set. */
enum {
    OBOR_BTN_UP = 0,
    OBOR_BTN_DOWN,
    OBOR_BTN_LEFT,
    OBOR_BTN_RIGHT,
    OBOR_BTN_ATTACK,    /* FIRE1 */
    OBOR_BTN_ATTACK2,
    OBOR_BTN_ATTACK3,
    OBOR_BTN_ATTACK4,
    OBOR_BTN_JUMP,
    OBOR_BTN_SPECIAL,
    OBOR_BTN_START,
    OBOR_BTN_ESC,
    OBOR_BTN_COUNT
};

#define OBOR_MAX_PLAYERS 4

#define OBOR_MAX_ENGINE_REGIONS 8
typedef struct {
    uint64_t begin, end;
    uint32_t engine_build;
} obor_engine_region;

typedef struct {
    uint32_t    abi_version;   /* glue sets = OBOR_ABI_VERSION */
    const char *pak_path;      /* absolute path to the .pak — or, with
                                * raw_dir, to the mod ROOT (the directory
                                * that contains data/) */
    const char *save_dir;      /* writable dir for Saves/ (may be NULL -> next to pak) */
    const char *log_dir;       /* writable dir for Logs/  (may be NULL -> save_dir) */
    int32_t     arena_reserved; /* 1 only if this loaded core owns the entire range */
    int32_t     sample_rate;   /* requested mixer rate (44100) */
    int32_t     raw_dir;       /* 1 = unpacked mod: chdir to pak_path and let
                                * the engine's isRawData() read loose files;
                                * Logs/Saves are redirected to the frontend
                                * save directory */
    const obor_engine_region *engine_regions; /* copied during boot */
    uint32_t engine_region_count;
} obor_boot_info;

/* Every function below is implemented by each linked engine object and wired
 * through the per-build vtable generated in obor_engines.h. */

OBOR_API uint32_t obor_abi_version(void);

/* 1 = ok, 0 = failure (details on the engine log). Must be called once. */
OBOR_API int32_t obor_boot(const obor_boot_info *info);

/* Advance exactly one video frame (1/60 s of emulated time).
 * Returns 1 while the engine is alive, 0 once it exited (user quit). */
OBOR_API int32_t obor_run_frame(void);

/* Framebuffer of the last completed frame, XRGB8888. Pointer owned by the
 * engine, valid until the next obor_run_frame call. Dimensions may change
 * between frames (OpenBOR games switch video modes). */
OBOR_API void obor_get_video(const uint32_t **pixels, int32_t *width,
                        int32_t *height, int32_t *pitch_pixels);

OBOR_API void obor_set_button(int32_t player, int32_t button, int32_t down);

/* Mix and write up to max_frames interleaved stereo s16 frames.
 * Returns frames written (the engine produces 1/60 s worth per video frame). */
OBOR_API int32_t obor_get_audio(int16_t *out, int32_t max_frames);

/* Save states.
 * obor_serialize_size: stable upper bound (never grows while a game runs).
 * obor_serialize: returns bytes written (<= size), 0 on failure.
 * obor_unserialize: 1 = ok, 0 = rejected (bad magic/version/context). */
OBOR_API uint32_t obor_serialize_size(void);
OBOR_API uint32_t obor_serialize(void *buf, uint32_t size);
OBOR_API int32_t obor_unserialize(const void *buf, uint32_t size);

OBOR_API void obor_shutdown(void);

/* --- v2 queries (poll-style; the engine never calls out) ---------------- */

/* Consume the pending rumble request for a player: *ratio in 0..100
 * (0 = none pending), *msec its duration. */
OBOR_API void obor_get_rumble(int32_t player, int32_t *ratio, int32_t *msec);

/* Snapshot arena location: fixed base + bytes currently in use. For the
 * frontend's memory map (cheat search); grows monotonically per session. */
OBOR_API void obor_get_arena(void **base, uint32_t *used);

/* Active character of a player slot: model name + facing (1 = right).
 * Returns 1 if the slot has a live entity. */
OBOR_API int32_t obor_get_player_state(int32_t player, char *name,
                                       int32_t cap, int32_t *facing);

#ifdef __cplusplus
}
#endif

#endif /* OBOR_ABI_H */
