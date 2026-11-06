"""Check source-defined early AI caller decisions and state publication.

Complete native caller/distance functions execute; target, pick, probability,
random samples, enumeration and idle callbacks are observed providers.
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-early-normal-attack-contracts.json'
INPUTS = ('clock', 'nextattack', 'stalltime', 'combotime', 'combo', 'supplied', 'target',
          'valid', 'weapon', 'energy', 'pick', 'vulnerable', 'drop', 'attacking', 'rising',
          'aggression', 'probability', 'entity_count', 'mutate', 'distance')
OUTPUTS = ('result', 'nextattack', 'stalltime', 'action', 'prepared', 'aggression')


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source early caller coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or not row['source_sha256'] or
                any(not re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values()) or
                not isinstance(row['cases'], list) or not 1 <= len(row['cases']) <= 128):
            raise ValueError('Bound own-source identities and bounded caller cases required')
        for c in row['cases']:
            if (set(c) != {'name', 'inputs', 'random', 'floats', 'expected'} or
                    not isinstance(c['name'], str) or not 0 < len(c['name']) <= 96 or
                    set(c['inputs']) != set(INPUTS) or
                    set(c['expected']) != set(OUTPUTS) | {'trace'} or
                    any(type(c['inputs'][k]) is not int or not -32768 <= c['inputs'][k] <= 0xffffffff
                        for k in INPUTS) or
                    any(type(c['expected'][k]) is not int or not -32768 <= c['expected'][k] <= 0xffffffff
                        for k in OUTPUTS) or
                    not isinstance(c['random'], list) or not 0 <= len(c['random']) <= 4 or
                    any(type(v) is not int or not 0 <= v <= 0x7fffffff for v in c['random']) or
                    not isinstance(c['floats'], list) or not 0 <= len(c['floats']) <= 2 or
                    any(not isinstance(pair, list) or len(pair) != 2 or
                        any(type(v) not in (int, float) for v in pair) or
                        not 0 <= pair[1] <= pair[0] <= 10000 for pair in c['floats']) or
                    not isinstance(c['expected']['trace'], str) or
                    not re.fullmatch(r'[A-Z0-9:;.\-]{0,2048}', c['expected']['trace'])):
                raise ValueError('Explicit bounded caller state and ordered observations required')
    return data


def program(data):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    entries = []
    for row in data:
        for c in row['cases']:
            inputs = [str(c['inputs'][k]) + ('u' if k in
                ('clock', 'nextattack', 'stalltime', 'combotime') else '') for k in INPUTS]
            outputs = [str(c['expected'][k]) + ('u' if k in ('nextattack', 'stalltime') else '')
                       for k in OUTPUTS]
            floats = ['{' + ','.join(float(v).hex() + 'f' for v in pair) + '}' for pair in c['floats']]
            entries.append('{%du,%s,%s,%s,%s,%d,{%s},%d,{%s}}' % (
                row['revision'], json.dumps(c['name']), ','.join(inputs), ','.join(outputs),
                json.dumps(c['expected']['trace']), len(c['random']),
                ','.join(map(str, c['random'])) or '0', len(floats), ','.join(floats) or '{0,0}'))
    return Path(__file__).with_name('early_normal_attack_contract.c.in').read_text().replace(
        '@DISTANCE@', function(source, 'diff')).replace(
        '@CALLER@', function(source, 'common_try_normalattack')).replace('@CASES@', ',\n'.join(entries))


class EarlyNormalAttackContracts(unittest.TestCase):
    def test_target_wait_probability_and_idle_callback_order(self):
        engine = ROOT / 'src/engines/3741'
        paths = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-early-normal-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(rows()))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-Wall', '-Wextra',
                '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-g', *('-I' + str(p) for p in paths),
                str(source), '-lm', '-o', str(executable)], check=True, timeout=45)
            subprocess.run([str(executable)], check=True, timeout=30, env=sanitizer_environment())




def early_jump_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    keys = ('available','supplied','found','vulnerable','drop','attacking','direction',
            'distance','aggression','probability','dust','spawn','mutate')
    inputs = []
    for row in data['cases']:
        a = row['inputs']
        inputs.append('{%s,%du,%d,%d,%s}' % (','.join(str(a[k]) for k in keys),
            a['timer'], a['word'], a['bit'], float(a['sample']).hex()+'f'))
    matrices = []
    for group in data['expected']:
        entries = []
        for row in group:
            events = ['{%s,%s,%s}' % (','.join(str(x) for x in event[:4]),
                float(event[4]).hex()+'f', float(event[5]).hex()+'f') for event in row['events']]
            entries.append('{%d,%d,%d,%du,%s,%s,%d,{%s},%d,%d,{%s}}' % (
                row['result'],row['action'],row['animation'],row['timer'],
                float(row['x']).hex()+'f',float(row['z']).hex()+'f',len(row['random']),
                ','.join(str(v) for v in row['random']) or '0',row['floats'],
                len(events),','.join(events) or '{0}'))
        matrices.append('{'+',\n'.join(entries)+'}')
    profiles = []
    for row in data['sources']:
        contract = data['contracts'][row['contract']]
        profiles.append('{%du,%d,%d,%s}' % (row['revision'],row['contract'],
            contract['autokill'],float(contract['minimum']).hex()+'f'))
    text = Path(__file__).with_name('early_jump_contract.c.in').read_text()
    for key,value in dict(INPUTS=',\n'.join(inputs),EXPECTED=',\n'.join(matrices),
            PROFILES=',\n'.join(profiles),DISTANCE=function(source,'diff'),
            CALLER=function(source,'common_try_jumpattack')).items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved early jump dependency')
    return re.sub(r'(?m)^[ \t]+',lambda m:m[0].expandtabs(4),text)


def early_grab_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    move = function(source,'common_trymove')
    a = move.index('//------------------ grab/throw checking')
    a = move.index('if(',a)
    z = move.index('// ---------------  end of grab/throw checking',a)
    inputs = ['{%s}' % ','.join(str(row['inputs'][k]) for k in
        ('available','idling','found','can_grab','adjust','word','wait','mutate')) for row in data['cases']]
    matrices = []
    for group in data['expected']:
        entries = []
        for row in group:
            events = ['{%d,{%s}}' % (event[0],','.join(str(v) for v in event[1])) for event in row['events']]
            entries.append('{%d,%d,{%s},%d,{%s}}' % (row['result'],row['rands'],
                ','.join(str(v) for v in row['final']),len(events),','.join(events) or '{0}'))
        matrices.append('{'+',\n'.join(entries)+'}')
    text = Path(__file__).with_name('early_grab_contract.c.in').read_text()
    replacements = dict(INPUTS=',\n'.join(inputs),EXPECTED=',\n'.join(matrices),
        PROFILES=',\n'.join('{%du,%d}' % (row['revision'],row['contract']) for row in data['sources']),
        LINKS='\n'.join(function(source,n) for n in ('ent_unlink','ents_link','set_opponent')),
        GRAB=function(source,'trygrab'),SELECTOR=move[a:z])
    for key,value in replacements.items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved early grab dependency')
    return re.sub(r'(?m)^[ \t]+',lambda m:m[0].expandtabs(4),text)


class EarlyJumpMovementContracts(unittest.TestCase):
    def test_complete_jump_caller_and_callback_order(self):
        self.check_contract('profile-early-jump-contracts.json',early_jump_program)

    def test_grab_selection_and_complete_grab_callback_order(self):
        self.check_contract('profile-early-grab-contracts.json',early_grab_program)

    def check_contract(self,name,render):
        from test_historical_common_think import native_output
        data = load_contract_fixture(Path(__file__).parent/'fixtures'/name)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual(revisions,contract_revisions(data,data['expected_revisions']))
        for profile in contract_profiles(data,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if any(span['engine']==profile['engine'] and span['first']<=revision<=span['last'] for span in data['coverage']):
                self.assertIn(revision,revisions)
        result = json.loads(native_output(render(data),data))
        self.assertEqual(result,dict(contexts=len(revisions),cases=len(revisions)*len(data['cases'])))
        print(json.dumps(dict(fixture=name,**result)),file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
