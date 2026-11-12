"""Check native triangle diagnostics and valid vertex/texture assignments.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def api_window():
    text = (ROOT / 'src/glue/anybor_content_contracts.h').read_text()
    windows = []
    for name in ['setvertex', 'settexture']:
        rows = re.findall(r'\{\s*"'+name+r'",\s*OBOR_CT_FUNCTION,\s*(\d+),\s*(\d+),', text)
        if len(rows) != 1:
            raise ValueError('One explicit native function contract required')
        windows.append(tuple(map(int, rows[0])))
    if windows[0] != windows[1]:
        raise ValueError('Review divergent triangle API windows separately')
    return windows[0]


def program(engine, profiles):
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    match = re.search(r'(?m)^static[ \t]+gfx_entry[ \t]+texture;\s*'
                      r'#define[ \t]+vert_buf_size[ \t]+([0-9]+)\s*'
                      r'static[ \t]+vert2d[ \t]+verts\[vert_buf_size\];', script)
    if match is None or not 1 <= int(match[1]) <= 4096:
        raise ValueError('Bounded actual vertex and texture declarations required')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    texture_callback = function(script, 'openbor_settexture')
    values = dict(STORAGE=match[0], CONVERTER=function(variant, 'ScriptVariant_IntegerValue'),
                  TYPE_MATCH='texture.type==(kind)' if 'texture.type =' in texture_callback else '1',
                  CALLBACKS='\n'.join(function(script, name) for name in
                                      ['openbor_setvertex', 'openbor_settexture']),
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                                    for p in profiles))
    text = (HERE / 'triangle_diagnostics.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class TriangleDiagnosticTests(unittest.TestCase):
    def test_native_argument_diagnostics_and_valid_stores(self):
        low, high = api_window()
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build'] and
                        low <= int(p.get('revision', p['build'].split('-')[0])) <= high]
            if not profiles:
                continue
            engine = ROOT / 'src/engines' / row['build']
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(profiles=len(profiles), calls=17*len(profiles)))


if __name__ == '__main__':
    unittest.main()
