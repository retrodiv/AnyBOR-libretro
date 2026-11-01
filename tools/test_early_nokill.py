"""Check source-defined no-kill attacks, callback order and property indices.

Native command/list/variant units run with the actual attack record, getter
case, mapper window and damage function. Model arguments, animations and script
callbacks are controlled providers; complete model loading/gameplay is separate.
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

from contract_fixtures import contract_profiles, load_contract_fixture
from native_allocation_policy import bind_named_allocation_support
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_early_entity_namespaces import namespace_descriptor
from test_early_system_callbacks import block
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-nokill.json'


class EarlyNoKillTests(unittest.TestCase):
    def test_registry_and_source_controls(self):
        fixture = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in fixture['sources']:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['names']), len(row['getters']))
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_native_command_properties_damage_and_callbacks(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        header = (engine / 'openbor.h').read_text()
        record = re.search(r'typedef struct\s*\{[^{}]*\}\s*s_attack;', header)
        self.assertIsNotNone(record)
        enum = re.search(r'enum gep_attack_enum\s*\{[^}]*\};', script)
        self.assertIsNotNone(enum)
        first = script.index('/* Source-owned attack property namespaces. */')
        last = script.index('/* End source-owned attack property namespaces. */', first)
        namespaces = script[first:last]
        mapper = function(script, 'mapstrings_getentityproperty')
        first = mapper.index('if((varlist[1]->vt == VT_INTEGER) && (obor_property == _gep_attack))')
        mapping = block(mapper, first)
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', script)
        self.assertIsNotNone(macro)
        unused, getter_cases = switch_cases(script, 'openbor_getentityproperty', 'propind')
        loader = function(core, 'load_cached_model').replace('switch(cmd)', 'switch(model_command)', 1)
        unused, model_cases = switch_cases(loader, 'load_cached_model', 'model_command')
        first = core.index('const s_attack emptyattack = {')
        last = core.index('\n};', first) + len('\n};')
        constant = core[first:last]
        pit = re.search(r'(?m)^#define\s+PIT_DEPTH\s+[^\n]+', header)
        self.assertIsNotNone(pit)
        arrays, checks = [], []
        for row in fixture['sources']:
            entries = []
            for name, expected in zip(row['names'], row['getters']):
                entries.append('{%s,%d,%d,%.17g}' % (json.dumps(name), expected['kind'],
                               expected.get('integer', 0), expected.get('decimal', 0)))
            label = 'properties_' + str(row['revision'])
            arrays.append('static const property_case %s[]={%s};' % (label, ','.join(entries)))
            checks.append('check(%d,%d,%s,sizeof(%s)/sizeof(*%s));' %
                          (row['revision'], row['nokill'], label, label, label))
        assignments = []
        for name, value in fixture['sample_fields'].items():
            assignments.append('attack.%s=%s;' % (name, json.dumps(value)))
        damage = []
        for case in fixture['damage_cases']:
            damage.append('{%s,{%s},{%s}}' % (','.join(str(case[k]) for k in
                ('health', 'maximum', 'force', 'flag', 'invincible', 'pit', 'expired', 'broken_guard',
                 'offense', 'defense', 'projectile', 'landing_self', 'effective_force')),
                ','.join(str(v) for v in case['old']), ','.join(str(v) for v in case['new'])))
        code = (FIXTURE.parent / 'early_nokill.c').read_text()
        values = dict(RECORD=record[0], ENUM=enum[0], NAMESPACES=namespaces,
            DESCRIPTOR=namespace_descriptor(script, 'obor_property_namespace'), MACRO=macro[0],
            SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'), MAPPING=mapping,
            QUERY=getter_cases['_gep_attack']['body'], SETTER=model_cases['CMD_MODEL_NOKILL']['body'],
            DAMAGE=function(core, 'checkdamage'), EMPTY=constant, PIT=pit[0],
            LOWER=function((engine / 'source/utils.c').read_text(), 'lc'),
            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks),
            INITIALIZE='\n'.join(assignments), DAMAGE_CASES=',\n'.join(damage))
        for key, value in values.items():
            code = code.replace('@' + key + '@', value)
        code = bind_named_allocation_support(code, engine)
        with tempfile.TemporaryDirectory(prefix='early-nokill-') as directory:
            source, binary = Path(directory) / 'probe.c', Path(directory) / 'probe'
            source.write_text(code)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            includes = [engine, engine / 'source', ROOT / 'src/port/libretro',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            flags = ['-std=gnu11', '-O0', '-g', '-fcommon', '-fsigned-char',
                     '-fno-omit-frame-pointer', '-ffunction-sections', '-fdata-sections',
                     '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + fixture['engine'],
                     '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                     *['-I' + str(p) for p in includes]]
            objects = []
            for i, unit in enumerate(('source/scriptlib/List.c', 'source/scriptlib/ScriptVariant.c',
                                      'source/gamelib/commands.c')):
                obj = Path(directory) / ('native-%d.o' % i)
                compile_checked(compiler + flags + ['-Wno-deprecated-declarations', '-c', str(engine / unit), '-o', str(obj)])
                objects.append(str(obj))
            warnings = ['-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                        '-Wno-error=sign-compare', '-Wno-missing-field-initializers']
            if sys.platform == 'darwin':
                warnings.append('-Wno-error=pragma-pack')
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            compile_checked(compiler + flags + warnings + [str(source), *objects, *links, '-lm', '-o', str(binary)])
            result = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30,
                                    env=sanitizer_environment())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('early_nokill=1', result.stdout)


if __name__ == '__main__':
    unittest.main()
