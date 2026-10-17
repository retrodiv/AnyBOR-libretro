"""Exercise divergent revision contracts at the real native C boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_BRANCH_ENGINE', ROOT / 'src/engines/7142'))
FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def source(name):
    return (ENGINE / name).read_bytes().decode('utf-8', 'surrogateescape')


def outer_case(text, label):
    start = re.search(r'(?m)^    case ' + re.escape(label) + r':\s*$', text)
    if start is None:
        raise AssertionError('Missing native case ' + label)
    end = re.search(r'(?m)^    (?:case \w+:|default:)', text[start.end():])
    if end is None:
        raise AssertionError('Unterminated native case ' + label)
    return text[start.start():start.end() + end.start()]


def native_engine(program):
    includes = [ENGINE, ROOT / 'src/port/libretro'] + [ENGINE / 'source' / sub for sub in (
        '', 'adpcmlib', 'gamelib', 'gfxlib', 'preprocessorlib', 'ramlib',
        'randlib', 'scriptlib', 'openborscript', 'pnglib', 'webmlib')]
    with tempfile.TemporaryDirectory(prefix='anybor-branch-contract-') as temp:
        work = Path(temp)
        probe = work / 'probe.c'
        probe.write_text(program)
        command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
            '-std=gnu99', '-g', '-O1', '-fsanitize=address,undefined',
            '-fno-omit-frame-pointer', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=7142',
            ('-DDARWIN=1' if sys.platform == 'darwin' else '-DLINUX=1')] + ['-I' + str(path) for path in includes]
        subprocess.run(command + [str(probe), '-lm', '-o', str(work / 'probe')], check=True, timeout=60)
        subprocess.run([str(work / 'probe')], check=True, timeout=20,
                       stdout=subprocess.DEVNULL)


class BranchProfileTests(unittest.TestCase):
    def test_projectile_origins_and_summon_removal_attack_slots(self):
        text = source('openbor.c')
        update = function(text, 'update_frame')
        start = update.index('int position_x = anim->projectile.position.x;')
        end = update.index('if(anim->projectile.throwframe', start)
        knife = re.search(r'(?m)^\s*#define __tryknife (.+)$', update)[1]
        shoot = re.search(r'(?m)^\s*(knife_spawn\([^\n]+, 1, 0\);)', update)[1]
        bomb = re.search(r'(?m)^\s*(bomb_spawn\([^\n]+;)', update)[1]
        removal = re.search(r'attack.attack_type = ([^;]+);', update[update.index('if(anim->unsummonframe'):])[1]
        parent = re.search(r'attack.attack_type = ([^;]+);', function(text, 'kill_entity'))[1]
        program = (FIXTURES / 'branch_projectiles.c').read_text()
        for key, value in (('__OBOR_ORIGIN__', update[start:end]), ('__OBOR_KNIFE__', knife),
                           ('__OBOR_SHOOT__', shoot), ('__OBOR_BOMB__', bomb),
                           ('__OBOR_UNSUMMON__', removal), ('__OBOR_PARENT__', parent)):
            program = program.replace(key, value)
        native_engine(program)

    def test_attack_script_entry_points_roundtrip_and_reject_before_mutation(self):
        program = (FIXTURES / 'branch_script_ids.c').read_text()
        variants = source('source/scriptlib/ScriptVariant.c')
        methods = '\n'.join(function(variants, name) for name in (
            'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue'))
        native_engine(program.replace('CONVERSIONS', methods))

    def test_energy_binding_and_frame_actions_execute_native_contracts(self):
        text = source('openbor.c')
        methods = '\n'.join(function(text, name) for name in (
            'check_bind_override', 'check_energy', 'check_jumpframe',
            'check_landframe', 'check_frame_set_drop'))
        gravity = function(text, 'check_gravity')
        begin = gravity.index('if(obor_profile_legacy_branch())')
        end = gravity.index('check_frame_set_drop(self);', begin) + len('check_frame_set_drop(self);')
        program = (FIXTURES / 'branch_actions.c').read_text()
        jump = function(text, 'player_jump_check')
        start = jump.index('                if(')
        finish = jump.index('                if(candospecial)', start)
        native_engine(program.replace('METHODS', methods).replace('__OBOR_DROP_BRANCH__', gravity[begin:end])
                      .replace('__OBOR_JUMP_COST__', jump[start:finish]))

    def test_optional_entity_properties_keep_absence_and_setter_behavior(self):
        text = source('openborscript.c')
        getter = function(text, 'openbor_getentityproperty')
        setter = function(text, 'openbor_changeentityproperty')
        program = (FIXTURES / 'branch_optional.c').read_text()
        program = program.replace('GETTER_CASES', '\n'.join(outer_case(getter, name)
                                  for name in ('_ep_dropframe', '_ep_energy_cost', '_ep_landframe')))
        program = program.replace('SETTER_CASE', outer_case(setter, '_ep_energy_cost'))
        variants = source('source/scriptlib/ScriptVariant.c')
        program = program.replace('CONVERSIONS', function(variants, 'ScriptVariant_IntegerValue'))
        native_engine(program)

    def test_incoming_attack_history_and_selection_menu_branch(self):
        text = source('openbor.c')
        program = (FIXTURES / 'branch_selection.c').read_text()
        methods = '\n'.join(function(text, name) for name in (
            'obor_attack_seen', 'obor_remember_attack', 'goto_mainmenu', 'menu_options'))
        testmove = function(text, 'testmove')
        screen = testmove[testmove.index('    // screen checking'):]
        screen = screen[:screen.index('    //-----------end of bounds checking')]
        select = function(text, 'selectplayer')
        # Execute the original branch predicates, including simultaneous keys.
        choices = list(re.finditer(r'else if \(([^\n]+)\)', select))
        early = next(value for value in choices if 'obor_profile_build == 7123' in value[1])
        lateral = next(value for value in choices if 'FLAG_MOVELEFT | FLAG_MOVERIGHT' in value[1])
        confirm = next(value for value in choices if value[1].startswith('(player[i].newkeys & FLAG_ANYBUTTON)'))
        self.assertLess(early.start(), lateral.start())
        self.assertLess(lateral.start(), confirm.start())
        escape = select[select.index('\t\tif ((bothnewkeys & FLAG_ESC)'):]
        escape = escape[:escape.index('\n\t\t}') + len('\n\t\t}')]
        program = program.replace('METHODS', methods).replace('SCREEN', screen)
        program = program.replace('EARLY_CHOICE', early[1]).replace('LATERAL_CHOICE', lateral[1])
        program = program.replace('CONFIRM_CHOICE', confirm[1]).replace('ESCAPE', escape)
        native_engine(program)

    def test_animation_native_selectors_types_presence_and_setters(self):
        program = (FIXTURES / 'branch_animation.c').read_text()
        variants = source('source/scriptlib/ScriptVariant.c')
        conversions = '\n'.join(function(variants, name) for name in (
            'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue'))
        native_engine(program.replace('CONVERSIONS', conversions))

    def test_attack_spawn_domains_and_real_constant_mapping(self):
        program = (FIXTURES / 'branch_domains.c').read_text()
        header = source('source/openborscript/scriptcommon.h')
        integers = re.findall(r'extern int\s+(\w+)\s*;', header)
        arrays = re.findall(r'extern int\s+\*(anim\w+)\s*;', header)
        globals = '\n'.join('int ' + name + ';' for name in integers)
        globals += '\nstatic int slots[128];\n'
        globals += '\n'.join('int *' + name + '=slots;' for name in arrays)
        native_engine(program.replace('GLOBALS', globals))

    def test_platform_boundary_preserves_menu_default_and_script_fps(self):
        program = (FIXTURES / 'branch_platform.c').read_text()
        text = source('openbor.c')
        methods = '\n'.join(function(text, name) for name in (
            'libretro_default_buttons', 'clearbuttons', 'clearsettings', 'getFPS'))
        timer = (ROOT / 'src/port/libretro/timer.c').read_text()
        control = (ROOT / 'src/port/libretro/control.c').read_text()
        methods = function(control, 'flag_to_index') + function(control, 'control_setkey') + function(timer, 'timer_uticks') + methods
        native_engine(program.replace('METHODS', methods))

    def test_actual_build_source_list_has_no_standalone_platform_objects(self):
        with tempfile.TemporaryDirectory(prefix='anybor-branch-source-list-') as temp:
            supplement = Path(temp) / 'sources.mk'
            supplement.write_text("contract-source-list:\n\t@printf '%s\\n' '$(ENGINE_SRCS)'\n")
            result = subprocess.run(['make', '-s', '-f', str(ENGINE / 'Makefile.libretro'),
                                     '-f', str(supplement), 'PLATFORM=linux',
                                     'PORT_ROOT=' + str(ROOT / 'src/port/libretro'),
                                     'contract-source-list'], cwd=ENGINE, text=True,
                                    capture_output=True, check=True, timeout=20)
            sources = result.stdout.split()
            self.assertIn('openbor.c', sources)
            self.assertIn('openborscript.c', sources)
            self.assertIn('source/gamelib/packfile.c', sources)
            self.assertFalse(any(name.startswith(('sdl/', 'android/', 'psp/', 'vita/', 'wii/', 'xbox/'))
                                 for name in sources))

    def test_model_commands_presence_defaults_and_original_condition_values(self):
        program = (FIXTURES / 'branch_model.c').read_text()
        source_text = source('openbor.c')
        text = function(source_text, 'load_cached_model')
        begin = text.index('newanim->obor_counter_present =')
        end = text.index('if((ani_id = translate_ani_id', begin)
        initializer = text[begin:end]
        names = ('ENERGY_COST', 'MPCOST', 'MPONLY', 'DIVE', 'DIVE1', 'DIVE2',
                 'JUMPFRAME', 'LANDFRAME', 'DROPFRAME', 'FOLLOWCOND', 'COUNTERRANGE',
                 'PROJECTILE_POSITION_X', 'PROJECTILE_POSITION_Y', 'PROJECTILE_POSITION_Z',
                 'DEFENSE', 'OFFENSE')
        labels = list(re.finditer(r'(?m)^[ \t]*case CMD_MODEL_[A-Z_0-9]+:', text))
        cases = []
        for i, match in enumerate(labels):
            name = match.group().split('CMD_MODEL_', 1)[1][:-1]
            if name in names:
                end = labels[i + 1].start() if i + 1 < len(labels) else len(text)
                cases.append(text[match.start():end])
        self.assertEqual(len(cases), len(names))
        translate = function(source_text, 'translate_ani_id')
        begin = translate.index('else if(stricmp(value, "special")')
        end = translate.index('else if(starts_with_num(value, "freespecial"))', begin)
        type_methods = '\n'.join(function(source_text, name) for name in (
            'find_entity_type_from_string', 'obor_legacy_lcmHandleCommandHostile',
            'lcmHandleCommandHostile', 'obor_legacy_lcmHandleCommandCandamage',
            'lcmHandleCommandCandamage', 'obor_legacy_lcmHandleCommandProjectilehit',
            'lcmHandleCommandProjectilehit'))
        native_engine(program.replace('INITIALIZER', initializer).replace('CASES', '\n'.join(cases))
                      .replace('SPECIAL_DEFAULTS', translate[begin:end]).replace('TYPE_METHODS', type_methods))

    def test_follow_counter_native_decisions_damage_and_actions(self):
        program = (FIXTURES / 'branch_combat.c').read_text()
        methods = '\n'.join(function(source('openbor.c'), name) for name in (
            'check_follow_up_condition', 'try_follow_up', 'check_counter_condition', 'try_counter_action'))
        native_engine(program.replace('METHODS', methods).replace('__OBOR_DAMAGE_FUNCTION__', function(source('openbor.c'), 'calculate_force_damage')))


if __name__ == '__main__':
    unittest.main()
