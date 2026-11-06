"""Check source-defined automatic animation groups and their selector effect.

Exact name branches and the complete selector run with native records. Other
model-loading work and frame execution remain outside this focused contract.
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

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).with_name('fixtures')/'profile-animation-default-groups.json'
NAMES=('idle','walk','up','down','backwalk','grabwalk','grabwalkup','grabwalkdown',
       'grabbackwalk','grabbedwalk','grabbedwalkup','grabbedwalkdown','grabbedbackwalk')
GROUPS={'-1','ANI_WALK','ANI_GRABWALK','ANI_GRABBEDWALK'}


def branches(source):
    """Keep each selected condition/body byte-for-byte, using the C tokenizer."""
    command=source.split('case CMD_MODEL_ANIM:',1)[1].split('case CMD_MODEL_LOOP:',1)[0]
    selected={}
    for name in NAMES:
        matches=list(re.finditer(r'(?m)^[ \t]*(?:else[ \t]+)?if\(str(?:n)?icmp\(value,\s*"'+name+r'"',command))
        if len(matches)!=1:
            raise ValueError('Unique animation name branch required: '+name)
        first=matches[0].start();brace=command.index('{',matches[0].end())
        # The existing function extractor balances the original C body and
        # ignores braces in data. Only its synthetic signature is discarded.
        prefix='void selected_branch(void)'
        body=function(prefix+command[brace:],'selected_branch')[len(prefix):].rstrip('\n')
        selected[name]=command[first:brace]+body
    return command,selected


def rows():
    fixture=load_contract_fixture(FIXTURE);data=fixture['sources']
    revisions=[r['revision'] for r in data]
    if (len(set(revisions))!=len(data) or
            set(revisions)!=contract_revisions(fixture,fixture['expected_revisions']) or
            not set(fixture['boundary_controls'])<=set(revisions)):
        raise ValueError('Own-source default-group coverage differs')
    for row in data:
        if (row['engine']!='3741' or type(row['revision'])is not int or row['revision']<=0 or
                type(row['sync_available'])is not bool or type(row['sync_mode'])is not int or
                not 0<=row['sync_mode']<=3 or not re.fullmatch('[0-9a-f]{40}',row['commit']) or
                set(row['groups'])!=set(NAMES) or any(v not in GROUPS for v in row['groups'].values()) or
                any(not re.fullmatch('[0-9a-f]{64}',v) for v in row['source_sha256'].values())):
            raise ValueError('Explicit native group and source identities required')
    return data


def program(data,*,perturb=False):
    source=(ROOT/'src/engines/3741/openbor.c').read_text();command,parts=branches(source)
    initialize=re.search(r'newanim->sync\s*=\s*-1\s*;',command)
    if initialize is None:
        raise ValueError('Native default synchronization initializer required')
    native='\n'.join(parts[name] for name in NAMES)
    if perturb:
        marker='newanim->sync = ANI_GRABWALK;'
        if native.count(marker)!=4:
            raise ValueError('Four native grab-walk assignments required for the observation control')
        native=native.replace(marker,'newanim->sync = ANI_WALK;',1)
    cases=[]
    for row in data:
        for name in NAMES:
            for query in (name,name.upper()):
                cases.append('{%d,%d,%d,%s,%s}'%(row['revision'],row['sync_available'],
                    row['sync_mode'],json.dumps(query),row['groups'][name]))
    template=Path(__file__).with_name('animation_default_groups.c.in').read_text()
    return template.replace('@INITIALIZE@',initialize[0]).replace('@BRANCHES@',native).replace(
        '@SELECTOR@',function(source,'ent_set_anim')).replace('@CASES@',',\n'.join(cases))


class AnimationDefaultGroups(unittest.TestCase):
    def run_program(self,code,*,refusal=False):
        engine=ROOT/'src/engines/3741'
        includes=[ROOT/'src/port/libretro',engine,engine/'source']+[
            p for p in sorted((engine/'source').iterdir()) if p.is_dir()]
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        warnings=['-Wno-pragma-pack'] if sys.platform=='darwin' or any(
            'clang' in Path(p).name for p in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-animation-default-groups-') as temporary:
            path=Path(temporary)/'contract.c';executable=Path(temporary)/'contract';path.write_text(code)
            subprocess.run(compiler+warnings+['-std=gnu99','-fsigned-char','-Wall','-Wextra','-Werror',
                '-Wno-unused-function','-Wno-unused-variable','-Wno-error=deprecated-declarations',
                '-DOBOR_ENGINE_BUILD=3741','-DLIBRETRO=1','-fsanitize=address,undefined','-g',
                *('-I'+str(p) for p in includes),str(path),'-o',str(executable)],check=True,timeout=45)
            result=subprocess.run([str(executable)],env=sanitizer_environment(),capture_output=True,
                                  text=True,timeout=30)
            if refusal:
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Animation default mismatch',result.stderr)
            else:
                self.assertEqual(result.returncode,0,result.stderr)

    def test_name_groups_and_effective_synchronization_by_profile(self):
        self.run_program(program(rows()))

    def test_changed_retained_group_is_rejected(self):
        self.run_program(program(rows(),perturb=True),refusal=True)


if __name__=='__main__':
    unittest.main()
