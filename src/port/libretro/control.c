/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR input backend.
 *
 * The glue pushes held-button state into obor_pad[player][button] through
 * the ABI; this file translates it into the engine's keycode/bitmask model.
 */
#include "libretroport.h"
#include "control.h"
#include "obor_abi.h"

#include <stdio.h>
#include <string.h>

#if OBOR_ENGINE_BUILD >= 8023

/* The controller branch indexes devices, not a global keyboard keyspace.
 * Each frontend port is a stable device. Mappings contain RetroPad button
 * numbers, and all four devices use the same default layout. */
static int mappings[4][OBOR_INPUT_COUNT];
static int initialized;
static int mapping_ready;
static int remap_device = -1;
static int remap_key = -1;
static unsigned char remap_previous[16];
static int rumble_ratio[4], rumble_ms[4];

static void defaults(int device)
{
    static const int buttons[OBOR_INPUT_COUNT] = {
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 11
    };
    memcpy(mappings[device], buttons, sizeof(buttons));
}

bool control_isvaliddevice(int deviceID)
{
    return deviceID >= 0 && deviceID < 4;
}

void control_init(void)
{
    if (initialized)
        return;
    if (!mapping_ready)
        control_clearmappings();
    initialized = 1;
    remap_device = -1;
    remap_key = -1;
}

void control_exit(void)
{
    initialized = 0;
    mapping_ready = 0;
    remap_device = -1;
    remap_key = -1;
}

void control_clearmappings(void)
{
    for (int device = 0; device < 4; ++device)
        defaults(device);
    mapping_ready = 1;
}

void control_resetmappings(int deviceID)
{
    if (control_isvaliddevice(deviceID))
        defaults(deviceID);
}

int *control_getmappings(int deviceID)
{
    static int none[OBOR_INPUT_COUNT];
    return control_isvaliddevice(deviceID) ? mappings[deviceID] : none;
}

void control_remapdevice(int deviceID)
{
    remap_device = control_isvaliddevice(deviceID) ? deviceID : -1;
    remap_key = -1;
    if (remap_device >= 0)
        memcpy(remap_previous, obor_pad[remap_device], sizeof(remap_previous));
}

int control_getremappedkey(void)
{
    return remap_key;
}

void control_update(s_playercontrols **players, int count)
{
    obor_poll_tick();
    if (remap_device >= 0 && remap_key < 0) {
        for (int button = 0; button < 16; ++button) {
            if (obor_pad[remap_device][button] && !remap_previous[button]) {
                remap_key = button;
                break;
            }
        }
        memcpy(remap_previous, obor_pad[remap_device], sizeof(remap_previous));
    }
    for (int i = 0; i < count; ++i) {
        s_playercontrols *player = players[i];
        uint32_t flags = 0;
        int device = player->deviceID;
        if (control_isvaliddevice(device)) {
            for (int button = 0; button < OBOR_INPUT_COUNT; ++button) {
                int mapped = mappings[device][button];
                if (mapped >= 0 && mapped < 16 && obor_pad[device][mapped])
                    flags |= UINT32_C(1) << button;
            }
        }
        player->newkeyflags = flags & ~player->keyflags;
        player->keyflags = flags;
    }
}

void control_update_keyboard(s_playercontrols *player)
{
    s_playercontrols *one[] = {player};
    control_update(one, 1);
}

const char *control_getkeyname(int deviceID, int keycode)
{
    static const char *names[16] = {
        "Up", "Down", "Left", "Right", "Attack 1", "Attack 2",
        "Attack 3", "Attack 4", "Jump", "Special", "Start", "Exit",
        "Screenshot", "Button 13", "Button 14", "Button 15"
    };
    (void)deviceID;
    return keycode >= 0 && keycode < 16 ? names[keycode] : "None";
}

const char *control_getdevicename(int deviceID)
{
    static const char *names[4] = {
        "RetroPad 1", "RetroPad 2", "RetroPad 3", "RetroPad 4"
    };
    return control_isvaliddevice(deviceID) ? names[deviceID] : "None";
}

/* Independent of the SDL controller database. Only our own versioned map is
 * accepted; malformed or truncated files leave the defaults intact. */
bool control_loadmappings(const char *filename)
{
    static const unsigned char magic[8] = {'A','B','C','T','R','L','0','1'};
    unsigned char header[8];
    int32_t saved[4][OBOR_INPUT_COUNT];
    FILE *file = fopen(filename, "rb");
    if (!file)
        return false;
    bool valid = fread(header, 1, sizeof(header), file) == sizeof(header) &&
        memcmp(header, magic, sizeof(magic)) == 0 &&
        fread(saved, 1, sizeof(saved), file) == sizeof(saved) &&
        fgetc(file) == EOF;
    fclose(file);
    if (!valid)
        return false;
    for (int device = 0; device < 4; ++device)
        for (int button = 0; button < OBOR_INPUT_COUNT; ++button)
            if (saved[device][button] < -1 || saved[device][button] >= 16)
                return false;
    for (int device = 0; device < 4; ++device)
        for (int button = 0; button < OBOR_INPUT_COUNT; ++button)
            mappings[device][button] = saved[device][button];
    return true;
}

