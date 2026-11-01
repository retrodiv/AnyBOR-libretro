/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Complete renderer unit, with bounded services for the pixel callback only.
 */
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include @RENDERER@
static int probe_mode;
static @PIXEL@ probe_mix(@MIX_ARGS@)
{
    @MIX_UNUSED@
    if(probe_mode == 2) return fillcolor;
    if(probe_mode == 3) source = fillcolor;
    return (@PIXEL@)(source ^ destination ^ 0x5a);
}
void render_@UNIT@(int epoch, int x, int cx, int scale, int flip, int mode,
                  int row, int *line, uint32_t *output)
{
    @PIXEL@ image[72], palette[256];
    unsigned char table[256];
    int i;
    (void)epoch;
    for(i=0;i<72;i++) image[i]=(@PIXEL@)(i*13+7);
    for(i=0;i<256;i++) {
        palette[i]=(@PIXEL@)@PALETTE@;
        table[i]=(unsigned char)i;
    }
    screenwidth=8;
    screenheight=9;
    probe_mode=mode;
    fillcolor=(@PIXEL@)@FILL@;
    @CALL@
    for(i=0;i<72;i++) output[i]=image[i];
}
