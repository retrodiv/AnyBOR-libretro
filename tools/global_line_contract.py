"""Run native global configuration readers against source-bound line oracles.

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

from contract_fixtures import load_contract_fixture, contract_profiles
from native_sanitizers import sanitizer_environment
from test_historical_player import function


def check_global_lines(root, fixture_path):
    fixture = load_contract_fixture(fixture_path)
    rows, cases = fixture['sources'], fixture['cases']
    revisions = [row['revision'] for row in rows]
    if (not rows or len(revisions) != len(set(revisions)) or len(rows) > 256 or
            not 1 <= len(cases) <= 96):
        raise ValueError('Unique bounded line-reader contexts and cases required')
    for row in rows:
        if (row['engine'] != fixture['engine'] or type(row['revision']) is not int or
                row['revision'] <= 0 or not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not row['source_sha256'] or any(not re.fullmatch('[0-9a-f]{64}', value)
                    for value in row['source_sha256'].values()) or
                type(row['contract']) is not int or not 0 <= row['contract'] < len(fixture['expected'])):
            raise ValueError('Bound source identities and line-reader contract required')
    pin = json.loads((root / 'src/pin.json').read_text())
    for profile in contract_profiles(fixture, pin['profiles']):
        revision = int(profile.get('revision', profile['build']))
        if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
            if revision not in revisions:
                raise ValueError('Registered profile lacks its line-reader oracle')
    for case in cases:
        if (set(case) != {'name', 'reader', 'text', 'present'} or
                case['reader'] not in (0, 1, 2) or type(case['present']) is not int or
                case['present'] not in (0, 1) or not isinstance(case['text'], str) or
                len(case['text'].encode()) > 2048 or '\0' in case['text']):
            raise ValueError('Bounded configuration text required')
    engine = root / 'src/engines' / fixture['engine']
    text = (engine / 'openbor.c').read_text()
    loader = function(text, 'load_models')
    start = loader.index('while(pos<size) // peek global settings')
    end = loader.index('// calculate max animations', start)
    replacements = dict(
        LOWERCASE=function((engine / 'source/utils.c').read_text(), 'lc'),
        NEWLINE=function((engine / 'source/utils.c').read_text(), 'getNewLineStart'),
        LIST_C=json.dumps(str(engine / 'source/scriptlib/List.c')),
        COMMANDS_C=json.dumps(str(engine / 'source/gamelib/commands.c')),
        PARSERS='\n'.join(function(text, name) for name in
            ('isNumeric', 'getValidInt', 'getValidFloat', 'ParseArgs')),
        MACROS='\n'.join(re.search(r'(?m)^#define ' + name + r'\(z\)[^\r\n]*', text)[0]
            for name in ('GET_ARG', 'GET_INT_ARG', 'GET_FLOAT_ARG')),
        LIFEBAR=function(text, 'lifebar_colors'),
        SCRIPT=function(text, 'load_script_setting'),
        MODELS=loader[start:end],
        CASES=',\n'.join('{%d,%d,%s}' % (row['reader'], row['present'], json.dumps(row['text']))
            for row in cases),
        PROFILES=','.join(str(row['revision']) + 'u' for row in rows))
    program = Path(__file__).with_name('global_line_contract.c.in').read_text()
    for key, value in replacements.items():
        program = program.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', program):
        raise ValueError('Unresolved native line-reader dependency')
    includes = [engine, root / 'src/port/libretro', root / 'src/glue', engine / 'source',
                *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
    compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
    clang = sys.platform == 'darwin' or any('clang' in Path(word).name for word in compiler)
    flags = ['-Wno-pragma-pack'] if clang else []
    flags += ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-DLINUX=1', '-Wl,--gc-sections']
    with tempfile.TemporaryDirectory(prefix='anybor-global-lines-') as temporary:
        source, executable = Path(temporary) / 'probe.c', Path(temporary) / 'probe'
        source.write_text(program)
        subprocess.run(compiler + ['-std=gnu11', '-fsigned-char', '-Wall', '-Wextra', '-Werror',
            '-Wno-error=deprecated-declarations', '-Wno-unused-variable', '-Wno-unused-function',
            '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-int-to-pointer-cast',
            '-Wno-implicit-fallthrough',
            '-ffunction-sections', '-fdata-sections', '-DLIBRETRO=1',
            '-DOBOR_ENGINE_BUILD=' + fixture['engine'], '-g', '-fsanitize=address,undefined',
            *flags, *('-I' + str(p) for p in includes), str(source), '-o', str(executable)],
            check=True, timeout=60)
        output = subprocess.check_output([str(executable)], text=True, timeout=30,
                                         env=sanitizer_environment())
    observations = [json.loads(line) for line in output.splitlines()]
    if len(observations) != len(rows) * len(cases):
        raise AssertionError('Incomplete native line-reader output')
    for i, actual in enumerate(observations):
        row, case_index = rows[i // len(cases)], i % len(cases)
        expected = fixture['expected'][row['contract']][case_index]
        if actual != {'revision': row['revision'], 'case': case_index, **expected}:
            raise AssertionError('Line reader mismatch revision=%d case=%s: %r != %r' %
                (row['revision'], cases[case_index]['name'], actual, expected))
