/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* AnyBOR — vga.h shim.
 * Newer eras keep vga.h in gamelib; older ones ship it per platform dir.
 * This copy (superset of both) shadows gamelib's via include order. */
#ifndef VGA_H
#define VGA_H

void vga_setpalette(unsigned char *palette);
void vga_set_color_correction(int gm, int br);
void vga_vwait(void);

#endif
