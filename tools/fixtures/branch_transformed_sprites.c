/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include "anybor_resources.h"
#include <assert.h>
#include <string.h>

uint32_t obor_profile_build;
unsigned char pal[MAX_PAL_SIZE];
static unsigned *registered_palette;
static transpixelfunc pfp;
static blend16fp pfp16;
static blend32fp pfp32;
static unsigned fillcolor;
static unsigned char *table;
static unsigned char *remaptable;
static unsigned char *ptr_src;
static unsigned char *ptr_src_mask;
static unsigned char *cur_src;
static unsigned char *cur_src_mask;
static unsigned char *cur_dest;
static unsigned char *cur_spr;
static unsigned char dummyptrs[8];
static int spf, dpf, transbg, wpcond;

int obor_allocation_contains(const void *pointer, size_t size)
{
    return pointer == registered_palette && size <= 256 * sizeof(unsigned);
}

#include "source/gamelib/writepixel.h"

@BLEND@
@METHODS@

void *checkAlloc(void *pointer, size_t size, const char *function, const char *file, int line)
{
    (void)size;
    (void)function;
    (void)file;
    (void)line;
    assert(pointer);
    return pointer;
}

static void make_sprite(s_sprite *sprite, unsigned char *palette, unsigned char value)
{
    sprite->magic = sprite_magic;
    sprite->width = sprite->height = 1;
    sprite->pixelformat = PIXEL_x8;
    sprite->palette = palette;
    sprite->data[0] = sizeof(int);
    memcpy((unsigned char *)sprite->data + sizeof(int),
           (unsigned char[]){0, 1, value, 255}, 4);
}

static void render_sprite_scanline(gfx_entry *src, unsigned *result)
{
    spf = src->sprite->pixelformat;
    dpf = PIXEL_32;
    transbg = 1;
    fillcolor = 0;
    table = src->sprite->palette;
    ptr_src = (unsigned char *)src->sprite->data;
    @MASK@
    _sprite_seek(0, 0);
    cur_dest = (unsigned char *)result;
    calc_wp_cond();
    writepixelswitch(,;)
}

static unsigned render_solid_fill(unsigned char *palette)
{
    unsigned source_pixel = 0;
    unsigned result = 0;
    spf = dpf = PIXEL_32;
    transbg = 0;
    fillcolor = 0x12ab1fu;
    table = palette;
    ptr_src_mask = NULL;
    cur_src = (unsigned char *)&source_pixel;
    cur_src[0] = 1;
    cur_dest = (unsigned char *)&result;
    calc_wp_cond();
    writepixelswitch(,;)
    return result;
}

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    const unsigned foreground = 0x341278u;
    const unsigned background = 0x50e20au;
    unsigned palette[256] = {[1] = foreground};
    unsigned small_table[2] = {[1] = foreground};
    registered_palette = palette;
    memcpy(pal + sizeof(foreground), &foreground, sizeof(foreground));
    s_sprite sprite = {0};
    s_sprite mask = {0};
    make_sprite(&sprite, (unsigned char *)palette, 1);
    make_sprite(&mask, NULL, 64);
    gfx_entry entry = {.sprite = &sprite};
    s_screen *screen = calloc(1, sizeof(*screen) + sizeof(unsigned));
    assert(screen);
    screen->width = screen->height = 1;
    screen->pixelformat = PIXEL_32;
    unsigned *pixel = (unsigned *)screen->data;
    const unsigned blended = blend_channel32(foreground, background, 64);
    const unsigned scanline_blended = blend_channel32(foreground, background, 0);
    assert(blended != foreground);
    assert(scanline_blended != foreground);
    for(size_t p = 0; p < sizeof(profiles) / sizeof(profiles[0]); ++p)
    {
        obor_profile_build = profiles[p];
        const int early = profiles[p] == 6997 || profiles[p] == 7039;
        for(int masked = 0; masked <= 1; ++masked)
        {
            sprite.mask = masked ? &mask : NULL;
            const int uses_mask = masked && !early;
            *pixel = background;
            table = NULL;
            fillcolor = 0;
            draw_pixel_sprite(screen, &entry, 0, 0, 0, 0);
            assert(*pixel == (uses_mask ? blended : foreground));
            *pixel = background;
            render_sprite_scanline(&entry, pixel);
            // The scanline writer reads the first byte of the encoded mask row.
            assert(*pixel == (uses_mask ? scanline_blended : foreground));
        }
        assert(render_solid_fill((unsigned char *)palette) == (early ? foreground : 0x12ab1fu));
        assert(render_solid_fill(pal) == (early ? foreground : 0x12ab1fu));
        assert(render_solid_fill((unsigned char *)small_table) == 0x12ab1fu);
        assert(render_solid_fill(NULL) == 0x12ab1fu);
    }
    free(screen);
}
