"""Check complete native HUD callers with resolved and missing selection models.

Native records and caller bodies are used. Model lookup/navigation, rendering,
colour services and spawning are bounded observable providers; this is not a
whole model cache, renderer or gameplay acceptance test.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/hud-model-native-baseline.json'


def declarations(core):
    text = core[core.index('#include "openbor.h"'):core.index('void setDrawMethod(')]
    # Preserve native packed globals, replacing unused rendering initializers
    # that otherwise introduce unrelated Mach-O pointer fixups.
    text, count = re.subn(
        r'(?m)^((?:palette_table_function|blend_table_function)\s+'
        r'blending_table_functions(?:16|32)?\[[^\]]+\])\s*=\s*\{[^}]*\};',
        r'\1 = {0};', text)
    if count not in (1, 3):
        raise ValueError('Native raster provider tables required')
    text, count = re.subn(r'(?m)^(s_barstatus\s+[A-Za-z_, \t]+)\s*=\s*'
                         r'(?://[^\n]*\n\s*)?\{[\s\S]*?\};', r'\1 = {0};', text)
    if count not in (3, 4):
        raise ValueError('Native auxiliary bar records required')
    return text


def program(engine, profiles, *, alter_lookup=False):
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    original = load_contract_fixture(FIXTURE)['engines'][engine.name]
    providers = {name: 'fixture_' + name for name in (
        'findmodel', 'prevplayermodel', 'nextplayermodel', 'prevplayermodeln',
        'nextplayermodeln', 'nextcolourmap', 'prevcolourmap', 'nextcolourmapn',
        'prevcolourmapn', 'font_printf', 'spriteq_add_sprite', 'spriteq_add_box',
        'getFPS', 'commaprint', 'sound_play_sample', 'spawnplayer',
        'execute_join_script', 'drop_all_enemies', 'execute_timetick_script',
        'model_get_colourmap', 'draw_visual_debug', 'spriteq_get_sprite_count',
        'spriteq_get_sprite_max', 'obor_rush_value', 'Tr')}
    bodies = []
    for label in ('original', 'checked'):
        names = {name: label + '_' + name for name in original}
        for name, baseline in original.items():
            body = baseline if label == 'original' else function(core, name)
            if alter_lookup and label == 'checked' and name == 'updatestatus':
                # A defined valid-input mutation: replace the historical
                # carried-model choice at confirmation with an extra lookup.
                body, count = re.subn(r'(?m)^([ \t]*)if\(\(obor_profile_build >= 3553',
                    r'\1model = findmodel(player[i].name);\n\g<0>', body)
                if count != 1:
                    raise ValueError('One native joining confirmation required')
            bodies.append(rename_identifiers(body, dict(providers, **names)))
    prefix = declarations(core)
    old = engine.name == '3400'
    settings = ('maxplayers[current_set]=target+1;skipselect=&forced_names;'
                if old else 'levelsets=sets;sets[0].maxplayers=target+1;')
    forced = ('forced_names[0][target]="missing";' if old else
              'sets[0].skipselect[target]="missing";' if engine.name == '3741' else
              'strcpy(skipselect[target],"missing");')
    if engine.name == '3741':
        forced = ('if(obor_profile_build<3698)sets[0].skipselect[target]="missing";'
                  'else strcpy(skipselect[target],"missing");')
    update = original.get('updatestatus', original['predrawstatus'])
    clock = ('global_config.counter_speed=100;global_config.game_speed=100;timeleft=9900;'
             if 'global_config.counter_speed' in update else 'timeleft=99*COUNTER_SPEED;')
    clock += '_time=1000;' if re.search(r'\b_time\b', update) else 'time=1000;'
    clock += ('global_config.showgo=0;global_config.cheats=0;global_sample_list.go=-1;'
              if 'global_config.showgo' in update else ('showgo=0;' if re.search(r'\bshowgo\b',update) else '')+'SAMPLE_GO=-1;creditscheat=0;')
    if 'is_total_timeover' in update:
        clock += 'is_total_timeover=0;'
    if 'screen_status' in update:
        clock += 'screen_status=0;'
    call = lambda label: (label+'_predrawstatus();' if old else
                          label+'_updatestatus();'+label+'_predrawstatus();')
    values = dict(CONFIG='#include "config.h"' if (engine/'config.h').is_file() else '',
        DECLARATIONS=prefix,
        SAVEDATA='' if re.search(r'(?m)^s_savedata\s+savedata\s*;', prefix) else 's_savedata savedata;',
        SET_STORAGE='' if old else 'static s_set_entry sets[2];',
        FORCED_STORAGE='static char *forced_names[MAX_DIFFICULTIES][MAX_PLAYERS];' if old else '',
        CLEAR_SET='memset(forced_names,0,sizeof(forced_names));' if old else
                  'memset(sets,0,sizeof(sets));memset(skipselect,0,sizeof(skipselect));',
        SETTINGS=settings, FORCED=forced,
        OLD_SAMEPLAYER='sameplayer=same;' if 'sameplayer' in original.get('updatestatus',original['predrawstatus']) else '(void)same;',
        CLOCK_SETUP=clock,
        CALL_ORIGINAL=call('original'), CALL_CHECKED=call('checked'),
        ROUTINES='\n'.join(bodies),
        MODEL_TYPE='TYPE_PLAYER',
        COLOUR_STORAGE=('for(int j=0;j<4;++j)fixture_models[i].colourmap[j]=fixture_maps[j];'
            if re.search(r'unsigned char\s*\*\s*colourmap\s*\[',(engine/'openbor.h').read_text(encoding='latin1'))
            else 'fixture_models[i].colourmap=fixture_maps;'),
        HEALTH='fixture_entities[0].'+re.search(r'player\[i\]\.ent->([a-z_.]*health\w*)',original['predrawstatus'])[1]+'=100;',
        DISPLAY_DECL=('#define fixture_display_state timetoshow' if re.search(r'\btimetoshow\b',prefix) else
                      'static int fixture_display_state;'),
        PROFILES=','.join(str(int(p.get('revision',p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE/'hud_model_inputs.c.in').read_text()
    for key,value in values.items():
        text=text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved HUD fixture input')
    return text


class HudModelInputTests(unittest.TestCase):
    def check_callers(self, *, energy_record):
        pin=json.loads((ROOT/'src/pin.json').read_text())
        for row in pin['engines']:
            engine=ROOT/'src/engines'/row['build']
            original=load_contract_fixture(FIXTURE)['engines'][engine.name]['predrawstatus']
            if ('energy_status.' in original or 'energy_state.' in original)!=energy_record:
                continue
            profiles=[p for p in pin['profiles'] if p['engine']==engine.name]
            with self.subTest(engine=engine.name):
                result=run_native(engine,program(engine,profiles))
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                value=json.loads(result.stdout)
                self.assertEqual(value['profiles'],len(profiles))
                self.assertEqual(value,dict(status='PASS',profiles=len(profiles),cases=210*len(profiles)))

    def test_classic_callers_keep_valid_state_and_defined_missing_model_results(self):
        self.check_callers(energy_record=False)

    def test_energy_record_callers_keep_valid_state_and_defined_missing_model_results(self):
        self.check_callers(energy_record=True)

    def test_extra_lookup_breaks_defined_carried_model_equivalence(self):
        pin=json.loads((ROOT/'src/pin.json').read_text())
        engine=ROOT/'src/engines/3741'
        profile=next(p for p in pin['profiles'] if int(p.get('revision',p['build'].split('-')[0]))==3552)
        result=run_native(engine,program(engine,[profile],alter_lookup=True))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('valid native HUD observations',result.stderr)
        self.assertNotIn('runtime error:',result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer',result.stderr)


if __name__=='__main__':
    unittest.main()
