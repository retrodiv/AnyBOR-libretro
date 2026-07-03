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
