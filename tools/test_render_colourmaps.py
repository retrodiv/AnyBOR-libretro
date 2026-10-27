"""Check native rendering colourmap choice for every declared source context.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from historical_render_colourmaps import extract_render_colourmaps,render_colourmap_selection
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/render-colourmap-contracts.json'


def profile_program(code):
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded map-selection entry point required')
    code=code.replace(marker,'''int main(int argc,char **argv){
 (void)revisions;
 CHECK(argc==2,"profile argument");char *end=NULL;unsigned long selected=strtoul(argv[1],&end,10);
 CHECK(end && !*end && selected>0 && selected<=UINT32_MAX,"profile revision");
''')
    return code.replace('obor_profile_build=revisions[context];','obor_profile_build=(uint32_t)selected;')


class RenderColourmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FIXTURE.read_text());cls.rows=cls.fixture['sources']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text());cls.contexts={row['revision']:row for row in cls.rows}
        engine=SOURCE/'src/engines/3741';text=(engine/'openbor.c').read_text()
        parts=extract_render_colourmaps({name:function(text,name)for name in
            ['predrawstatus','display_ents','common_lie','checkdamageeffects']})
        helper=function(text,'model_get_colourmap')
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        temp=tempfile.TemporaryDirectory(prefix='anybor-render-colourmaps-');cls.addClassCleanup(temp.cleanup)
        work=Path(temp.name);cls.executables={};cls.group_for={};cls.counts={}
        for row in cls.rows:
            key=json.dumps({name:row[name]for name in ['counter','fixed_limit','policy','models','zero_defined']},sort_keys=True)
            cls.group_for[row['revision']]=key
            if key in cls.executables:continue
            lookups=[lookup|dict(zero_defined=row['zero_defined'][lookup['name']])for lookup in parts['lookups']]
            code=render_colourmap_selection(revisions=[row['revision']],lookups=lookups,
                ko_block=parts['ko_block'],helper=helper,counter=row['counter'],fixed_table=False,
                fixed_limit=row['fixed_limit'],policy=row['policy'],models=row['models'],mode='all')
            source=work/(str(len(cls.executables))+'.c');source.write_text(profile_program(code));binary=source.with_suffix('')
            compile_checked(compiler+['-std=gnu11','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-error=sign-compare','-fsigned-char',
                '-O0','-g','-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                str(source),'-o',str(binary)])
            cls.executables[key]=binary
            cls.counts[key]=6+sum((len(lookups)+4)*model['slots']+sum(x['zero_defined']for x in lookups)
                                 for model in row['models'])

    def check_context(self,revision):
        key=self.group_for[revision];result=subprocess.check_output([str(self.executables[key]),str(revision)],
            text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(result),dict(status='PASS',contexts=1,cases=self.counts[key]))

    def test_fixture_and_registered_sources_have_explicit_contexts(self):
        self.assertEqual(len(self.rows),len(self.contexts))
        for profile in self.pin['profiles']:
            if profile['engine']=='3741':self.assertIn(int(profile.get('revision',profile['build'])),self.contexts)
        for row in self.rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['ko_block_sha256'],r'^[0-9a-f]{64}$')
            self.assertEqual(set(row['lookup_sha256']),set(row['zero_defined']))
            for value in row['lookup_sha256'].values():self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_every_own_source_context_preserves_selection_and_ko_predicate(self):
        for row in self.rows:
            with self.subTest(profile=row['revision']):self.check_context(row['revision'])

    def test_every_registered_context_preserves_selection_and_bounded_results(self):
        for profile in self.pin['profiles']:
            if profile['engine']=='3741':
                with self.subTest(profile=profile['build']):
                    self.check_context(int(profile.get('revision',profile['build'])))


if __name__=='__main__':unittest.main()
