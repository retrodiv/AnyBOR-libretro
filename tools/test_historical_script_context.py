"""Check source-profile script selection, callback restoration and cleanup.

Native functions and headers run with bounded scalar variable/interpreter
providers. This checks context routing, not complete VM or gameplay behavior.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-context-contracts.json'
CALLBACKS = '''execute_takedamage_script execute_onpain_script execute_onfall_script
execute_onblocks_script execute_onblockw_script execute_onblocko_script
execute_onblockz_script execute_onblocka_script execute_onmovex_script
execute_onmovez_script execute_onmovea_script execute_ondeath_script
execute_onkill_script execute_didblock_script execute_ondoattack_script
execute_updateentity_script execute_think_script execute_didhit_script
execute_onspawn_script execute_entity_key_script execute_spawn_script
execute_level_key_script execute_key_script_all execute_timetick_script
execute_loading_script execute_key_script execute_join_script execute_respawn_script
execute_pdie_script addscore execute_updatescripts execute_updatedscripts'''.split()


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source script context coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or
                row['revision'] <= 0 or type(row['legacy_context']) is not bool or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                any(not re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Bound source identity and explicit context contract required')
    return data


def program(data):
    engine = ROOT / 'src/engines/3741'
    script = (engine / 'openborscript.c').read_text()
    game = (engine / 'openbor.c').read_text()
    names = ['_set_var','Script_Get_Local_Variant','Script_Set_Local_Variant',
             'Script_Local_Clear','obor_script_destroy_interpreter',
             'obor_script_replace_interpreter','obor_script_destroy_comment',
             'obor_script_replace_comment','obor_script_share_references',
             'Script_Init','Script_Copy','Script_Clear','Script_AppendText',
             'Script_IsInitialized','Script_Execute','system_getlocalvar',
             'system_setlocalvar','system_clearlocalvar']
    native = '\n'.join(function(script, name) for name in names)
    native += '\n' + '\n'.join(function(game, name) for name in CALLBACKS + ['loadScriptFile','playlevel'])
    native += '\n'  # The level source's earlier-profile new-game flag is private.
    template = Path(__file__).with_name('script_context_contract.c.in').read_text()
    cases = ','.join('{%d,%d}' % (row['revision'], row['legacy_context']) for row in data)
    return template.replace('@FUNCTIONS@', native).replace('@CASES@', cases)


class ScriptContextContracts(unittest.TestCase):
    def test_selected_owner_callbacks_and_cleanup_by_profile(self):
        engine = ROOT / 'src/engines/3741'
        port = ROOT / 'src/port/libretro'
        paths = [port, engine, engine / 'source'] + [engine / 'source' / name for name in (
            'gamelib','scriptlib','preprocessorlib','ramlib','randlib','adpcmlib','gfxlib')]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-script-context-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(rows()))
            subprocess.run(compiler + warnings + ['-std=gnu99','-fsigned-char',
                '-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
                '-Wno-error=deprecated-declarations','-DOBOR_ENGINE_BUILD=3741',
                '-DLIBRETRO=1','-fsanitize=address,undefined','-g',
                *('-I'+str(path) for path in paths),str(source),'-o',str(executable)],
                check=True,timeout=45)
            subprocess.run([str(executable)],check=True,timeout=30,
                           env=sanitizer_environment(),cwd=temporary)


if __name__ == '__main__':
    unittest.main()
