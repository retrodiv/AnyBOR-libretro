/* AnyBOR modification record: 2026-10-30.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the restored inverse-transform and water renderer without changing
 * its original attribution or license.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
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

#include <stdint.h>
#include <limits.h>
static inline int obor_transform_add_center(int *x,int *y,const s_drawmethod *method)
{
    int64_t cx=(int64_t)*x+method->centerx;
    int64_t cy=(int64_t)*y+method->centery;
    if(cx<INT_MIN || cx>INT_MAX || cy<INT_MIN || cy>INT_MAX) return 0;
    *x=(int)cx;*y=(int)cy;
    return 1;
}

void gfx_draw_rotate(s_screen* dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod);
void gfx_draw_scale(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod);

void gfx_draw_water(s_screen *dest, gfx_entry *src, int x, int y,
                    int centerx, int centery, s_drawmethod *method);
void gfx_draw_plane(s_screen *dest, gfx_entry *src, int x, int y,
                    int centerx, int centery, s_drawmethod *method);
void obor_transform_triangle(vert2d *vertices, s_screen *dest, gfx_entry *src,
                             s_drawmethod *method, int count);
void obor_putsprite_inverse(int x, int y, s_sprite *frame, s_screen *screen,
                            s_drawmethod *method);
#endif
