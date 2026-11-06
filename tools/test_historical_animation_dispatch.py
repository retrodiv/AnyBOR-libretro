"""Check animation script dispatch and generated guards by source profile.

Actual script lifecycle/dispatcher functions run with a bounded VM observer.
Generated source is inspected separately; this does not execute a complete VM.
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
from historical_frame_events import render_frame_services
from test_historical_player import function
from test_historical_script_context import program as context_program

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures')/'profile-animation-dispatch-contracts.json'


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [r['revision'] for r in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source animation dispatch coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                type(row['legacy_context']) is not bool or type(row['handle_type']) is not int or
                type(row['frame_interrupt']) is not bool or type(row['frame_cached']) is not bool or
                'script_without_animation_error' not in row or
                row.get('script_without_animation_error') is not None and (
                    not isinstance(row['script_without_animation_error'],str) or
                    not 0<len(row['script_without_animation_error'])<=512 or
                    any(not 32<=ord(c)<=126 for c in row['script_without_animation_error'])) or
                not 0 <= row['handle_type'] <= 2 or not re.fullmatch('[0-9a-f]{40}',row['commit']) or
                any(not re.fullmatch('[0-9a-f]{64}',s) for s in row['source_sha256'].values()) or
                not isinstance(row['cases'],list) or not 1 <= len(row['cases']) <= 32):
            raise ValueError('Explicit source identity and bounded dispatch contexts required')
        for case in row['cases']:
            if (set(case) != {'entity','model','default','same','null_models','mutation','callees','locals'} or
                    any(type(case[k]) is not int or not 0 <= case[k] <= 1
                        for k in ('entity','model','default','same','null_models','locals')) or
                    type(case['mutation']) is not int or not 0 <= case['mutation'] <= 2 or
                    not isinstance(case['callees'],list) or len(case['callees']) > 2 or
                    any(type(k) is not int or not 0 <= k <= 2 for k in case['callees'])):
                raise ValueError('Explicit initialized-script and callee observations required')
    return data


def dispatch_program(data):
    code = context_program(data)
    # This is an observer hook in the test's bounded VM provider. Candidate
    # dispatcher/lifecycle bodies remain intact.
    marker = 'HRESULT Interpreter_EvaluateImmediate(Interpreter *p) {'
    if code.count(marker) != 1 or code.count('int main(void) {') != 1:
        raise ValueError('Unique bounded VM provider and context entry point required')
    code = code.replace(marker, 'static int animation_fixture_active;\n'
        'static void observe_animation_call(Interpreter *);\n' + marker +
        '\n if(animation_fixture_active) observe_animation_call(p);')
    code = code.replace('int main(void) {','int historical_context_main(void) {')
    source = (ROOT/'src/engines/3741/openbor.c').read_text()
    native = (function(source,'obor_profile_animation_identity')
              if 'static LONG obor_profile_animation_identity(' in source else '')
    native += function(source,'execute_animation_script')
    cases = []
    for row in data:
        for case in row['cases']:
            values = [row['revision'],int(row['legacy_context']),row['handle_type']]
            values += [case[k] for k in ('entity','model','default','same','null_models','mutation','locals')]
            values += [len(case['callees']),*(case['callees']+[-1,-1])[:2]]
            cases.append('{'+','.join(map(str,values))+'}')
    tail = Path(__file__).with_name('animation_dispatch_contract.c.in').read_text()
    return code + tail.replace('@NATIVE@',native).replace('@CASES@',',\n'.join(cases))


def generator_program(data):
    source=(ROOT/'src/engines/3741/openbor.c').read_text()
    model=function(source,'load_cached_model')
    start=re.search(r'static const char(?:\*\s*|\s+)pre_text',model).start()
    constants=model[start:model.index('modelCommands cmd;',start)]
    script=model.split('case CMD_MODEL_AT_SCRIPT:',1)[1].split('case CMD_MODEL_AT_CMD:',1)[0]
    command=model.split('case CMD_MODEL_AT_CMD:',1)[1].split('default:',1)[0]
    helper=(function(source,'obor_profile_animation_identity')
            if 'static LONG obor_profile_animation_identity(' in source else '')
    template=Path(__file__).with_name('animation_guard_contract.c.in').read_text()
    cases=','.join('{%d,%d,%s}'%(r['revision'],r['handle_type'],
        'NULL' if r['script_without_animation_error'] is None else
        json.dumps(r['script_without_animation_error'])) for r in data)
    replacements={'@HELPER@':helper,'@APPEND@':function(source,'buffer_append'),
                  '@CONSTANTS@':constants,'@SCRIPT@':script,'@COMMAND@':command,'@CASES@':cases}
    for key,value in replacements.items():
        template=template.replace(key,value)
    return template


def allocation_program(data):
    source=(ROOT/'src/engines/3741/openbor.c').read_text()
    revisions=','.join(str(r['revision']) for r in data if r['handle_type']==2)
    if not revisions:
        raise ValueError('Native indexed-allocation controls required')
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
uint32_t obor_profile_build;
s_anim_list *anim_list;
int anims_loaded;
@ALLOC@
int main(void) {
 const unsigned revisions[]={@REVISIONS@};
 int expected_index=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i) {
  obor_profile_build=revisions[i];
  for(int count=0;count<3;++count) {
   s_anim *animation=alloc_anim();
   assert(animation && animation->index==expected_index++);
   assert(animation->numframes==0 && animation->animhits==0);
  }
  assert(anims_loaded==expected_index);
  while(anim_list) {
   s_anim_list *next=anim_list->next;
   free(anim_list->anim);free(anim_list);anim_list=next;
  }
 }
 return 0;
}
'''.replace('@ALLOC@',function(source,'alloc_anim')).replace('@REVISIONS@',revisions)


def interrupt_program(data):
    source=(ROOT/'src/engines/3741/openbor.c').read_text()
    native=function(source,'obor_profile_frame_unsummon')+function(source,'update_frame')
    cases=','.join('{%d,%d,%d}'%(r['revision'],r['frame_interrupt'],r['frame_cached']) for r in data)
    body=r'''
int main(void) {
 const struct {unsigned revision;int interrupt,cached;} cases[]={@CASES@};
 for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);++i) for(int mode=0;mode<3;++mode) {
  active_case=i*3u+(unsigned)mode;obor_profile_build=cases[i].revision;
  memset(&subject,0,sizeof(subject));memset(&other,0,sizeof(other));
  memset(&animation,0,sizeof(animation));memset(&replacement,0,sizeof(replacement));
  __typeof__(*animation.delay) delay[4]={10,10,10,10};
  __typeof__(*animation.spawnframe) spawnframe[1]={2};
  animation.numframes=4;animation.delay=delay;animation.spawnframe=spawnframe;animation.subentity=1;
  animation.flipframe=animation.jumpframe.f=animation.throwframe=animation.shootframe=animation.tossframe=-1;
  animation.quakeframe.framestart=-1;animation.unsummonframe=-1;
  subject.animation=&animation;subject.animpos=1;subject.animating=1;
  subject.nextanim=77;subject.modeldata.edelay.range_max=20;
  subject.modeldata.edelay.cap_max=20;subject.modeldata.edelay.mode=1;subject.modeldata.edelay.factor=1;
  self=&other;level=NULL;fixture_clock=100;interrupt_mode=mode;
  trace_count=0;memset(trace,0,sizeof(trace));
  update_frame(&subject,2);
  assert(self==&other && subject.animpos==(mode==2?3:2) && subject.nextanim==110);
  assert(subject.animation==(mode==1?&replacement:&animation));
  int stopped=mode && cases[i].interrupt;
  int spawned=!stopped && (mode!=1 || cases[i].cached);
  assert(trace_count==(spawned?2:1) && trace[0]==1);
  if(spawned) assert(trace[1]==2);
 }
 return 0;
}
'''.replace('@CASES@',cases)
    return render_frame_services(revision=3741)+native+body


class AnimationDispatchContracts(unittest.TestCase):
    def run_program(self, program):
        engine=ROOT/'src/engines/3741'
        includes=[ROOT/'src/port/libretro',engine,engine/'source'] + [
            p for p in sorted((engine/'source').iterdir()) if p.is_dir()]
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        warnings=['-Wno-pragma-pack'] if sys.platform=='darwin' or any(
            'clang' in Path(p).name for p in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-animation-dispatch-') as temporary:
            source=Path(temporary)/'contract.c';executable=Path(temporary)/'contract'
            source.write_text(program)
            subprocess.run(compiler+warnings+['-std=gnu99','-fsigned-char','-Wall','-Wextra','-Werror',
                '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
                '-Wno-error=deprecated-declarations','-DOBOR_ENGINE_BUILD=3741','-DLIBRETRO=1',
                '-fsanitize=address,undefined','-g',*('-I'+str(p) for p in includes),
                str(source),'-lm','-o',str(executable)],check=True,timeout=45)
            subprocess.run([str(executable)],cwd=temporary,env=sanitizer_environment(),
                           check=True,timeout=30)

    def test_dispatch_order_context_locals_and_shared_references(self):
        self.run_program(dispatch_program(rows()))

    def test_generated_script_and_command_guards_match_runtime_identity(self):
        self.run_program(generator_program(rows()))

    def test_indexed_animation_allocation_by_profile(self):
        self.run_program(allocation_program(rows()))

    def test_frame_continuation_after_animation_or_position_change(self):
        self.run_program(interrupt_program(rows()))


if __name__ == '__main__':
    unittest.main()
