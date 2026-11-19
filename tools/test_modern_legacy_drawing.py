"""Check legacy drawing setters and getters across flag representations.

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
from test_historical_player import function, rename_identifiers, switch_cases


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-legacy-drawing-contracts.json'
SETTINGS = FIXTURE.with_name('profile-4432-settings-record-contracts.json')


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    declaration = re.search(r'(?ms)^enum(?: drawmethod_enum)?\s*\{\s*_dm_alpha,.*?^\};', script)
    start = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    if declaration is None or start is None:
        raise ValueError('Native legacy enum and default drawing record required')
    parts = dict(
        DEFAULT=core[start.start():core.index('\n};', start.end()) + 3],
        ENUM=declaration[0],
        VARIANTS='\n'.join(function(variants, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                                       'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        API='\n'.join(function(script, n) for n in ('mapstrings_drawmethodproperty',
                      'openbor_changedrawmethod', 'openbor_getdrawmethod', 'openbor_setdrawmethod')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        NAMES=','.join(json.dumps(n) for n in data['names']),
        VALUES=','.join('{%d,%s}' % (kind, value) for kind, value in data['values']),
        SEED=','.join(str(v) for v in data['seed']),
        POSITIONAL=','.join('{%d,{%s}}' % (row['count'], ','.join(str(v) for v in row['values']))
                            for row in data['positional']))
    code = Path(__file__).with_name('modern_legacy_drawing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved legacy drawing contract input')
    return code


def late_4432_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    registry = '\n'.join(function(script, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    getter = 'openbor_getdrawmethod'
    stubs = sorted(set(re.findall(r'\(void\s*\*\)\s*((?:openbor|math|system)_\w+)', registry)) -
                   {getter, 'openbor_get_set_handle', 'openbor_get_layer_handle'})
    replacements = {name: 'probe_' + name for name in stubs}
    replacements.update(theFunctionList='probe_list', List_Reset='probe_reset',
                        List_InsertAfter='probe_insert')
    video = function(core, 'init_videomodes')
    keyboard = function(core, 'keyboard_setup')
    loader = function(core, 'load_cached_model')
    _, palette_commands = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
    _, system_fields = switch_cases(core, 'getsyspropertybyindex', 'index', outermost=True)
    values = dict(
        REGISTRY=rename_identifiers(registry, replacements),
        STUBS='\n'.join('static void probe_' + name + '(void) {}' for name in stubs),
        ENUM=re.search(r'(?ms)^enum drawmethod_enum\s*\{\s*_dm_alpha,.*?^\};', script)[0],
        MAP_MACRO=re.search(r'(?ms)^#define MAPSTRINGS\(.*?^\}', script)[0],
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        METHODS='\n'.join(function(script, name) for name in ('mapstrings_drawmethodproperty', getter)),
        GET_SET_HANDLE=function(script, 'openbor_get_set_handle'),
        GET_LAYER_HANDLE=function(script, 'openbor_get_layer_handle'),
        VARIANTS='\n'.join(function(variants, name) for name in
                           ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        VIDEO=re.search(r'(?ms)^    if\(.*?screenformat = PIXEL_32;.*?^    \}', video)[0],
        COLOURDEPTH=re.search(r'(?ms)^                if\(([^\n]+)\)\n[^\n]+\n[^\n]+Colordepth is depreciated', video)[1],
        BUTTONS=re.search(r'(?m)^    const int btnnum = .*;', keyboard)[0],
        EXIT=re.search(r'(?m)^    if\([^\n]+disabledkey\[SDID_ESC\] = 1;', keyboard)[0],
        PALETTE=re.search(r'(?ms)^    if\(pixelformat == PIXEL_x8[^\n]*\)\n'
                          r'    \{[^\n]*\n        if\(!convert_map_to_palette.*?^    \}', loader)[0],
        PALETTE_LOADER=function(core, 'obor_load_model_palette'),
        PALETTE_COMMANDS='\n'.join('case ' + name + ':' + palette_commands[name]['body']
                                   for name in ('CMD_MODEL_PALETTE', 'CMD_MODEL_ALTERNATEPAL', 'CMD_MODEL_GLOBALMAP')),
        BLOCKADE=system_fields['_sv_blockade']['body'],
        PALETTE_AND_SYSTEM_PROFILES=',\n'.join('{%d,%d,%d,%d,%d}' % (row['revision'], row['act'],
            row['decimal_blockade'], row['setter_alias'], row['globalmap_indexed'])
            for row in data['model_palette_and_system_routes']),
        SET_HANDLE_PROFILES=',\n'.join('{%d,%d}' % (row['revision'], row['available'])
                                     for row in data['set_handle_routes']),
        LAYER_HANDLE_PROFILES=',\n'.join('{%d,%d}' % (row['revision'], row['available'])
                                       for row in data['layer_handle_routes']),
        PROFILES=',\n'.join('{%d,%d,%d,%d}' % (row['revision'], row['fixed_video'],
                          row['map_conversion'], row['getdrawmethod']) for row in data['video_and_drawing']))
    text = Path(__file__).with_name('late_4432_video_drawing_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved video and drawing contract input')
    return text


class ModernLegacyDrawingContracts(unittest.TestCase):
    def test_named_and_positional_flag_roundtrips(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], **data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)

    def test_4432_video_and_drawing_boundaries(self):
        data = load_contract_fixture(SETTINGS)
        rows = data['video_and_drawing']
        self.assertEqual([row['revision'] for row in rows], [4432, 4453, 4454, 4455, 4456, 4510])
        self.assertTrue({row['revision'] for row in rows} <= {row['revision'] for row in data['sources']})
        observed = json.loads(native_output(late_4432_program(data), data))
        self.assertEqual(observed, {'profiles': len(rows),
            'palette_and_system_profiles': len(data['model_palette_and_system_routes']),
            'set_handle_profiles': len(data['set_handle_routes']),
            'layer_handle_profiles': len(data['layer_handle_routes']), 'status': 'PASS'})


if __name__ == '__main__':
    unittest.main()
