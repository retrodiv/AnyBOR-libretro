/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include <assert.h>

uint32_t obor_profile_build;
char packfile[OBOR_CONTENT_PATH_MAX] = "profile-test.pak";
int pixelbytes[5] = {[PIXEL_32] = 4};
unsigned char pal[MAX_PAL_SIZE];
unsigned char neontable[MAX_PAL_SIZE];
s_screen *background;

static s_screen screen;
static unsigned char image_palette[MAX_PAL_SIZE];
static int palette_calls;

void unload_background(void)
{
    background = NULL;
}

int loadscreen(char *name, char *archive, unsigned char *palette, int mode, s_screen **result)
{
    assert(strcmp(name, "background.png") == 0 && archive == packfile);
    assert(palette == NULL && mode == PIXEL_x8 && *result == NULL);
    if(screen.pixelformat == PIXEL_32)
    {
        return 0;
    }
    *result = &screen;
    return 1;
}

int loadscreen32(char *name, char *archive, s_screen **result)
{
    assert(strcmp(name, "background.png") == 0 && archive == packfile);
    assert(screen.pixelformat == PIXEL_32 && *result == NULL);
    *result = &screen;
    return 1;
}

void standard_palette(int immediate)
{
    assert(!immediate);
    assert(background == &screen);
    assert(pal[0] == (screen.pixelformat == PIXEL_x8 ? 31 : 17));
    memset(pal, 113, PAL_BYTES / 2);
    ++palette_calls;
}

void borShutdown(int status, char *message, ...)
{
    (void)status;
    (void)message;
    abort();
}

void writeToLogFile(const char *message, ...)
{
    (void)message;
}

@METHODS@

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    const int modes[] = {PIXEL_x8, PIXEL_32};
    const int paths = 4;
    memset(image_palette, 31, sizeof(image_palette));
    screen.palette = image_palette;
    for(size_t profile = 0; profile < sizeof(profiles) / sizeof(profiles[0]); ++profile)
    {
        obor_profile_build = profiles[profile];
        const int early = obor_profile_build == 6997 || obor_profile_build == 7039;
        for(size_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode)
        {
            screen.pixelformat = modes[mode];
            for(int path = 0; path < paths; ++path)
            {
                palette_calls = 0;
                memset(pal, 17, sizeof(pal));
                memset(neontable, 23, sizeof(neontable));
                switch(path)
                {
                case 0: load_background("background.png"); break;
                case 1: load_cached_background("background.png"); break;
                case 2: obor_load_background("background.png", 1); break;
                case 3: obor_load_cached_background("background.png", 1); break;
                }
                const int apply_standard = early && path >= 2;
                const int image_value = modes[mode] == PIXEL_x8 ? 31 : 17;
                assert(palette_calls == apply_standard);
                assert(pal[0] == (apply_standard ? 113 : image_value));
                assert(pal[MAX_PAL_SIZE / 2] == image_value);
                assert(neontable[0] == (modes[mode] == PIXEL_x8 ? 31 : 23));
            }
        }
    }
}
