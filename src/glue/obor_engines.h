/* SPDX-License-Identifier: BSD-3-Clause */
/* Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Engine ABI table generated from src/pin.json. */
#include "obor_abi.h"

#define OBOR_CORE_VERSION "0.1.0"
#define OBOR_FALLBACK_BUILD 6412

typedef struct {
    uint32_t (*abi_version)(void);
    int32_t (*boot)(const obor_boot_info *);
    int32_t (*run_frame)(void);
    void (*get_video)(const uint32_t **, int32_t *, int32_t *, int32_t *);
    void (*set_button)(int32_t, int32_t, int32_t);
    int32_t (*get_audio)(int16_t *, int32_t);
    uint32_t (*serialize_size)(void);
    uint32_t (*serialize)(void *, uint32_t);
    int32_t (*unserialize)(const void *, uint32_t);
    void (*shutdown)(void);
    void (*get_rumble)(int32_t, int32_t *, int32_t *);
    void (*get_arena)(void **, uint32_t *);
    int32_t (*get_player_state)(int32_t, char *, int32_t, int32_t *);
} obor_vtbl;

extern "C" {
extern char __obor_bss_begin_3400[], __obor_bss_end_3400[];
uint32_t obor_abi_version_3400(void);
int32_t obor_boot_3400(const obor_boot_info *);
int32_t obor_run_frame_3400(void);
void obor_get_video_3400(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_3400(int32_t, int32_t, int32_t);
int32_t obor_get_audio_3400(int16_t *, int32_t);
uint32_t obor_serialize_size_3400(void);
uint32_t obor_serialize_3400(void *, uint32_t);
int32_t obor_unserialize_3400(const void *, uint32_t);
void obor_shutdown_3400(void);
void obor_get_rumble_3400(int32_t, int32_t *, int32_t *);
void obor_get_arena_3400(void **, uint32_t *);
int32_t obor_get_player_state_3400(int32_t, char *, int32_t, int32_t *);
extern char __obor_bss_begin_3842[], __obor_bss_end_3842[];
uint32_t obor_abi_version_3842(void);
int32_t obor_boot_3842(const obor_boot_info *);
int32_t obor_run_frame_3842(void);
void obor_get_video_3842(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_3842(int32_t, int32_t, int32_t);
int32_t obor_get_audio_3842(int16_t *, int32_t);
uint32_t obor_serialize_size_3842(void);
uint32_t obor_serialize_3842(void *, uint32_t);
int32_t obor_unserialize_3842(const void *, uint32_t);
void obor_shutdown_3842(void);
void obor_get_rumble_3842(int32_t, int32_t *, int32_t *);
void obor_get_arena_3842(void **, uint32_t *);
int32_t obor_get_player_state_3842(int32_t, char *, int32_t, int32_t *);
extern char __obor_bss_begin_4086[], __obor_bss_end_4086[];
uint32_t obor_abi_version_4086(void);
int32_t obor_boot_4086(const obor_boot_info *);
int32_t obor_run_frame_4086(void);
void obor_get_video_4086(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_4086(int32_t, int32_t, int32_t);
int32_t obor_get_audio_4086(int16_t *, int32_t);
uint32_t obor_serialize_size_4086(void);
uint32_t obor_serialize_4086(void *, uint32_t);
int32_t obor_unserialize_4086(const void *, uint32_t);
void obor_shutdown_4086(void);
void obor_get_rumble_4086(int32_t, int32_t *, int32_t *);
void obor_get_arena_4086(void **, uint32_t *);
int32_t obor_get_player_state_4086(int32_t, char *, int32_t, int32_t *);
extern char __obor_bss_begin_4432[], __obor_bss_end_4432[];
uint32_t obor_abi_version_4432(void);
int32_t obor_boot_4432(const obor_boot_info *);
int32_t obor_run_frame_4432(void);
void obor_get_video_4432(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_4432(int32_t, int32_t, int32_t);
int32_t obor_get_audio_4432(int16_t *, int32_t);
uint32_t obor_serialize_size_4432(void);
uint32_t obor_serialize_4432(void *, uint32_t);
int32_t obor_unserialize_4432(const void *, uint32_t);
void obor_shutdown_4432(void);
void obor_get_rumble_4432(int32_t, int32_t *, int32_t *);
void obor_get_arena_4432(void **, uint32_t *);
int32_t obor_get_player_state_4432(int32_t, char *, int32_t, int32_t *);
extern char __obor_bss_begin_6412[], __obor_bss_end_6412[];
uint32_t obor_abi_version_6412(void);
int32_t obor_boot_6412(const obor_boot_info *);
int32_t obor_run_frame_6412(void);
void obor_get_video_6412(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_6412(int32_t, int32_t, int32_t);
int32_t obor_get_audio_6412(int16_t *, int32_t);
uint32_t obor_serialize_size_6412(void);
uint32_t obor_serialize_6412(void *, uint32_t);
int32_t obor_unserialize_6412(const void *, uint32_t);
void obor_shutdown_6412(void);
void obor_get_rumble_6412(int32_t, int32_t *, int32_t *);
void obor_get_arena_6412(void **, uint32_t *);
int32_t obor_get_player_state_6412(int32_t, char *, int32_t, int32_t *);
}

typedef struct { int build; const char *name; const char *disp; obor_vtbl v; const char *bss_begin, *bss_end; } obor_engine_def;
static const obor_engine_def kEngineDefs[] = {
    { 3400, "3400", "v2-v3 3400", { obor_abi_version_3400, obor_boot_3400, obor_run_frame_3400, obor_get_video_3400, obor_set_button_3400, obor_get_audio_3400, obor_serialize_size_3400, obor_serialize_3400, obor_unserialize_3400, obor_shutdown_3400, obor_get_rumble_3400, obor_get_arena_3400, obor_get_player_state_3400 }, __obor_bss_begin_3400, __obor_bss_end_3400 },
    { 3842, "3842", "v3 3842", { obor_abi_version_3842, obor_boot_3842, obor_run_frame_3842, obor_get_video_3842, obor_set_button_3842, obor_get_audio_3842, obor_serialize_size_3842, obor_serialize_3842, obor_unserialize_3842, obor_shutdown_3842, obor_get_rumble_3842, obor_get_arena_3842, obor_get_player_state_3842 }, __obor_bss_begin_3842, __obor_bss_end_3842 },
    { 4086, "4086", "v3 4086", { obor_abi_version_4086, obor_boot_4086, obor_run_frame_4086, obor_get_video_4086, obor_set_button_4086, obor_get_audio_4086, obor_serialize_size_4086, obor_serialize_4086, obor_unserialize_4086, obor_shutdown_4086, obor_get_rumble_4086, obor_get_arena_4086, obor_get_player_state_4086 }, __obor_bss_begin_4086, __obor_bss_end_4086 },
    { 4432, "4432", "v3 4432", { obor_abi_version_4432, obor_boot_4432, obor_run_frame_4432, obor_get_video_4432, obor_set_button_4432, obor_get_audio_4432, obor_serialize_size_4432, obor_serialize_4432, obor_unserialize_4432, obor_shutdown_4432, obor_get_rumble_4432, obor_get_arena_4432, obor_get_player_state_4432 }, __obor_bss_begin_4432, __obor_bss_end_4432 },
    { 6412, "6412", "v3 6412", { obor_abi_version_6412, obor_boot_6412, obor_run_frame_6412, obor_get_video_6412, obor_set_button_6412, obor_get_audio_6412, obor_serialize_size_6412, obor_serialize_6412, obor_unserialize_6412, obor_shutdown_6412, obor_get_rumble_6412, obor_get_arena_6412, obor_get_player_state_6412 }, __obor_bss_begin_6412, __obor_bss_end_6412 },
};
