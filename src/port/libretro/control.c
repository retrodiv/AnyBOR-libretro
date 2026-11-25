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
#include "anybor_abi.h"

#include <stdio.h>
#include <string.h>

static int key_down(int code)
{
    if (code < OBOR_KEYBASE || code >= OBOR_KEYBASE + 4 * OBOR_KEYSPAN)
        return 0;
    int player = (code - OBOR_KEYBASE) / OBOR_KEYSPAN;
    int button = (code - OBOR_KEYBASE) % OBOR_KEYSPAN;
    return button < 16 && obor_pad[player][button];
}

static unsigned char prev_pad[4][16];

static int scan_virtual_key(int ports)
{
    int hit = 0;
    for (int port = 0; port < ports && !hit; ++port) {
        for (int button = 0; button < 16; ++button) {
            if (obor_pad[port][button] && !prev_pad[port][button]) {
                hit = OBOR_KEY(port, button);
                break;
            }
        }
    }
    memcpy(prev_pad, obor_pad, sizeof(prev_pad));
    return hit;
}

static char *virtual_key_name(unsigned int keycode)
{
    static const char *btn_names[16] = {
        "Up", "Down", "Left", "Right", "Attack1", "Attack2", "Attack3",
        "Attack4", "Jump", "Special", "Start", "Esc", "Shot", "?", "?", "?",
    };
    static char name[32];
    if (keycode >= OBOR_KEYBASE && keycode < OBOR_KEYBASE + 4 * OBOR_KEYSPAN) {
        int port = ((int)keycode - OBOR_KEYBASE) / OBOR_KEYSPAN;
        int button = ((int)keycode - OBOR_KEYBASE) % OBOR_KEYSPAN;
        snprintf(name, sizeof(name), "P%d %s", port + 1,
                 button < 16 ? btn_names[button] : "?");
        return name;
    }
    return (char *)"None";
}

#if OBOR_ENGINE_BUILD >= 8023 || OBOR_ENGINE_BUILD == 7533

/* The controller branch indexes devices, not a global keyboard keyspace.
 * Each frontend port is a stable device. Mappings contain RetroPad button
 * numbers, and all four devices use the same default layout. */
static int mappings[4][OBOR_INPUT_COUNT];
static int initialized;
static int mapping_ready;
static int remap_device = -1;
static int remap_key = -1;
static unsigned char remap_previous[16];
static const int default_buttons[OBOR_INPUT_COUNT] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 11
};

static void defaults(int device)
{
    memcpy(mappings[device], default_buttons, sizeof(default_buttons));
}

bool control_isvaliddevice(int deviceID)
{
    return deviceID >= 0 && deviceID < 4;
}

static void begin_device_input(void)
{
    if (initialized)
        return;
    if (!mapping_ready)
        control_clearmappings();
    initialized = 1;
    remap_device = -1;
    remap_key = -1;
}

static void end_device_input(void)
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

static void update_device_input(s_playercontrols **players, int count)
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
#if OBOR_ENGINE_BUILD == 7533
        player->kb_break = 0;
#endif
    }
}

static const char *device_key_name(int keycode)
{
    static const char *names[16] = {
        "Up", "Down", "Left", "Right", "Attack 1", "Attack 2",
        "Attack 3", "Attack 4", "Jump", "Special", "Start", "Exit",
        "Screenshot", "Button 13", "Button 14", "Button 15"
    };
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
#endif

#if OBOR_ENGINE_BUILD >= 8023

static int legacy_keys[4][OBOR_INPUT_COUNT];
static int legacy_usejoy;

void control_legacy_default_keys(int player, int *keys)
{
    for (int button = 0; button < OBOR_INPUT_COUNT - 1; ++button)
        keys[button] = player == 0 ? OBOR_KEY(0, default_buttons[button]) : CONTROL_NONE;
}

void control_legacy_apply_keys(int player, const int *keys)
{
    if (!control_isvaliddevice(player))
        return;
    memcpy(legacy_keys[player], keys, sizeof(legacy_keys[player]));
    legacy_keys[player][OBOR_INPUT_COUNT - 1] = OBOR_KEY(0, default_buttons[OBOR_INPUT_COUNT - 1]);
}

void control_legacy_usejoy(int enabled)
{
    legacy_usejoy = enabled;
}

void control_legacy_begin_scan(void)
{
    memcpy(prev_pad, obor_pad, sizeof(prev_pad));
}

int control_legacy_scan_key(void)
{
    return scan_virtual_key(legacy_usejoy ? 4 : 1);
}

const char *control_legacy_key_name(int keycode)
{
    return virtual_key_name(keycode);
}

static void update_legacy_input(s_playercontrols **players, int count)
{
    obor_poll_tick();
    for (int i = 0; i < count; ++i) {
        s_playercontrols *player = players[i];
        const int device = player->deviceID;
        uint32_t primary = 0;
        uint32_t other = 0;
        if (control_isvaliddevice(device)) {
            for (int button = 0; button < OBOR_INPUT_COUNT; ++button) {
                const int code = legacy_keys[device][button];
                if (!key_down(code))
                    continue;
                if (code < OBOR_KEY(1, 0))
                    primary |= UINT32_C(1) << button;
                else if (legacy_usejoy)
                    other |= UINT32_C(1) << button;
            }
            /* The primary RetroPad stands in for the original keyboard. */
            if (device == 0 && !primary) {
                for (int button = 0; button < OBOR_INPUT_COUNT; ++button) {
                    if (obor_pad[0][default_buttons[button]])
                        primary |= UINT32_C(1) << button;
                }
            }
        }
        const uint32_t flags = primary | other;
        player->newkeyflags = flags & ~player->keyflags;
        player->keyflags = flags;
    }
}

void control_init(void)
{
    begin_device_input();
}

void control_exit(void)
{
    end_device_input();
}

void control_update(s_playercontrols **players, int count)
{
    if (control_uses_legacy_8020(obor_profile_build))
        update_legacy_input(players, count);
    else
        update_device_input(players, count);
}

void control_update_keyboard(s_playercontrols *player)
{
    s_playercontrols *one[] = {player};
    control_update(one, 1);
}

const char *control_getkeyname(int deviceID, int keycode)
{
    (void)deviceID;
    return device_key_name(keycode);
}

static int rumble_ratio[4], rumble_ms[4];

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
    if (!control_isvaliddevice(deviceID) || ratio <= 0 || msec <= 0)
        return;
    rumble_ratio[deviceID] = 100;
    rumble_ms[deviceID] = msec;
}

