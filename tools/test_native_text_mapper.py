"""Check published native text-property results and defined input boundaries.

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

from historical_string_mapper import render_string_mapper
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function
from test_color_blends import compile_checked

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))


class NativeTextMapperTests(unittest.TestCase):
    def test_each_published_profile_native_names_numbers_and_returns(self):
        fixture=load_contract_fixture(Path(__file__).with_name('fixtures').joinpath('native-text-mapper-contracts.json'))
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        cc=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))
        version=subprocess.check_output(cc+['--version'],text=True,timeout=10)
        extra=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype'] if 'clang' in version.lower() else []
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        link=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        for model in fixture['models']:
            with self.subTest(model=model['id']),tempfile.TemporaryDirectory(prefix='native-text-mapper-') as temporary:
                engine=model['engine'];root=SOURCE/'src/engines'/engine
                required={int(p.get('revision',p['build'])) for p in contract_profiles(fixture, pin['profiles']) if p['engine']==engine}
                covered={n for m in fixture['models'] if m['engine']==engine for n in m['revisions']}
                self.assertTrue(required<=covered)
                script=(root/'openborscript.c').read_text()
                enums='\n'.join(re.findall(r'enum (?:g|c)top_enum\s*\{[^}]*\};',script))
                self.assertTrue(enums)
                method_name=model.get('method_name','mapstrings_textobjproperty')
                options={key:model[key] for key in ['revisions','header_includes','cases','nullable_inputs']}
                options.update({key:model[key] for key in ['return_type','input_setup'] if key in model})
                declarations=enums+'\n'+function((root/'source/utils.c').read_text(),'searchList')
                declarations+='\n'+'\n'.join(function(script,name) for name in model.get('extra_methods',[]))
                code=render_string_mapper(**options,method_name=method_name,
                    declarations=declarations,
                    method=function(script,method_name))
                work=Path(temporary);source=work/'probe.c'
                source.write_text(bind_named_allocation_support(code, root));binary=work/'probe'
                includes=[root/'source/scriptlib',root,SOURCE/'src/port/libretro',root/'source',
                          *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
                compile_checked(cc+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                    '-Wno-error=deprecated-declarations','-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare','-Wno-unused-variable','-Wno-unused-function',
                    '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough',
                    '-O0','-g','-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
                    '-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,*host,*extra,
                    '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                    *['-I'+str(p) for p in includes],str(source),
                    str(root/'source/scriptlib/ScriptVariant.c'),*link,'-lm','-o',str(binary)])
                run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15,
                                   env=sanitizer_environment())
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                self.assertEqual(json.loads(run.stdout),dict(status='PASS',contexts=len(model['revisions']),
                    checks=len(model['revisions'])*(len(model['cases'])+1+2*int(model['nullable_inputs']))))


if __name__=='__main__':
    unittest.main()
