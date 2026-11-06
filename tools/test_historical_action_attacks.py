"""Check native rise/block attacks and grab release/vault call ordering.

Providers observe call context; animation, pain and delegated AI internals
remain separate contracts. Only defined type/animation selections execute.
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

from contract_fixtures import load_contract_fixture, contract_revisions, contract_profiles
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-action-attack-contracts.json'


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    table = re.search(r'(?ms)^int[ \t]+grab_attacks\[5\]\[2\]\s*=\s*\{.*?\};', core)
    if table is None:
        raise ValueError('Missing native grab animation table')
    parts = {
        'FUNCTIONS': '\n'.join(
            ('#define dograbattack observed_grab_attack\n' + function(core, name) +
             '\n#undef dograbattack\n') if name == 'common_grab_check' else
            function(core, name) for name in data['functions']),
        'UNLINK': function(core, 'ent_unlink'),
        'GRAB_TABLE': table[0],
        'PROFILES': ','.join(str(row['revision']) + 'u' for row in data['sources']),
        'CASES': ',\n'.join('{%s}' % ','.join(str(row[k]) for k in data['parameters'])
                            for row in data['cases'])}
    text = Path(__file__).with_name('action_attack_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack caller dependency')
    return text


class ActionAttackContracts(unittest.TestCase):
    def test_native_calls_visible_state_and_continuation_writes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        engine = ROOT / 'src/engines' / data['engine']
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in
            sorted((engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-action-attacks-') as temporary:
            source = Path(temporary) / 'probe.c'
            binary = Path(temporary) / 'probe'
            source.write_text(program(data))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-O2', '-fsigned-char',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=' + data['engine'],
                '-DLIBRETRO=1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in includes), str(source), '-o', str(binary)],
                check=True, timeout=60)
            raw = subprocess.check_output([str(binary)], text=True, timeout=30,
                                          env=sanitizer_environment())
        actual = [json.loads(line) for line in raw.splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))




def callback_program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    initialize = function(core, 'ent_default_init')
    marker = 'if(time && level->spawn[(int)e->playerindex][2] > e->a)'
    start = initialize.index(marker)
    end = initialize.index('if(time && e->modeldata.makeinv)', start)
    spawn = initialize[start:end].rstrip()
    # Preserve the complete inner conditional; the trailing brace closes its caller.
    if not spawn.endswith('}\n\t\t\t}'):
        raise ValueError('Native spawn-drop section must end at its parent branch')
    spawn = spawn[:spawn.rfind('}')]
    attack = function(core, 'do_attack')
    start = attack.index('self->takeaction = common_block;')
    line = attack.rfind('\n', 0, start) + 1
    end = attack.index('execute_didblock_script', start)
    block = attack[line:end]
    default = re.search(r'const\s+s_defense\s+default_defense\s*=\s*\{[^}]*\};', core)
    if default is None:
        raise ValueError('Native defense default required')
    helpers = default[0] + '\n' + function(core, 'obor_combat_defense')
    if 'static u32 obor_profile_pain_deadline(' in core:
        helpers += '\n' + function(core, 'obor_profile_pain_deadline')
    text = Path(__file__).with_name('action_callback_contract.c.in').read_text()
    replacements = dict(HELPERS=helpers, OPPONENT=function(core, 'set_opponent'),
        DAMAGE=function(core, 'common_takedamage'), SPAWN=spawn, BLOCK=block,
        PROFILES=',\n'.join('{%du,%d}' % (row['revision'], row['action_before_callback'])
                             for row in data['sources']))
    for key, value in replacements.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native callback dependency')
    return re.sub(r'(?m)^[ \t]+', lambda match: match[0].expandtabs(4), text)


class ActionCallbackContracts(unittest.TestCase):
    def test_native_callbacks_see_original_action_and_time_order(self):
        from test_historical_common_think import native_output
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-action-callback-contracts.json')
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(span['engine'] == profile['engine'] and span['first'] <= revision <= span['last']
                   for span in data['coverage']):
                self.assertIn(revision, revisions)
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
        result = json.loads(native_output(callback_program(data), data))
        self.assertEqual(result, dict(contexts=len(revisions), cases=16*len(revisions)))
        print(json.dumps(result), file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
