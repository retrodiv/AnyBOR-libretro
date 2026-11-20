"""Check native AI gate order, callback state and historical escape resets.

Actual caller and gate bodies execute; delegated services observe state.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from native_sanitizers import sanitizer_environment
from test_early_jump_walkoff import braced_statement
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-common-think-contracts.json'
ANIMATION_RANGE = FIXTURE.with_name('profile-6391-animation-range.json')
TIMED_COLOURMAP = FIXTURE.with_name('profile-timed-colourmap-expiry.json')


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = ('diff', 'ai_check_warp', 'ai_check_lie', 'ai_check_grabbed',
             'ai_check_grab', 'ai_check_escape', 'ai_check_busy', 'common_think',
             'update_animation')
    parts = {'FUNCTIONS': '\n'.join(function(core, name) for name in names),
        'PROFILES': ','.join(str(row['revision']) + 'u' for row in data['sources']),
        'CASES': ',\n'.join('{%s}' % ','.join(str(row[k]) for k in data['parameters'])
                            for row in data['cases'])}
    text = Path(__file__).with_name('common_think_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native common thinker dependency')
    return text




def script_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    header = (engine / 'openborscript.h').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    callbacks = ['openbor_' + row['name'] for row in data['script_callbacks']]
    methods = '\n'.join(function(source, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(void\*\)\s*(\w+)', methods)))
    if not 8 <= len(symbols) <= 512 or not set(callbacks) <= set(symbols):
        raise ValueError('Bounded complete script registry and callbacks required')
    prototypes = []
    for name in callbacks:
        match = re.search(r'(?m)^HRESULT[ \t]+' + name + r'\([^;{]*\);', header)
        if match is None:
            raise ValueError('Native script callback prototype required')
        prototypes.append(match[0])
    gates = []
    for i, row in enumerate(data['script_callbacks']):
        gates.append('int %s(void){++calls[%d];return returned_value;}' % (row['native'], i))
    values = dict(PROTOTYPES='\n'.join(prototypes), CALLBACK_POINTERS=','.join(callbacks),
                  NAMES=','.join(json.dumps(row['name']) for row in data['script_callbacks']),
                  VARIANTS='\n'.join(function(variant, name) for name in
                                      ('ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
                  STUBS='\n'.join('static void '+name+'(void){}' for name in symbols
                                   if name not in callbacks),
                  GATES='\n'.join(gates),
                  CALLBACKS='\n'.join(function(source, name) for name in callbacks),
                  AVAILABILITY=function(source, 'obor_script_function_available'),
                  METHODS=methods,
                  CHECKS='\n'.join('check(%du,%d);' % (row['revision'], row['ai_api'])
                                    for row in data['sources']))
    text = Path(__file__).with_name('common_think_script_contract.c.in').read_text()
    for name, value in values.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved script registry dependency')
    return text

def timed_colourmap_program(data, engine):
    core = (engine / 'openbor.c').read_text(encoding='latin-1')
    script = (engine / 'openborscript.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    update = function(core, 'update_animation')
    effects = function(core, 'checkdamageeffects')
    _, setters = switch_cases(script, 'openbor_changeentityproperty', 'propind', outermost=True)
    names = ('ent_set_colourmap', 'model_get_colourmap')
    if data['engine'] == '4432':
        expiry = braced_statement(update, 'if(self->maptime && time >= self->maptime)')
    else:
        expiry = re.search(r'(?m)^\s*(colorset_timed_expire\(self\);)', update)[1]
        names += ('colorset_timed_expire',)
    values = {
        'METHODS': '\n'.join(function(core, name) for name in names),
        'EXPIRY': expiry,
        'EFFECT_MACROS': '\n'.join(re.findall(r'(?m)^#define\s+_(?:remap|freeze|maptime)\b[^\n]+', effects)),
        'FORCED_MAP': braced_statement(effects, 'if(_remap > 0 && !_freeze)'),
        'INTEGER': function(variant, 'ScriptVariant_IntegerValue'),
        'MAPTIME_SETTER': setters['_ep_maptime']['body'],
        'ROWS': ','.join('{%du,%d}' % (row['revision'], row['clear_timer']) for row in data['sources']),
    }
    template = Path(__file__).with_name('timed_colourmap_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)


def ogg_configuration(template):
    """Configure the vendored Ogg integer types without host development headers."""
    values = dict(INCLUDE_INTTYPES_H='1', INCLUDE_STDINT_H='1', INCLUDE_SYS_TYPES_H='1',
                  SIZE16='int16_t', USIZE16='uint16_t', SIZE32='int32_t', USIZE32='uint32_t',
                  SIZE64='int64_t', USIZE64='uint64_t')
    for name, value in values.items():
        template = template.replace('@' + name + '@', value)
    if re.search(r'@[^@\n]+@', template):
        raise ValueError('Unresolved vendored Ogg configuration')
    return template


def native_output(code, data, *, extra_includes=(), extra_cflags=(), configure_ogg=False, libraries=(), engine_source=None):
    engine = Path(engine_source) if engine_source is not None else ROOT / 'src/engines' / data['engine']
    if not (engine/'openbor.h').is_file() or not (engine/'source/gamelib/types.h').is_file():
        raise ValueError('Selected native engine headers are unavailable')
    includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in
        sorted((engine / 'source').iterdir()) if p.is_dir()]
    for directory in extra_includes:
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError('Missing declared native dependency include directory')
        includes.append(directory)
    compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
    warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
        'clang' in Path(word).name for word in compiler) else []
    with tempfile.TemporaryDirectory(prefix='anybor-common-think-') as temporary:
        if configure_ogg:
            template = ROOT / 'src/deps/libogg/include/ogg/config_types.h.in'
            configured = Path(temporary) / 'include/ogg/config_types.h'
            configured.parent.mkdir(parents=True)
            configured.write_text(ogg_configuration(template.read_text()))
            includes.insert(0, configured.parent.parent)
        source = Path(temporary) / 'probe.c'
        binary = Path(temporary) / 'probe'
        source.write_text(code)
        subprocess.run(compiler + warnings + ['-std=gnu99', '-O2', '-fsigned-char',
            '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function',
            '-Wno-unused-parameter',
            '-Wno-error=deprecated-declarations', '-Wno-error=sign-compare',
            '-DOBOR_ENGINE_BUILD=' + data['engine'],
            '-DLIBRETRO=1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g', *extra_cflags,
            *('-I' + str(p) for p in includes), str(source), '-o', str(binary),
            *('-l' + library for library in libraries)],
            check=True, timeout=60)
        raw = subprocess.check_output([str(binary)], text=True, timeout=30,
                                      env=sanitizer_environment())
    return raw

class CommonThinkContracts(unittest.TestCase):
    def check_timed_colourmap(self, engine_id):
        data = load_contract_fixture(TIMED_COLOURMAP)
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        data = data | {'engine': engine_id, 'sources': rows}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        output = native_output(timed_colourmap_program(data, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_timed_colourmap(self):
        self.check_timed_colourmap('4432')

    def test_6391_timed_colourmap(self):
        self.check_timed_colourmap('6391')

    def test_6391_animation_range_arithmetic(self):
        data = load_contract_fixture(ANIMATION_RANGE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        names = ('obor_check_range_5134', 'check_range_target_all', 'check_range_target_base',
                 'check_range_target_x', 'check_range_target_y', 'check_range_target_z')
        cases = []
        for row in data['cases']:
            points = [','.join(float(n).hex() + 'f' for n in row[key]) for key in ('from', 'to')]
            bounds = [','.join(str(int(n)) for n in row[key]) for key in ('min', 'max')]
            cases.append('{%d,%d,' % (row['right'], row['present']) +
                         ','.join('{' + values + '}' for values in points + bounds) + '}')
        values = {
            'DECLARATIONS': '\n'.join('int ' + name + '(entity *,entity *,s_anim *);' for name in names[2:]) +
                            '\n' + '\n'.join(function(source, name) for name in names),
            'SET_RANGES': '\n    '.join(
                f'animation.range.{axis}.{limit} = input->{limit}[{i}];'
                for i, axis in enumerate(('x', 'y', 'z', 'base')) for limit in ('min', 'max')),
            'EVALUATE': 'check_range_target_all(origin, target, 0)',
            'PROFILES': ','.join(str(n) for n in revisions),
            'CASES': ',\n'.join(cases),
        }
        template = Path(__file__).with_name('animation_range_contract.c.in').read_text()
        program_text = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        result = native_output(program_text, data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',), libraries=('m',))
        expected = [dict(revision=row['revision'], results=data['contracts'][row['contract']])
                    for row in rows]
        self.assertEqual(json.loads(result), {'status': 'PASS', 'profiles': expected})

    def test_native_calls_visible_state_and_continuation_writes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        raw = native_output(program(data), data)
        actual = [json.loads(line) for line in raw.splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))

    def test_script_registry_names_and_integer_bridge(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual(len(data['script_callbacks']), 8)
        self.assertEqual(len({row['name'] for row in data['script_callbacks']}), 8)
        native_output(script_program(data), data)


if __name__ == '__main__':
    unittest.main()
