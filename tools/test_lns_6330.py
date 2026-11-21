"""Compare modified 6330 profile contracts with their own source.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_historical_player import function, rename_identifiers
from test_historical_behavior import native
from test_historical_common_think import native_output
from test_branch_profiles import outer_case
from contract_fixtures import contract_revisions, fixture_path, load_contract_fixture

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_LNS_ENGINE', ROOT / 'src/engines/6391'))
ABI = Path(os.environ.get('OBOR_PROFILE_ABI_HEADER', ROOT / 'src/glue/anybor_abi.h'))
READER_HEADER = Path(os.environ.get('OBOR_LNS_READER_HEADER', ROOT / 'src/port/libretro/anybor_lns_pak.h'))
CONTROL_HEADER = Path(os.environ.get('OBOR_CONTROL_HEADER', ROOT / 'src/port/libretro/control.h'))
CONTROL_SOURCE = Path(os.environ.get('OBOR_CONTROL_SOURCE', CONTROL_HEADER.with_name('control.c')))
FIXTURE = fixture_path(Path(__file__).with_name('fixtures') / 'lns-6330-attack-original.c')
SYSTEMVARIANT_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-6391-systemvariants.json'


def systemvariant_helpers(source):
    names = ('obor_uses_6119_systemvariants', 'obor_systemvariant_6119_native',
             'obor_systemvariant_decimal_value', 'obor_systemvariant_native')
    return '\n'.join(function(source, name) for name in names
                     if name == 'obor_systemvariant_native' or re.search(r'\b' + name + r'\([^()]*\)\s*\{', source))


def systemvariant_tables(source):
    return '\n'.join(re.search(r'static const char \*' + name + r'\[\]\s*=\s*\{[^}]+\};', source)[0]
                     for name in ('svlist', 'obor_svlist6330lns'))


def selected_systemvariant_cases(source, function_name, labels):
    body = function(source, function_name)
    return (body[:body.index('    case ')] + ''.join(outer_case(body, '_sv_' + label) for label in labels)
            + body[body.rfind('    default:'):])


def palette_profile_context(source):
    if 'obor_select_colourmap(' not in source:
        return ''
    ids = (ENGINE / 'source/openborscript/profile_ids.h').read_text()
    return 'static uint32_t obor_profile_build = 6330;\n' + function(ids, 'obor_profile_uses_5134_script_ids')


def profile_keys(header):
    declaration = re.search(r'typedef enum\s*\{[^}]*\bFLAG_ESC\b[^}]+\}\s*e_key_def;', header).group()
    return declaration + '\n' + '\n'.join(re.search(r'^#define ' + name + r'[^\r\n]+', header, re.M).group()
        for name in ('FLAG_ANYBUTTON', 'FLAG_CONTROLKEYS'))


def saved_record_type(source, name):
    return re.search(r'typedef struct\s*\{[^{}]*\}\s*' + name + r'\s*;', source).group()


def saved_record_helpers(source, record, names):
    return ('static uint32_t obor_profile_build;\n'
            + function(source, 'obor_profile_early_save_layout') + '\n'
            + saved_record_type(source, record) + '\n'
            + '\n'.join(function(source, name) for name in names))


def early_score_name_storage(source):
    return re.search(r'(?m)^static char obor_early_score_names\[[^;]+;', source)[0] + '\n'


def profile_id_support(code):
    early = 'obor_profile_uses_5134_script_ids'
    back_rise = 'obor_profile_has_back_rise_animations'
    names = (early, 'obor_profile_has_animation_entity_collision', back_rise,
             'obor_profile_uses_legacy_path_sizes', 'obor_profile_has_checkbase')
    selected = [name for name in names if name + '(' in code]
    if not selected:
        return code
    if back_rise in selected and early not in selected:
        selected.insert(0, early)
    header = (ENGINE / 'source/openborscript/profile_ids.h').read_text()
    return '\n'.join([*(function(header, name) for name in selected), code])


def original_keys(context, code):
    data = json.loads((FIXTURE.parent / 'lns-6330-keys-original.json').read_text())
    row = data['contexts']['physical' if context == 'previous' else context]
    declaration = row['enum']
    names = {name: context + '_' + name for name in set(re.findall(r'\bFLAG_[A-Z0-9_]+\b', declaration))}
    names['e_key_def'] = context + '_key_def'
    return rename_identifiers(declaration + '\n' + code, names)


class Lns6330AttackTests(unittest.TestCase):
    def test_combat_completion_busy_and_incoming_id_callsite_boundaries(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-combat-boundaries-original.json').read_text())
        current = function(source, 'do_attack')
        declarations = re.search(r'typedef enum\s*\{[^{}]*\bATTACKING_INACTIVE\b[^{}]*\}\s*e_attacking_state;', header).group()
        script = function((ENGINE / 'openborscript.c').read_text(), 'openbor_changeentityproperty')
        entity_script = function((ENGINE / 'source/openborscript/entity.c').read_text(), 'openbor_set_entity_property')
        entity_script = re.sub(r'(?m)^    ', '', entity_script)
        candidate_setters = [outer_case(script, '_ep_hitbyid'), outer_case(entity_script, '_ENTITY_ATTACK_ID_INCOMING')]
        code = []
        for key, row in [('candidate', {'do_attack': current}), *data['contexts'].items()]:
            text = row['do_attack']
            prefix = text[:text.index('        attack = lasthit.attack;')] + '    }\n(void)them;\n}\n'
            if key == 'candidate':
                for name in data['contexts']:
                    code.append(prefix.replace('do_attack(', 'candidate_' + name + '_prefix(', 1))
            else:
                self.assertEqual(re.sub(r'\s+', '', row['attacking_enum']), re.sub(r'\s+', '', declarations))
                code.append(prefix.replace('do_attack(', key + '_prefix(', 1))
            match = re.search(r'!self->idling\s*&&\s*(.*?)(?=\)\)\s*&&)', text, re.S)
            self.assertIsNotNone(match)
            code.append('static int ' + key + '_busy(void) {return !self->idling && (' + match[1] + ');}\n')
            start = text.index('        // Attack IDs must be different.')
            history = text[start:text.index('        // Target laying down?', start)]
            code.append('static int ' + key + '_seen(entity *target,int current_attack_id,s_collision_attack *attack) {'
                'for(int once=0;once<1;++once) {' + history + 'return 0;}return 1;}\n')
            writes = re.findall(r'(?m)^\s*(?:self->attack_id_incoming\s*=\s*current_attack_id|'
                r'insert_attack_id_incoming\(self, current_attack_id\)|obor_remember_attack\(self, current_attack_id\));', text)
            self.assertEqual(len(writes), 2)
            code.append('static void ' + key + '_write(unsigned which,int current_attack_id) {'
                'if(which==0){' + writes[0] + '}else{' + writes[1] + '}}\n')
            setters = candidate_setters if key == 'candidate' else [row['setters'][name]['case'] for name in ('legacy', 'entity')]
            code.append('static void ' + key + '_setter(unsigned which,ScriptVariant **varlist) {'
                'entity *ent=self,*handle=self;LONG ltemp,temp_int;if(which==0){switch(1){'
                + setters[0] + '}}else{switch(1){' + setters[1] + '}}}\n')
        history = '\n'.join(function(source, name) for name in ('obor_attack_seen', 'obor_remember_attack'))
        reference = '\n'.join(data['contexts']['lns']['history_functions'].values())
        reference = rename_identifiers(reference, {
            'attack_id_incoming': 'lns_attack_id_incoming', 'attack_id_incoming_index': 'lns_attack_id_incoming_index'})
        # Source-owned history helpers retain their names in the isolated program.
        history = reference + '\n' + history
        program = (FIXTURE.parent / 'lns-6330-combat-boundaries-contract.c.in').read_text()
        includes = (ABI.parent, READER_HEADER.parent, ENGINE, ENGINE / 'source',
            *(p for p in sorted((ENGINE / 'source').iterdir()) if p.is_dir()))
        native(program.replace('@HISTORY@', history).replace('@CODE@', '\n'.join(code)), include_dirs=includes,
            extra_flags=('-DLINUX=1', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=6391', '-O1', '-fcommon',
                '-Wno-unused-variable', '-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-type-limits', '-Wno-misleading-indentation'))

    def test_default_shutdown_version_matches_lns_and_preserves_physical_control(self):
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-version-original.json').read_text())
        start = re.search(r'^#define\s+OBOR_DEFAULT_SHUTDOWN_MESSAGE\b', header, re.M).start()
        stop = re.search(r'^#define\s+COMPATIBLEVERSION\b', header, re.M).start()
        code = header[start:stop]
        row = data['contexts']['lns']
        names = {name:'lns_' + name for name in ('VERSION_MAJOR', 'VERSION_MINOR', 'VERSION_BUILD', 'VERSION', 'DEFAULT_SHUTDOWN_MESSAGE')}
        code += rename_identifiers(row['version_defines'] + '\n' + row['default_shutdown_macro'], names) + '\n'
        for key in ('official', 'physical'):
            text = data['contexts'][key]['default_shutdown_macro']
            code += rename_identifiers(text, {'DEFAULT_SHUTDOWN_MESSAGE': key + '_default'}) + '\n'
        program = r'''#include <assert.h>
#include <stdint.h>
#include <string.h>
#include @ABI@
#include "version.h"
static unsigned obor_profile_features;
@CODE@
int main(void) {
 for(obor_profile_features=0;obor_profile_features<8;++obor_profile_features) {
  const char *actual=DEFAULT_SHUTDOWN_MESSAGE;
  const char *expected=obor_profile_features&OBOR_PROFILE_LNS_6330?lns_DEFAULT_SHUTDOWN_MESSAGE:physical_default;
  assert(!strcmp(actual,expected));
  if(!(obor_profile_features&OBOR_PROFILE_LNS_6330))assert(!strcmp(actual,official_default));
 }
 return 0;
}
'''
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@CODE@', code), include_dirs=(ENGINE,))

    def test_full_audio_mixer_and_native_null_buffer_carryover(self):
        source = (ENGINE / 'source/gamelib/soundmix.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-audio-original.json').read_text())
        types = {name: re.search(r'typedef struct\s*\{[^{}]*\}\s*' + name + ';', source).group()
            for name in ('channelstruct', 'samplestruct', 's_soundcache')}
        code = function(source, 'mixaudio').replace('mixaudio(', 'candidate_mix(', 1)
        max_volume = re.search(r'^#define\s+MAXVOLUME\s+[^\r\n]*', source, re.M).group()
        for key, row in data['contexts'].items():
            for name, declaration in types.items():
                self.assertEqual(re.sub(r'\s+', '', declaration), re.sub(r'\s+', '', row['types'][name]))
            self.assertEqual(re.sub(r'\s+', '', max_volume), re.sub(r'\s+', '', row['max_volume']))
            code += row['function'].replace('mixaudio(', key + '_mix(', 1)
        program = (FIXTURE.parent / 'lns-6330-audio-contract.c.in').read_text()
        native(program.replace('@TYPES@', '\n'.join(types.values()))
            .replace('@MAX_VOLUME@', max_volume).replace('@CODE@', code),
            include_dirs=(ENGINE / 'source/gamelib',))

    def test_loading_progress_cache_hits_and_level_model_arguments_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-ui-original.json').read_text())
        level = function(source, 'load_level')
        models = function(source, 'load_models')
        start = level.index('        case CMD_LEVEL_LOAD:')
        candidate = {
            'progress': [re.search(r'update_loading\(&loadingbg\[0\],[^;]+;', models).group(),
                re.search(r'update_loading\(&loadingbg\[1\],[^;]+;', level).group(),
                re.search(r'update_loading\(&bgPosi,[^;]+;', level).group()],
            'level_load': level[start:level.index('        case CMD_LEVEL_ALPHAMASK:', start)],
            'spawn_item_weapon_calls': re.findall(
                r'tempmodel = load_cached_model\(GET_ARG\(1\), filename,\s+[^;]+;', level)}
        programs = []
        for key, row in [('candidate', candidate), *data['contexts'].items()]:
            self.assertEqual(len(row['progress']), 3)
            self.assertEqual(len(row['spawn_item_weapon_calls']), 3)
            code = '\n'.join(row['progress']) + '\nswitch(CMD_LEVEL_LOAD) {' + row['level_load'] + '}\n'
            code += '\n'.join(row['spawn_item_weapon_calls'])
            if key == 'lns':
                code = rename_identifiers(code, {'load_cached_model': 'reference_load'})
            programs.append('static void ' + key + '_contract(void) {s_model *tempmodel;'
                + code + '\n(void)tempmodel;}')
        program = (FIXTURE.parent / 'lns-6330-loading-ui-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@CODE@', '\n'.join(programs)))

    def test_complete_credits_layout_logo_gate_and_callback_order_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-ui-original.json').read_text())
        macro = re.search(r'^#define _strmidx[^\r\n]*', header, re.M).group()
        code = function(source, 'display_credits').replace('display_credits(', 'candidate_credits(', 1)
        for key, row in data['contexts'].items():
            self.assertEqual(re.sub(r'\s+', '', row['strmidx']), re.sub(r'\s+', '', macro))
            code += original_keys(key, row['functions']['display_credits'].replace(
                'display_credits(', key + '_credits(', 1))
        program = (FIXTURE.parent / 'lns-6330-credits-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@KEYS@', profile_keys(header))
            .replace('@GAME_SPEED@', re.search(r'^#define\s+GAME_SPEED[^\r\n]*', header, re.M).group())
            .replace('@MACRO@', macro).replace('@CODE@', code))

    def test_historical_credits_match_own_source_by_profile(self):
        path = Path(__file__).with_name('fixtures')
        data = load_contract_fixture(path / 'profile-credits-layouts.json')
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        template = (path / 'lns-6330-credits-contract.c.in').read_text()
        harness, separator, _ = template.partition('\nint main(void)')
        self.assertTrue(separator)
        runner = (path / 'historical-credits-runner.c.in').read_text()
        engines = {'4432': Path(os.environ.get('OBOR_CREDITS_ENGINE_4432', ROOT / 'src/engines/4432')),
                   '6391': ENGINE}
        for engine, source_dir in engines.items():
            with self.subTest(engine=engine):
                cases = [row for row in rows if row['engine'] == engine]
                header = (source_dir / 'openbor.h').read_text()
                source = (source_dir / 'openbor.c').read_text()
                macro = re.search(r'^#define _strmidx[^\r\n]*', header, re.M).group()
                speed = re.search(r'^#define\s+GAME_SPEED\s+(\d+)', header, re.M)
                keys = {name: int(value, 16) for name, value in re.findall(
                    r'\b(FLAG_ESC|FLAG_START|FLAG_ATTACK)\s*=\s*(0x[0-9a-fA-F]+)', header)}
                code = [rename_identifiers(function(source, 'display_credits'),
                           {'display_credits': 'candidate_credits', 'time': '_time'})]
                for contract in sorted({row['contract'] for row in cases}):
                    original = data['contracts'][str(contract)]
                    self.assertEqual(re.sub(r'\s+', '', original['strmidx']), re.sub(r'\s+', '', macro))
                    self.assertEqual(original['game_speed'], int(speed[1]))
                    self.assertEqual(original['keys'], keys)
                    code.append(rename_identifiers(original['function'],
                        {'display_credits': 'reference_%d' % contract, 'time': '_time'}))
                records = ',\n'.join('{%du,reference_%d}' % (row['revision'], row['contract']) for row in cases)
                program = (harness.replace('@ABI@', json.dumps(str(ABI))).replace('@KEYS@', '')
                    .replace('@GAME_SPEED@', speed[0]).replace('@MACRO@', macro)
                    .replace('@CODE@', '\n'.join(code)) + '\n' + runner.replace('@RECORDS@', records))
                definitions = ''.join('#define %s %du\n' % (name, value) for name, value in keys.items())
                native(definitions + program)

    def test_complete_scene_escape_dispatch_matches_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text() + '\n' + (ENGINE / 'source/savedata.h').read_text()
        header += '\n' + (ENGINE / 'source/globals.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-ui-original.json').read_text())
        code = function(source, 'playscene').replace('playscene(', 'candidate_scene(', 1)
        if 'scene_media_path(' in code:
            code = ('static uint32_t obor_profile_build = 6330;\n'
                    + profile_id_support(function(source, 'scene_media_path') + code))
        for key, row in data['contexts'].items():
            code += original_keys(key, row['functions']['playscene'].replace('playscene(', key + '_scene(', 1))
        program = (FIXTURE.parent / 'lns-6330-scene-contract.c.in').read_text()
        program = (program.replace('@ABI@', json.dumps(str(ABI)))
            .replace('@KEYS@', profile_keys(header))
            .replace('@LIMITS@', '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
                for name in ('MAX_ARG_LEN', 'MAX_ARG_COUNT', 'MAX_BUFFER_LEN', 'MAX_PLAYERS')))
            .replace('@ARGLIST@', re.search(r'typedef struct ArgList\s*\{[^}]+\}\s*ArgList;', header).group())
            .replace('@ARG_MACROS@', '\n'.join(re.search(r'^#define ' + name + r'[^\r\n]*', header, re.M).group()
                for name in ('GET_ARG', 'GET_INT_ARG')))
            .replace('@PARSER@', function(source, 'ParseArgs')).replace('@CODE@', code))
        for flags in ((), ('-DWEBM=1',)):
            with self.subTest(video_condition=flags):
                native(program, extra_flags=(*flags, '-Wno-unused-variable', '-Wno-unused-function',
                    '-Wno-implicit-fallthrough', '-Wno-misleading-indentation'))

    def test_complete_savelevel_record_and_compatibility_version_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-ui-original.json').read_text())
        code = ('uint32_t obor_profile_build;\n'
                + function(source, 'obor_profile_early_save_layout') + '\n'
                + function(source, 'savelevelinfo').replace('savelevelinfo(', 'candidate_savelevel(', 1))
        version = re.search(r'^#define\s+CV_SAVED_GAME\s+[^\r\n]*', header, re.M).group()
        for key, row in data['contexts'].items():
            self.assertEqual(re.sub(r'\s+', '', row['saved_game_version']), re.sub(r'\s+', '', version))
            code += row['functions']['savelevelinfo'].replace('savelevelinfo(', key + '_savelevel(', 1)
        program = (FIXTURE.parent / 'lns-6330-savelevel-contract.c.in').read_text()
        includes = (ABI.parent, READER_HEADER.parent, ENGINE, ENGINE / 'source',
            *(p for p in sorted((ENGINE / 'source').iterdir()) if p.is_dir()))
        native(program.replace('@CODE@', code), include_dirs=includes,
            extra_flags=('-DLINUX=1', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=6391', '-O1', '-fcommon', '-Wno-sign-compare'))

    def test_palette_rise_item_obstacle_and_display_profile_contracts(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-entity-actions-original.json').read_text())
        names = ('ent_set_colourmap', 'set_riseattack', 'drop_item', 'check_block_obstacle')
        originals = []
        display = []
        for key, row in data['contexts'].items():
            originals.append(rename_identifiers('\n'.join(row['functions'].values()),
                {name:key + '_' + name for name in names}))
            for name, expression in row['display'].items():
                display.append('static int ' + key + '_' + name + '(entity *e) { return ' + expression + '; }')
        text = function(source, 'display_ents')
        sort = re.findall(r'\bif\s*\(([^{};]+)\)\s*\{?\s*sortid\s*=\s*e->owner->sortid\s*\+\s*1\s*;', text)
        mirror = [m for m in re.findall(r'can_mirror\s*=([^;]+);', text) if 'use_mirror' in m]
        self.assertEqual((len(sort), len(mirror)), (1, 1))
        for name, expression in (('sort', sort[0]), ('mirror', mirror[0])):
            display.append('static int candidate_' + name + '(entity *e) { return ' + expression + '; }')
        candidate = rename_identifiers('\n'.join(function(source, name) for name in names),
            {name:'candidate_' + name for name in names})
        display_code = '\n'.join(display)
        candidate = profile_id_support(candidate + display_code)
        program = (FIXTURE.parent / 'lns-6330-entity-actions-contract.c.in').read_text()
        includes = (ABI.parent, READER_HEADER.parent, ENGINE, ENGINE / 'source',
            *(p for p in sorted((ENGINE / 'source').iterdir()) if p.is_dir()))
        native(program.replace('@CANDIDATE@', candidate).replace('@ORIGINAL@', '\n'.join(originals))
            .replace('@DISPLAY@', ''), include_dirs=includes,
            extra_flags=('-DLINUX=1', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=6391', '-O1', '-fcommon',
                '-Wno-unused-variable', '-Wno-unused-parameter', '-Wno-sign-compare'))

    def test_projectile_player_inheritance_and_callback_order_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-projectile-player-original.json').read_text())
        names = ('knife_spawn', 'boomerang_spawn', 'bomb_spawn', 'star_spawn')
        originals = []
        for key, row in data['contexts'].items():
            originals.append(rename_identifiers('\n'.join(row['functions'].values()),
                {name:key + '_' + name for name in names}))
        code = rename_identifiers('\n'.join(function(source, name) for name in names),
            {name:'candidate_' + name for name in names})
        if 'obor_spawn_excludes_player_targets(' in code:
            code = profile_id_support(function(source, 'obor_spawn_excludes_player_targets') + code)
        program = (FIXTURE.parent / 'lns-6330-projectile-player-contract.c.in').read_text()
        includes = (ABI.parent, READER_HEADER.parent, ENGINE, ENGINE / 'source',
            *(p for p in sorted((ENGINE / 'source').iterdir()) if p.is_dir()))
        native(program.replace('@CANDIDATE@', code).replace('@ORIGINAL@', '\n'.join(originals)),
            include_dirs=includes, extra_flags=('-DLINUX=1', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=6391',
                '-O1', '-fcommon', '-Wno-unused-variable', '-Wno-unused-parameter', '-Wno-sign-compare'))

    def test_projectile_ricochet_profile_boundary_matches_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-deflect-original.json').read_text())
        original = '\n'.join(row['function'].replace('projectile_wall_deflect(', key + '_deflect(', 1)
            for key, row in data['contexts'].items())
        candidate = function(source, 'projectile_wall_deflect').replace('projectile_wall_deflect(', 'candidate_deflect(', 1)
        if 'obor_profile_build' in candidate:
            candidate = 'static uint32_t obor_profile_build = 6330;\n' + candidate
        program = (FIXTURE.parent / 'lns-6330-deflect-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@CANDIDATE@', candidate)
            .replace('@ORIGINAL@', original), extra_flags=('-Wno-unused-parameter',))

    def test_movement_epsilon_and_grab_fallback_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-movement-original.json').read_text())
        originals = []
        for key, row in data['contexts'].items():
            originals.append(rename_identifiers('\n'.join(row['functions'].values()),
                {name:key + '_' + name for name in ('testmove', 'adjust_grabposition')}))
        names = ('testmove', 'obor_lns_adjust_grabposition', 'adjust_grabposition')
        code = '\n'.join(function(source, name) for name in names)
        code = rename_identifiers(code, {name:'candidate_' + name for name in names})
        if 'movement_wall_altitude(' in code:
            code = ('static uint32_t obor_profile_build = 6330;\n'
                    + profile_id_support(function(source, 'movement_wall_altitude') + code))
        program = (FIXTURE.parent / 'lns-6330-movement-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@CANDIDATE@', code)
            .replace('@ORIGINAL@', '\n'.join(originals)))

    def test_cached_reader_signedness_seek_and_large_offsets_match_originals(self):
        pack = (ENGINE / 'source/gamelib/packfile.c').read_text()
        cache = (ENGINE / 'source/gamelib/filecache.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-io-original.json').read_text())
        pack_names = ('pak_isvalidhandle', 'update_filecache_vfd', 'pak_rawread',
                      'readpackfileblocking', 'seekPackfileCached', 'pak_getsectors', 'pak_init', 'pak_term')
        fields = ('paksize', 'pak_vfdexists', 'pak_vfdstart', 'pak_vfdsize',
                  'pak_vfdpos', 'pak_vfdreadahead', 'pak_headerstart', 'pak_headersize')
        cache_names = ('filecache_blocksize filecache_blocks max_vfds default_minimum_run_bytes '
            'real_pakfd total_pakblocks filecache filecache_head filecache_pakmap '
            'where_is_this_pakblock_cached cacheblock_mru cacheblock_lastused '
            'cacheblock_mru_counter cacheblock_mark_used vfd_readptr_pakblock '
            'vfd_desired_readahead_blocks vfd_startptr_pakblock vfd_blocks_available '
            'request_read_pakblock filecache_maxcdsectors find_least_useful_cacheblock '
            'get_vfd_blocks_available which_pakblock_to_read last_cacheblock_read '
            'last_pakblock_read filecache_ready pakblock_run_ptr pakblock_run_len '
            'pakblock_run_min filecache_process filecache_readpakblock filecache_setvfd '
            'filecache_term filecache_init filecache_wait_for_prebuffer').split()
        def body(pack_source, cache_source):
            declarations = '\n'.join(re.search(r'^static [^;\r\n]*\b' + name + r'(?:\[[^]]+\])?[^;\r\n]*;',
                pack_source, re.M).group() for name in fields)
            # Includes are supplied by the harness; platform branches and all
            # original cache function bodies and declarations stay intact.
            cache_source = re.sub(r'^#include[^\r\n]*', '', cache_source, flags=re.M)
            return ('#define MAXPACKHANDLES 8\n#define CACHEBLOCKSIZE 32768\n'
                + '#define CACHEBLOCKS 96\n#define PACKMAGIC 0x4B434150\n#define PACKVERSION 0\n'
                + cache_source + '\nint pakfd;\n' + declarations + '\n'
                + 'static int pak_initialized;static unsigned char *pak_cdheader,*pak_header;\n'
                + 'char packfile[1];\n'
                + 'static int (*pOpenPackfile)(const char *,const char *);\n'
                + 'static int (*pReadPackfile)(int,void *,int);\n'
                + 'static int (*pSeekPackfile)(int,int,int);static int (*pClosePackfile)(int);\n'
                + 'int openPackfileCached(const char *a,const char *b) { return -1; }\n'
                + 'int readPackfileCached(int a,void *b,int c) { return -1; }\n'
                + 'int closePackfileCached(int a) { return -1; }\n'
                + 'int seekPackfileCached(int,int,int);int isRawData(void) { return 0; }\n'
                + '\n'.join(function(pack_source, name) for name in pack_names))
        candidate = body(pack, cache)
        for key, row in data['contexts'].items():
            with self.subTest(original=key):
                original = body(row['sources']['packfile.c'], row['sources']['filecache.c'])
                names = {name:'original_' + name for name in [*fields, *pack_names, *cache_names, 'pakfd',
                    'pak_initialized', 'pak_cdheader', 'pak_header', 'packfile',
                    'pOpenPackfile', 'pReadPackfile', 'pSeekPackfile', 'pClosePackfile',
                    'openPackfileCached', 'readPackfileCached', 'closePackfileCached', 'isRawData']}
                original = rename_identifiers(original, names)
                program = (FIXTURE.parent / 'lns-6330-io-contract.c.in').read_text()
                stubs = ''
                if key == 'lns':
                    # This contract compares the original PACK0 cache. The
                    # separate multipart backend has its own native controls.
                    stubs += ('int obor_multipart_init(const char *p) { return 0; }\n'
                              'int obor_multipart_active(void) { return 0; }\n'
                              'void obor_multipart_term(void) { abort(); }\n')
                if key != 'lns':
                    for name, args in (
                        ('filecache_process', 'void'), ('filecache_term', 'void'),
                        ('filecache_setvfd', 'unsigned int a,unsigned int b,unsigned int c,unsigned int d'),
                        ('filecache_init', 'int a,unsigned int b,unsigned int c,unsigned char d,unsigned int e'),
                        ('filecache_wait_for_prebuffer', 'unsigned int a,unsigned int b')):
                        stubs += 'void obor_lns_' + name + '(' + args + ') { abort(); }\n'
                    stubs += 'int obor_lns_pak_init(void) { abort(); }\nvoid obor_lns_pak_term(void) { abort(); }\n'
                    stubs += ('int obor_lns_filecache_readpakblock(unsigned char *a,unsigned int b,'
                              'int c,int d,int e) { abort(); }\n')
                program = (program.replace('@ABI@', json.dumps(str(ABI)))
                    .replace('@READER_HEADER@', json.dumps(str(READER_HEADER)))
                    .replace('@VARIANT@', ('#define OBOR_LNS_PAK_IMPL 1\n#include ' + json.dumps(str(READER_HEADER.with_name('anybor_pak_multipart.h')))) if key == 'lns' else '')
                    .replace('@CANDIDATE@', candidate).replace('@ORIGINAL@', original)
                    .replace('@STUBS@', stubs).replace('@SIZE_COUNT@', '6' if key == 'lns' else '2'))
                native(program, include_dirs=(ABI.parent,), extra_flags=(
                    '-DLINUX=1', '-Wno-sign-compare', '-Wno-type-limits', '-Wno-unused-parameter'))

    def test_default_key_fallback_context_and_virtual_routing_match_original(self):
        source = (ENGINE / 'openbor.c').read_text()
        control = CONTROL_SOURCE.read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-default-keys-original.json').read_text())
        previous = data['previous_backend']['function']
        at = previous.index('        pcontrols->kb_break = 0;')
        fallback = rename_identifiers(data['original_fallback'], {'allow_default_keys': 'reference_allow_default_keys'})
        normalized = previous[:at] + ('#if OBOR_ENGINE_BUILD == 6391\n'
            '        if(obor_profile_features & OBOR_PROFILE_LNS_6330) {\n'
            '            unsigned i;int t;unsigned char *keystate_def=reference_keys;\n'
            + fallback + '        }\n#endif\n') + previous[at:]
        normalized = normalized.replace('control_update(', 'reference_control_update(', 1)
        helper = ('uint32_t obor_profile_build;\n'
                  + function(source, 'allow_default_keys').replace('allow_default_keys(', 'candidate_allowed(', 1))
        helper += data['original_helper'].replace('allow_default_keys(', 'original_allowed(', 1)
        start = control.index('void control_update(s_playercontrols **playercontrols, int numplayers)')
        methods = '\n'.join(function(control, name) for name in ('flag_to_index', 'control_setkey', 'key_down'))
        methods += function(control[start:], 'control_update')
        program = (FIXTURE.parent / 'lns-6330-default-keys-contract.c.in').read_text()
        program = (program.replace('@ABI@', json.dumps(str(ABI)))
            .replace('@CONTROL_HEADER@', json.dumps(str(CONTROL_HEADER)))
            .replace('@HELPERS@', helper).replace('@FUNCTIONS@', methods).replace('@REFERENCE@', normalized))
        for build in (6391, 7142):
            with self.subTest(physical_backend=build):
                native(program, include_dirs=(CONTROL_HEADER.parent, ENGINE / 'source/gamelib'),
                    extra_flags=('-DLINUX=1', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + str(build)))

    def test_option_submenu_dispatch_and_return_policies_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        savedata = (ENGINE / 'source/savedata.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-options-original.json').read_text())
        names = ('menu_options_input', 'menu_options_sound', 'menu_options_config',
            'menu_options_debug', 'menu_options_system', 'menu_options_video')
        macros = {name:re.search(r'^#define ' + name + r'\([^\r\n]+', header, re.M).group()
            for name in ('_strmidx', '_colx', '_liney', '_menutextm', '_menutext')}
        originals = []
        for key, row in data['contexts'].items():
            for name, value in row['macros'].items():
                self.assertEqual(re.sub(r'\s+', '', value), re.sub(r'\s+', '', macros[name]))
            code = '\n'.join(row['functions'][name].replace(name + '(', key + '_' + name + '(', 1) for name in names)
            code += 'static void ' + key + '_choose_title(void) {' + row['choose_title'] + '}\n'
            originals.append(original_keys(key, code))
        candidate = '\n'.join(function(source, name).replace(name + '(', 'candidate_' + name + '(', 1) for name in names)
        title = re.search(r'_menutextm\(2,[^\n]+Tr\("Choose Mode"\)[^\n]*;', function(source, 'choose_mode')).group()
        candidate += 'static void candidate_choose_title(void) {' + title + '}\n'
        limits = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]+', savedata, re.M).group()
            for name in ('MAX_PLAYERS', 'MAX_BTN_NUM'))
        candidate = profile_id_support(candidate)
        program = (FIXTURE.parent / 'lns-6330-options-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', limits)
            .replace('@KEYS@', profile_keys(header)).replace('@RECORD@', re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', savedata).group())
            .replace('@MACROS@', '\n'.join(macros.values())).replace('@CANDIDATE@', candidate)
            .replace('@ORIGINALS@', '\n'.join(originals)), extra_flags=('-Wno-sign-compare', '-DLINUX=1', '-DLIBRETRO=1'))

    def test_key_slots_defaults_control_bindings_and_keyboard_labels_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        savedata = (ENGINE / 'source/savedata.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-key-slots-original.json').read_text())
        slot_enum = re.search(r'typedef enum\s*\{[^}]*\bSDID_MOVEUP\b[^}]+\}\s*e_key_id;', header).group()
        keys = profile_keys(header) + '\n' + slot_enum
        keys += '\n' + '\n'.join(re.search(r'^#define ' + name + r'[^\r\n]+', header, re.M).group()
            for name in ('SDID_ATTACK2', 'SDID_ATTACK3', 'SDID_ATTACK4', 'SDID_JUMP', 'SDID_SPECIAL'))
        macros = {name:re.search(r'^#define ' + name + r'\([^\r\n]+', header, re.M).group()
            for name in ('_strmidx', '_liney', '_menutextm')}
        limits = {name:re.search(r'^#define\s+' + name + r'[^\r\n]+', savedata, re.M).group()
            for name in ('MAX_PLAYERS', 'MAX_BTN_NUM')}

        def keyboard_fragments(text, prefix):
            body = function(text, 'keyboard_setup')
            start = body.index('    strcpy(buttonnames[SDID_MOVEUP]')
            labels = body[start:body.index('    savesettings();', start)]
            title = re.search(r'_menutextm\(2,[^\n]+Tr\("Player %i"\)[^\n]+;', body).group()
            return ('static void ' + prefix + '_labels(char buttonnames[MAX_BTN_NUM][32]) {' + labels + '}\n'
                + 'static void ' + prefix + '_title(int player) {' + title + '}\n')

        originals = []
        names = ('clearbuttons', 'apply_controls', 'translate_SDID')
        for key, row in data['contexts'].items():
            for name, value in row['limits'].items():
                self.assertEqual(re.search(r'\s(\d+)', value).group(1), re.search(r'\s(\d+)', limits[name]).group(1))
            for name, value in row['macros'].items():
                self.assertEqual(re.sub(r'\s+', '', value), re.sub(r'\s+', '', macros[name]))
            code = row['enum'] + '\n' + '\n'.join(row['functions'][name] for name in names)
            code += keyboard_fragments(row['functions']['keyboard_setup'], key)
            mapping = {name:key + '_' + name for name in set(re.findall(r'\bSDID_[A-Z0-9_]+\b', row['enum']))}
            mapping.update({name:key + '_' + name for name in names})
            mapping['e_key_id'] = key + '_key_id'
            originals.append(original_keys(key, rename_identifiers(code, mapping)))
        candidate = ('#include <stdbool.h>\nstatic uint32_t obor_profile_build;\n'
            + '\n'.join(function(source, name) for name in names) + keyboard_fragments(source, 'candidate'))
        # Use the port's real virtual key definitions while observing calls;
        # this does not claim the original platform's physical keyboard codes.
        control = '\n'.join(line for line in CONTROL_HEADER.read_text().splitlines()
            if re.match(r'^#define (?:OBOR_KEY(?:BASE|SPAN)?\b|CONTROL_ESC\b|CONTROL_DEFAULT[1-4]_)', line))
        program = (FIXTURE.parent / 'lns-6330-key-slots-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@KEYS@', keys)
            .replace('@LIMITS@', '\n'.join(limits.values())).replace('@CONTROL@', control)
            .replace('@MACROS@', '\n'.join(macros.values())).replace('@CANDIDATE@', candidate)
            .replace('@ORIGINALS@', '\n'.join(originals)), extra_flags=('-Wno-sign-compare',))

    def test_6391_early_control_reset_settings_and_rumble(self):
        source = (ENGINE / 'openbor.c').read_text()
        main_header = (ENGINE / 'openbor.h').read_text()
        savedata = (ENGINE / 'source/savedata.h').read_text()
        data = load_contract_fixture(Path(__file__).with_name('fixtures') / 'profile-6391-early-controls.json')
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        contracts, cases = [], []
        for row in rows:
            revision = row['revision']
            original = data['contracts'][row['contract']]
            record = f'savedata_{revision}'
            contracts.append(rename_identifiers(original['settings'], {'s_savedata': record}))
            contracts.append(f'static {record} original_{revision};')
            contracts.append(rename_identifiers(original['reset'], {'savedata': f'original_{revision}',
                'clearbuttons': f'clearbuttons_{revision}'}))
            seed_rumble = (f'original_{revision}.joyrumble[p] = 1;' if row['has_haptics'] else '(void)p;')
            cases.append(f'CHECK_CONTROLS({revision}, {int(row["has_haptics"])}, '
                         f'{int(row["has_rumble_output"])}, {int(row["resets_rumble"])}, '
                         f'{int(row["has_default_keyboard"])}, {seed_rumble});')
        limits = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', savedata, re.M)[0]
                           for name in ('MAX_PLAYERS', 'MAX_BTN_NUM'))
        identifiers = re.search(r'typedef enum\s*\{[^{}]*\bSDID_MOVEUP\b[^{}]*\}\s*e_key_id;', main_header)[0]
        keys = identifiers + '\n' + profile_keys(main_header) + '\n' + '\n'.join(
            re.search(r'^#define ' + name + r'[^\r\n]*', main_header, re.M)[0]
            for name in ('SDID_ATTACK2', 'SDID_ATTACK3', 'SDID_ATTACK4', 'SDID_JUMP', 'SDID_SPECIAL'))
        control_codes = '\n'.join(line for line in CONTROL_HEADER.read_text().splitlines()
            if re.match(r'^#define (?:OBOR_KEY(?:BASE|SPAN)?\b|CONTROL_ESC\b|CONTROL_DEFAULT[1-4]_)', line))
        overlay = CONTROL_SOURCE.read_text()
        input_code = overlay[overlay.index('static int flag_to_index('):]
        rumble = overlay[overlay.rindex('void obor_get_rumble('):]
        callers = ('check_gravity', 'checkhitscore', 'common_takedamage', 'player_die',
                   'bike_crash', 'obstacle_takedamage')
        events = [line.strip() for name in callers for line in function(source, name).splitlines()
                  if 'control_rumble(' in line]
        self.assertEqual(len(events), 8)
        values = {
            'ABI': json.dumps(str(ABI)), 'LIMITS': limits, 'KEYS': keys, 'CONTROL_CODES': control_codes,
            'RECORD': saved_record_type(savedata, 's_savedata'), 'ORIGINALS': '\n'.join(contracts),
            'METHODS': '\n'.join(function(source, name) for name in ('clearbuttons',
                'obor_profile_settings_bytes', 'obor_profile_settings_io',
                'obor_profile_read_settings', 'obor_profile_write_settings')),
            'BACKEND': (function(input_code, 'key_down') + function(input_code, 'control_update')
                        + function(rumble, 'obor_get_rumble') + function(rumble, 'control_rumble')),
            'EVENTS': '\n'.join(line + f'\n    check_event(port, enabled, durations[{i}]);'
                                for i, line in enumerate(events)),
            'TESTS': '\n'.join(cases),
        }
        template = (Path(__file__).with_name('fixtures') / 'early-controls-contract.c.in').read_text()
        native(re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template),
               extra_flags=('-DSDL=1', '-DOBOR_ENGINE_BUILD=6391'))

    def test_6391_android_settings_records(self):
        source = (ENGINE / 'openbor.c').read_text()
        savedata = (ENGINE / 'source/savedata.h').read_text()
        data = load_contract_fixture(Path(__file__).with_name('fixtures') / 'profile-6391-early-controls.json')
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        records = []
        for row in rows:
            record = data['contracts'][row['contract']]['settings']
            records.append(rename_identifiers(record, {'s_savedata': f'savedata_{row["revision"]}'}))
        parts = {
            'ABI': json.dumps(str(ABI)),
            'LIMITS': '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', savedata, re.M)[0]
                                for name in ('MAX_PLAYERS', 'MAX_BTN_NUM')),
            'RECORD': saved_record_type(savedata, 's_savedata'),
            'ORIGINALS': '\n'.join(records),
            'METHODS': '\n'.join(function(source, name) for name in ('obor_profile_settings_bytes',
                'obor_profile_settings_io', 'obor_profile_read_settings', 'obor_profile_write_settings')),
            'TESTS': '\n    '.join(f'check({revision}u, sizeof(savedata_{revision}));' for revision in revisions),
        }
        template = (Path(__file__).with_name('fixtures') / 'android-settings-layout-contract.c.in').read_text()
        native(re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template),
               extra_flags=('-DANDROID=1', '-DSDL=1'))

    def test_6391_live_input_widths(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        script = (ENGINE / 'openborscript.c').read_text()
        data = load_contract_fixture(Path(__file__).with_name('fixtures') / 'profile-6391-live-input.json')
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        setter = function(script, 'openbor_changeplayerproperty')
        properties = ('disablekeys', 'playkeys', 'keys', 'newkeys', 'releasekeys')
        control = CONTROL_SOURCE.read_text()
        control = control[control.index('static int flag_to_index('):]
        native_player_fields = '\n'.join(re.search(r'(?m)^\s*u64\s+' + name + r';', header)[0].strip()
            for name in (*properties, 'prevkeys'))
        parts = {
            'ABI': json.dumps(str(ABI)),
            'FLAGS': profile_keys(header),
            'CODES': '\n'.join(line for line in CONTROL_HEADER.read_text().splitlines()
                if re.match(r'^#define (?:OBOR_KEY(?:BASE|SPAN)?\b|JOY_MAX_INPUTS\b)', line)),
            'PLAYER_FIELDS': native_player_fields,
            'COMBO_HISTORY': re.search(r'(?m)^\s*u(?:32|64) combokey\[MAX_SPECIAL_INPUTS\];', header)[0].strip(),
            'METHODS': '\n'.join(function(control, name) for name in ('key_down', 'control_update'))
                + '\n'.join(function(source, name) for name in ('inputrefresh', 'player_check_special', 'match_combo')),
            'PROFILE_WIDTH': re.search(r'(?m)^\s*const bool early_input_masks = [^;]+;', setter)[0],
            'SETTERS': '\n'.join(outer_case(setter, '_pp_' + name) for name in properties),
            'COMBO_SETTER': outer_case(setter, '_pp_combokey'),
            'PROFILES': ',\n'.join(f'{{{row["revision"]}u, {row["key_width"]}u, {row["combo_width"]}u}}'
                                  for row in rows),
        }
        template = (Path(__file__).with_name('fixtures') / 'live-input-contract.c.in').read_text()
        native(re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template),
               extra_flags=('-DOBOR_ENGINE_BUILD=6391',))

    def test_composite_key_masks_match_each_original_and_script_binding(self):
        header = (ENGINE / 'openbor.h').read_text()
        constants = (ENGINE / 'source/openborscript/constants.c').read_text()
        self.assertIn('ICMPCONST(FLAG_ANYBUTTON)', constants)
        originals = '\n'.join(original_keys(key, '') for key in ('official', 'physical', 'lns'))
        native(r'''#include <assert.h>
#include <stdint.h>
#include @ABI@
static uint32_t obor_profile_features;
@KEYS@
@ORIGINALS@
int main(void) {
 for(unsigned feature=0;feature<8;++feature) {
  obor_profile_features=feature;
  uint32_t any=(feature&OBOR_PROFILE_LNS_6330)?lns_FLAG_ANYBUTTON:official_FLAG_ANYBUTTON;
  uint32_t controls=(feature&OBOR_PROFILE_LNS_6330)?lns_FLAG_CONTROLKEYS:official_FLAG_CONTROLKEYS;
  assert((uint32_t)official_FLAG_ANYBUTTON==(uint32_t)physical_FLAG_ANYBUTTON && (uint32_t)official_FLAG_CONTROLKEYS==(uint32_t)physical_FLAG_CONTROLKEYS);
  assert((uint32_t)FLAG_ANYBUTTON==any && (uint32_t)FLAG_CONTROLKEYS==controls);
  for(unsigned keys=0;keys<8192;++keys) {
   assert((keys&FLAG_ANYBUTTON)==(keys&any));
   assert((keys&~FLAG_CONTROLKEYS)==(keys&~controls));
  }
 }
 return 0;
}
'''.replace('@ABI@', json.dumps(str(ABI))).replace('@KEYS@', profile_keys(header))
            .replace('@ORIGINALS@', originals))

    def test_lifebar_colors_defaults_tables_and_bar_boundaries_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-colors-original.json').read_text())
        lns_names = ['empty_transparent', 'color25', 'color50', 'color100', 'color200',
            'color300', 'color400', 'color500', 'color600', 'color700', 'color800']
        names = ['color_black', 'color_white', 'color_red', 'color_orange', 'color_yellow',
            'color_blue', 'color_green', 'color_pink', 'color_purple', 'color_magic',
            'color_magic2', 'shadowcolor', 'shadowalpha', 'shadowopacity', 'colorbars']
        names += ['obor_lns_' + name for name in lns_names]
        aliases = '\n'.join('#define ' + name + ' globals[' + str(i) + ']' for i, name in enumerate(names))
        aliases += '\n#define GLOBAL_COUNT ' + str(len(names))

        def defaults(text, prefix):
            body = function(text, 'load_background')
            start = body.index('    lifebar_colors();')
            return 'static void ' + prefix + '_defaults(void) {' + body[start:body.index('    video_clearscreen();', start)] + '}\n'

        originals = []
        for key, row in data['contexts'].items():
            body = '\n'.join(row['functions'][name] for name in ('lifebar_colors', 'init_colourtable', 'bar'))
            body += defaults(row['functions']['load_background'], key)
            mapping = {name: key + '_' + name for name in ('lifebar_colors', 'init_colourtable', 'bar')}
            if key == 'lns':
                mapping.update({name: 'obor_lns_' + name for name in lns_names})
            originals.append(rename_identifiers(body, mapping))
        candidate = '\n'.join(function(source, name) for name in
            ('obor_lns_lifebar_colors', 'lifebar_colors', 'init_colourtable', 'bar')) + defaults(source, 'candidate')
        enums = '\n'.join(re.search(r'typedef enum\s*\{[^}]*\}\s*' + name + ';', header).group()
            for name in ('e_bar_dir', 'e_barorient', 'e_bartype'))
        record = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_barstatus;', header).group()
        limits = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_ARG_LEN', 'MAX_ARG_COUNT', 'GET_ARG', 'GET_INT_ARG'))
        parser = (function(source, 'isNumeric') + function(source, 'getValidInt') + function(source, 'ParseArgs')
            + function((ENGINE / 'source/utils.c').read_text(), 'getNewLineStart'))
        program = (FIXTURE.parent / 'lns-6330-colors-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@GLOBALS@', aliases)
            .replace('@LIMITS@', limits).replace('@ENUMS@', enums).replace('@BAR_RECORD@', record)
            .replace('@ARGLIST@', re.search(r'typedef struct ArgList\s*\{[^}]+\}\s*ArgList;', header).group())
            .replace('@PARSER@', parser).replace('@CANDIDATE@', candidate).replace('@ORIGINALS@', '\n'.join(originals)),
            extra_flags=('-Wno-sign-compare', '-Wno-implicit-fallthrough'))

    def test_game_restore_selection_completion_and_cleanup_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text() + '\n' + (ENGINE / 'source/savedata.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-playgame-original.json').read_text())

        def fragments(text, prefix):
            body = function(text, 'playgame')
            start = body.index('    if(useSavedGame == 1 && save->flag)')
            resume = body[start:body.index('    nosave = 1;', start)]
            resume = re.sub(r'\breturn;', 'return 0;', resume)
            start = body.index('                set->noselect = 0;')
            selection = body[start:body.index('            else if(le->type == LE_TYPE_SKIP_SELECT)', start)]
            selection = selection[:selection.rfind('            }')]
            start = body.rindex('        if(current_level >= set->numlevels)')
            complete = body[start:body.index('\n    }\n\nendgame:', start)]
            start = body.index('    // clear global script variant list')
            cleanup = body[start:body.rfind('}')]
            return ('static int ' + prefix + '_resume(int useSavedGame,Set *set,Save *save,int *players) {int i;'
                + resume + 'return 1;}\nstatic int ' + prefix + '_selection(Set *set,Level *le,int *players,int useSavedGame) {'
                + 'int i,continued=0;do {' + selection + 'continued=1;}while(0);return continued;}\n'
                + 'static void ' + prefix + '_completed(Set *set,Save *save) {' + complete + '}\n'
                + 'static void ' + prefix + '_cleanup(void) {' + cleanup + '}\n')
        originals = '\n'.join(fragments(row['function'], key) for key, row in data['contexts'].items())
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_NAME_LEN', 'MAX_PLAYERS'))
        program = (FIXTURE.parent / 'lns-6330-playgame-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
            .replace('@CANDIDATE@', fragments(source, 'candidate')).replace('@ORIGINALS@', originals),
            extra_flags=('-Wno-sign-compare', '-Wno-unused-parameter'))

    def test_saved_menu_finished_version_slot_switch_and_safety_match_source(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text() + '\n' + (ENGINE / 'source/globals.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-saved-menu-original.json').read_text())
        originals = []
        for key, row in data['contexts'].items():
            originals.append(original_keys(key, rename_identifiers(row['function'],
                {'load_saved_game': key + '_load_saved_game', 'getPakName': 'original_getPakName'})))
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_NAME_LEN', 'MAX_BUFFER_LEN', 'CV_SAVED_GAME'))
        names = ('_strmidx', '_colx', '_liney', '_menutextm', '_menutext')
        macros = '\n'.join(re.search(r'^#define ' + name + r'\([^\r\n]+', header, re.M).group() for name in names)
        program = (FIXTURE.parent / 'lns-6330-saved-menu-contract.c.in').read_text()
        ids = (ENGINE / 'source/openborscript/profile_ids.h').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
            .replace('@KEYS@', profile_keys(header))
            .replace('@MACROS@', macros).replace('@CANDIDATE@',
                'static uint32_t obor_profile_build;\n'
                + function(source, 'obor_profile_early_save_layout') + '\n'
                + function(ids, 'obor_profile_uses_legacy_path_sizes') + '\n'
                + function(source, 'load_saved_game'))
            .replace('@ORIGINALS@', '\n'.join(originals)), extra_flags=('-Wno-sign-compare',))

    def test_native_startup_banner_uses_the_modified_source_label_and_format(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-menus-original.json').read_text())
        main = function(source, 'openborMain')
        start = main.index('    printf(')
        banner = main[start:main.index(';', start) + 1]
        self.assertFalse(data['contexts']['lns']['source_version_build_empty'])
        original = rename_identifiers(data['contexts']['lns']['banner'], {'VERSION':'lns_version'})
        native(r'''#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include @ABI@
@VERSION@
static unsigned obor_profile_features;
static char text[256],expected[256];
static const char lns_version[]=@LNS_VERSION@;
static int captured_printf(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(text,sizeof(text),format,args);va_end(args);assert(n>=0 && n<256);return n;
}
#define printf captured_printf
static void candidate(void) {@BANNER@}
static void modified_original(void) {@ORIGINAL@}
static void previous_shared(void) {@PREVIOUS@}
#undef printf
int main(void) {
 for(unsigned flags=0;flags<8;++flags) {
  obor_profile_features=flags;
  memset(text,0,sizeof(text));if(flags&OBOR_PROFILE_LNS_6330)modified_original();else previous_shared();memcpy(expected,text,sizeof(text));
  memset(text,0,sizeof(text));candidate();assert(!memcmp(text,expected,sizeof(text)));
 }
 return 0;
}
'''.replace('@ABI@', json.dumps(str(ABI))).replace('@VERSION@', (ENGINE / 'version.h').read_text())
            .replace('@LNS_VERSION@', json.dumps(data['contexts']['lns']['version_label']))
            .replace('@BANNER@', banner).replace('@ORIGINAL@', original)
            .replace('@PREVIOUS@', data['previous_shared_menu']['banner']))

    def test_native_launch_argument_position_parsing_and_bonus_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-menus-original.json').read_text())
        main = function(source, 'openborMain')
        start = main.index('    if(argc > 1)')
        prefix = main[start:main.index('    modelcmdlist =', start)]
        code = (function(source, 'isNumeric') + function(source, 'getValidInt')
            + 'static void candidate_args(int argc,char **argv) {int argl;' + prefix + '}\n')
        for key, row in data['contexts'].items():
            text = '\n'.join(row['numeric_helpers'].values())
            text += 'static void ' + key + '_args(int argc,char **argv) {int argl;' + row['initial_arguments'] + '}\n'
            code += rename_identifiers(text, {name:key + '_' + name for name in ('isNumeric','getValidInt')})
        program = (FIXTURE.parent / 'lns-6330-arguments-main-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@CODE@', code))

    def test_mode_pagination_and_option_inputs_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-menus-original.json').read_text())
        macros = {name: re.search(r'^#define ' + name + r'\([^\r\n]+', header, re.M).group()
            for name in ('_strmidx', '_colx', '_liney', '_menutextm', '_menutext')}
        originals = []
        for key, row in data['contexts'].items():
            for name, declaration in row['macros'].items():
                self.assertEqual(re.sub(r'\s+', '', macros[name]), re.sub(r'\s+', '', declaration))
            names = {name: key + '_' + name for name in ('menu_difficulty', 'menu_options')}
            originals.append(original_keys(key, rename_identifiers('\n'.join(row['functions'].values()), names)))
        originals.append(original_keys('previous', rename_identifiers(data['previous_shared_menu']['function'],
            {'menu_options': 'previous_menu_options'})))
        candidate = function(source, 'menu_difficulty') + function(source, 'menu_options')
        if 'obor_profile_early_save_layout(' in candidate:
            candidate = ('static uint32_t obor_profile_build = 6330;\n'
                         + function(source, 'obor_profile_early_save_layout') + candidate)
        program = (FIXTURE.parent / 'lns-6330-menus-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
            .replace('@LIMITS@', re.search(r'^#define\s+MAX_NAME_LEN[^\r\n]*', header, re.M).group())
            .replace('@KEYS@', profile_keys(header))
            .replace('@MACROS@', '\n'.join(macros.values()))
            .replace('@CANDIDATE@', candidate)
            .replace('@ORIGINALS@', '\n'.join(originals)), extra_flags=('-Wno-sign-compare',))

    def test_settings_record_suffix_partial_reads_and_defaults_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'source/savedata.h').read_text()
        main_header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-settings-original.json').read_text())
        records, references = [], []
        for key, row in data['contexts'].items():
            for name, declaration in row['limits'].items():
                self.assertEqual(re.search(r'\s(\d+)', declaration).group(1),
                    re.search(r'^#define\s+' + name + r'\s+(\d+)', header, re.M).group(1))
            records.append(rename_identifiers(row['record'], {'s_savedata': key + '_savedata'}))
            text = ('static ' + key + '_savedata ' + key + '_settings;\n'
                + 'static unsigned ' + key + '_button_calls;\n'
                + 'static void ' + key + '_clearbuttons(int p) {'
                + 'assert((unsigned)p==' + key + '_button_calls++ && p<MAX_PLAYERS);'
                + 'for(int j=0;j<MAX_BTN_NUM;++j)' + key + '_settings.keys[p][j]=p*32+j;}\n'
                + '#undef COMPATIBLEVERSION\n' + row['compatible_version'] + '\n')
            names = {'savedata': key + '_settings', 'clearsettings': key + '_clearsettings',
                'clearbuttons': key + '_clearbuttons'}
            text += rename_identifiers(row['functions']['clearsettings'], names)
            for kind, name, verb in [('read', 'loadsettings', 'fread'), ('write', 'savesettings', 'fwrite')]:
                statement = re.search(verb + r'\(&savedata,\s*1,\s*sizeof\(savedata\),\s*handle\);',
                    row['functions'][name]).group()
                text += 'static void ' + key + '_' + kind + '(FILE *handle) {' + rename_identifiers(statement, names) + '}\n'
            references.append(text)
        for name, helper in [('savesettings', 'obor_profile_write_settings'),
                ('saveasdefault', 'obor_profile_write_settings'), ('loadsettings', 'obor_profile_read_settings'),
                ('loadfromdefault', 'obor_profile_read_settings')]:
            self.assertEqual(function(source, name).count(helper + '(handle)'), 1)
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_PLAYERS', 'MAX_BTN_NUM'))
        version = '#undef COMPATIBLEVERSION\n' + re.search(r'^#define\s+COMPATIBLEVERSION[^\r\n]*', main_header, re.M).group()
        program = (FIXTURE.parent / 'lns-6330-settings-contract.c.in').read_text()
        program = (program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
            .replace('@RECORD@', re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savedata;', header).group())
            .replace('@REFERENCE_RECORDS@', '\n'.join(records)).replace('@REFERENCE_CODE@', '\n'.join(references))
            .replace('@VERSION@', version).replace('@DEFAULTS@', function(source, 'clearsettings'))
            .replace('@HELPERS@', '#include <stdbool.h>\n' + '\n'.join(function(source, name) for name in
                ('obor_profile_settings_bytes', 'obor_profile_settings_io',
                 'obor_profile_read_settings', 'obor_profile_write_settings'))))
        # Undefine disabled macros: the own declarations use #if, defaults use #ifdef.
        for flags in [(), ('-DSDL=1',), ('-DANDROID=1',), ('-DSDL=1', '-DANDROID=1'), ('-DRASPBERRY=1',)]:
            with self.subTest(conditions=flags):
                native(program, extra_flags=flags)

    def test_hall_of_fame_ranking_initials_navigation_and_dispatch_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text() + '\n' + (ENGINE / 'source/savedata.h').read_text() + '\n' + (ENGINE / 'source/globals.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-hof-ui-original.json').read_text())
        macros = {name: re.search(r'^#define ' + name + r'\([^\r\n]+', header, re.M).group()
            for name in ('_strmidx', '_colx', '_liney', '_menutextm')}
        originals = []
        for key, row in data['contexts'].items():
            for name, declaration in row['limits'].items():
                self.assertEqual(re.search(r'^#define\s+' + name + r'\s+(\d+)', declaration).group(1),
                    re.search(r'^#define\s+' + name + r'\s+(\d+)', header, re.M).group(1))
            for name, declaration in row['macros'].items():
                self.assertEqual(re.sub(r'\s+', '', macros[name]), re.sub(r'\s+', '', declaration))
            names = {'hallfame': key + '_hallfame', 'CV_HIGH_SCORE': key + '_CV_HIGH_SCORE'}
            order = ['hallfame']
            if key == 'lns':
                order = ['hallfame_add', 'hallfame_show', 'hallfame']
                names.update({name: key + '_' + name for name in order})
            originals.append('#define ' + key + '_CV_HIGH_SCORE ' + row['score_version']['literal'] + '\n'
                + original_keys(key, rename_identifiers('\n'.join(row['functions'][name] for name in order), names)))
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_NAME_LEN', 'MAX_PLAYERS', 'MAX_BUFFER_LEN', 'NUM_INITIALS', 'MAX_DIFFICULTIES', 'CV_HIGH_SCORE', 'GAME_SPEED'))
        candidate = '\n'.join(function(source, name) for name in ('obor_lns_score_name', 'hallfame_add', 'hallfame_show', 'hallfame'))
        if 'startup_asset_path(' in candidate:
            candidate = ('static uint32_t obor_profile_build = 6330;\n'
                         'static void borShutdown(int mode, const char *format, ...) { (void)mode; (void)format; abort(); }\n'
                         + function(source, 'obor_profile_early_save_layout')
                         + function(header, 'obor_profile_name_width')
                         + early_score_name_storage(source)
                         + function(source, 'obor_profile_score_name')
                         + function(source, 'obor_copy_display_name')
                         + profile_id_support(function(source, 'startup_asset_path') + candidate))
        program = (FIXTURE.parent / 'lns-6330-hof-ui-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
            .replace('@KEYS@', profile_keys(header))
            .replace('@RECORD@', re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savescore;', header).group())
            .replace('@ALPHABET@', re.search(r'^char savescore_initials_default\[\d+\] = [^\n]+;', source, re.M).group())
            .replace('@EXPECTED_ALPHABET@', data['contexts']['lns']['alphabet_literal'])
            .replace('@MACROS@', '\n'.join(macros.values()))
            .replace('@CANDIDATE@', candidate).replace('@ORIGINALS@', '\n'.join(originals)),
            extra_flags=('-Wno-sign-compare',))

    def test_score_initialization_occurs_at_its_original_startup_boundary(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-hof-ui-original.json').read_text())
        startup = function(source, 'startup')
        start = startup.index('    ob_inittrans();')
        prefix = startup[start:startup.index('    init_videomodes(', start)]
        order = function(source, 'load_levelorder')
        calls = re.findall(r'^    [^\n]*\binitHighScore\(\);[^\S\n]*$', order, re.M)
        self.assertEqual(len(calls), 1)
        code = 'static void candidate_start(void) {' + prefix + '}\n'
        code += 'static void candidate_order(void) {' + calls[0] + '}\n'
        for key, row in data['contexts'].items():
            code += 'static void ' + key + '_start(void) {' + row['startup_score_prefix'] + '}\n'
            code += 'static void ' + key + '_order(void) {' + row['score_init_before_cleanup'] + '}\n'
        native(r'''#include <assert.h>
#include <string.h>
#include @ABI@
static unsigned obor_profile_features;
static int phase,events[8],count;
static void ob_inittrans(void) {assert(!phase);phase=1;events[count++]=10;}
static void clearSavedGame(void) {assert(phase==1);events[count++]=11;}
static int loadHighScoreFile(void) {assert(phase==1);events[count++]=12;return 1;}
static void initHighScore(void) {assert(phase==2);events[count++]=13;}
@CODE@
int main(void) {
 unsigned masks[]={0,OBOR_PROFILE_ATTACK_HISTORY_FOUR,OBOR_PROFILE_LNS_6330};
 for(unsigned m=0;m<3;++m) {
  obor_profile_features=masks[m];phase=count=0;memset(events,0,sizeof(events));
  if(m==2)lns_start();else if(m==1)physical_start();else official_start();
  phase=2;
  if(m==2)lns_order();else if(m==1)physical_order();else official_order();
  int expected[8],wanted=count;memcpy(expected,events,sizeof(events));
  phase=count=0;memset(events,0,sizeof(events));candidate_start();phase=2;candidate_order();
  assert(count==wanted && !memcmp(events,expected,sizeof(events)));
 }
 return 0;
}
'''.replace('@ABI@', json.dumps(str(ABI))).replace('@CODE@', code))

    def test_hall_of_fame_commands_registration_limits_and_owned_metadata(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        commands = (ENGINE / 'source/openborscript/commands.c').read_text()
        command_header = (ENGINE / 'source/openborscript/commands.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-scores-original.json').read_text())
        for name, value in data['contexts']['lns']['limits'].items():
            self.assertEqual(int(re.search(r'^#define\s+' + name + r'\s+(\d+)', header, re.M).group(1)), value)
        names = {'savescore_modes': 'reference_modes', 'savescore_modes_count': 'reference_modes_count',
            'savescore_difficulty_count': 'reference_difficulty_count', 'savescore_difficulty_names': 'reference_names',
            'savescore_difficulty_variable': 'reference_variable', 'savescore_initials': 'reference_initials',
            'savescore_initials_default': 'reference_default', 'savescore_max_time': 'reference_max',
            'savescore_min_time': 'reference_min', 'savescore_extra_time': 'reference_extra',
            'CV_HIGH_SCORE': 'reference_CV_HIGH_SCORE'}
        enums, registrations = [], [function(commands, 'createLevelOrderCommandList')]
        for key, row in data['contexts'].items():
            ids = set(re.findall(r'\bCMD_LEVELORDER_\w+', row['command_enum']))
            mapping = {name: key + '_' + name for name in ids}
            mapping.update({'levelOrderCommands': key + '_levelOrderCommands',
                'levelOrderCommand': key + '_levelOrderCommand',
                'createLevelOrderCommandList': key + '_createLevelOrderCommandList'})
            enums.append(rename_identifiers(row['command_enum'], mapping))
            registrations.append(rename_identifiers(row['command_registration'], mapping))
        start = source.index('        case CMD_LEVELORDER_HALLFAME:')
        cases = source[start:source.index('        case CMD_LEVELORDER_IFCOMPLETE:', start)]
        start = source.index('// New savescore system')
        globals_text = source[start:source.index('s_savedata savedata;', start)]
        cleanup = function(source, 'unload_levelorder')
        start = cleanup.index('    free(savescore_modes);')
        cleanup = 'int i;\n' + cleanup[start:cleanup.index('    num_difficulties = 0;', start)]
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_NAME_LEN', 'MAX_DIFFICULTIES', 'MAX_ARG_LEN', 'MAX_ARG_COUNT', 'CV_HIGH_SCORE'))
        program = (FIXTURE.parent / 'lns-6330-hof-commands-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
            .replace('@RECORD@', re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savescore;', header).group())
            .replace('@ARGLIST@', re.search(r'typedef struct ArgList\s*\{[^}]+\}\s*ArgList;', header).group())
            .replace('@ENUM@', re.search(r'typedef enum levelOrderCommand\s*\{[^}]+\}\s*levelOrderCommands;', command_header).group())
            .replace('@REFERENCE_ENUMS@', '\n'.join(enums) + '\n#define reference_CV_HIGH_SCORE '
                + data['contexts']['lns']['score_version']['literal']).replace('@PARSER@', function(source, 'ParseArgs'))
            .replace('@GLOBALS@', globals_text).replace('@REFERENCE_GLOBALS@',
                rename_identifiers(data['contexts']['lns']['score_globals'], names)
                    .replace('reference_default[41]', 'reference_default[41] SOURCE_NONSTRING'))
            .replace('@REGISTRATIONS@', '\n'.join(registrations))
            .replace('@CANDIDATE_CASES@', cases).replace('@REFERENCE_CASES@',
                rename_identifiers(data['contexts']['lns']['level_order_cases'], names))
            .replace('@CLEANUP@', cleanup), extra_flags=('-Wno-sign-compare', '-Wno-implicit-fallthrough'))

    def test_high_score_wire_formats_and_complete_record_mode_loading(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text() + '\n' + (ENGINE / 'source/globals.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-scores-original.json').read_text())
        originals, records = [], []
        for key, row in data['contexts'].items():
            records.append(rename_identifiers(row['record'], {'s_savescore': key + '_savescore'}))
            names = {name: key + '_' + name for name in row['functions']}
            names.update({'s_savescore': key + '_savescore',
                'savescore': 'original_score' if key == 'lns' else key + '_score',
                'CV_HIGH_SCORE': key + '_CV_HIGH_SCORE'})
            if key == 'lns':
                names.update({'savescore_modes': 'original_modes', 'savescore_modes_count': 'original_modes_count',
                    'savescore_difficulty_count': 'original_difficulty_count', 'levelsets': 'original_sets'})
            functions = []
            for name in ('clearHighScore', 'saveHighScoreFile', 'loadHighScoreFile',
                         *(['initHighScore'] if key == 'lns' else [])):
                body = row['functions'][name]
                if name == 'initHighScore':
                    body = rename_identifiers(body, {'fread': 'complete_source_read'})
                mapping = dict(names, getPakName='original_getPakName')
                if name == 'initHighScore':
                    del mapping['savescore']
                functions.append(rename_identifiers(body, mapping))
            originals.append('#define ' + key + '_CV_HIGH_SCORE ' + row['score_version']['literal'] + '\n'
                + '\n'.join(functions))
        candidate = early_score_name_storage(source) + saved_record_helpers(
            source, 'obor_early_savescore', ('obor_profile_score_name', 'clearHighScore',
            'obor_profile_early_savescore_io', 'obor_profile_savescore_size', 'initHighScore',
            'saveHighScoreFile', 'loadHighScoreFile'))
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_NAME_LEN', 'MAX_BUFFER_LEN', 'CV_HIGH_SCORE', 'MAX_DIFFICULTIES'))
        prototypes = ('int loadHighScoreFile(void);int lns_loadHighScoreFile(void);'
            'int official_loadHighScoreFile(void);int physical_loadHighScoreFile(void);\n')
        program = (FIXTURE.parent / 'lns-6330-scores-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
            .replace('@RECORD@', re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savescore;', header).group())
            .replace('@ORIGINAL_RECORDS@', '\n'.join(records))
            .replace('@CANDIDATE@', prototypes + candidate).replace('@ORIGINALS@', '\n'.join(originals)),
            extra_flags=('-Wno-sign-compare',))

    def test_selection_file_load_flags_and_saved_command_bounds(self):
        source = (ENGINE / 'openbor.c').read_text()
        original = json.loads((FIXTURE.parent / 'lns-6330-argument-layout-original.json').read_text())
        selection = json.loads((FIXTURE.parent / 'lns-6330-selection-original.json').read_text())

        def load_branch(text):
            text = function(text, 'selectplayer')
            start = text.index('                    tempmodel = findmodel(GET_ARG(1));')
            return text[start:text.index('                    // SAVE', start)]

        references = []
        for key, row in original['contexts'].items():
            branch = load_branch(selection['contexts'][key]['functions']['selectplayer'])
            code = ('static void ' + key + '_file_load(char *input) {'
                    'ArgList arglist;char argbuf[1025];s_model *tempmodel;char *filename="authored",*command;'
                    'ParseArgs(&arglist,input,argbuf);command=GET_ARG(0);(void)command;' + branch + '}\n'
                    + row['load_selection'].replace('load_select_screen_info(', key + '_restore(', 1))
            if key == 'lns':
                code = re.sub(r'\bload_cached_model\(', 'original_load_cached_model(', code)
            references.append(code)
        candidate = ('static void candidate_file_load(char *input) {'
                    'const bool lns=(obor_profile_features&OBOR_PROFILE_LNS_6330)!=0;'
                    'ArgList arglist;char argbuf[1025];s_model *tempmodel;char *filename="authored",*command;'
                    'ParseArgs(&arglist,input,argbuf);command=GET_ARG(0);(void)command;' + load_branch(source) + '}\n'
                    + function(source, 'load_select_screen_info'))
        program = (FIXTURE.parent / 'lns-6330-saved-selection-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@PARSER@', function(source, 'ParseArgs'))
               .replace('@CANDIDATE@', candidate).replace('@ORIGINALS@', '\n'.join(references)),
               extra_flags=('-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-implicit-fallthrough', '-fsigned-char'))

    def test_argument_limits_retained_bytes_and_script_constant_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        constants = (ENGINE / 'source/openborscript/constants.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-argument-layout-original.json').read_text())
        originals = []
        for key, row in data['contexts'].items():
            text = '\n'.join((row['arglist'], row['parse'], row['findarg']))
            text = rename_identifiers(text, {'ArgList': key + '_ArgList',
                'ParseArgs': key + '_ParseArgs', 'findarg': key + '_findarg'})
            originals.append('#undef MAX_ARG_LEN\n#undef MAX_ARG_COUNT\n#define MAX_ARG_LEN '
                + str(row['arg_capacity']) + '\n#define MAX_ARG_COUNT ' + str(row['arg_count']) + '\n' + text)
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
                                 for name in ('MAX_ARG_LEN', 'MAX_ARG_COUNT'))
        program = (FIXTURE.parent / 'lns-6330-arguments-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
               .replace('@RECORD@', re.search(r'typedef struct ArgList\s*\{[^}]+\}\s*ArgList;', header).group())
               .replace('@PARSER@', function(source, 'ParseArgs'))
               .replace('@FINDER@', function(source, 'findarg'))
               .replace('@CONSTANT@', re.search(r'else if\(stricmp\("MAX_ARG_LEN", constname\) == 0\)\s*\{[^}]+\}', constants).group())
               .replace('@ORIGINALS@', '\n'.join(originals)),
               extra_flags=('-Wno-implicit-fallthrough',))

    def test_6391_original_progress_and_high_score_records(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = '\n'.join((ENGINE / name).read_text()
                           for name in ('openbor.h', 'source/savedata.h', 'source/globals.h'))
        fixtures = Path(__file__).with_name('fixtures')
        data = load_contract_fixture(fixtures / 'profile-6391-save-record-boundaries.json')
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        originals = [
            rename_identifiers(record[name], {name: f'{name}_{index}'})
            for index, record in enumerate(data['layouts']) for name in ('s_savelevel', 's_savescore')
        ]
        progress_name = re.findall(r'strncpy\(save->dName,[^;]+;', function(source, 'savelevelinfo'))
        menu_names = re.findall(r'strncpy\(savelevel\[saveslot\]\.dName,[^;]+;',
                                function(source, 'menu_difficulty'))
        self.assertEqual((len(progress_name), len(menu_names)), (1, 2))
        limits = ('MAX_NAME_LEN', 'MAX_ARG_LEN', 'MAX_PLAYERS', 'MAX_ALLOWSELECT_LEN',
                  'MAX_SELECT_LOADS', 'MAX_BUFFER_LEN', 'CV_SAVED_GAME', 'CV_HIGH_SCORE')
        values = {
            'ABI': json.dumps(str(ABI)),
            'LIMITS': '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M)[0]
                                for name in limits),
            'RECORDS': '\n'.join(saved_record_type(header, name) for name in ('s_savelevel', 's_savescore')),
            'ORIGINALS': '\n'.join(originals),
            'LEVEL_IO': saved_record_helpers(source, 'obor_early_savelevel',
                ('obor_profile_early_savelevel_copy', 'obor_profile_early_savelevels_io',
                 'obor_profile_savelevel_size', 'obor_profile_savelevels_io')),
            'SCORE_IO': early_score_name_storage(source) + saved_record_type(source, 'obor_early_savescore') + '\n'
                + '\n'.join(function(source, name) for name in ('obor_profile_score_name', 'clearHighScore',
                    'obor_profile_early_savescore_io', 'obor_profile_savescore_size',
                    'saveHighScoreFile', 'loadHighScoreFile')),
            'PROGRESS_NAME': progress_name[0],
            'MENU_NAME_FIRST': menu_names[0],
            'MENU_NAME_SECOND': menu_names[1],
            'LAYOUT_CHECKS': '\n'.join(f'static void check_layout_{index}(unsigned revision) '
                                       f'{{ CHECK_RECORDS(revision, {index}); }}'
                                       for index in range(len(data['layouts']))),
            'TESTS': '\n'.join(f'check_layout_{row["layout"]}({row["revision"]});\n'
                f'check_difficulty_names({row["revision"]}, {row["progress_name_width"]}, '
                f'{row["menu_name_widths"][0]}, {row["menu_name_widths"][1]});' for row in rows),
        }
        template = (fixtures / 'early-save-records-contract.c.in').read_text()
        native(re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template))

    def test_6391_original_player_and_score_display_names(self):
        fixtures = Path(__file__).with_name('fixtures')
        data = load_contract_fixture(fixtures / 'profile-6391-player-and-score-display.json')
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine_source = (ENGINE / 'openbor.c').read_text(encoding='latin-1')
        script_source = (ENGINE / 'openborscript.c').read_text(encoding='latin-1')
        select = function(engine_source, 'selectplayer')
        hall = function(engine_source, 'hallfame')
        setter = function(script_source, 'openbor_changeplayerproperty')

        def name_copy(body, origin):
            return re.search(r'(?:safe_strncpy|obor_copy_display_name)\(player\[i\]\.name, '
                             + re.escape(origin) + r'(?:, obor_profile_name_width\(\))?\);', body)[0]

        values = {
            'SUPPORT': function((ENGINE / 'source/utils.c').read_text(), 'safe_strncpy')
                + function(engine_source, 'obor_profile_early_save_layout')
                + early_score_name_storage(engine_source)
                + function(engine_source, 'obor_profile_score_name')
                + function(engine_source, 'obor_copy_display_name')
                + function(engine_source, 'clearHighScore'),
            'JOIN_NAME': name_copy(function(engine_source, 'updatestatus'), 'model->name'),
            'SKIP_NAME': name_copy(select, 'skipselect[i]'),
            'SELECT_NAME': name_copy(select, 'example[i]->model->name'),
            'RESTORE_NAME': name_copy(function(engine_source, 'playgame'), 'save->pName[i]'),
            'SAVE_NAME': re.search(r'strncpy\(save->pName\[i\], player\[i\]\.name, MAX_NAME_LEN\);',
                                   function(engine_source, 'savelevelinfo'))[0],
            'SCRIPT_NAME': re.search(r'(?ms)^        if\(!tempstr \|\| strlen\(tempstr\) > obor_profile_name_width\(\)\)'
                                     r'\n.*?^        strcpy\(player\[index\]\.name, tempstr\);', setter)[0],
            'RANKING': re.search(r'(?ms)^    if\(addtoscore\)\n.*?^    \}', hall)[0],
            'DISPLAY': re.search(r'(?ms)^        for\(i = 0; i < 10; i\+\+\)\n.*?^        \}', hall)[0],
            'CASES': '\n    '.join('check(%du, %du, %du);' %
                                   (row['revision'], row['player_name_bytes'], row['score_name_bytes'])
                                   for row in rows),
        }
        template = (fixtures / 'player-score-display-contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        self.assertEqual(native_output(code, data, engine_source=ENGINE),
                         ''.join(f'PASS {revision}\n' for revision in revisions))

    def test_saved_selection_wire_layout_and_partial_reads_match_originals(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text() + '\n' + (ENGINE / 'source/savedata.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-argument-layout-original.json').read_text())
        declarations = '\n'.join(re.search(r'^#define\s+' + name + r'[^\r\n]*', header, re.M).group()
            for name in ('MAX_ARG_LEN', 'MAX_NAME_LEN', 'MAX_PLAYERS', 'MAX_ALLOWSELECT_LEN', 'MAX_SELECT_LOADS'))
        originals = []
        for key, row in data['contexts'].items():
            originals.append('\n'.join('#undef ' + name + '\n#define ' + name + ' ' + str(value)
                for name, value in row['layout_limits'].items()) + '\n'
                + rename_identifiers(row['record'], {'s_savelevel': key + '_savelevel'}))
        program = (Path(__file__).with_name('fixtures') / 'lns-6330-save-layout-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@LIMITS@', declarations)
               .replace('@RECORD@', re.search(r'typedef struct\s*\{[^{}]*\}\s*s_savelevel;', header).group())
               .replace('@HELPERS@', saved_record_helpers(source, 'obor_early_savelevel',
                    ('obor_profile_early_savelevel_copy', 'obor_profile_early_savelevels_io',
                     'obor_profile_savelevel_size', 'obor_profile_savelevels_io')))
               .replace('@ORIGINALS@', '\n'.join(originals)).replace('@RESET_LIMITS@',
                    '\n'.join('#undef ' + name for name in data['contexts']['lns']['layout_limits'])))

    def test_selection_and_continue_input_order_and_initial_player_state(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-selection-original.json').read_text())

        def fragments(text, prefix, candidate=False):
            status = function(text, 'updatestatus')
            status = status[:status.index('    if(dt >= 99)')] + 'observed_dt=dt;\n}\n'
            status = status.replace('void updatestatus()', 'static void ' + prefix + '_status(void)', 1)
            menu = function(text, 'selectplayer')
            start = menu.index('            if(!ready[i])')
            inputs = menu[start:menu.index('            else if(ready[i] == 1)', start)]
            start = menu.index('    for(i = 0; i < set->maxplayers; i++)\n    {\n        if(players[i])',
                               menu.index('    //loadGameFile();'))
            initial = menu[start:menu.index('    _time = 0;', start)]
            lines = '\n'.join(line for line in menu.splitlines() if
                re.search(r'\b(?:memcpy\(player_copy|memset\(player,)', line))
            start = menu.index('    for(i = 0; i < set->maxplayers; i++)')
            restore = menu[start:menu.index('    for(i = 0; i < set->maxplayers; i++)', start + 1)]
            declaration = ('const bool lns=(obor_profile_features&OBOR_PROFILE_LNS_6330)!=0;'
                           if candidate else '')
            code = status + ('static void ' + prefix + '_menu(int i) {' + declaration
                + 'int *players=obor_lns_players;s_set_entry *set=levelsets+current_set;'
                + inputs + '}\nstatic void ' + prefix + '_initial(void) {' + declaration
                + 'int i,*players=obor_lns_players;s_set_entry *set=levelsets+current_set;'
                + initial + '}\nstatic void ' + prefix + '_restore(void) {' + declaration
                + 'int i,*players=obor_lns_players;s_set_entry *set=levelsets+current_set;s_player player_copy[MAX_PLAYERS];'
                + '(void)player_copy;' + lines + '\n' + restore + '}\n')
            if prefix == 'lns':
                code = rename_identifiers(code, {'players': 'obor_lns_players',
                    'load_cached_model': 'original_load_cached_model'})
                # The wrapper already supplies the original function parameter.
                code = code.replace('int *obor_lns_players=obor_lns_players;',
                                    'int *players=obor_lns_players;')
                code = code.replace('int i,*obor_lns_players=obor_lns_players;',
                                    'int i,*players=obor_lns_players;')
            return code

        originals = []
        for key, context in data['contexts'].items():
            originals.append(original_keys(key, fragments('\n'.join(context['functions'].values()), key)))
        program = (FIXTURE.parent / 'lns-6330-selection-input-contract.c.in').read_text()
        palette = palette_profile_context(source)
        if 'obor_profile_has_player_status()' in source:
            ids = (ENGINE / 'source/openborscript/profile_ids.h').read_text()
            palette += '\n' + function(ids, 'obor_profile_has_player_status')
        if 'obor_initial_colourmap(' in source:
            palette += """
