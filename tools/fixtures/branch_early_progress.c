/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include <assert.h>
#include <inttypes.h>
#include <stdarg.h>

uint32_t obor_profile_build;
int pixelformat;
static int palette_calls;
static char output[512];

void standard_palette(int replace)
{
    assert(replace == 1);
    ++palette_calls;
}

static void record_printf(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    vsnprintf(output, sizeof(output), format, args);
    va_end(args);
}

static struct
{
    int x, y;
    const char *text;
} credit_lines[40];
static size_t credit_count;

void font_printf(int x, int y, int font, int layer, char *text, ...)
{
    (void)font;
    (void)layer;
    assert(credit_count < sizeof(credit_lines) / sizeof(credit_lines[0]));
    credit_lines[credit_count].x = x;
    credit_lines[credit_count].y = y;
    credit_lines[credit_count++].text = text;
}

static int credit_row(int column, const char *name)
{
    for(size_t i = 0; i < credit_count; ++i)
    {
        if(credit_lines[i].x == column && !strcmp(credit_lines[i].text, name))
        {
            return credit_lines[i].y;
        }
    }
    return -1;
}

#undef _strmidx
#define _strmidx(...) 0
static void credits(void)
{
    int m, s = 0, v = 1, col1 = 1, col2 = 2;
    credit_count = 0;
    @CREDITS@
}

@TABLE@
static int selected_grab(int rnum)
{
    int which;
    @ORDER@
    return grab_attacks[which][0];
}

#undef ANDROID
#define ANDROID 1
#undef _menutext
#undef _menutextm
#undef Tr
#define Tr(name) (name)
#define _menutext(selected, x, y, text) font_printf((x), (y), (selected), 0, (text))
#define _menutextm(selected, y, shift, text) font_printf((shift), (y), (selected), 0, (text))
static void touchpad_label(int enabled)
{
    struct { int is_touchpad_vibration_enabled; } savedata = {enabled};
    int x_pos = 7, selector = 5;
    credit_count = 0;
    @TOUCH@
}

u64 getSystemRam(int unit) { assert(unit == 1); return 12; }
u64 getFreeRam(int unit) { assert(unit == 1); return 5; }
u64 getUsedRam(int unit) { assert(unit == 1); return 7; }

#undef printf
#define printf record_printf
@DIAGNOSTICS@
static void level_diagnostics(void)
{
    u64 totalram = 12, freeram = 5, usedram = 7;
    @LEVEL@
}
static void startup_palette(void)
{
    @STARTUP@
}
#undef printf

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    const int original[] = {ANI_GRABATTACK, ANI_GRABFORWARD, ANI_GRABUP, ANI_GRABDOWN, ANI_GRABBACKWARD};
    const int later[] = {ANI_GRABATTACK, ANI_GRABBACKWARD, ANI_GRABFORWARD, ANI_GRABDOWN, ANI_GRABUP};
    for(size_t p = 0; p < sizeof(profiles) / sizeof(profiles[0]); ++p)
    {
        obor_profile_build = profiles[p];
        const int oldest = obor_profile_build == 6997;
        const int early = oldest || obor_profile_build == 7039;
        for(int value = 13; value <= 31; ++value)
        {
            assert(selected_grab(value) == (oldest ? original : later)[value % 5]);
        }

        credits();
        assert(credit_row(1, oldest ? "White Dragon" : "Msmalik681") == 4);
        assert((credit_row(2, "White Dragon") == credit_row(1, "uTunnels")) == !oldest);
        assert((credit_row(1, "OpenDingux") >= 0) == oldest);
        assert((credit_row(1, "DreamCast") >= 0) == oldest);
        assert(credit_row(2, oldest ? "Plombo, SX" : "Plombo, SX, Msmalik681") == credit_row(1, "Wii"));
        assert(credit_row(2, oldest ? "uTunnels," : "uTunnels, Msmalik681") == credit_row(1, "Android") + 1);

        for(int enabled = 0; enabled <= 1; ++enabled)
        {
            touchpad_label(enabled);
            assert(credit_count == 1 && credit_lines[0].x == (early ? 7 : 0) && credit_lines[0].y == 4);
            assert(!strcmp(credit_lines[0].text, enabled ? "Touchpad Vibration Enabled" : "Touchpad Vibration Disabled"));
        }

        palette_calls = 0;
        pixelformat = PIXEL_32;
        startup_palette();
        assert(!palette_calls);
        pixelformat = PIXEL_8;
        startup_palette();
        assert(palette_calls == early);

        const char *legacy = "Total Ram: 12 Bytes\n Free Ram: 5 Bytes\n Used Ram: 7 Bytes\n";
        getRamStatus(1);
        assert((strncmp(legacy, output, strlen(legacy)) == 0) == oldest);
        assert((strstr(output, " MB ") != NULL) == !oldest);
        assert(output[strlen(output) - 2] == '\n');
        level_diagnostics();
        assert((strcmp(legacy, output) == 0) == oldest);
        assert((strstr(output, " MB ") != NULL) == !oldest);
    }
}
