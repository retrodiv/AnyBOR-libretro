"""Check source-owned mixer sums, positions, volume caps and sample IDs.

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
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-audio-mixer-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/gamelib/soundmix.c').read_text()
    wanted = ('channelstruct', 'samplestruct', 's_soundcache', 's_sound_parameters', 's_audio_global')
    typedefs = {m[1]: m[0] for m in re.finditer(
        r'(?ms)^typedef struct(?:\s+\w+)?\s*\{.*?^\}\s*(\w+)\s*;', source) if m[1] in wanted}
    if set(typedefs) != set(wanted):
        raise ValueError('Complete source-owned audio types required')
    globals_ = []
    for declaration in ('s_sound_parameters sound_parameters', 's_audio_global audio_global',
                        'musicchannelstruct musicchannel'):
        match = re.search(r'(?ms)^' + declaration + r'\s*=\s*\{[^}]*\}\s*;', source)
        if match is None:
            raise ValueError('Complete source-owned audio initializer required')
        globals_.append(match[0])
    parts = dict(TYPES='\n'.join(typedefs[name] for name in wanted), GLOBALS='\n'.join(globals_),
        FUNCTIONS='\n'.join(function(source, name) for name in (
            'sound_profile_sample_limit', 'sound_profile_sample_play_id', 'obor_audio_next_sample_id',
            'sound_music_channel_clear', 'sound_reload_sample', 'mixaudio', 'sound_profile_sample_volume_cap', 'sound_play_sample',
            'sound_volume_sample', 'sound_volume_music')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    for key in ('mix_cases', 'play_cases', 'volume_cases'):
        parts[key.upper()] = ','.join('{' + ','.join(str(v) for v in row) + '}' for row in data[key])
    code = Path(__file__).with_name('modern_audio_mixer_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved mixer contract input')
    return code


class ModernAudioMixerContracts(unittest.TestCase):
    def test_original_channel_capacity(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'source/gamelib/soundmix.c').read_text()
        scripts = (engine / 'openborscript.c').read_text()
        _, getters = switch_cases(scripts, 'getsyspropertybyindex', 'index', outermost=True)
        self.assertIn('var->lVal = maxchannels();', getters['SYSTEM_PROPERTY_MAXSOUNDCHANNELS']['body'])
        defines = re.findall(r'(?m)^#define\s+(?:MAX_CHANNELS|SB_BUFFER_SIZE|MIXBUF_SIZE)\s+[^\n]+', source)
        channel = re.search(r'(?ms)^typedef struct\s*\{[^}]+\}\s*channelstruct;', source)[0]
        code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "soundmix.h"
#include "List.h"
#undef assert
#undef malloc
#include <assert.h>

uint32_t obor_profile_build;
@TYPES@
static channelstruct vchannel[MAX_CHANNELS];
static s32 *mixbuf;
static int max_channels, mixing_active, mixing_inited, lists_initialized;
static List samplelist;
#define OBOR_AUDIO_SAMPLE_LIST samplelist

void sound_exit(void)
{
    free(mixbuf);
    mixbuf = NULL;
    mixing_inited = 0;
}

void List_Init(List *list)
{
    assert(list == &samplelist);
    ++lists_initialized;
}

@METHODS@

int main(void)
{
    const unsigned profiles[] = {7369, 7391, 7420, 7473, 7474, 7533, 8023};
    const int requests[] = {0, 1, 2, 63, 64, 65, 128, 255, 256, 257};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int capacity = profiles[i] < 7474 ? 64 : 256;
        assert(maxchannels() == capacity);
        for (size_t j = 0; j < sizeof(requests) / sizeof(*requests); ++j)
        {
            const int request = requests[j];
            const int expected = request > capacity ? capacity : (request < 2 ? 2 : request);
            for (int c = 0; c < MAX_CHANNELS; ++c) vchannel[c].active = 1;
            const int old_lists = lists_initialized;
            mixing_active = 1;
            assert(sound_init(request));
            assert(max_channels == expected && mixing_inited && !mixing_active);
            assert(lists_initialized == old_lists + 1);
            for (int c = 0; c < MAX_CHANNELS; ++c)
            {
                assert(vchannel[c].active == (c >= expected));
            }
        }
    }
    sound_exit();
    return 0;
}
'''
        code = code.replace('@TYPES@', '\n'.join([*defines, channel]))
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in ('maxchannels', 'sound_init')))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_music_and_sample_levels(self):
        controls = [
            (7369, 1.0, 1.0, 64, 512), (7391, 1.0, 1.0, 64, 512), (7406, 1.0, 1.0, 64, 512),
            (7409, 2.0, 2.0, 128, 1024), (7420, 2.0, 2.0, 128, 1024), (7447, 2.0, 2.0, 128, 1024),
            (7452, 2.5, 1.5, 96, 512), (7533, 2.5, 1.5, 96, 512),
        ]
        left, right = 64, 31
        data = {
            'engine': '7533',
            'sources': [{'revision': build} for build, *_ in controls],
            'mix_cases': [[kind, bits, 1, left, right, 100, 0, 0, 48000]
                          for kind, bits in ((0, 8), (0, 16), (1, 16))],
            'play_cases': [[0, 1, 0, 100, 320, 640, 0, 0, 12, 48000]],
            'volume_cases': [[1, 250, 1500]],
        }
        result = json.loads(native_output(program(data), data))
        for row, (build, music_gain, sample_gain, sample_cap, music_cap) in zip(
                result['profiles'], controls, strict=True):
            with self.subTest(build=build):
                self.assertEqual(row['revision'], build)
                self.assertEqual(row['volumes'], [[sample_cap, sample_cap, 250, music_cap]])
                self.assertEqual(row['plays'][0][-1][-2:], [sample_cap, sample_cap])
                for case, raw, gain, offset in (
                    (0, [sample * 256 for sample in (240, 35, 110, 210)], sample_gain, 32768),
                    (1, [32767, 31, -31, 4095], sample_gain, 0),
                    (2, [-32768, -16384, -1001, -1, 0, 1, 1001, 16384], music_gain, 0),
                ):
                    expected = [int(int(sample * channel / 64) * gain - offset)
                                for sample in raw for channel in (left, right)]
                    expected.extend([0] * (32 - len(expected)))
                    self.assertEqual(row['mixes'][case]['blocks'][0]['sums'], expected)

    def test_sound_menu_uses_original_volume_controls(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        menu = function((engine / 'openbor.c').read_text(), 'menu_options_sound')
        code = r'''
#include <stdint.h>
#include <string.h>
#include "openbor.h"
#include "sblaster.h"
#include "soundmix.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
u32 bothnewkeys;
e_screen_status screen_status;
s_level *level;
s_savedata savedata;
s_global_sample global_sample_list = {.beep = -1, .beep_2 = -1};
static const char *selected_labels[2];
static int menu_row, updates, saves, voice_writes, music_writes;

static void capture_label(int row, const char *message, ...)
{
    if ((row == -2 || row == -1) && strcmp(message, "%i"))
    {
        selected_labels[row + 2] = message;
    }
}

#undef Tr
#define Tr(value) (value)
#undef _menutext
#undef _menutextm
#define _menutext(selected, x, row, ...) capture_label(row, __VA_ARGS__)
#define _menutextm(...) ((void)0)

void update(int ingame, int wait)
{
    (void)ingame; (void)wait;
    assert(screen_status & IN_SCREEN_SOUND_OPTIONS_MENU);
    bothnewkeys = updates < menu_row ? FLAG_MOVEDOWN : updates == menu_row ? FLAG_MOVERIGHT : FLAG_ESC;
    ++updates;
}

void savesettings(void) { ++saves; }
void SB_setvolume(char device, char value)
{
    assert(device == SB_VOICEVOL && value == savedata.soundvol);
    ++voice_writes;
}
void sound_volume_music(int left, int right)
{
    assert(left == savedata.musicvol && right == left);
    ++music_writes;
}
int sound_play_sample(int sample, unsigned priority, int left, int right, unsigned speed)
{
    (void)sample; (void)priority; (void)left; (void)right; (void)speed;
    assert(0);
    return 0;
}
int music(char *filename, int loop, long offset) { (void)filename; (void)loop; (void)offset; return 0; }
void sound_close_music(void) { }

@MENU@

int main(void)
{
    static const struct { uint32_t revision; int master_step, step, master, effects, music; } cases[] = {
        {7369, 1, 4, 15, 512, 512}, {7391, 1, 4, 15, 512, 512},
        {7406, 1, 4, 15, 512, 512}, {7409, 1, 5, 15, 120, 240},
        {7420, 1, 5, 15, 120, 240}, {7447, 1, 5, 15, 120, 240},
        {7452, 5, 5, 100, 100, 200}, {7533, 5, 5, 100, 100, 200}
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        obor_profile_build = cases[i].revision;
        const int linked = cases[i].master == 100;
        for (menu_row = 0; menu_row < 3; ++menu_row)
        {
            const int limits[] = {cases[i].master, cases[i].effects, cases[i].music};
            for (int at_limit = 0; at_limit < 2; ++at_limit)
            {
                int levels[] = {3, 6, 9};
                if (at_limit) levels[menu_row] = limits[menu_row] - 1;
                savedata.soundvol = levels[0];
                savedata.effectvol = levels[1];
                savedata.musicvol = levels[2];
                updates = saves = voice_writes = music_writes = 0;
                menu_options_sound();
                levels[menu_row] = at_limit ? limits[menu_row] : levels[menu_row] +
                    (menu_row == 0 ? cases[i].master_step : cases[i].step);
                if (menu_row == 0 && linked) levels[1] = levels[2] = levels[0];
                assert(savedata.soundvol == levels[0] && savedata.effectvol == levels[1] && savedata.musicvol == levels[2]);
                assert(!strcmp(selected_labels[0], linked ? "Master Volume:" : "Sound Volume:"));
                assert(!strcmp(selected_labels[1], linked ? "Effects Volume:" : "SFX Volume:"));
                assert(saves == 1 && voice_writes == (menu_row == 0) && music_writes == (menu_row == 2));
                assert(!(screen_status & IN_SCREEN_SOUND_OPTIONS_MENU) && bothnewkeys == 0);
            }
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@MENU@', menu), {'engine': '7533'}, engine_source=engine), '')

    def test_mixer_sums_fixed_positions_limits_and_counters(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', initial_music_class=7, sizes=[40,24,36], profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
