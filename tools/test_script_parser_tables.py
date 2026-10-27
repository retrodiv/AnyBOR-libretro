"""Check native parser tables without changing valid token membership.

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
import unittest

from native_sanitizers import sanitizer_environment

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))


class ParserTables(unittest.TestCase):
    def test_complete_tables_and_all_valid_token_memberships_in_each_engine(self):
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        with tempfile.TemporaryDirectory(prefix='anybor-parser-tables-') as directory:
            executable = Path(directory) / 'contract'
            for engine in pin['engines']:
                with self.subTest(engine=engine['build']):
                    library = SOURCE / 'src/engines' / engine['build'] / 'source/scriptlib'
                    compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
                    warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
                        'clang' in Path(word).name for word in compiler) else []
                    includes = [library, library.parent, library.parent / 'gamelib',
                                library.parent / 'preprocessorlib']
                    subprocess.run(compiler + warnings + [
                        '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-error=deprecated-declarations',
                        '-DOBOR_ENGINE_BUILD=' + engine['build'],
                        '-fsanitize=address,undefined', '-g',
                        *('-I'+str(path) for path in includes),
                        str(Path(__file__).with_name('script_parser_sets_contract.c')),
                        '-o', str(executable)], check=True, timeout=45)
                    subprocess.run([str(executable)], check=True, timeout=15,
                                   env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
