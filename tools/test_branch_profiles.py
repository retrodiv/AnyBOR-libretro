"""Exercise divergent revision contracts at the real native C boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from contract_fixtures import load_contract_fixture
from test_historical_model_defaults import model_command_functions
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_BRANCH_ENGINE', ROOT / 'src/engines/7142'))
FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def source(name):
    return (ENGINE / name).read_bytes().decode('utf-8', 'surrogateescape')


def outer_case(text, label, *, indent='    '):
    prefix = re.escape(indent)
    start = re.search(r'(?m)^' + prefix + r'case ' + re.escape(label) + r':[ \t]*$', text)
    if start is None:
        raise AssertionError('Missing native case ' + label)
    end = re.search(r'(?m)^' + prefix + r'(?:case \w+:|default:)', text[start.end():])
    if end is None:
        raise AssertionError('Unterminated native case ' + label)
    return text[start.start():start.end() + end.start()]


def native_engine(program, libraries=()):
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
        subprocess.run(command + [str(probe), '-lm', *libraries, '-o', str(work / 'probe')],
                       check=True, timeout=60)
        subprocess.run([str(work / 'probe')], check=True, timeout=20,
                       stdout=subprocess.DEVNULL)


class BranchProfileTests(unittest.TestCase):
    def test_historical_model_command_names_match_original_sources(self):
        data = load_contract_fixture(FIXTURES / 'profile-7142-model-command-names.json')
        names = data['commands']
        rows = []
        for row in data['sources']:
            selectors = ', '.join(symbol if present else '0'
                                  for (_, symbol), present in zip(names, row['admitted'], strict=True))
            rows.append('{%d, {%s}}' % (row['revision'], selectors))
        commands = model_command_functions(source('source/openborscript/commands.c'),
                                           source('source/utils.c'))
        template = r'''
#include "openbor.h"
#include "source/openborscript/commands.h"
#include "source/scriptlib/List.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>

uint32_t obor_profile_build;

void *checkAlloc(void *pointer, size_t size, const char *function, const char *file, int line)
{
    (void)size;
    (void)function;
    (void)file;
    (void)line;
    assert(pointer);
    return pointer;
}

@COMMANDS@

int main(void)
{
    static const char names[][32] = {@NAMES@};
    static const struct {
        unsigned revision;
        modelCommands expected[sizeof(names) / sizeof(names[0])];
    } cases[] = {@CASES@};

    for(size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
    {
        obor_profile_build = cases[i].revision;
        List *registry = createModelCommandList();
        assert(registry);
        for(size_t j = 0; j < sizeof(names) / sizeof(names[0]); ++j)
        {
            char name[sizeof(names[0])];
            memcpy(name, names[j], sizeof(name));
            modelCommands actual = getModelCommand(registry, name);
            if(actual != cases[i].expected[j])
            {
                fprintf(stderr, "%u %s returned %d, expected %d\n",
                        cases[i].revision, name, (int)actual, (int)cases[i].expected[j]);
                freeCommandList(registry);
                return 1;
            }
        }
        freeCommandList(registry);
    }
    return 0;
}
'''
        program = (template.replace('@COMMANDS@', commands)
                   .replace('@NAMES@', ', '.join(json.dumps(name) for name, _ in names))
                   .replace('@CASES@', ', '.join(rows)))
        native_engine(program)

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
        names = ('_ep_dropframe', '_ep_energy_cost', '_ep_landframe', '_ep_animhits')
        program = program.replace('GETTER_CASES', '\n'.join(outer_case(getter, name)
                                  for name in names))
        program = program.replace('SETTER_CASES', '\n'.join(outer_case(setter, name)
                                  for name in ('_ep_energy_cost', '_ep_animhits')))
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

    def test_historical_script_property_conversion_routes(self):
        data = load_contract_fixture(FIXTURES / 'profile-7142-script-property-mappers.json')
        dispatch = function(source('source/openborscript/index.c'), 'Script_GetStringMapFunction')
        symbols = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', dispatch)))
        aliases = '\n'.join('#define %s probe_%s' % (name, name) for name in symbols)
        stubs = '\n'.join('static void probe_%s(void) {}' % name for name in symbols
                          if name != 'mapstrings_entity_property')
        entity = source('source/openborscript/entity.c')
        prefixes = []
        for operation in ('get', 'set'):
            name = 'openbor_' + operation + '_entity_property'
            prefix = function(entity, name).split('switch(property)', 1)[0]
            prefix = prefix.replace(name + '(', 'entity_' + operation + '_probe(', 1)
            prefixes.append(prefix + '''
    return S_OK;
error_local:
    return E_FAIL;
}
#undef SELF_NAME
#undef ARG_MINIMUM
#undef ARG_HANDLE
#undef ARG_PROPERTY
#undef ARG_VALUE
''')
        cases = ', '.join('{%d, %d, %d}' % (
            row['revision'], row['animation_compile_mapper'], row['entity_runtime_mapper'])
            for row in data['sources'])
        template = r'''
#include "openbor.h"
#include <assert.h>
#include <string.h>

uint32_t obor_profile_build;
void ScriptVariant_Clear(ScriptVariant *value) { memset(value, 0, sizeof(*value)); }

@ALIASES@
@STUBS@
static int probe_mapstrings_entity_property(ScriptVariant **args, int count)
{
    if(count >= 2 && args[1]->vt == VT_STR)
    {
        args[1]->vt = VT_INTEGER;
        args[1]->lVal = 0;
    }
    return 1;
}

@DISPATCH@
@ENTITY@

int main(void)
{
    static const struct {
        unsigned revision;
        int animation_compile_mapper;
        int entity_runtime_mapper;
    } cases[] = {@CASES@};
    entity actor = {0};

    for(size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
    {
        obor_profile_build = cases[i].revision;
        void *animation_mapper = cases[i].animation_compile_mapper
            ? (void *)mapstrings_animation_property : NULL;
        assert(Script_GetStringMapFunction((void *)openbor_get_animation_property) == animation_mapper);
        assert(Script_GetStringMapFunction((void *)openbor_set_animation_property) == animation_mapper);
        assert(Script_GetStringMapFunction((void *)openbor_get_entity_property) == (void *)mapstrings_entity_property);
        assert(Script_GetStringMapFunction((void *)openbor_set_entity_property) == (void *)mapstrings_entity_property);

        for(int set = 0; set < 2; ++set)
        {
            HRESULT (*call)(ScriptVariant **, ScriptVariant **, int) =
                set ? entity_set_probe : entity_get_probe;
            ScriptVariant handle = {.vt = VT_PTR, .ptrVal = &actor};
            ScriptVariant property = {.vt = VT_STR, .strVal = 0};
            ScriptVariant value = {.vt = VT_INTEGER, .lVal = 1};
            ScriptVariant result = {0}, *out = &result;
            ScriptVariant *args[] = {&handle, &property, &value};
            int count = set ? 3 : 2;
            assert(call(args, &out, count) == (cases[i].entity_runtime_mapper ? S_OK : E_FAIL));
            assert(property.vt == (cases[i].entity_runtime_mapper ? VT_INTEGER : VT_STR));
            assert(out == (cases[i].entity_runtime_mapper ? &result : NULL));

            property.vt = VT_STR;
            out = &result;
            assert(mapstrings_entity_property(args, count) && property.vt == VT_INTEGER);
            assert(call(args, &out, count) == S_OK && out == &result);
        }
    }
    return 0;
}
'''
        native_engine(template.replace('@ALIASES@', aliases).replace('@STUBS@', stubs)
                      .replace('@DISPATCH@', dispatch).replace('@ENTITY@', '\n'.join(prefixes))
                      .replace('@CASES@', cases))

    def test_historical_binding_position_and_block_eligibility(self):
        text = source('openbor.c')
        methods = '\n'.join(function(text, name) for name in (
            'direction_adjustment', 'binding_position', 'adjust_bind', 'check_blocking_eligible'))
        template = (FIXTURES / 'branch_binding_blocking.c').read_text()
        native_engine(template.replace('@METHODS@', methods))

    def test_historical_grab_drawing_order_and_debug_range_coordinates(self):
        core = source('openbor.c')
        methods = '\n'.join(function(core, name) for name in ('diff', 'adjust_grabposition'))
        display = function(core, 'display_ents')
        start = display.index('z = (int)e->position.z;    // Set the layer offset')
        end = display.index('if(other &&', start)
        order = display[start:end]
        debug = function(core, 'draw_visual_debug')
        start = debug.index('\n', debug.index('if(savedata.debuginfo & DEBUG_DISPLAY_RANGE)'))
        end = debug.index('        // Collision body debug requested?', start)
        debug_range = debug[start:end]
        template = (FIXTURES / 'branch_grab_rendering.c').read_text()
        native_engine(template.replace('@METHODS@', methods).replace('@ORDER@', order)
                      .replace('@RANGE@', debug_range))

    def test_historical_level_palette_transport_and_blending_collection(self):
        core = source('openbor.c')
        methods = '\n'.join(function(core, name) for name in (
            'obor_load_act_palette', 'load_palette', 'obor_add_level_palette'))
        methods += function(source('source/gamelib/pixelformat.c'), 'colour32')
        command = outer_case(function(core, 'load_level'), 'CMD_LEVEL_PALETTE', indent='        ')
        getter = function(source('source/openborscript/level.c'), 'openbor_get_level_property')
        property_case = outer_case(getter, 'LEVEL_PROP_PALETTE_BLENDING_COLLECTION', indent='        ')
        cleanup = function(core, 'free_level').split('    if(lv->palettes)', 1)[1].rsplit('}', 1)[0]
        template = (FIXTURES / 'branch_level_palettes.c').read_text()
        native_engine(template.replace('@METHODS@', methods).replace('@COMMAND@', command)
                      .replace('@PROPERTY@', property_case)
                      .replace('@CLEANUP@', '    if(lv->palettes)' + cleanup))

    def test_historical_background_standard_palette_timing(self):
        core = source('openbor.c')
        transport = function(core, 'obor_load_background').split('    lifebar_colors();', 1)
        self.assertEqual(len(transport), 2)
        methods = transport[0] + '}\n' + '\n'.join(function(core, name) for name in (
            'load_background', 'obor_load_cached_background', 'load_cached_background'))
        template = (FIXTURES / 'branch_background_palette.c').read_text()
        native_engine(template.replace('@METHODS@', methods))

    def test_historical_transformed_sprite_alpha_and_color_table(self):
        transform = source('source/gamelib/transform.c')
        init = function(transform, 'init_gfx_global_draw_stuff')
        mask = re.search(r'(?ms)^\s*ptr_src_mask = (?!NULL;)[^;]+;', init).group()
        methods = '\n'.join(function(transform, name) for name in (
            'sprite_get_pixel', 'draw_pixel_sprite', '_sprite_seek', 'calc_wp_cond'))
        pixels = source('source/gamelib/pixelformat.c')
        blend_macros = '\n'.join(re.search(r'(?m)^#define\s+' + macro + r'\([^\n]+', pixels).group()
                                 for macro in ('_color', '_channel'))
        template = (FIXTURES / 'branch_transformed_sprites.c').read_text()
        native_engine(template.replace('@METHODS@', methods).replace('@MASK@', mask)
                      .replace('@BLEND@', blend_macros + '\n' + function(pixels, 'blend_channel32')))

    def test_historical_interlaced_png_layout_and_acceptance(self):
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))

        def image(width, interlaced):
            height = 8
            passes = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
                      (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)) if interlaced else ((0, 0, 1, 1),)
            rows = bytearray()
            for x_start, y_start, x_step, y_step in passes:
                pass_width = len(range(x_start, width, x_step))
                if pass_width:
                    for _ in range(y_start, height, y_step):
                        rows.extend(b'\0' + b'\1' * pass_width)
            return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, interlaced))
                    + chunk(b'PLTE', bytes((0, 0, 0, 32, 64, 128)) + bytes(range(21)))
                    + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))

        loader = source('source/gamelib/loadimg.c')
        start = loader.index('#define PNG_MAGIC')
        end = loader.index('static void closepng', start)
        methods = loader[start:end] + '\n'.join(function(loader, name) for name in (
            'png_paeth_predictor', 'png_decode_regular', 'png_decode_interlaced', 'readpng'))
        methods = function(source('source/gamelib/pixelformat.c'), 'colour32') + methods
        arrays, contexts = [], []
        for width, interlaced, early_rejected, output_width in (
                (1, 1, 1, 1), (2, 1, 1, 2), (4, 1, 0, 4), (8, 1, 0, 8),
                (9, 1, 0, 9), (1, 0, 0, 1), (9, 0, 0, 8), (9, 1, 0, 8)):
            name = f'png_{width}_{interlaced}_{output_width}'
            arrays.append(f'static const unsigned char {name}[] = {{' + ', '.join(map(str, image(width, interlaced))) + '};')
            contexts.append(f'{{{name}, sizeof({name}), {width}, {interlaced}, {early_rejected}, {output_width}}}')
        template = (FIXTURES / 'branch_interlaced_png.c').read_text()
        native_engine(template.replace('@METHODS@', methods).replace('@FILES@', '\n'.join(arrays))
                      .replace('@CONTEXTS@', ',\n    '.join(contexts)), ('-lz',))

    def test_original_grab_order_startup_and_menu_output(self):
        core = source('openbor.c')
        def between(text, first, last):
            start = text.index(first)
            return text[start:text.index(last, start)]

        grab = between(function(core, 'common_grab_check'), '    which = rnum %', '    // grab attacks')
        table = between(core, 'int                 grab_attacks[', '\n};') + '\n};'
        startup = between(function(core, 'startup'), '    if(obor_profile_6997_or_7039()', '    load_menu_txt();')
        credits = between(function(core, 'display_credits'), '        m = 2;', '        update(2, 0);')
        menu = function(core, 'menu_options_input').split('Tr("Setup Player 4..."));', 1)[1]
        touch = between(menu, '        #if ANDROID', '        _menutextm((selector == 6)')
        diagnostics = function(source('source/ramlib/ram.c'), 'getRamStatus')
        level = function(core, 'load_level').split('usedram = getUsedRam(BYTES);', 1)[1]
        level = between(level, '    if(obor_profile_build == 6997)', '    printf("Total sprites mapped:')
        template = (FIXTURES / 'branch_early_progress.c').read_text()
        for key, value in (('ORDER', grab), ('TABLE', table), ('STARTUP', startup),
                           ('CREDITS', credits), ('TOUCH', touch + '\n#endif\n'),
                           ('DIAGNOSTICS', diagnostics), ('LEVEL', level)):
            template = template.replace('@' + key + '@', value)
        native_engine(template)

    def test_attack_spawn_domains_and_real_constant_mapping(self):
        program = (FIXTURES / 'branch_domains.c').read_text()
        header = source('source/openborscript/scriptcommon.h')
        integers = re.findall(r'extern int\s+(\w+)\s*;', header)
        arrays = re.findall(r'extern int\s+\*(anim\w+)\s*;', header)
        globals = '\n'.join('int ' + name + ';' for name in integers)
        globals += '\nstatic int slots[128];\n'
        globals += '\n'.join('int *' + name + '=slots;' for name in arrays)
        data = load_contract_fixture(FIXTURES / 'profile-7142-script-property-mappers.json')
        constants = ', '.join('{%s, %d}' % (json.dumps(name), value)
                              for name, value in data['animation_constants'].items())
        names = data['later_constants']
        self.assertTrue(names and all(re.fullmatch(r'[A-Z][A-Z0-9_]*', name) for name in names))
        later_constants = ', '.join('{%s, %s}' % (json.dumps(name), name) for name in names)
        native_engine(program.replace('GLOBALS', globals).replace('@ANIMATION_CONSTANTS@', constants)
                      .replace('@LATER_CONSTANTS@', later_constants))

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
        begin = text.index('newanim->range.y.min')
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
            'lcmHandleCommandSmartbomb',
            'find_entity_type_from_string', 'obor_legacy_lcmHandleCommandHostile',
            'lcmHandleCommandHostile', 'obor_legacy_lcmHandleCommandCandamage',
            'lcmHandleCommandCandamage', 'obor_legacy_lcmHandleCommandProjectilehit',
            'lcmHandleCommandProjectilehit'))
        native_engine(program.replace('INITIALIZER', initializer).replace('CASES', '\n'.join(cases))
                      .replace('SPECIAL_DEFAULTS', translate[begin:end]).replace('TYPE_METHODS', type_methods))

    def test_follow_counter_native_decisions_damage_and_actions(self):
        program = (FIXTURES / 'branch_combat.c').read_text()
        core = source('openbor.c')
        methods = '\n'.join(function(core, name) for name in (
            'check_follow_up_condition', 'try_follow_up', 'check_counter_condition',
            'try_counter_action', 'obor_remember_attack'))
        attack = function(core, 'do_attack')
        start = attack.index('else if((counter_result = try_counter_action(')
        stop = attack.index('else if(self->takedamage(', start)
        native_engine(program.replace('METHODS', methods)
                      .replace('__OBOR_DAMAGE_FUNCTION__', function(core, 'calculate_force_damage'))
                      .replace('__OBOR_COUNTER_CALL__', attack[start:stop]))


if __name__ == '__main__':
    unittest.main()
