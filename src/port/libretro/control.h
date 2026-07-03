/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR input backend — API mirror of sdl/control.h.
 *
 * Virtual keycode space: code = OBOR_KEYBASE + player*OBOR_KEYSPAN + button,
 * one code per (RetroPad player, OpenBOR button). The default bindings wire
 * player N's pad to player N's controls, so games are playable out of the
 * box and the in-game control options can still rebind (control_scankey
 * reports any newly pressed pad button as its code).
 */
#ifndef CONTROL_H
#define CONTROL_H

#define OBOR_KEYBASE 100
#define OBOR_KEYSPAN 32
#define OBOR_KEY(pl, btn) (OBOR_KEYBASE + (pl) * OBOR_KEYSPAN + (btn))
/* button indexes follow obor_abi.h (OBOR_BTN_*) */

#define JOY_TYPE_DEFAULT 0
#define JOY_AXIS_X 0
#define JOY_AXIS_Y 1
#define JOY_MAX_INPUTS 64
#define JOY_LIST_FIRST 600
#define JOY_LIST_TOTAL 4
#define JOY_LIST_LAST (JOY_LIST_FIRST + JOY_MAX_INPUTS * JOY_LIST_TOTAL)
#define JOY_NAME_SIZE (1 + 1 + JOY_MAX_INPUTS * JOY_LIST_TOTAL)

/* Key range the engine treats as "valid keyboard key" (see control_update
 * range checks in openbor.c options menus). */
#define SDLK_FIRST 0
#define SDLK_LAST (OBOR_KEYBASE + 4 * OBOR_KEYSPAN)

#define CONTROL_ESC OBOR_KEY(0, 11 /* OBOR_BTN_ESC */)

/* sentinel used by newer engines (>=7xxx) to clear a binding */
#define CONTROL_NONE ((JOY_LIST_FIRST + 1) + (JOY_MAX_INPUTS * 99))

#define CONTROL_DEFAULT1_UP OBOR_KEY(0, 0)
#define CONTROL_DEFAULT1_DOWN OBOR_KEY(0, 1)
#define CONTROL_DEFAULT1_LEFT OBOR_KEY(0, 2)
#define CONTROL_DEFAULT1_RIGHT OBOR_KEY(0, 3)
#define CONTROL_DEFAULT1_FIRE1 OBOR_KEY(0, 4) /* attack  */
#define CONTROL_DEFAULT1_FIRE2 OBOR_KEY(0, 5) /* attack2 */
#define CONTROL_DEFAULT1_FIRE3 OBOR_KEY(0, 6) /* attack3 */
#define CONTROL_DEFAULT1_FIRE4 OBOR_KEY(0, 7) /* attack4 */
#define CONTROL_DEFAULT1_FIRE5 OBOR_KEY(0, 8) /* jump    */
#define CONTROL_DEFAULT1_FIRE6 OBOR_KEY(0, 9) /* special */
#define CONTROL_DEFAULT1_START OBOR_KEY(0, 10)
#define CONTROL_DEFAULT1_SCREENSHOT OBOR_KEY(0, 12)
#define CONTROL_DEFAULT1_ESC OBOR_KEY(0, 11)

#define CONTROL_DEFAULT2_UP OBOR_KEY(1, 0)
#define CONTROL_DEFAULT2_DOWN OBOR_KEY(1, 1)
#define CONTROL_DEFAULT2_LEFT OBOR_KEY(1, 2)
#define CONTROL_DEFAULT2_RIGHT OBOR_KEY(1, 3)
#define CONTROL_DEFAULT2_FIRE1 OBOR_KEY(1, 4)
#define CONTROL_DEFAULT2_FIRE2 OBOR_KEY(1, 5)
#define CONTROL_DEFAULT2_FIRE3 OBOR_KEY(1, 6)
#define CONTROL_DEFAULT2_FIRE4 OBOR_KEY(1, 7)
#define CONTROL_DEFAULT2_FIRE5 OBOR_KEY(1, 8)
#define CONTROL_DEFAULT2_FIRE6 OBOR_KEY(1, 9)
#define CONTROL_DEFAULT2_START OBOR_KEY(1, 10)
#define CONTROL_DEFAULT2_SCREENSHOT OBOR_KEY(1, 12)

#define CONTROL_DEFAULT3_UP OBOR_KEY(2, 0)
#define CONTROL_DEFAULT3_DOWN OBOR_KEY(2, 1)
#define CONTROL_DEFAULT3_LEFT OBOR_KEY(2, 2)
#define CONTROL_DEFAULT3_RIGHT OBOR_KEY(2, 3)
#define CONTROL_DEFAULT3_FIRE1 OBOR_KEY(2, 4)
#define CONTROL_DEFAULT3_FIRE2 OBOR_KEY(2, 5)
#define CONTROL_DEFAULT3_FIRE3 OBOR_KEY(2, 6)
#define CONTROL_DEFAULT3_FIRE4 OBOR_KEY(2, 7)
#define CONTROL_DEFAULT3_FIRE5 OBOR_KEY(2, 8)
#define CONTROL_DEFAULT3_FIRE6 OBOR_KEY(2, 9)
#define CONTROL_DEFAULT3_START OBOR_KEY(2, 10)
#define CONTROL_DEFAULT3_SCREENSHOT OBOR_KEY(2, 12)

#define CONTROL_DEFAULT4_UP OBOR_KEY(3, 0)
#define CONTROL_DEFAULT4_DOWN OBOR_KEY(3, 1)
#define CONTROL_DEFAULT4_LEFT OBOR_KEY(3, 2)
#define CONTROL_DEFAULT4_RIGHT OBOR_KEY(3, 3)
#define CONTROL_DEFAULT4_FIRE1 OBOR_KEY(3, 4)
#define CONTROL_DEFAULT4_FIRE2 OBOR_KEY(3, 5)
#define CONTROL_DEFAULT4_FIRE3 OBOR_KEY(3, 6)
#define CONTROL_DEFAULT4_FIRE4 OBOR_KEY(3, 7)
#define CONTROL_DEFAULT4_FIRE5 OBOR_KEY(3, 8)
#define CONTROL_DEFAULT4_FIRE6 OBOR_KEY(3, 9)
#define CONTROL_DEFAULT4_START OBOR_KEY(3, 10)
#define CONTROL_DEFAULT4_SCREENSHOT OBOR_KEY(3, 12)

#include "types.h"

typedef struct
{
    int settings[JOY_MAX_INPUTS];
    u64 keyflags, newkeyflags;
    int kb_break;
} s_playercontrols;

void control_exit(void);
void control_init(int joy_enable);
int control_usejoy(int enable);
int control_getjoyenabled(void);
void control_setkey(s_playercontrols *pcontrols, unsigned int flag, int key);
int control_scankey(void);
char *control_getkeyname(unsigned int keycode);
void control_update(s_playercontrols **playercontrols, int numplayers);
/* rumble grew a ratio arg in the 6xxx era */
#if OBOR_ENGINE_BUILD >= 5000
void control_rumble(int port, int ratio, int msec);
#else
void control_rumble(int port, int msec);
#endif
int keyboard_getlastkey(void);

#endif
