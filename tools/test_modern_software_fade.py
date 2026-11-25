"""Check the native software fade when host color correction is unavailable.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-software-fade-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    port = Path(os.environ.get('OBOR_TEST_PORT', ROOT / 'src/port/libretro'))
    source = (engine / 'openbor.c').read_text()
    match = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', source)
    if match is None:
        raise ValueError('Native default drawmethod required')
    parts = dict(DEFAULT=source[match.start():source.index('\n};', match.end()) + 3],
        BACKEND=colour_backend((port / 'video.c').read_text()),
        FUNCTIONS='\n'.join(function(source, name) for name in ('set_color_correction', 'fade_out')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_software_fade_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved software fade input')
    return code


def colour_backend(video):
    start = video.index('static unsigned char colour_map[256];')
    end = video.index('#endif', start)
    return video[start:end] + function(video, 'video_set_color_correction')


def colour_program(engine, port):
    video = (port / 'video.c').read_text()
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    code = r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>

enum { PIXEL_8 = 1, PIXEL_16 = 2, PIXEL_32 = 4 };
typedef struct {
    int width, height, pixelformat;
    unsigned char *palette;
    _Alignas(uint32_t) unsigned char data[8];
} s_screen;
static unsigned buffer[2], *fb = buffer, pal32[256];
static const s_screen *state_source;
static struct { int gamma, brightness; } savedata;
static int screenformat = PIXEL_32, pal;
static int ensure_fb(int w, int h) { return w == 2 && h == 1; }
static void palette_set_corrected(int p, int gr, int gg, int gb, int br, int bg, int bb)
{ (void)p; (void)gr; (void)gg; (void)gb; (void)br; (void)bg; (void)bb; }
@BACKEND@
@HOOK@
@CONVERT@

int main(void)
{
    s_screen src = { .width=2, .height=1, .pixelformat=PIXEL_32 };
    const unsigned raw[] = {0x00204080, 0x0000ff00};
    memcpy(src.data, raw, sizeof(raw));
    assert(convert_screen(&src));
    assert(buffer[0] == 0x00804020 && state_source == &src);

    savedata.gamma = 256;
    int supported = set_color_correction(savedata.gamma, 0);
    assert(convert_screen(&src));
#if OBOR_ENGINE_BUILD == 8023
    assert(supported && buffer[0] == 0x00804020 && state_source == &src);
#else
    assert(supported && buffer[0] == 0x00c0703c && state_source == NULL);
    assert(buffer[1] == 0x0000ff00);
    savedata.gamma = -256;
    assert(set_color_correction(savedata.gamma, 0));
    assert(convert_screen(&src) && buffer[0] == 0x00401004);
    savedata.gamma = 0;
    savedata.brightness = 128;
    assert(set_color_correction(0, savedata.brightness));
    assert(convert_screen(&src) && buffer[0] == 0x00c0a090);
    assert(set_color_correction(0, 999));
    assert(convert_screen(&src) && buffer[0] == 0x00ffffff);
    assert(set_color_correction(0, -999));
    assert(convert_screen(&src) && !buffer[0]);
    savedata.brightness = 0;
    assert(!set_color_correction(0, 0));
    assert(convert_screen(&src) && buffer[0] == 0x00804020 && state_source == &src);
#endif
    assert(!memcmp(src.data, raw, sizeof(raw)));
    video_set_color_correction(256, -256);
    src.pixelformat = PIXEL_8;
    src.data[0] = 2;
    pal32[2] = 0x00804020;
    assert(convert_screen(&src) && buffer[0] == 0x00804020 && state_source == &src);
    return 0;
}
"""
    return (code.replace('@BACKEND@', colour_backend(video))
            .replace('@HOOK@', function(source, 'set_color_correction'))
            .replace('@CONVERT@', function(video, 'convert_screen')))


class ModernSoftwareFadeContracts(unittest.TestCase):
    def test_colour_controls_reach_output_pixels_and_exclude_8023(self):
        port = ROOT / 'src/port/libretro'
        for build in ('3400', '3741', '3842', '4086', '4432', '6391', '7142', '7533', '8023'):
            with self.subTest(build=build):
                engine = ROOT / 'src/engines' / build
                result = native_output(colour_program(engine, port), {'engine': build},
                                       engine_source=engine)
                self.assertEqual(result, '')

    def test_native_fade_uses_available_software_path(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
