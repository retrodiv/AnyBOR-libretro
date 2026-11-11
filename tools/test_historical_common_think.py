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
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-common-think-contracts.json'


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


def native_output(code, data, *, extra_includes=(), configure_ogg=False):
    engine = ROOT / 'src/engines' / data['engine']
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
            '-DLIBRETRO=1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
            *('-I' + str(p) for p in includes), str(source), '-o', str(binary)],
            check=True, timeout=60)
        raw = subprocess.check_output([str(binary)], text=True, timeout=30,
                                      env=sanitizer_environment())
    return raw

class CommonThinkContracts(unittest.TestCase):
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
