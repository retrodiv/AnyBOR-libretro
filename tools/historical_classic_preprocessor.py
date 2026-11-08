"""Check macro argument admission, whitespace and directive position.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
from native_allocation_policy import bind_named_allocation_support
from native_sanitizers import sanitizer_environment

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


def check_contract(self, fixture_name='profile-classic-preprocessor.json'):
    data = load_contract_fixture(Path(__file__).parent / 'fixtures' / fixture_name)
    revisions = [row['revision'] for row in data['sources']]
    self.assertEqual(len(revisions), len(set(revisions)))
    self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
    registered = contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles'])
    self.assertTrue({int(row.get('revision', row['build'])) for row in registered
                     if row['engine'] == data['engine']} <= set(revisions))
    checks = []
    for row in data['sources']:
        for index, case in enumerate(data['cases']):
            expected = case['old' if row['old_arguments'] else 'later']
            checks.append('check(%du,%du,%s,%d,%s,%s,%s);' % (
                row['revision'], index, json.dumps(case['source']), expected['accepted'],
                json.dumps('|'.join(expected['tokens'])), json.dumps(expected['diagnostic']),
                json.dumps(expected.get('exact', ''))))
    engine = ROOT / 'src/engines' / data['engine']
    text = Path(__file__).with_name('classic_preprocessor_contract.c.in').read_text()
    text = text.replace('@CHECKS@', '\n'.join(checks))
    text = bind_named_allocation_support(text, engine)
    pp, script = engine / 'source/preprocessorlib', engine / 'source/scriptlib'
    with tempfile.TemporaryDirectory(prefix='classic-preprocessor-') as name:
        path = Path(name); unit = path / 'probe.c'; binary = path / 'probe'
        unit.write_text(text)
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
            '-std=gnu99', '-O1', '-g', '-fcommon', '-ffunction-sections', '-fdata-sections',
            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-DPP_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
            '-Wno-deprecated-declarations', '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast',
            '-DOBOR_ENGINE_BUILD=' + data['engine'],
            *('-I' + str(p) for p in (pp, script, engine / 'source',
                                     engine / 'source/gamelib', ROOT / 'src/port/libretro')),
            str(unit), str(pp / 'pp_parser.c'), str(pp / 'pp_lexer.c'),
            str(pp / 'pp_expr.c'), str(script / 'List.c'), *links, '-o', str(binary)]
        subprocess.run(command, check=True, timeout=60)
        output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                         env=sanitizer_environment())
    self.assertEqual(json.loads(output), dict(contexts=len(revisions),
                     cases=len(revisions) * len(data['cases']), status='PASS'))
