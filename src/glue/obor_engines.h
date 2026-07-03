/* SPDX-License-Identifier: BSD-3-Clause */
/* Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Engine ABI table generated from src/pin.json. */
#include "obor_abi.h"

#define OBOR_CORE_VERSION "0.1.0"
#define OBOR_FALLBACK_BUILD 0

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
}

typedef struct { int build; const char *name; const char *disp; obor_vtbl v; const char *bss_begin, *bss_end; } obor_engine_def;
static const obor_engine_def kEngineDefs[] = {
};
