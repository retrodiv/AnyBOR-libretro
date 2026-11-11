"""Check native model backing storage replaced by subclass commands.

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

from native_allocation_policy import bind_named_allocation_support
from native_sanitizers import sanitizer_environment
from test_historical_player import function


HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles):
    game = (engine / 'openbor.c').read_text(encoding='latin1')
    constructor = function(game, 'init_model')
    inline = 'newchar->defense_factors' in constructor
    modern = 'defense_allocate_object()' in constructor
    fields = (['defense_factors', 'defense_pain', 'defense_knockdown', 'defense_blockpower',
               'defense_blockthreshold', 'defense_blockratio', 'defense_blocktype'] if inline else ['defense'])
    fields += ['offense' if modern else 'offense_factors', 'special', 'animation']
    start = game.index('case CMD_MODEL_SUBCLASS:')
    case = game[start + len('case CMD_MODEL_SUBCLASS:'):game.index('case CMD_MODEL_NAME:', start)]
    modern_storage = '\n'.join(function(game, name) for name in (
        'defense_allocate_object', 'defense_free_object', 'offense_allocate_object', 'offense_free_object')) if modern else ''
    globals_ = '''int max_attack_types=MAX_ATKS,max_animations=16,max_freespecials=MAX_SPECIALS;
int magic_type;
float default_model_jumpheight=4.0f,default_model_jumpspeed=-1.0f,default_model_grabdistance=36.0f;
float noatk_duration=0.75f;
s_modelcache *model_cache;
'''
    if not inline:
        globals_ += 'const s_defense default_defense={0};\n'
    if modern:
        globals_ += 'const s_offense default_offense={0};\n'
    if 'global_config.' in constructor:
        globals_ += 's_global_config global_config={.game_speed=GAME_SPEED_DEFAULT};\n'
    script_allocator = '''static void fixture_alloc_scripts(s_scripts *scripts) {
 memset(scripts,0,sizeof(*scripts));scripts->animation_script=observe_calloc(1,sizeof(Script));
}''' if inline else '''static void fixture_alloc_scripts(void *out) {
 s_scripts *scripts=observe_calloc(1,sizeof(*scripts));
 scripts->animation_script=observe_calloc(1,sizeof(Script));
 memcpy(out,&scripts,sizeof(scripts));
}'''
    copy = ''
    if 'obor_model_copy(newchar, tempmodel)' in case:
        copy = '#include "obor_colourmap_storage.h"\n' + function(game, 'obor_model_copy')
    header = 'openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h'
    diagnostic = re.findall(r'(?m)^(?:static\s+const\s+char\s*\*\s*E_OUT_OF_MEMORY|char\s+E_OUT_OF_MEMORY\[\])[^;]*;', game)
    if len(diagnostic) != 1:
        raise ValueError('One native constructor diagnostic required')
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
                  SCRIPT_HEADER=header, GLOBALS=globals_, SCRIPT_ALLOCATOR=script_allocator,
                  MODERN_STORAGE=modern_storage, DIAGNOSTIC=diagnostic[0], CONSTRUCTOR=constructor,
                  DEFAULT_DEFENSE=function(game, 'obor_profile_default_defense') if 'obor_profile_default_defense()' in constructor else '',
                  HASFREE=function(game, 'hasFreetype'),
                  RELEASE=function(game, 'obor_model_release_constructor_storage'), MODEL_COPY=copy,
                  SCRIPTS_TYPE='s_scripts' if inline else 's_scripts *', CASE=case,
                  SCRIPTS_ADDRESS='&model->scripts' if inline else 'model->scripts',
                  CHILD_SCRIPTS_ADDRESS='(&child->scripts)' if inline else 'child->scripts',
                  SCRIPT_AGGREGATE_RELEASE='' if inline else 'observe_free(scripts);',
                  SCRIPT_ALLOCATION_COUNT=str(1 if inline else 2), STORAGE_FIELD_COUNT=str(len(fields)),
                  CHECK_CONSTRUCTOR_FIELDS='\n'.join('CHECK(child->%s && child->%s!=parent->%s);' % (f, f, f) for f in fields),
                  SUPPORTS_SUBCLASS='obor_profile_build>=3221' if inline else '1',
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'model_constructor_ownership.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return bind_named_allocation_support(text, engine, marker='@NAMED_ALLOCATION_SUPPORT@').replace('@NAMED_ALLOCATION_SUPPORT@', '')


def run_native(engine, text):
    compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
    warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any('clang' in Path(p).name for p in compiler) else []
    with tempfile.TemporaryDirectory(prefix='native-model-ownership-') as name:
        work = Path(name)
        source, binary = work / 'probe.c', work / 'probe'
        source.write_text(text)
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source',
                    *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        flags = ['-std=gnu11', '-fgnu89-inline', '-O1', '-g', '-fcommon', '-Wall', '-Wextra', '-Werror',
                 '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                 '-Wno-error=deprecated-declarations', '-Wno-error=sign-compare', '-Wno-error=ignored-qualifiers',
                 '-ffunction-sections', '-fdata-sections', '-DLIBRETRO=1', '-DSAFEALLOC_H=1',
                 '-DOBOR_ENGINE_BUILD='+engine.name, '-fsanitize=address,undefined', '-fno-sanitize-recover=all']
        subprocess.run(compiler+warnings+flags+['-I'+str(p) for p in includes]+[str(source), *links, '-lm', '-o', str(binary)],
                       check=True, timeout=60)
        return subprocess.run([str(binary)], text=True, capture_output=True, timeout=30, env=sanitizer_environment())


class ModelConstructorOwnershipTests(unittest.TestCase):
    def test_native_constructor_storage_and_inherited_owners_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                text = program(engine, profiles)
                result = run_native(engine, text)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                inline = 's_scripts tempscripts;' in text
                cases = sum(16 if inline and int(p.get('revision', p['build'].split('-')[0])) < 3221 else 22 for p in profiles)
                self.assertEqual(json.loads(result.stdout), dict(status='PASS', profiles=len(profiles), cases=cases))

    def test_omitting_storage_release_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][0]
        engine = ROOT / 'src/engines' / row['build']
        profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
        profile = max(profiles, key=lambda p: int(p.get('revision', p['build'].split('-')[0])))
        text = program(engine, [profile])
        call = 'obor_model_release_constructor_storage(newchar, tempmodel);'
        self.assertEqual(text.count(call), 1)
        result = run_native(engine, text.replace(call, '(void)0;'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('live(1)==1+', result.stderr)


if __name__ == '__main__':
    unittest.main()
