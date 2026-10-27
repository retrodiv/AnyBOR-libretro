"""Check native text collection/count fields and missing script entries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_text_collection import render_text_collection
from native_sanitizers import sanitizer_environment
from test_historical_player import function
from test_color_blends import compile_checked

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))


class TextCollectionPropertyTests(unittest.TestCase):
    def test_native_results_owner_selection_and_missing_entries(self):
        fixture=load_contract_fixture(Path(__file__).with_name('fixtures').joinpath('text-collection-contracts.json'))
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        cc=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))
        version=subprocess.check_output(cc+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype'] if 'clang'in version.lower() else []
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        link=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        for model in fixture['models']:
            with self.subTest(model=model['id']),tempfile.TemporaryDirectory(prefix='text-collection-') as temporary:
                engine=model['engine'];root=SOURCE/'src/engines'/engine
                covered={row['profile']for row in model['original_sources']}
                self.assertTrue({p['build']for p in contract_profiles(fixture, pin['profiles'])if p['engine']==engine}<=covered)
                self.assertEqual(model['revisions'],sorted({r['revision']for r in model['original_sources']}))
                original=model['original_case_indices'];candidate=model['candidate_only_case_indices']
                self.assertFalse(set(original)&set(candidate))
                self.assertEqual(sorted(original+candidate),list(range(len(model['cases']))))
                for row in model['original_sources']:
                    self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
                    for digest in row['functions'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
                text=(root/'source/openborscript/level.c').read_text()
                prefix='LEVEL_PROPERTY_' if 'LEVEL_PROPERTY_TEXT_OBJECT_COLLECTION'in text else 'LEVEL_PROP_'
                code=render_text_collection(revisions=model['revisions'],header_includes=model['header_includes'],
                    getter=function(text,'openbor_get_level_property'),setter=function(text,'openbor_set_level_property'),
                    declarations=re.search(r'(?m)^#define invalid_pointer_input[^\n]+',text)[0],
                    properties=dict(collection=prefix+'TEXT_OBJECT_COLLECTION',count=prefix+'TEXT_OBJECT_COUNT'),
                    cases=model['cases'])
                work=Path(temporary);source=work/'probe.c';source.write_text(code);binary=work/'probe'
                includes=[root/'source/scriptlib',root,SOURCE/'src/port/libretro',root/'source',
                          *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
                compile_checked(cc+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                    '-Wno-error=deprecated-declarations','-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare','-Wno-unused-variable','-Wno-unused-function',
                    '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough',
                    '-O0','-g','-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
                    '-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,*host,*warnings,
                    '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                    *['-I'+str(p)for p in includes],str(source),str(root/'source/scriptlib/ScriptVariant.c'),
                    *link,'-lm','-o',str(binary)])
                run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15,env=sanitizer_environment())
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                self.assertEqual(json.loads(run.stdout),dict(status='PASS',contexts=len(model['revisions']),
                    checks=len(model['cases'])*len(model['revisions'])))


if __name__=='__main__':
    unittest.main()