#else

static int usejoy = 1;

#if OBOR_ENGINE_BUILD == 7533
extern s_playercontrols *playercontrolpointers[];

bool control_uses_device_mappings(void)
{
    return obor_profile_build && obor_profile_build < 7404u;
}

const char *control_getdevicekeyname(int keycode)
{
    return device_key_name(keycode);
}
#endif

void control_init(int joy_enable)
{
    usejoy = joy_enable;
    memset(prev_pad, 0, sizeof(prev_pad));
#if OBOR_ENGINE_BUILD == 7533
    if (control_uses_device_mappings() && !initialized) {
        begin_device_input();
        for (int player = 0; player < 4; ++player)
            playercontrolpointers[player]->deviceID = player;
    }
#endif
}

void control_exit(void)
{
#if OBOR_ENGINE_BUILD == 7533
    end_device_input();
#endif
}

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

#if OBOR_ENGINE_BUILD == 6391
extern s_playercontrols default_control;
extern int allow_default_keys(void);
#endif

void control_update(s_playercontrols **playercontrols, int numplayers)
{
#if OBOR_ENGINE_BUILD == 7533
    if (control_uses_device_mappings()) {
        update_device_input(playercontrols, numplayers);
        return;
    }
#endif
    obor_poll_tick();
    for (int player = 0; player < numplayers; player++) {
        s_playercontrols *pcontrols = playercontrols[player];
        u64 k = 0;
        for (int i = 0; i < JOY_MAX_INPUTS; i++) {
            if (key_down(pcontrols->settings[i]))
                k |= ((u64)1 << i);
        }
#if OBOR_ENGINE_BUILD == 6391
        if (player == 0 && !k &&
            ((obor_profile_features & OBOR_PROFILE_LNS_6330) ? allow_default_keys() :
             (obor_profile_build >= 6250 && obor_profile_build <= 6391))) {
            for (int i = 0; i < JOY_MAX_INPUTS; i++) {
                if (key_down(default_control.settings[i]))
                    k |= ((u64)1 << i);
            }
        }
        if (obor_profile_build && obor_profile_build < 6173)
            k &= UINT32_MAX;
#endif
        pcontrols->kb_break = 0;
        pcontrols->newkeyflags = k & (~pcontrols->keyflags);
        pcontrols->keyflags = k;
    }
}

/* Newly pressed (edge) pad button -> its virtual keycode. Used by the
 * in-game control-binding menu. */
int control_scankey(void)
{
    return scan_virtual_key(4);
}

int keyboard_getlastkey(void)
{
    return control_scankey();
}

char *control_getkeyname(unsigned int keycode)
{
    return virtual_key_name(keycode);
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
#if OBOR_ENGINE_BUILD == 6391
    if (obor_profile_build && obor_profile_build < 6229)
        return;
#endif
#if OBOR_ENGINE_BUILD == 7533
    if (control_uses_device_mappings() && port >= 0 && port < 4)
        port = playercontrolpointers[port]->deviceID;
#endif
    if (port < 0 || port >= 4 || ratio <= 0 || msec <= 0)
        return;
    /* The source engines pass integer 1 as SDL's normalized full strength. */
    rumble_ratio[port] = 100;
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
