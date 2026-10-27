"""Render native fade frames against source-derived arithmetic expectations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def _divide(value, divisor):
    return value // divisor if value >= 0 else -((-value) // divisor)


def _initial(fmt):
    if fmt == 0:
        return bytes([0, 1, 7, 64, 127, 128, 254, 255])
    values = ([0x1234, 0xffff, 0, 0xf800, 0x07e0, 0x001f, 0x7bef, 0x8421]
              if fmt == 2 else
              [0xa5123456, 0xffffffff, 0, 0x10ff0000, 0x2000ff00,
               0x300000ff, 0x407f8081, 0x55010203])
    return b''.join(value.to_bytes(fmt, 'little') for value in values)


def _reference(kind, fmt, mode, speed, step, overlap, gamma, bright):
    """Integer equations read from each original; no native probe execution."""
    image = _initial(fmt)
    original = image
    frames, corrections, volumes = [], [], []
    updates = timers = waits = closes = 0
    current = speed or 80
    legacy = kind.startswith('legacy_')
    capped = kind == 'buffer_capped'
    j = i = 0

    def correct(value, gm, br):
        gm, br = max(-255, min(255, gm)), max(-255, min(255, br))
        value = value * (255 + br) // 255 if br < 0 else br + value * (255 - br) // 255
        return (value * (65025 + (255 - value) * gm) // 65025 if gm <= 0 else
                255 - (255 - value) * (65025 - value * gm) // 65025)

    while j < 64:
        while j <= i and (not capped or j < 64):
            if mode in (0, 1):
                br = _divide((bright + 256) * (64 - j), 64) - 256
                gm = 256 - _divide((gamma + 256) * (64 - j), 64)
                corrections += [gm, br]
                waits += 1
                if fmt:
                    output = bytearray()
                    factor = ((256 - 4 * (j + 1)) if kind == 'buffer_delta' else
                              _divide(254 * (64 - j), 64)) & 0xffffffff
                    for offset in range(0, len(image), fmt):
                        value = int.from_bytes((image if legacy else original)[offset:offset + fmt], 'little')
                        if legacy:
                            if fmt == 2:
                                red = (value & 31) * 255 // 31
                                green = ((value >> 5) & 63) * 255 // 63
                                blue = (value >> 11) * 255 // 31
                            else:
                                red, green, blue = value & 255, (value >> 8) & 255, (value >> 16) & 255
                            other = gamma if kind == 'legacy_mixed_gamma' else gm
                            red, green, blue = correct(red, gm, br), correct(green, other, br), correct(blue, other, br)
                            value = (((blue & 248) << 8) | ((green & 252) << 3) | (red >> 3) if fmt == 2 else
                                     (value & 0xff000000) | (blue << 16) | (green << 8) | red)
                        else:
                            if fmt == 2:
                                components = [value & 31, (value >> 5) & 63, value >> 11]
                                red, green, blue = [((component * factor) & 0xffffffff) >> 8 for component in components]
                                value = ((blue << 11) | (green << 5) | red) & 0xffff
                            else:
                                components = [value & 255, (value >> 8) & 255, value >> 16]
                                red, green, blue = [((component * factor) & 0xffffffff) >> 8 for component in components]
                                value = ((blue << 16) | (green << 8) | red) & 0xffffffff
                        output += value.to_bytes(fmt, 'little')
                    image = bytes(output)
            j += 1
            if mode in (0, 1):
                frames.append(image.hex())
        if mode in (0, 2):
            updates += 1
            if not overlap:
                volumes.append(_divide(71 * (64 - j), 64))
        timers += 1
        interval = current // 60 if step > current else step
        i += min(interval, current // 4)
    if mode in (0, 2) and not overlap:
        closes = 1
    if mode in (0, 1):
        frames.append(bytes(len(image)).hex())
        waits += 1
        corrections += [gamma, bright]
    return dict(frames=''.join(frames), corrections=corrections, volumes=volumes,
                video=len(frames), updates=updates, timers=timers, waits=waits,
                closes=closes, buffer=int(not legacy and fmt != 0 and mode in (0, 1)))


def render_fade(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    pix = (engine / 'source/gamelib/pixelformat.c').read_text()
    palette = (engine / 'source/gamelib/palette.h').read_text()
    macros = '\n'.join(line for line in palette.splitlines() if line.startswith('#define') and
                       any(name in line for name in ('gammacorrect', 'brightnesscorrect', 'gbcorrect')))
    names = ('_channel', '_color', '_b1', '_g1', '_r1', '_b2', '_g2', '_r2', '_channel16', '_color16')
    macros += '\n' + '\n'.join(re.search(r'(?m)^#define\s+' + name + r'(?=[(\s])[^\n]*', pix)[0] for name in names)
    kernels = '\n'.join(function(pix, name) for name in ('colour16', 'blend_rgbchannel16', 'blend_rgbchannel32'))
    kernels += '\n' + '\n'.join(function((engine / ('source/gamelib/screen%d.c' % bits)).read_text(),
                                         'blendscreen%d' % bits) for bits in (16, 32))
    scenarios = [(fmt, 1 if gm == 64 else 0, 0 if gm == 64 else 64, step,
                  int(gm == -80), gm, br) for fmt in (2, 4)
                 for gm, br in ((0, 0), (64, -32), (-80, 40)) for step in (1, 17)]
    scenarios += [(0, mode, 64, step, 0, 64, -32) for mode in (0, 1) for step in (1, 17)]
    scenarios += [(4, 2, 64, step, overlap, 0, 0) for overlap in (0, 1) for step in (1, 17)]
    kinds = sorted({row['fade_kind'] for row in fixture['sources']})
    tables = []
    for kind in kinds:
        for values in scenarios:
            result = _reference(kind, *values)
            def array(name):
                return '(const int[]){' + ','.join(map(str, result[name] or [0])) + '}'
            tables.append('{' + ','.join(map(str, values)) + ',' + ','.join(str(result[key]) for key in
                ('video', 'updates', 'timers', 'waits', 'closes', 'buffer')) + ',' +
                str(len(result['corrections'])) + ',' + str(len(result['volumes'])) + ',"' + result['frames'] + '",' +
                array('corrections') + ',' + array('volumes') + '}')
    checks = '\n'.join('obor_profile_build=%d;check(%d);' % (row['revision'], kinds.index(row['fade_kind']))
                       for row in fixture['sources'])
    legacy = function(source, '_fade_screen') if '_fade_screen(' in source else ''
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdalign.h>
typedef uint32_t u32;
typedef uint16_t u16;
#define PIXEL_8 0
#define PIXEL_16 2
#define PIXEL_32 4
static uint32_t obor_profile_build;
static unsigned cases;
static int sample;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"fade profile=%u sample=%d line=%d\n",obor_profile_build,sample,__LINE__);abort();}}while(0)
typedef struct {int width,height,pixelformat;alignas(4) unsigned char data[32];} s_screen;
typedef struct {int flag,alpha;unsigned channelr,channelg,channelb;} s_drawmethod;
static s_screen display,copy,*vscreen=&display;
static s_drawmethod plainmethod={1,0,255,255,255};
static struct {int gamma,brightness,musicvol;} savedata;
static int fade=80,musicoverlap,screenformat,pal;
static const int pixelbytes[]={1,1,2,3,4};
static unsigned channelr,channelg,channelb;
static int useclip,clipx1,clipx2,clipy1,clipy2;
@MACROS@
@KERNELS@
@LEGACY@
typedef struct {
 int fmt,mode,speed,step,overlap,gamma,bright,video,updates,timers,waits,closes,buffer,correction_n,volume_n;
 const char *frames;const int *corrections,*volumes;
} Scenario;
static const Scenario scenarios[]={@TABLES@};
static const Scenario *expected;
static int videos,updates,timers,waits,closes,allocs,copies,frees,corrections,volumes,palettes;
static unsigned char initial[32];
static int digit(char c){return c<='9'?c-'0':c-'a'+10;}
static void video_copy_screen(s_screen *screen){
 assert(screen==vscreen && videos<expected->video);
 size_t len=(size_t)(8*pixelbytes[screenformat]);
 const char *hex=expected->frames+(size_t)videos*len*2;
 for(size_t k=0;k<len;++k)assert(screen->data[k]==digit(hex[k*2])*16+digit(hex[k*2+1]));
 ++videos;
}
static void palette_set_corrected(int value,int gr,int gg,int gb,int br,int bg,int bb){
 assert(value==pal && screenformat==PIXEL_8);
 assert(gr==savedata.gamma && gg==gr && gb==gr);
 assert(br==savedata.brightness && bg==br && bb==br);++palettes;
}
@CORRECTION@
static int tracked_correction(int gm,int br){
 assert(corrections+1<expected->correction_n);
 assert(gm==expected->corrections[corrections++] && br==expected->corrections[corrections++]);
 return set_color_correction(gm,br);
}
#define set_color_correction tracked_correction
static void vga_vwait(void){++waits;}
static void clearscreen(s_screen *screen){assert(screen==vscreen);memset(screen->data,0,8*pixelbytes[screenformat]);}
static s_screen *allocscreen(int w,int h,int fmt){assert(w==4 && h==2 && fmt==screenformat);++allocs;copy=(s_screen){.width=w,.height=h,.pixelformat=fmt};return &copy;}
static void copyscreen(s_screen *dest,s_screen *src){assert(dest==&copy && src==vscreen);memcpy(dest->data,src->data,sizeof(src->data));++copies;}
static void freescreen(s_screen **screen){assert(*screen==&copy);++frees;*screen=NULL;}
static void putscreen(s_screen *dest,s_screen *src,int x,int y,s_drawmethod *dm){
 assert(dest==vscreen && src==&copy && !x && !y && dm->flag==1 && dm->alpha==6);
 assert(dm->channelr==dm->channelg && dm->channelg==dm->channelb);
 assert(!memcmp(src->data,initial,8*pixelbytes[screenformat]));
 for(int k=0;k<8*pixelbytes[screenformat];++k)assert(!dest->data[k]);
 channelr=dm->channelr;channelg=dm->channelg;channelb=dm->channelb;
 if(screenformat==PIXEL_16)blendscreen16(dest,src,0,0,0,blend_rgbchannel16);
 else {assert(screenformat==PIXEL_32);blendscreen32(dest,src,0,0,0,blend_rgbchannel32);}
}
static void sound_update_music(void){++updates;}
static void sound_volume_music(int left,int right){assert(volumes<expected->volume_n && left==right && left==expected->volumes[volumes++]);}
static void sound_close_music(void){++closes;}
static u32 timer_getinterval(int current){assert(current==(expected->speed?expected->speed:fade));++timers;return (u32)expected->step;}
@FADE@
#undef set_color_correction
static void check(int kind){
 const u16 pixels16[]={0x1234,0xffff,0,0xf800,0x07e0,0x001f,0x7bef,0x8421};
 const u32 pixels32[]={0xa5123456,0xffffffff,0,0x10ff0000,0x2000ff00,0x300000ff,0x407f8081,0x55010203};
 const unsigned char pixels8[]={0,1,7,64,127,128,254,255};
 const uint32_t endian=1;assert(*(const unsigned char*)&endian==1);
 for(sample=0;sample<@SCENARIO_COUNT@;++sample){
  expected=&scenarios[kind*@SCENARIO_COUNT@+sample];screenformat=expected->fmt;
  savedata.gamma=expected->gamma;savedata.brightness=expected->bright;savedata.musicvol=71;
  musicoverlap=expected->overlap;display=(s_screen){.width=4,.height=2,.pixelformat=screenformat};
  memcpy(display.data,screenformat==0?(const void*)pixels8:screenformat==2?(const void*)pixels16:(const void*)pixels32,8*pixelbytes[screenformat]);
  memcpy(initial,display.data,sizeof(initial));
  videos=updates=timers=waits=closes=allocs=copies=frees=corrections=volumes=palettes=0;
  fade_out(expected->mode,expected->speed);
  assert(videos==expected->video && updates==expected->updates && timers==expected->timers && waits==expected->waits && closes==expected->closes);
  assert(corrections==expected->correction_n && volumes==expected->volume_n);
  assert(allocs==expected->buffer && copies==allocs && frees==allocs);
  assert(palettes==(screenformat==0?corrections/2:0));++cases;
 }
}
int main(void){@CHECKS@printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;}
'''.replace('@MACROS@', macros).replace('@KERNELS@', kernels).replace('@LEGACY@', legacy).replace(
        '@TABLES@', ',\n'.join(tables)).replace('@CORRECTION@', function(source, 'set_color_correction')).replace(
        '@FADE@', function(source, 'fade_out')).replace('@CHECKS@', checks).replace('@SCENARIO_COUNT@', str(len(scenarios)))
