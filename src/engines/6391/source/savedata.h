/* AnyBOR modification record: 2026-11-15.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Reserve the modified 6330 settings synchronization field while profile-
 * specific I/O preserves the native record size and values.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/6391.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2015 OpenBOR Team
 */

#ifndef SAVEDATA_H
#define SAVEDATA_H

#define     MAX_PLAYERS         4
#define     MAX_BTN_NUM         13

typedef struct
{
    unsigned compatibleversion;
    int gamma;
    int brightness;
    int usesound; // Use SB
    unsigned soundrate; // SB freq
    int soundvol; // SB volume
    int usemusic; // Play music
    int musicvol; // Music volume
    int effectvol; // Sound fx volume
    int soundbits; // SB bits
    int usejoy;
    int mode; // Mode now saves
    int windowpos;
    int keys[MAX_PLAYERS][MAX_BTN_NUM];
    int joyrumble[MAX_PLAYERS];
    int showtitles;
    int videoNTSC;
    int swfilter; // Software scaling filter
    int logo;
    int uselog;
    int debuginfo; // FPS, Memory, etc...
    int debug_collision_attack;
    int debug_collision_body;
    int debug_collision_entity;
    int debug_collision_range;
    int debug_position;
    int debug_features;
    int fullscreen; // Window or Full Screen Mode
    int stretch; // Stretch (1) or preserve aspect ratio (0) in fullscreen mode
    int screen[1][2];
#if SDL
    int usegl; // 1 if OpenGL is preferred over SDL software blitting
    float hwscale; // Scale factor for OpenGL
    int hwfilter; // Simple or bilinear scaling
#endif
#if PSP
    int pspcpuspeed; // PSP CPU Speed
    int overscan[4]; // Control TV Overscan
    int usetv; // Initilize TV at bootup
#endif
#if ANDROID
    int is_touchpad_vibration_enabled;
#endif
    int vsync;
} s_savedata;

extern s_savedata     savedata;

#endif
