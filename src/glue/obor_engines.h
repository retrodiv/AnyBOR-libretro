/* SPDX-License-Identifier: BSD-3-Clause */
/* Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Engine ABI table generated from src/pin.json. */
#include "obor_abi.h"

#define OBOR_CORE_VERSION "0.1.70"
#define OBOR_FALLBACK_BUILD 6391

typedef struct {
    uint32_t (*abi_version)(void);
    int32_t (*boot)(const obor_boot_info *);
    int32_t (*run_frame)(void);
    int32_t (*startup_complete)(void);
    int32_t (*get_exit_status)(void);
    int32_t (*get_fault_message)(char *, uint32_t);
    int32_t (*abandon)(void);
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
    int32_t (*owned_begin)(void *, void *, uint32_t);
    uint32_t (*owned_serialize)(void *, uint32_t, obor_state_ranges *);
    int32_t (*owned_end)(void);
    uint32_t (*prepare_state)(void);
} obor_vtbl;

extern "C" {
extern char __obor_bss_begin_3400[], __obor_bss_end_3400[];
uint32_t obor_abi_version_3400(void);
int32_t obor_boot_3400(const obor_boot_info *);
int32_t obor_run_frame_3400(void);
int32_t obor_startup_complete_3400(void);
int32_t obor_get_exit_status_3400(void);
int32_t obor_get_fault_message_3400(char *, uint32_t);
int32_t obor_abandon_3400(void);
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
int32_t obor_owned_begin_3400(void *, void *, uint32_t);
uint32_t obor_owned_serialize_3400(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_3400(void);
uint32_t obor_prepare_state_3400(void);
extern char __obor_bss_begin_3842[], __obor_bss_end_3842[];
uint32_t obor_abi_version_3842(void);
int32_t obor_boot_3842(const obor_boot_info *);
int32_t obor_run_frame_3842(void);
int32_t obor_startup_complete_3842(void);
int32_t obor_get_exit_status_3842(void);
int32_t obor_get_fault_message_3842(char *, uint32_t);
int32_t obor_abandon_3842(void);
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
int32_t obor_owned_begin_3842(void *, void *, uint32_t);
uint32_t obor_owned_serialize_3842(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_3842(void);
uint32_t obor_prepare_state_3842(void);
extern char __obor_bss_begin_4086[], __obor_bss_end_4086[];
uint32_t obor_abi_version_4086(void);
int32_t obor_boot_4086(const obor_boot_info *);
int32_t obor_run_frame_4086(void);
int32_t obor_startup_complete_4086(void);
int32_t obor_get_exit_status_4086(void);
int32_t obor_get_fault_message_4086(char *, uint32_t);
int32_t obor_abandon_4086(void);
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
int32_t obor_owned_begin_4086(void *, void *, uint32_t);
uint32_t obor_owned_serialize_4086(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_4086(void);
uint32_t obor_prepare_state_4086(void);
extern char __obor_bss_begin_4432[], __obor_bss_end_4432[];
uint32_t obor_abi_version_4432(void);
int32_t obor_boot_4432(const obor_boot_info *);
int32_t obor_run_frame_4432(void);
int32_t obor_startup_complete_4432(void);
int32_t obor_get_exit_status_4432(void);
int32_t obor_get_fault_message_4432(char *, uint32_t);
int32_t obor_abandon_4432(void);
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
int32_t obor_owned_begin_4432(void *, void *, uint32_t);
uint32_t obor_owned_serialize_4432(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_4432(void);
uint32_t obor_prepare_state_4432(void);
extern char __obor_bss_begin_6391[], __obor_bss_end_6391[];
uint32_t obor_abi_version_6391(void);
int32_t obor_boot_6391(const obor_boot_info *);
int32_t obor_run_frame_6391(void);
int32_t obor_startup_complete_6391(void);
int32_t obor_get_exit_status_6391(void);
int32_t obor_get_fault_message_6391(char *, uint32_t);
int32_t obor_abandon_6391(void);
void obor_get_video_6391(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_6391(int32_t, int32_t, int32_t);
int32_t obor_get_audio_6391(int16_t *, int32_t);
uint32_t obor_serialize_size_6391(void);
uint32_t obor_serialize_6391(void *, uint32_t);
int32_t obor_unserialize_6391(const void *, uint32_t);
void obor_shutdown_6391(void);
void obor_get_rumble_6391(int32_t, int32_t *, int32_t *);
void obor_get_arena_6391(void **, uint32_t *);
int32_t obor_get_player_state_6391(int32_t, char *, int32_t, int32_t *);
int32_t obor_owned_begin_6391(void *, void *, uint32_t);
uint32_t obor_owned_serialize_6391(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_6391(void);
uint32_t obor_prepare_state_6391(void);
extern char __obor_bss_begin_7142[], __obor_bss_end_7142[];
uint32_t obor_abi_version_7142(void);
int32_t obor_boot_7142(const obor_boot_info *);
int32_t obor_run_frame_7142(void);
int32_t obor_startup_complete_7142(void);
int32_t obor_get_exit_status_7142(void);
int32_t obor_get_fault_message_7142(char *, uint32_t);
int32_t obor_abandon_7142(void);
void obor_get_video_7142(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_7142(int32_t, int32_t, int32_t);
int32_t obor_get_audio_7142(int16_t *, int32_t);
uint32_t obor_serialize_size_7142(void);
uint32_t obor_serialize_7142(void *, uint32_t);
int32_t obor_unserialize_7142(const void *, uint32_t);
void obor_shutdown_7142(void);
void obor_get_rumble_7142(int32_t, int32_t *, int32_t *);
void obor_get_arena_7142(void **, uint32_t *);
int32_t obor_get_player_state_7142(int32_t, char *, int32_t, int32_t *);
int32_t obor_owned_begin_7142(void *, void *, uint32_t);
uint32_t obor_owned_serialize_7142(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_7142(void);
uint32_t obor_prepare_state_7142(void);
extern char __obor_bss_begin_7533[], __obor_bss_end_7533[];
uint32_t obor_abi_version_7533(void);
int32_t obor_boot_7533(const obor_boot_info *);
int32_t obor_run_frame_7533(void);
int32_t obor_startup_complete_7533(void);
int32_t obor_get_exit_status_7533(void);
int32_t obor_get_fault_message_7533(char *, uint32_t);
int32_t obor_abandon_7533(void);
void obor_get_video_7533(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_7533(int32_t, int32_t, int32_t);
int32_t obor_get_audio_7533(int16_t *, int32_t);
uint32_t obor_serialize_size_7533(void);
uint32_t obor_serialize_7533(void *, uint32_t);
int32_t obor_unserialize_7533(const void *, uint32_t);
void obor_shutdown_7533(void);
void obor_get_rumble_7533(int32_t, int32_t *, int32_t *);
void obor_get_arena_7533(void **, uint32_t *);
int32_t obor_get_player_state_7533(int32_t, char *, int32_t, int32_t *);
int32_t obor_owned_begin_7533(void *, void *, uint32_t);
uint32_t obor_owned_serialize_7533(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_7533(void);
uint32_t obor_prepare_state_7533(void);
extern char __obor_bss_begin_8023[], __obor_bss_end_8023[];
uint32_t obor_abi_version_8023(void);
int32_t obor_boot_8023(const obor_boot_info *);
int32_t obor_run_frame_8023(void);
int32_t obor_startup_complete_8023(void);
int32_t obor_get_exit_status_8023(void);
int32_t obor_get_fault_message_8023(char *, uint32_t);
int32_t obor_abandon_8023(void);
void obor_get_video_8023(const uint32_t **, int32_t *, int32_t *, int32_t *);
void obor_set_button_8023(int32_t, int32_t, int32_t);
int32_t obor_get_audio_8023(int16_t *, int32_t);
uint32_t obor_serialize_size_8023(void);
uint32_t obor_serialize_8023(void *, uint32_t);
int32_t obor_unserialize_8023(const void *, uint32_t);
void obor_shutdown_8023(void);
void obor_get_rumble_8023(int32_t, int32_t *, int32_t *);
void obor_get_arena_8023(void **, uint32_t *);
int32_t obor_get_player_state_8023(int32_t, char *, int32_t, int32_t *);
int32_t obor_owned_begin_8023(void *, void *, uint32_t);
uint32_t obor_owned_serialize_8023(void *, uint32_t, obor_state_ranges *);
int32_t obor_owned_end_8023(void);
uint32_t obor_prepare_state_8023(void);
}

typedef struct { int build; const char *name; obor_vtbl v; const char *bss_begin, *bss_end; } obor_engine_def;
static const obor_engine_def kEngineDefs[] = {
    { 3400, "3400", { obor_abi_version_3400, obor_boot_3400, obor_run_frame_3400, obor_startup_complete_3400, obor_get_exit_status_3400, obor_get_fault_message_3400, obor_abandon_3400, obor_get_video_3400, obor_set_button_3400, obor_get_audio_3400, obor_serialize_size_3400, obor_serialize_3400, obor_unserialize_3400, obor_shutdown_3400, obor_get_rumble_3400, obor_get_arena_3400, obor_get_player_state_3400, obor_owned_begin_3400, obor_owned_serialize_3400, obor_owned_end_3400, obor_prepare_state_3400 }, __obor_bss_begin_3400, __obor_bss_end_3400 },
    { 3842, "3842", { obor_abi_version_3842, obor_boot_3842, obor_run_frame_3842, obor_startup_complete_3842, obor_get_exit_status_3842, obor_get_fault_message_3842, obor_abandon_3842, obor_get_video_3842, obor_set_button_3842, obor_get_audio_3842, obor_serialize_size_3842, obor_serialize_3842, obor_unserialize_3842, obor_shutdown_3842, obor_get_rumble_3842, obor_get_arena_3842, obor_get_player_state_3842, obor_owned_begin_3842, obor_owned_serialize_3842, obor_owned_end_3842, obor_prepare_state_3842 }, __obor_bss_begin_3842, __obor_bss_end_3842 },
    { 4086, "4086", { obor_abi_version_4086, obor_boot_4086, obor_run_frame_4086, obor_startup_complete_4086, obor_get_exit_status_4086, obor_get_fault_message_4086, obor_abandon_4086, obor_get_video_4086, obor_set_button_4086, obor_get_audio_4086, obor_serialize_size_4086, obor_serialize_4086, obor_unserialize_4086, obor_shutdown_4086, obor_get_rumble_4086, obor_get_arena_4086, obor_get_player_state_4086, obor_owned_begin_4086, obor_owned_serialize_4086, obor_owned_end_4086, obor_prepare_state_4086 }, __obor_bss_begin_4086, __obor_bss_end_4086 },
    { 4432, "4432", { obor_abi_version_4432, obor_boot_4432, obor_run_frame_4432, obor_startup_complete_4432, obor_get_exit_status_4432, obor_get_fault_message_4432, obor_abandon_4432, obor_get_video_4432, obor_set_button_4432, obor_get_audio_4432, obor_serialize_size_4432, obor_serialize_4432, obor_unserialize_4432, obor_shutdown_4432, obor_get_rumble_4432, obor_get_arena_4432, obor_get_player_state_4432, obor_owned_begin_4432, obor_owned_serialize_4432, obor_owned_end_4432, obor_prepare_state_4432 }, __obor_bss_begin_4432, __obor_bss_end_4432 },
    { 6391, "6391", { obor_abi_version_6391, obor_boot_6391, obor_run_frame_6391, obor_startup_complete_6391, obor_get_exit_status_6391, obor_get_fault_message_6391, obor_abandon_6391, obor_get_video_6391, obor_set_button_6391, obor_get_audio_6391, obor_serialize_size_6391, obor_serialize_6391, obor_unserialize_6391, obor_shutdown_6391, obor_get_rumble_6391, obor_get_arena_6391, obor_get_player_state_6391, obor_owned_begin_6391, obor_owned_serialize_6391, obor_owned_end_6391, obor_prepare_state_6391 }, __obor_bss_begin_6391, __obor_bss_end_6391 },
    { 7142, "7142", { obor_abi_version_7142, obor_boot_7142, obor_run_frame_7142, obor_startup_complete_7142, obor_get_exit_status_7142, obor_get_fault_message_7142, obor_abandon_7142, obor_get_video_7142, obor_set_button_7142, obor_get_audio_7142, obor_serialize_size_7142, obor_serialize_7142, obor_unserialize_7142, obor_shutdown_7142, obor_get_rumble_7142, obor_get_arena_7142, obor_get_player_state_7142, obor_owned_begin_7142, obor_owned_serialize_7142, obor_owned_end_7142, obor_prepare_state_7142 }, __obor_bss_begin_7142, __obor_bss_end_7142 },
    { 7533, "7533", { obor_abi_version_7533, obor_boot_7533, obor_run_frame_7533, obor_startup_complete_7533, obor_get_exit_status_7533, obor_get_fault_message_7533, obor_abandon_7533, obor_get_video_7533, obor_set_button_7533, obor_get_audio_7533, obor_serialize_size_7533, obor_serialize_7533, obor_unserialize_7533, obor_shutdown_7533, obor_get_rumble_7533, obor_get_arena_7533, obor_get_player_state_7533, obor_owned_begin_7533, obor_owned_serialize_7533, obor_owned_end_7533, obor_prepare_state_7533 }, __obor_bss_begin_7533, __obor_bss_end_7533 },
    { 8023, "8023", { obor_abi_version_8023, obor_boot_8023, obor_run_frame_8023, obor_startup_complete_8023, obor_get_exit_status_8023, obor_get_fault_message_8023, obor_abandon_8023, obor_get_video_8023, obor_set_button_8023, obor_get_audio_8023, obor_serialize_size_8023, obor_serialize_8023, obor_unserialize_8023, obor_shutdown_8023, obor_get_rumble_8023, obor_get_arena_8023, obor_get_player_state_8023, obor_owned_begin_8023, obor_owned_serialize_8023, obor_owned_end_8023, obor_prepare_state_8023 }, __obor_bss_begin_8023, __obor_bss_end_8023 },
};

typedef struct { int build; const char *name; const char *disp; int engine_build; int auto_until; int automatic; int tagged; int triage; const char *variant; uint32_t features; } obor_profile_def;
static const obor_profile_def kProfiles[] = {
    { 3400, "3400", "v3.0 3400", 3400, 3400, 1, 1, 1, "", 0u },
    { 3780, "3780", "v3.0 3780", 3842, 3780, 1, 1, 1, "", 0u },
    { 3783, "3783", "v3.0 3783", 3842, 3783, 1, 1, 1, "", 0u },
    { 3789, "3789", "v3.0 3789", 3842, 3789, 1, 1, 1, "", 0u },
    { 3793, "3793", "v3.0 3793", 3842, 3793, 1, 1, 1, "", 0u },
    { 3797, "3797", "v3.0 3797", 3842, 3797, 1, 1, 1, "", 0u },
    { 3805, "3805", "v3.0 3805", 3842, 3805, 1, 1, 1, "", 0u },
    { 3814, "3814", "v3.0 3814", 3842, 3814, 1, 1, 1, "", 0u },
    { 3818, "3818", "v3.0 3818", 3842, 3818, 1, 1, 1, "", 0u },
    { 3822, "3822", "v3.0 3822", 3842, 3822, 1, 1, 1, "", 0u },
    { 3824, "3824", "v3.0 3824", 3842, 3824, 1, 1, 1, "", 0u },
    { 3829, "3829", "v3.0 3829", 3842, 3829, 1, 1, 1, "", 0u },
    { 3831, "3831", "v3.0 3831", 3842, 3831, 1, 1, 1, "", 0u },
    { 3837, "3837", "v3.0 3837", 3842, 3837, 1, 1, 1, "", 0u },
    { 3839, "3839", "v3.0 3839", 3842, 3839, 1, 1, 1, "", 0u },
    { 3842, "3842", "v3.0 3842", 3842, 3842, 1, 1, 1, "", 0u },
    { 4086, "4086", "v3.0 4086", 4086, 4086, 1, 1, 1, "", 0u },
    { 4088, "4088", "v3.0 4088-dev", 4086, 4088, 0, 1, 0, "dev", 0u },
    { 4107, "4107", "v3.0 4107", 4086, 4107, 1, 1, 1, "", 0u },
    { 4111, "4111", "v3.0 4111", 4086, 4111, 1, 1, 1, "", 0u },
    { 4129, "4129", "v3.0 4129", 4086, 4129, 1, 1, 1, "", 0u },
    { 4153, "4153", "v3.0 4153", 4086, 4153, 1, 1, 1, "", 0u },
    { 4432, "4432", "v3.0 4432", 4432, 4432, 1, 1, 1, "", 0u },
    { 4453, "4453", "v3.0 4453", 4432, 4453, 1, 1, 1, "", 0u },
    { 6330, "6330", "v3.0 6330", 6391, 6330, 1, 1, 1, "", 0u },
    { 6391, "6391", "v3.0 6391", 6391, 6412, 1, 1, 1, "", 0u },
    { 6391, "6391-mod", "v3.0 6391-mod", 6391, 6391, 0, 1, 0, "mod", 3u },
    { 6392, "6392", "v3.0 6392-dev", 6391, 6392, 0, 1, 1, "dev", 3u },
    { 6412, "6412", "v3.0 6412-dev", 6391, 6412, 0, 1, 1, "dev", 0u },
    { 6510, "6510", "v3.0 6510-dev", 6391, 6510, 0, 1, 1, "dev", 0u },
    { 7086, "7086", "v3.0 7086-dev", 7142, 7086, 0, 1, 1, "dev", 0u },
    { 7123, "7123", "v3.0 7123-dev", 7142, 7123, 0, 1, 1, "dev", 0u },
    { 7142, "7142", "v4.0 7142-alpha", 7142, 7142, 1, 1, 1, "alpha", 0u },
    { 7533, "7533", "v4.0 7533", 7533, 7533, 1, 1, 1, "", 0u },
    { 8023, "8023", "v4.0 8023-dev", 8023, 8023, 1, 1, 1, "dev", 0u },
};