bool control_savemappings(const char *filename)
{
    static const unsigned char magic[8] = {'A','B','C','T','R','L','0','1'};
    int32_t saved[4][OBOR_INPUT_COUNT];
    for (int device = 0; device < 4; ++device)
        for (int button = 0; button < OBOR_INPUT_COUNT; ++button)
            saved[device][button] = mappings[device][button];
    FILE *file = fopen(filename, "wb");
    if (!file)
        return false;
    bool valid = fwrite(magic, 1, sizeof(magic), file) == sizeof(magic) &&
        fwrite(saved, 1, sizeof(saved), file) == sizeof(saved);
    if (fclose(file) != 0)
        valid = false;
    return valid;
}

void obor_get_rumble(int32_t player, int32_t *ratio, int32_t *msec)
{
    *ratio = 0;
    *msec = 0;
    if (!control_isvaliddevice(player))
        return;
    *ratio = rumble_ratio[player];
    *msec = rumble_ms[player];
    rumble_ratio[player] = 0;
    rumble_ms[player] = 0;
}

void control_rumble(int deviceID, int ratio, int msec)
{
    if (!control_isvaliddevice(deviceID) || msec <= 0)
        return;
    rumble_ratio[deviceID] = ratio > 0 ? (ratio > 100 ? 100 : ratio) : 100;
    rumble_ms[deviceID] = msec;
}

#else

static int usejoy = 1;
static unsigned char prev_pad[4][16]; /* for control_scankey edge detect */

void control_init(int joy_enable)
{
    usejoy = joy_enable;
    memset(prev_pad, 0, sizeof(prev_pad));
}

void control_exit(void) {}

int control_usejoy(int enable)
{
    usejoy = enable;
    return usejoy;
}

int control_getjoyenabled(void)
{
    return usejoy;
}

static int flag_to_index(unsigned int flag)
{
    int index = 0;
    unsigned int bit = 1;
    while (!(bit & flag) && index < 31) {
        bit <<= 1;
        index++;
    }
    return index;
}

void control_setkey(s_playercontrols *pcontrols, unsigned int flag, int key)
{
    if (!pcontrols)
        return;
    pcontrols->settings[flag_to_index(flag)] = key;
}

static int key_down(int code)
{
    if (code < OBOR_KEYBASE || code >= OBOR_KEYBASE + 4 * OBOR_KEYSPAN)
        return 0;
    int pl = (code - OBOR_KEYBASE) / OBOR_KEYSPAN;
    int btn = (code - OBOR_KEYBASE) % OBOR_KEYSPAN;
    if (btn >= 16)
        return 0;
    return obor_pad[pl][btn];
}

void control_update(s_playercontrols **playercontrols, int numplayers)
{
    obor_poll_tick();
    for (int player = 0; player < numplayers; player++) {
        s_playercontrols *pcontrols = playercontrols[player];
        u64 k = 0;
        for (int i = 0; i < JOY_MAX_INPUTS; i++) {
            if (key_down(pcontrols->settings[i]))
                k |= ((u64)1 << i);
        }
        pcontrols->kb_break = 0;
        pcontrols->newkeyflags = k & (~pcontrols->keyflags);
        pcontrols->keyflags = k;
    }
}

/* Newly pressed (edge) pad button -> its virtual keycode. Used by the
 * in-game control-binding menu. */
int control_scankey(void)
{
    int hit = 0;
    for (int pl = 0; pl < 4 && !hit; pl++) {
        for (int btn = 0; btn < 16; btn++) {
            if (obor_pad[pl][btn] && !prev_pad[pl][btn]) {
                hit = OBOR_KEY(pl, btn);
                break;
            }
        }
    }
    memcpy(prev_pad, obor_pad, sizeof(prev_pad));
    return hit;
}

int keyboard_getlastkey(void)
{
    return control_scankey();
}

char *control_getkeyname(unsigned int keycode)
{
    static const char *btn_names[16] = {
        "Up", "Down", "Left", "Right", "Attack1", "Attack2", "Attack3",
        "Attack4", "Jump", "Special", "Start", "Esc", "Shot", "?", "?", "?",
    };
    static char name[32];
    if (keycode >= OBOR_KEYBASE && keycode < OBOR_KEYBASE + 4 * OBOR_KEYSPAN) {
        int pl = ((int)keycode - OBOR_KEYBASE) / OBOR_KEYSPAN;
        int btn = ((int)keycode - OBOR_KEYBASE) % OBOR_KEYSPAN;
        snprintf(name, sizeof(name), "P%d %s", pl + 1,
                 btn < 16 ? btn_names[btn] : "?");
        return name;
    }
    return (char *)"None";
}

/* Rumble: the engine pushes requests here; the glue polls them out once
 * per frame (obor_get_rumble) and drives the frontend's rumble interface. */
static int rumble_ratio[4], rumble_ms[4];

void obor_get_rumble(int32_t player, int32_t *ratio, int32_t *msec)
{
    *ratio = 0;
    *msec = 0;
    if (player < 0 || player >= 4)
        return;
    *ratio = rumble_ratio[player];
    *msec = rumble_ms[player];
    rumble_ratio[player] = 0;
    rumble_ms[player] = 0;
}

#if OBOR_ENGINE_BUILD >= 5000
void control_rumble(int port, int ratio, int msec)
{
    if (port < 0 || port >= 4 || msec <= 0)
        return;
    rumble_ratio[port] = ratio > 0 ? (ratio > 100 ? 100 : ratio) : 100;
    rumble_ms[port] = msec;
}
#else
void control_rumble(int port, int msec)
{
    if (port < 0 || port >= 4 || msec <= 0)
        return;
    rumble_ratio[port] = 100;
    rumble_ms[port] = msec;
}
#endif

#endif /* OBOR_ENGINE_BUILD >= 8023 */