static int nextcolourmap(s_model *model, int colour) { assert(0); return -1; }
static int obor_select_colourmap(s_model *model, int colour, int slot,
                                 int (*step)(s_model *, int), int use_default)
{
    assert(0);
    return -1;
}
""" + function(source, 'obor_initial_colourmap')
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@KEYS@', profile_keys(header))
               .replace('@CANDIDATE@', palette + fragments(source, 'candidate', True))
               .replace('@ORIGINALS@', '\n'.join(originals)),
               extra_flags=('-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-sign-compare'))

    def test_selection_models_columns_random_and_allow_lists_match_own_sources(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-selection-original.json').read_text())
        common = ('nextplayermodel', 'nextplayermodeln', 'prevplayermodel', 'prevplayermodeln',
                  'nextcolourmap', 'nextcolourmapn', 'prevcolourmap', 'prevcolourmapn',
                  'reset_playable_list', 'load_playable_list')
        extra = ('nextplayermodelcol', 'nextplayermodelcoln', 'prevplayermodelcol',
                 'prevplayermodelcoln', 'selectrandomplayer', 'selectrandomcolourmap')
        candidate = '\n'.join(function(source, name) for name in
            ('obor_selectable_player', *common, *extra))
        if 'obor_select_colourmap(' in source:
            candidate = palette_profile_context(source) + function(source, 'obor_select_colourmap') + candidate
        originals = []
        for key, context in data['contexts'].items():
            names = common + (extra if key == 'lns' else ())
            namespace = {name: key + '_' + name for name in names}
            if key == 'lns':
                namespace['load_cached_model'] = 'original_load_cached_model'
            originals.append(rename_identifiers('\n'.join(context['functions'][name]
                for name in names), namespace))
        program = (FIXTURE.parent / 'lns-6330-selection-models-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@CANDIDATE@', candidate).replace('@ORIGINALS@', '\n'.join(originals))
               .replace('@PARSER@', function(source, 'ParseArgs')),
               extra_flags=('-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-implicit-fallthrough'))

    def test_model_loading_callers_preserve_metadata_and_unload_semantics(self):
        source = (ENGINE / 'openbor.c').read_text()
        script = (ENGINE / 'openborscript.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-original.json').read_text())
        loader = function(source, 'load_cached_model')
        start = loader.index('            case CMD_MODEL_LOAD:')
        nested = loader[start:loader.index('            case CMD_MODEL_SCORE:', start)]
        loop = function(source, 'load_models')
        start = loop.index('    for(i = 0, pos = 0; i < models_cached; i++)')
        loop = loop[start:loop.index('    printf("\\nLoading models', start)]
        originals = []
        for key, context in data['contexts'].items():
            text = ('static void ' + key + '_nested(void) {char *value,*name="parent";s_model *tempmodel;'
                    'switch(CMD_MODEL_LOAD) {' + context['nested'] + '}}\n'
                    'static void ' + key + '_loop(void) {int i,pos;'
                    + context['model_loop'] + '}\n'
                    + context['script_loadmodel'].replace('openbor_loadmodel(', key + '_openbor_loadmodel(', 1))
            if key == 'lns':
                text = re.sub(r'\bload_cached_model\(', 'original_load_cached_model(', text)
            originals.append(text)
        program = (FIXTURE.parent / 'lns-6330-model-callers-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@NESTED@', nested).replace('@LOOP@', loop)
               .replace('@SCRIPT@', function(script, 'openbor_loadmodel'))
               .replace('@ORIGINALS@', '\n'.join(originals)),
               extra_flags=('-Wno-unused-parameter',))

    def test_model_load_barrier_covers_cache_hits_nested_loads_and_completion(self):
        source = (ENGINE / 'openbor.c').read_text()
        loader = function(source, 'load_cached_model')
        start = loader.index('    const bool lns =')
        prefix = loader[start:loader.index('    cacheindex = get_cached_model_index', start)]
        start = loader.index('    if(!shutdownmessage)')
        complete = loader[start:loader.index('    borShutdown(1, "Fatal Error', start)]
        initializer = re.search(r'^\s*newchar->quickload = quickload;', loader, re.M).group()
        program = (FIXTURE.parent / 'lns-6330-model-barrier-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@REQUEST@', prefix).replace('@COMPLETE@', complete)
               .replace('@INITIALIZER@', initializer)
               .replace('@QUICK_CONSTANT@', re.search(
                    r'^#define OBOR_LNS_QUICK_MODEL .*$', (ENGINE / 'openbor.h').read_text(), re.M).group()),
               extra_flags=('-Wno-unused-variable', '-Wno-unused-parameter'))

    def test_quick_model_filter_matches_original_command_sequences(self):
        source = (ENGINE / 'openbor.c').read_text()
        declaration = (ENGINE / 'source/openborscript/commands.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-original.json').read_text())
        enum = re.search(r'typedef enum modelCommand\s*\{[^}]+\}\s*modelCommands;', declaration).group()
        codes = re.findall(r'\bCMD_MODEL_\w+', enum)
        program = (FIXTURE.parent / 'lns-6330-quick-model-contract.c.in').read_text()
        native(program.replace('@ENUM@', enum).replace('@COMMANDS@', ','.join(codes))
               .replace('@FILTER@', function(source, 'obor_lns_quick_model_skip'))
               .replace('@ORIGINAL@', data['contexts']['lns']['filter']))

    def test_metadata_stops_at_first_type_and_refuses_missing_type(self):
        source = (ENGINE / 'openbor.c').read_text()
        utils = (ENGINE / 'source/utils.c').read_text()
        declaration = (ENGINE / 'source/openborscript/commands.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-original.json').read_text())
        program = (FIXTURE.parent / 'lns-6330-model-metadata-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@ENUM@', re.search(
            r'typedef enum modelCommand\s*\{[^}]+\}\s*modelCommands;', declaration).group())
               .replace('@PARSER@', function(source, 'ParseArgs'))
               .replace('@NEWLINE@', function(utils, 'getNewLineStart'))
               .replace('@CANDIDATE@', function(source, 'preload_cached_model'))
               .replace('@ORIGINAL@', data['contexts']['lns']['metadata'].replace(
                   'preload_cached_model(', 'original_preload_cached_model(', 1)),
               extra_flags=('-Wno-unused-parameter', '-Wno-implicit-fallthrough'))

    def test_lazy_model_resolution_and_player_upgrade_match_original(self):
        source = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-loading-original.json').read_text())
        program = (FIXTURE.parent / 'lns-6330-lazy-model-contract.c.in').read_text()
        spawn = function(source, 'spawn')
        start = spawn.index('    if(obor_profile_features & OBOR_PROFILE_LNS_6330)')
        spawn = spawn[start:spawn.index('    // Be a bit more tolerant...', start)]
        change = function(source, 'set_model_ex')
        start = change.index('    if(obor_profile_features & OBOR_PROFILE_LNS_6330)')
        change = change[start:change.index('    if(!newmodel)', start)]
        player = function(source, 'spawnplayer')
        start = player.index('    index &= 3;')
        player = player[start:player.index('    memset(&p', start)]
        originals = []
        for key, context in data['contexts'].items():
            # Original LNS uses an explicit fourth quickload argument. The
            # provider records it separately from the ordinary three-arg ABI.
            text = ('static s_model *' + key + '_spawn(char *name,int index,s_model *model) {'
                    'int i=0,count_frames=0;s_anim *anim=NULL;(void)i;(void)count_frames;(void)anim;'
                    + context['spawn'] + 'return model;}\n'
                    'static s_model *' + key + '_change(char *modelname,int index,s_model *newmodel) {'
                    + context['change'] + 'return newmodel;}\n'
                    'static void ' + key + '_player(int index) {s_model *model=NULL;(void)model;'
                    + context['player'] + '}\n')
            if key == 'lns':
                text = re.sub(r'\bload_cached_model\(', 'original_load_cached_model(', text)
            originals.append(text)
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@SPAWN_HELPER@', function(source, 'obor_lns_spawn_model'))
               .replace('@CHANGE_HELPER@', function(source, 'obor_lns_changed_model'))
               .replace('@UNLOAD@', function(source, 'unload_model'))
               .replace('@SPAWN@', spawn).replace('@CHANGE@', change).replace('@PLAYER@', player)
               .replace('@ORIGINALS@', '\n'.join(originals))
               .replace('@ORIGINAL_UNLOAD@', data['contexts']['lns']['unload'].replace(
                    'unload_model(', 'original_unload_model(', 1)),
               extra_flags=('-Wno-unused-parameter',))

    def test_save_queries_and_loaded_completion_bonus_match_original(self):
        source = (ENGINE / 'openborscript.c').read_text()
        game = (ENGINE / 'openbor.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-script-original.json').read_text())
        program = (FIXTURE.parent / 'lns-6330-save-query-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@SAVEINFO@', function(source, 'openbor_getsaveinfo'))
               .replace('@LOAD@', function(game, 'loadGameFile'))
               .replace('@ORIGINAL_SAVEINFO@', data['contexts']['lns']['saveinfo'].replace(
                    'openbor_getsaveinfo(', 'lns_openbor_getsaveinfo(', 1))
               .replace('@OFFICIAL_SAVEINFO@', data['contexts']['official']['saveinfo'].replace(
                    'openbor_getsaveinfo(', 'official_openbor_getsaveinfo(', 1))
               .replace('@ORIGINAL_LOAD@', data['contexts']['lns']['load_game'].replace(
                    'loadGameFile(', 'lns_loadGameFile(', 1))
               .replace('@OFFICIAL_LOAD@', data['contexts']['official']['load_game'].replace(
                    'loadGameFile(', 'official_loadGameFile(', 1)),
               extra_flags=('-Wno-unused-parameter',))

    def test_script_spawn_initial_indices_and_deferred_model_lookup(self):
        source = (ENGINE / 'openborscript.c').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-script-original.json').read_text())

        def fragment(name):
            f = function(source, name)
            start = f.index('    memset(&spawnentry')
            end = f.index('    drawmethod', start) if name == 'Script_Global_Init' else f.index('    for(i = 0; i < numfilestreams', start)
            return f[start:end]

        def wrappers(prefix, init, clear, case):
            local = '' if prefix == 'official' else 'char *name;'
            return ('static void ' + prefix + '_init(void) {' + init + '}\n'
                    + 'static void ' + prefix + '_clear(void) {' + clear + '}\n'
                    + 'static int ' + prefix + '_name(ScriptVariant *arg,ScriptVariant **pretvar) {' + local
                    + 'switch(_sse_name) {' + case + '}return S_OK;setspawnentry_error:*pretvar=NULL;return E_FAIL;}\n')
        candidate = wrappers('candidate', fragment('Script_Global_Init'), fragment('Script_Global_Clear'),
                             outer_case(function(source, 'openbor_setspawnentry'), '_sse_name'))
        originals = '\n'.join(wrappers(key, context['spawn_init'], context['spawn_clear'], context['spawn_name'])
                              for key, context in data['contexts'].items())
        program = (FIXTURE.parent / 'lns-6330-spawn-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI))).replace('@CANDIDATE@', candidate)
               .replace('@ORIGINALS@', originals))

    def test_system_native_namespace_and_inserted_readonly_property(self):
        source = (ENGINE / 'openborscript.c').read_text()
        config = (ENGINE / 'source/openborscript/config.h').read_text()
        data = json.loads((FIXTURE.parent / 'lns-6330-script-original.json').read_text())

        def select(name, labels):
            f = function(source, name)
            return (f[:f.index('    case ')] + ''.join(outer_case(f, label) for label in labels)
                    + f[f.rfind('    default:'):])

        def rename(text, prefix):
            text = re.sub(r'\b_sv_\w+', lambda m: prefix + m.group(), text)
            words = ('systemvariant_enum', 'svlist', 'mapstrings_systemvariant',
                     'getsyspropertybyindex', 'changesyspropertybyindex',
                     'openbor_systemvariant', 'openbor_setsystemvariant')
            return re.sub(r'\b(' + '|'.join(words) + r')\b', lambda m: prefix + m.group(), text)

        originals = []
        for key, context in data['contexts'].items():
            originals.append(rename('\n'.join(context[name] for name in
                ('enum', 'svlist', 'mapper', 'getter', 'setter', 'get_wrapper', 'set_wrapper')), key + '_'))
        program = (FIXTURE.parent / 'lns-6330-system-contract.c.in').read_text()
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@ENUM@', re.search(r'enum systemvariant_enum\s*\{[^}]+\};', config).group())
               .replace('@TABLES@', systemvariant_tables(source)).replace('@SEARCH@', data['search'])
               .replace('@MAP_MACRO@', data['map_macro'])
               .replace('@NATIVE@', systemvariant_helpers(source))
               .replace('@MAPPER@', function(source, 'mapstrings_systemvariant'))
               .replace('@GETTER@', select('getsyspropertybyindex',
                    ['_sv_in_options', '_sv_in_selectscreen', '_sv_in_sa_count']))
               .replace('@SETTER@', select('changesyspropertybyindex', ['_sv_current_set', '_sv_scrollmaxx']))
               .replace('@GET_WRAPPER@', function(source, 'openbor_systemvariant'))
               .replace('@SET_WRAPPER@', function(source, 'openbor_setsystemvariant'))
               .replace('@ORIGINALS@', '\n'.join(originals))
               .replace('@EXPECTED@', ','.join(data['contexts']['lns']['names'][:-1])),
               extra_flags=('-Wno-unused-parameter', '-Wno-misleading-indentation'))

    def test_6391_systemvariant_names_and_coordinate_writes(self):
        data = load_contract_fixture(SYSTEMVARIANT_FIXTURE)
        rows = data['sources']
        self.assertEqual([r['revision'] for r in rows], sorted(contract_revisions(data, data['expected_revisions'])))
        source = (ENGINE / 'openborscript.c').read_text(encoding='latin-1')
        variant = (ENGINE / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
        utility = (ENGINE / 'source/utils.c').read_text(encoding='latin-1')
        coordinates = data['coordinate_properties']
        bosses = ['bossescount', 'numbosses']
        values = {
            'TABLES': systemvariant_tables(source),
            'NATIVE': systemvariant_helpers(source),
            'MAPPER': function(source, 'mapstrings_systemvariant'),
            'GETTER': selected_systemvariant_cases(source, 'getsyspropertybyindex', coordinates + bosses + ['pakname']),
            'SETTER': selected_systemvariant_cases(source, 'changesyspropertybyindex', coordinates + bosses),
            'WRAPPERS': '\n'.join(function(source, name) for name in ('openbor_systemvariant', 'openbor_setsystemvariant')),
            'VARIANTS': '\n'.join(function(variant, name) for name in ('ScriptVariant_Init', 'ScriptVariant_Clear',
                                  'ScriptVariant_ChangeType', 'ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue')),
            'SEARCH': function(utility, 'searchList'),
            'COORDINATES': ','.join(json.dumps(name) for name in coordinates),
            'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['integer_coordinates'],
                                            row['pak_label_capacity']) for row in rows),
        }
        for family in ('6119', '6391'):
            values['NAMES_' + family] = ',\n'.join('{"%s",_sv_%s}' % (name, name) for name in data['names'][family])
            values['LEVEL_' + family] = ','.join(data['level_properties'][family])
        template = Path(__file__).with_name('systemvariant_profile_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_0-9]+)@', lambda match: values[match[1]], template)
        result = native_output(code, data, engine_source=ENGINE, extra_cflags=('-fgnu89-inline',))
        expected = []
        for row in rows:
            if row['integer_coordinates']:
                names = ''.join('\n\t' + name for name in data['names']['6119'])
                expected.extend(f"openborvariant: System variable name not found: '{name}'\n"
                                f"\n Available properties:\n{names}\n\n" for name in bosses)
            expected.append(f'{row["revision"]}\n')
        self.assertEqual(result, ''.join(expected))

    def test_wall_option_and_projectile_callers_keep_official_boundary(self):
        source = (ENGINE / 'openbor.c').read_text()
        original = json.loads((FIXTURE.parent / 'lns-6330-wall-bindings-original.json').read_text())
        program = (FIXTURE.parent / 'lns-6330-wall-bindings-contract.c.in').read_text()
        arrow = function(source, 'arrow_move')
        start = arrow.index('    if(level)')
        arrow = arrow[start:arrow.index('    if(self->projectile_prime', start)]
        bomb = function(source, 'bomb_move')
        start = bomb.index('    if((obor_profile_features & OBOR_PROFILE_LNS_6330) && level)')
        bomb = bomb[start:bomb.index('    return 1;', start)]
        wall_call = re.search(r'addwall\(GET_FLOAT_ARG\(1\).*?;', source).group()
        prefix = function(source, 'adjust_base')
        prefix = prefix[:prefix.index('    if(other && !(other->update_mark & 8))')]

        def close_prefix(text, name):
            return text.replace('void adjust_base(', 'static void ' + name + '(', 1) + '''
    reached=1;(void)wall;(void)hole;(void)seta;(void)maxbase;
    (void)sizeof(plat);(void)tempself;
}
'''
        native(program.replace('@ABI@', json.dumps(str(ABI)))
               .replace('@ADDWALL@', function(source, 'addwall'))
               .replace('@ORIGINAL_ADDWALL@', original['addwall'])
               .replace('@OFFICIAL_ADDWALL@', original['official_addwall'])
               .replace('@WALL_CALL@', wall_call).replace('@ORIGINAL_WALL_CALL@', original['wall_call'])
               .replace('@OFFICIAL_WALL_CALL@', original['official_wall_call'])
               .replace('@DEFAULT_CALL@', re.search(r'addwall\(level->width - 30.*?;', source).group())
               .replace('@ORIGINAL_DEFAULT_CALL@', original['default_call'])
               .replace('@OFFICIAL_DEFAULT_CALL@', original['official_default_call'])
               .replace('@ARROW@', arrow).replace('@BOMB@', bomb)
               .replace('@PREFIX@', close_prefix(prefix, 'candidate_adjust_prefix'))
               .replace('@ORIGINAL_PREFIX@', close_prefix(original['adjust_prefix'], 'lns_original_adjust_prefix'))
               .replace('@OFFICIAL_PREFIX@', close_prefix(original['official_adjust_prefix'], 'official_original_adjust_prefix')))

    def test_projectile_wall_function_matches_original_and_rejects_invalid_storage(self):
        source = (ENGINE / 'openbor.c').read_text()
        program = (FIXTURE.parent / 'lns-6330-projectile-contract.c.in').read_text()
        original = (FIXTURE.parent / 'lns-6330-projectile-original.c').read_text()
        native(program.replace('@ORIGINAL@', original)
               .replace('@INTEGER@', function(source, 'obor_lns_wall_integer'))
               .replace('@CANDIDATE@', function(source, 'check_projectile_wall_collision')))

    def test_model_commands_registration_defaults_and_assignment(self):
        source = (ENGINE / 'openbor.c').read_text()
        declarations = (ENGINE / 'source/openborscript/commands.h').read_text()
        commands = (ENGINE / 'source/openborscript/commands.c').read_text()
        original = json.loads((FIXTURE.parent / 'lns-6330-model-original.json').read_text())
        enum = re.search(r'typedef enum modelCommand\s*\{[^}]+\}\s*modelCommands;', declarations).group()
        registration = function(commands, 'createModelCommandList')
        cases = ''
        for label in original['commands']:
            start = source.index('            case ' + label + ':')
            cases += source[start:source.index('\n            case ', start + 1)]
        ctor = function(source, 'init_model')
        initializers = '\n'.join(re.search(r'^\s*newchar->' + field + r'\s*=.*?;', ctor, re.M).group()
                                 for field in ('flashoverridesource', 'ignore_projectile_wall_collision', 'noexplode', 'selectcol'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include @ABI@
static unsigned obor_profile_build,obor_profile_features;
@ENUM@
typedef struct {unsigned count;struct {intptr_t value;char name[96];} items[1024];} List;
static List entries;
static List *prepareList(void) {memset(&entries,0,sizeof(entries));return &entries;}
static void List_InsertAfter(List *list,void *value,const char *name) {
 assert(list->count<1024);unsigned n=list->count++;
 list->items[n].value=(intptr_t)value;snprintf(list->items[n].name,96,"%s",name);
}
@REGISTRATION@
static int lookup(List *list,const char *name) {
 for(unsigned n=0;n<list->count;++n)if(!strcmp(list->items[n].name,name))return (int)list->items[n].value;
 return 0;
}
typedef struct {int flashoverridesource,flashoverridetarget,ignore_projectile_wall_collision,noexplode,selectcol;} Model;
static const char *arguments[3];static int number,lookup_calls;
static int get_cached_model_index(const char *value) {
 ++lookup_calls;return !strcmp(value,"source")?7:!strcmp(value,"target")?9:-1;
}
#define GET_ARG(n) arguments[n]
#define GET_INT_ARG(n) ((void)(n),number)
static void candidate(int command,Model *newchar) {const char *value;switch(command) {@CASES@ default:break;}}
static void reference(int command,Model *newchar) {const char *value;switch(command) {@ORIGINAL_CASES@ default:break;}}
static void candidate_init(Model *newchar) {@INIT@}
static void reference_init(Model *newchar) {@ORIGINAL_INIT@}
int main(void) {
 const char *names[]={"flashoverride","ignore_projectile_wall_collision","noexplode","selectcol"};
 int codes[]={CMD_MODEL_FLASHOVERRIDE,CMD_MODEL_IGNOREPROJECTILEWALLCOLLISION,CMD_MODEL_NOEXPLODE,CMD_MODEL_SELECTCOL};
 const char *values[]={"source","target","missing",""};
 int numbers[]={INT32_MIN,-1,0,1,INT32_MAX};
 unsigned masks[]={0,OBOR_PROFILE_ATTACK_HISTORY_FOUR,OBOR_PROFILE_LNS_6330};
 for(unsigned rev=6330;rev<=6391;rev+=61)for(unsigned m=0;m<3;++m) {
  obor_profile_build=rev;obor_profile_features=masks[m];List *list=createModelCommandList();
  assert(lookup(list,"flash")==CMD_MODEL_FLASH && lookup(list,"bflash")==CMD_MODEL_BFLASH);
  for(unsigned c=0;c<4;++c) {
   int code=lookup(list,names[c]);assert(code==(m==2?codes[c]:0));
   for(unsigned a=0;a<4;++a)for(unsigned b=0;b<4;++b)for(unsigned n=0;n<5;++n) {
    arguments[1]=values[a];arguments[2]=values[b];number=numbers[n];
    Model actual={31,32,33,34,35},expected=actual;lookup_calls=0;
    candidate(code,&actual);int calls=lookup_calls;lookup_calls=0;
    if(m==2)reference(codes[c],&expected);
    assert(!memcmp(&actual,&expected,sizeof(actual)) && calls==lookup_calls);
   }
  }
 }
 Model a={31,32,33,34,35},b=a;candidate_init(&a);reference_init(&b);
 assert(!memcmp(&a,&b,sizeof(a)) && a.flashoverridesource==-1 && a.flashoverridetarget==-1);
 return 0;
}
'''.replace('@ABI@', json.dumps(str(ABI))).replace('@ENUM@', enum)
            .replace('@REGISTRATION@', registration).replace('@CASES@', cases)
            .replace('@ORIGINAL_CASES@', original['command_cases'])
            .replace('@INIT@', initializers).replace('@ORIGINAL_INIT@', original['initializers']),
               extra_flags=('-Wno-int-to-pointer-cast',))

    def test_hit_flash_and_attacker_explosion_match_original(self):
        source = (ENGINE / 'openbor.c').read_text()
        original = json.loads((FIXTURE.parent / 'lns-6330-model-original.json').read_text())
        start = source.index('                // Spawn a flash\n', source.index('else if(self->takedamage(e, attack, 0))'))
        flash = source[start:source.index('                topowner->combotime', start)]
        start = source.index('            //if #051\n')
        explode = source[start:source.index('            if(inair(self))', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include @ABI@
#define SPAWN_TYPE_FLASH 12
typedef struct {int noatflash,flash,flashoverridesource,flashoverridetarget,noexplode;} Model;
typedef struct {Model modeldata;int spawntype,toexplode;} entity;
typedef struct {int no_flash,hitflash;} Attack;
static unsigned obor_profile_build=6330,obor_profile_features;
static struct {struct {float x,y,z;} position;} lasthit={ {1,2,3} };
static struct {int calls,index,direction,scripts,modern,success;} trace;
static entity spawned;
static entity *spawn(float x,float z,float y,int direction,void *a,int index,void *b) {
 assert(x==1 && z==3 && y==2 && !a && !b);
 ++trace.calls;trace.index=index;trace.direction=direction;
 return trace.success?&spawned:NULL;
}
static void execute_onspawn_script(entity *e) {assert(e==&spawned && e->spawntype==SPAWN_TYPE_FLASH);++trace.scripts;}
static void spawn_attack_flash(entity *self,Attack *attack,int index,int fallback) {
 (void)self;(void)attack;(void)index;(void)fallback;++trace.modern;
}
static void candidate_flash(entity *self,entity *e,Attack *attack) {entity *flash=NULL;@FLASH@}
static void lns_flash(entity *self,entity *e,Attack *attack) {entity *flash=NULL;@LNS_FLASH@}
static void official_flash(entity *self,entity *e,Attack *attack) {entity *flash=NULL;@OFFICIAL_FLASH@}
static void candidate_explode(entity *self,entity *e) {@EXPLODE@}
static void lns_explode(entity *self,entity *e) {@LNS_EXPLODE@}
static void official_explode(entity *self,entity *e) {@OFFICIAL_EXPLODE@}
int main(void) {
 for(int lns=0;lns<2;++lns)for(int noflash=0;noflash<2;++noflash)
 for(int noat=0;noat<2;++noat)for(int source=-2;source<3;++source)
 for(int target=-2;target<3;++target)for(int hit=-2;hit<3;++hit)for(int success=0;success<2;++success) {
  obor_profile_features=lns?OBOR_PROFILE_LNS_6330:0;
  entity self={{noat,17,source,target,0},0,0},e={{0,23,0,0,0},0,0};Attack attack={noflash,hit};
  memset(&trace,0,sizeof(trace));memset(&spawned,0,sizeof(spawned));trace.success=success;
  candidate_flash(&self,&e,&attack);unsigned char actual[sizeof(trace)];memcpy(actual,&trace,sizeof(trace));
  int actual_type=spawned.spawntype;
  memset(&trace,0,sizeof(trace));memset(&spawned,0,sizeof(spawned));trace.success=success;
  if(lns)lns_flash(&self,&e,&attack);else official_flash(&self,&e,&attack);
  assert(!memcmp(actual,&trace,sizeof(trace)) && actual_type==spawned.spawntype);
 }
 for(int lns=0;lns<2;++lns)for(int flag=-1;flag<3;++flag)
 for(int self_state=-1;self_state<4;++self_state)for(int other_state=-1;other_state<4;++other_state) {
  obor_profile_features=lns?OBOR_PROFILE_LNS_6330:0;
  entity self={{0,0,0,0,flag},0,self_state},e={{0,0,0,0,flag},0,other_state};
  entity expected_self=self,expected_e=e;candidate_explode(&self,&e);
  if(lns)lns_explode(&expected_self,&expected_e);else official_explode(&expected_self,&expected_e);
  assert(!memcmp(&self,&expected_self,sizeof(self)) && !memcmp(&e,&expected_e,sizeof(e)));
 }
 return 0;
}
'''.replace('@ABI@', json.dumps(str(ABI))).replace('@FLASH@', flash)
            .replace('@LNS_FLASH@', original['flash']).replace('@OFFICIAL_FLASH@', original['official_flash'])
            .replace('@EXPLODE@', explode).replace('@LNS_EXPLODE@', original['explode'])
            .replace('@OFFICIAL_EXPLODE@', original['official_explode']))

    def test_flash_overrides_and_selection_hasplayed_match_own_sources(self):
        source = (ENGINE / 'openborscript.c').read_text()
        original = (FIXTURE.parent / 'lns-6330-flash-original.c').read_text()
        main = function((ENGINE / 'openbor.c').read_text(), 'openborMain')
        storage = '\n'.join(re.search(r'^\s*int ' + pattern + r'[^;]*;', main, re.M).group()
                            for pattern in (r'ordinary_players\[', r'\*players ='))
        flash = outer_case(function(source, 'openbor_getentityproperty'), '_ep_flash')
        played = outer_case(function(source, 'openbor_changeplayerproperty'), '_pp_hasplayed')
        enum = re.search(r'enum gep_flash_enum\s*\{[^}]+\};', source).group()
        mapper = function(source, 'mapstrings_entityproperty')
        table = re.search(r'static const char \*proplist_flash\[\]\s*=\s*\{[^}]+\};', mapper).group()
        mapping = outer_case(mapper, '_ep_flash')
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include @ABI@
typedef int64_t LONG;
enum { S_OK=0,E_FAIL=-1,VT_INTEGER=1,VT_STR=2,_ep_flash=10,_pp_hasplayed=20 };
typedef struct { int vt; LONG lVal; const char *strVal; } ScriptVariant;
typedef struct { struct { int bflash,flash,noatflash,flashoverridesource,flashoverridetarget; } modeldata; } entity;
static unsigned obor_profile_features;
static struct { const char *name; } model_cache[]={{"first"},{"second"},{"third"}};
static int models_cached=3,obor_lns_players[4];
#define MAX_PLAYERS 4
static struct {int hasplayed;} player[4];
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;}
static const char *StrCache_CreateNewFrom(const char *name) {return name;}
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
 if(v->vt!=VT_INTEGER)return E_FAIL;
 *out=v->lVal;return S_OK;
}
#define SUCCEEDED(x) ((x)>=0)
#define printf(...) ((void)0)
@ENUM@
@ORIGINAL@
static int candidate_flash(entity *ent,ScriptVariant **varlist,ScriptVariant **pretvar) {
 ScriptVariant *arg; LONG ltemp; int i;
 switch(_ep_flash) { @FLASH@ } return S_OK;
}
static int candidate_played(int index,ScriptVariant *arg) {
 LONG ltemp;switch(_pp_hasplayed) { @PLAYED@ } return S_OK;cpperror:return E_FAIL;
}
static void check_selection_storage(void) {
 @STORAGE@
 int prior=obor_lns_players[0];
 players[0]=73;
 if(obor_profile_features & OBOR_PROFILE_LNS_6330) {
  assert(players==obor_lns_players && obor_lns_players[0]==73);
 } else {
  assert(players==ordinary_players && ordinary_players[0]==73 && obor_lns_players[0]==prior);
 }
}
static int observed_count;
#define MAPSTRINGS(v,t,n,a,b) do { (void)(v); assert(sizeof(t)/sizeof(*(t))==5); observed_count=(n); } while(0)
static void candidate_map(ScriptVariant **varlist) {
 @TABLE@
 assert(!strcmp(proplist_flash[3],"overridesource"));
 assert(!strcmp(proplist_flash[4],"overridetarget"));
 switch(_ep_flash) { @MAPPING@ }
}
int main(void) {
 unsigned masks[]={0,OBOR_PROFILE_ATTACK_HISTORY_FOUR,OBOR_PROFILE_LNS_6330};
 for(unsigned m=0;m<3;++m) {
  obor_profile_features=masks[m];
  check_selection_storage();
  ScriptVariant v={VT_INTEGER,0,"untouched"};ScriptVariant *args[]={&v,&v,&v};
  candidate_map(args);assert(observed_count==(m==2?5:3));
  for(int prop=-2;prop<8;++prop)for(int idx=-2;idx<5;++idx)for(int type=1;type<=2;++type) {
   entity e={{-3,4,5,idx,idx}};
   v.vt=type;v.lVal=prop;
   ScriptVariant a={VT_STR,123,"untouched"},b=a,*pa=&a,*pb=&b;
   int actual=candidate_flash(&e,args,&pa);
   int expected=m==2?lns_original_flash(&e,args,&pb):official_original_flash(&e,args,&pb);
   assert(actual==expected && !!pa==!!pb && a.vt==b.vt && a.lVal==b.lVal);
   assert(!strcmp(a.strVal,b.strVal));
  }
  LONG values[]={INT32_MIN,-1,0,1,INT32_MAX};
  for(int index=0;index<4;++index)for(unsigned i=0;i<5;++i)for(int type=1;type<=2;++type) {
   v.vt=type;v.lVal=values[i];player[index].hasplayed=-17;obor_lns_players[index]=-18;
   int actual=candidate_played(index,&v),a=player[index].hasplayed,b=obor_lns_players[index];
   player[index].hasplayed=-17;obor_lns_players[index]=-18;
   int expected=m==2?lns_original_played(index,&v):official_original_played(index,&v);
   assert(actual==expected && a==player[index].hasplayed && b==obor_lns_players[index]);
  }
 }
 return 0;
}
'''.replace('@ABI@', json.dumps(str(ABI))).replace('@ENUM@', enum)
            .replace('@ORIGINAL@', original.replace('players[index]', 'obor_lns_players[index]'))
            .replace('@STORAGE@', storage).replace('@FLASH@', flash)
            .replace('@PLAYED@', played).replace('@TABLE@', table).replace('@MAPPING@', mapping))

    def test_native_property_namespace_and_scalar_accessors(self):
        source = (ENGINE / 'openborscript.c').read_text()
        fixtures = FIXTURE.parent
        original = (fixtures / 'lns-6330-entity-original.c').read_text()
        metadata = json.loads((fixtures / 'lns-6330-entity-names.json').read_text())
        enum = re.search(r'enum entityproperty_enum\s*\{[^}]+\};', source).group()
        declarations = []
        for name in ('eplist', 'obor_entityproperty6330', 'obor_eplist6330',
                     'obor_entityproperty6330lns', 'obor_eplist6330lns'):
            declarations.append(re.search(r'static const (?:int|char \*)\s*' + name +
                                         r'\[\]\s*=\s*\{[^}]+\};', source).group())
        mapper = function(source, 'mapstrings_entityproperty')
        first_level = mapper[mapper.index('    // map entity properties'):]
        first_level = first_level[:first_level.index('    if(paramCount < 3')]
        mapper_args = ''
        if 'varlist[1]->vt' in first_level:
            mapper_args = 'ScriptVariant property = {.vt = VT_STR}, *varlist[] = {NULL, &property};'
        mapping = function(source, 'obor_entityproperty')
        if 'obor_entityproperty_legacy_index(' in mapping:
            declarations.append(re.search(r'enum\s*\{\s*OBOR_6330_ENTITY_EDGE_ORDINAL[^}]+\};', source).group())
            selectors = ('obor_entityproperty_legacy_count', 'obor_entityproperty_legacy_index')
            header = (ENGINE / 'openbor.h').read_text()
            classic = function(header, 'obor_profile_has_classic_boomerang')
            mapping = '\n'.join([classic, *(function(source, name) for name in selectors), mapping])
        getters = function(source, 'openbor_getentityproperty')
        setters = function(source, 'openbor_changeentityproperty')
        get_cases = ''.join(outer_case(getters, name) for name in metadata['new_properties'])
        set_cases = ''.join(outer_case(setters, name) for name in metadata['new_properties'])
        expectations = '\n'.join('assert(obor_entityproperty(lns_original%s)==%s);' % (n, n)
                                 for n in metadata['native_names'])
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>
#include @ABI@
typedef int64_t LONG;
typedef int HRESULT;
enum { S_OK=0,E_FAIL=-1,VT_INTEGER=1,VT_OTHER=2,VT_STR=3 };
#define SUCCEEDED(x) ((x)>=0)
typedef struct { int vt;LONG lVal; } ScriptVariant;
typedef struct { int next_force_direction,override_next_force_direction;
                 struct {int ignore_projectile_wall_collision;} modeldata; } entity;
static uint32_t obor_profile_build=6330,obor_profile_features;
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt!=VT_INTEGER)return E_FAIL;
    *out=v->lVal;return S_OK;
}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;}
@ENUM@
@TABLES@
@MAPPING@
/* Observe which native table the real first-level mapper selects. Conversion
 * behavior is unchanged and covered by the shared variant-conversion tests. */
#define MAPSTRINGS(var,list,count,error) do { \
    for(unsigned i=0;i<(unsigned)(count);++i)if(!strcmp(name,(list)[i]))return (int)i; \
    return -1; \
} while(0)
static int map_name(const char *name) {
@MAPPER_ARGS@
@FIRST_LEVEL@
    return -1;
}
#undef MAPSTRINGS
@ORIGINAL@
static HRESULT candidate_get(entity *ent,int property,ScriptVariant **pretvar) {
    switch(obor_entityproperty(property)) {
@GET_CASES@
    default:return E_FAIL;
    }
    return S_OK;
}
static HRESULT candidate_set(entity *ent,int property,ScriptVariant **varlist,int paramCount) {
    LONG ltemp;
    switch(obor_entityproperty(property)) {
@SET_CASES@
    default:return E_FAIL;
    }
    return S_OK;
}
int main(void) {
    obor_profile_features=OBOR_PROFILE_LNS_6330;
@EXPECTATIONS@
    assert(sizeof(obor_eplist6330lns)/sizeof(*obor_eplist6330lns)==lns_original_ep_the_end);
    for(int i=0;i<lns_original_ep_the_end;++i) {
        assert(!strcmp(obor_eplist6330lns[i],lns_original_eplist[i]));
        assert(map_name(lns_original_eplist[i])==i);
    }
    assert(obor_entityproperty(-1)==_ep_the_end);
    assert(obor_entityproperty(lns_original_ep_the_end)==_ep_the_end);
    assert(map_name("not_a_property")==-1);
    const LONG values[]={INT32_MIN,-3,-1,0,1,2,3,INT32_MAX};
    const int properties[]={lns_original_ep_ignore_projectile_wall_collision,
        lns_original_ep_next_force_direction,lns_original_ep_override_next_force_direction};
    for(unsigned property=0;property<3;++property)
    for(unsigned a=0;a<sizeof(values)/sizeof(*values);++a)
    for(unsigned b=0;b<sizeof(values)/sizeof(*values);++b)
    for(int types=0;types<4;++types)
    for(int count=3;count<=5;++count) {
        entity actual={11,12,{13}},expected=actual;
        ScriptVariant v2={types&1?VT_INTEGER:VT_OTHER,values[a]};
        ScriptVariant v3={types&2?VT_INTEGER:VT_OTHER,values[b]},v4={0};
        ScriptVariant *argv[5]={0,0,&v2,&v3,&v4};
        assert(candidate_set(&actual,properties[property],argv,count)==
               lns_original_set(&expected,properties[property],argv,count));
        assert(!memcmp(&actual,&expected,sizeof(actual)));
        ScriptVariant left={VT_OTHER,99},right=left,*lp=&left,*rp=&right;
        assert(candidate_get(&actual,properties[property],&lp)==
               lns_original_get(&expected,properties[property],&rp));
        assert(lp==&left && rp==&right && left.vt==right.vt && left.lVal==right.lVal);
    }
    /* Ordinary 6330 and 6391 retain their existing numeric namespaces. */
    obor_profile_features=0;
    for(unsigned i=0;i<sizeof(obor_entityproperty6330)/sizeof(*obor_entityproperty6330);++i) {
        assert(obor_entityproperty(i)==obor_entityproperty6330[i]);
        assert(map_name(obor_eplist6330[i])==(int)i);
    }
    assert(map_name("nextforcedirection")==-1);
    assert(map_name("overridenextforcedirection")==-1);
    assert(map_name("ignore_projectile_wall_collision")==-1);
    obor_profile_build=6391;
    for(int i=0;i<_ep_boomerang;++i)assert(obor_entityproperty(i)==i);
    assert(map_name("nextforcedirection")==-1);
}
'''.replace('@ABI@', json.dumps(ABI.resolve().as_posix()))
           .replace('@ENUM@', enum).replace('@TABLES@', '\n'.join(declarations))
           .replace('@MAPPING@', mapping).replace('@MAPPER_ARGS@', mapper_args)
           .replace('@FIRST_LEVEL@', first_level).replace('@ORIGINAL@', original)
           .replace('@GET_CASES@', get_cases).replace('@SET_CASES@', set_cases)
           .replace('@EXPECTATIONS@', expectations))

    def test_forced_direction_override_order_and_official_boundary(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        enums = '\n'.join(re.search(r'typedef enum\s*\{[^}]*\}\s*' + name + ';',
                                    header).group() for name in
                          ('e_direction', 'e_direction_adjust'))
        fields = re.search(r'int override_next_force_direction;\s*'
                           r'int next_force_direction;', header).group()
        oracle = FIXTURE.with_name('lns-6330-direction-original.c').read_text()
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include @ABI@
@ENUMS@
typedef struct {
    int normaldamageflipdir,drop,frozen,inbackpain,direction;
    struct { int nopain,noflip; } modeldata;
    struct { float x; } position;
    struct { float pain; } defense[1];
    @FIELDS@
} entity;
typedef struct { int no_pain,attack_type,attack_force;
                 e_direction_adjust force_direction; } s_collision_attack;
static uint32_t obor_profile_features;
static entity *self,*reference_self;
@ORIGINAL@
@METHOD@
int main(void) {
    /* Both originals return for a null attacker without reading the attack.
     * A deliberately inaccessible address makes any speculative load fail. */
    for(int lns=0;lns<=1;++lns) {
        entity subject={0},expected={0};
        self=&subject;reference_self=&expected;
        obor_profile_features=lns?OBOR_PROFILE_LNS_6330:0;
        s_collision_attack *unread=(s_collision_attack *)(uintptr_t)1;
        checkdamageflip(0,unread);
        if(lns)reference_lns_checkdamageflip(0,unread);
        else reference_official_checkdamageflip(0,unread);
        assert(!memcmp(&subject,&expected,sizeof(subject)));
    }
    for(int lns=0;lns<=1;++lns)
    for(int mode=0;mode<9;++mode)
    for(int override=-1;override<=3;++override)
    for(int next=-3;next<=3;++next)
    for(int force=-2;force<=2;++force)
    for(int relative=-1;relative<=1;++relative)
    for(int back=0;back<=1;++back)
    for(int direction=0;direction<=1;++direction) {
        entity subject={0},attacker={0},expected_subject,expected_attacker;
        s_collision_attack attack={0};
        obor_profile_features=lns?OBOR_PROFILE_LNS_6330:0;
        subject.normaldamageflipdir=99;
        subject.position.x=relative;subject.direction=direction;subject.inbackpain=back;
        attacker.direction=!direction;
        attacker.override_next_force_direction=override;
        attacker.next_force_direction=next;
        attack.force_direction=force;attack.attack_force=5;
        if(mode==1)attack.no_pain=1;
        if(mode==2)subject.modeldata.nopain=1;
        if(mode==3)subject.defense[0].pain=10;
        if(mode==4){subject.drop=1;attack.no_pain=1;}
        if(mode==5)subject.frozen=1;
        if(mode==6)subject.modeldata.noflip=1;
        if(mode==7){subject.override_next_force_direction=override;
                    subject.next_force_direction=next;}
        expected_subject=subject;expected_attacker=attacker;
        self=&subject;reference_self=&expected_subject;
        entity *other=mode==8?0:mode==7?self:&attacker;
        entity *reference_other=mode==8?0:mode==7?reference_self:&expected_attacker;
        /* Repeated calls distinguish one-shot from persistent overrides. */
        for(int repeat=0;repeat<3;++repeat) {
            attack.force_direction=repeat==1?DIRECTION_ADJUST_LEFT:force;
            checkdamageflip(other,&attack);
            if(lns)reference_lns_checkdamageflip(reference_other,&attack);
            else reference_official_checkdamageflip(reference_other,&attack);
            assert(!memcmp(&subject,&expected_subject,sizeof(subject)));
            assert(!memcmp(&attacker,&expected_attacker,sizeof(attacker)));
        }
    }
}
'''.replace('@ABI@', json.dumps(ABI.resolve().as_posix()))
           .replace('@ENUMS@', enums).replace('@FIELDS@', fields)
           .replace('@ORIGINAL@', oracle)
           .replace('@METHOD@', function(source, 'checkdamageflip')))

    def test_circular_history_matches_original_and_keeps_other_profiles(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        fields = re.search(r'unsigned int attack_id_incoming;\s*'
                           r'unsigned int attack_id_incoming2;\s*'
                           r'unsigned int attack_id_incoming3;\s*'
                           r'unsigned int attack_id_incoming4;\s*'
                           r'unsigned int lns_attack_id_incoming\[100\];\s*'
                           r'unsigned int lns_attack_id_incoming_index;', header).group()
        methods = '\n'.join(function(source, name) for name in
                            ('obor_attack_seen', 'obor_remember_attack'))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include @ABI@
typedef struct { @FIELDS@ } entity;
static uint32_t obor_profile_features;
static int multihitcheat;
@ORIGINAL@
@METHODS@
int main(void) {
    entity candidate={0}, saved, other={0};
    lns_reference_entity original={0};
    obor_profile_features=OBOR_PROFILE_LNS_6330;
    assert(obor_attack_seen(&candidate,0,0)==1);
    for(unsigned step=0;step<1200;++step) {
        /* Includes zeros, duplicate IDs, wraparound and the unsigned endpoint. */
        unsigned id=step%113==0?0:step%29==0?UINT32_MAX:step%157;
        obor_remember_attack(&candidate,id);
        reference_insert_attack_id_incoming(&original,id);
        assert(candidate.lns_attack_id_incoming_index==original.attack_id_incoming_index);
        assert(!memcmp(candidate.lns_attack_id_incoming,original.attack_id_incoming,
                       sizeof(original.attack_id_incoming)));
        for(unsigned query=0;query<=159;++query) {
            for(int cheat=0;cheat<=1;++cheat) {
                multihitcheat=cheat;
                /* LNS's own collision path does not honor ignore_attack_id. */
                for(int ignore=0;ignore<=1;++ignore)
                    assert(obor_attack_seen(&candidate,query,ignore)==
                           reference_check_attack_id_incoming(&original,query));
            }
        }
        assert(obor_attack_seen(&candidate,UINT32_MAX,0)==
               reference_check_attack_id_incoming(&original,UINT32_MAX));
        saved=candidate;
        obor_remember_attack(&candidate,0x12345678);
        candidate=saved;
        assert(!memcmp(&candidate,&saved,sizeof(saved)));
        assert(other.lns_attack_id_incoming_index==0);
        assert(other.lns_attack_id_incoming[0]==0);
    }
    /* Boundary controls: regular 6330/6391 scalar history and the four-ID variant. */
    const unsigned masks[]={0,OBOR_PROFILE_ATTACK_HISTORY_FOUR};
    for(unsigned profile=0;profile<2;++profile) {
        obor_profile_features=masks[profile];candidate=(entity){0};multihitcheat=0;
        for(unsigned id=1;id<=9;++id) obor_remember_attack(&candidate,id);
        assert(candidate.attack_id_incoming==9);
        assert(candidate.lns_attack_id_incoming_index==0);
        for(unsigned id=1;id<=9;++id) {
            assert(obor_attack_seen(&candidate,id,0)==(id==9 || (profile && id>=6)));
            assert(!obor_attack_seen(&candidate,id,1));
        }
        multihitcheat=1;
        assert(!obor_attack_seen(&candidate,8,0));
        assert(obor_attack_seen(&candidate,9,0));
    }
}
'''
        native(program.replace('@ABI@', json.dumps(ABI.resolve().as_posix()))
               .replace('@FIELDS@', fields).replace('@METHODS@', methods)
               .replace('@ORIGINAL@', FIXTURE.read_text()))


if __name__ == '__main__':
    unittest.main()
