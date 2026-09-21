/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the raster helpers as ordinary functions; the header only declared
 * them inline and the definitions live in transform.c.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4432.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#ifndef TRANSFORM_H
#define TRANSFORM_H
void gfx_draw_rotate(s_screen *dest, gfx_entry *src, int x, int y, int centerx, int centery, s_drawmethod *drawmethod);
void gfx_draw_scale(s_screen *dest, gfx_entry *src, int x, int y, int centerx, int centery, s_drawmethod *drawmethod);
void gfx_draw_water(s_screen *dest, gfx_entry *src, int x, int y, int centerx, int centery, s_drawmethod *drawmethod);
void gfx_draw_plane(s_screen *dest, gfx_entry *src, int x, int y, int centerx, int centery, s_drawmethod *drawmethod);
void draw_pixel_screen(s_screen *dest, gfx_entry *src, int dx, int dy, int sx, int sy);
void draw_pixel_bitmap(s_screen *dest, gfx_entry *src, int dx, int dy, int sx, int sy);
void draw_pixel_sprite(s_screen *dest, gfx_entry *src, int dx, int dy, int sx, int sy);
void draw_pixel_gfx(s_screen *dest, gfx_entry *src, int dx, int dy, int sx, int sy);
void copy_pixel_block(int bytes);
void src_seek(int x, int y);
void dest_seek(int x, int y);
void src_line_inc();
void src_line_dec();
void src_inc();
void src_dec();
void dest_line_inc();
void dest_line_dec();
void dest_inc();
void dest_dec();
void write_pixel();
char sprite_get_pixel(s_sprite *sprite, int x, int y);
void init_gfx_global_draw_stuff(s_screen *, gfx_entry *, s_drawmethod *);
#endif
