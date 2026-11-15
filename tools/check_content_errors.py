#!/usr/bin/env python3
"""Exercise terminal model-script errors, visible frames and same-core reload.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from make_fixture import files, write_pak

ROOT=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT/'tools'))


def main():
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--core',type=Path,required=True)
    parser.add_argument('--profile',action='append')
    args=parser.parse_args();core=args.core.resolve()
    if sys.platform=="linux":
        from run_guarded import require_limits
        require_limits(2048)
    pin=json.loads((ROOT/'src/pin.json').read_text())
    profiles=args.profile or [next((p['build'] for p in pin['profiles'] if p['engine']==e['build'] and p['build']==e['build']),
        next(p['build'] for p in pin['profiles'] if p['engine']==e['build'])) for e in pin['engines']]
    assert core.is_file() and profiles and set(profiles)<={p['build'] for p in pin['profiles']}
    with tempfile.TemporaryDirectory(prefix='content-errors-') as directory:
        work=Path(directory);host=work/'host';source=work/'host.c'
        text=Path(os.environ.get('OBOR_TEST_HOST',ROOT/'tests/host/libretro_host.c')).read_text()
        marker='        if (g_frame == expect_recover_at) {'
        assert text.count(marker)==1
        # The maintained host already checks visible error pixels, rejected state
        # calls and descriptors. Add a test-only content cycle without unloading
        # the core module or resetting the process.
        text=text.replace(marker,'''        if (g_frame == (getenv("OBOR_CONTENT_RELOAD_AT") ? atoi(getenv("OBOR_CONTENT_RELOAD_AT")) : 50) && getenv("OBOR_CONTENT_RELOAD_PATH")) {
            p_retro_unload_game();
            g_startup_complete = 0;
            info.path = getenv("OBOR_CONTENT_RELOAD_PATH");
            if (!p_retro_load_game(&info)) return 1;
            printf("content_reloaded=1 frame=%d\\n",g_frame);
        }
'''+marker)
        text=text.replace('return 1;', '{fprintf(stderr,"content host stopped at line %d\\n",__LINE__);return 1;}')
        source.write_text(text)
        command=shlex.split(os.environ.get('HOST_CC','cc'))+['-O2','-I',str(ROOT/'src/third_party'),'-I',str(ROOT/'src/glue'),'-I',str(ROOT/'tests/host'),str(source),'-o',str(host)]
        if sys.platform!='darwin':command+=['-ldl']
        subprocess.run(command,check=True,timeout=60)
        good=files()
        good['data/chars/block.txt']=good['data/chars/block.txt'].replace(
            b'name TestBlock\n',b'name TestBlock\nanimationscript data/scripts/authored.c\n').rstrip(b'\n')
        good['data/scripts/authored.c']=b'void main(){setglobalvar("authored",1);}'
        bad=dict(good)
        bad['data/scripts/authored.c']=b'void main(){setglobalvar("authored","unterminated'
        # Early native readers compare backslashes; later readers accept both.
        for name,members in (('valid',good),('malformed',bad)):
            write_pak(work/(name+'.pak'),{key.replace('/','\\'):value for key,value in members.items()})
        later=dict(good)
        later['data/models.txt']+=b'know Later data/chars/later.txt\n'
        later['data/chars/later.txt']=good['data/chars/block.txt'].replace(b'name TestBlock',b'name Later').replace(b'type player',b'type enemy').replace(b'authored.c',b'later.c')
        later['data/scripts/later.c']=bad['data/scripts/authored.c']
        later['data/levels/room.txt']=b'load Later 0\n'+later['data/levels/room.txt']
        write_pak(work/'later.pak',{key.replace('/','\\'):value for key,value in later.items()})
        for profile,phase in ((p,phase) for p in profiles for phase in ('startup','later')):
            folder=work/(profile+'-'+phase);folder.mkdir()
            env={key:value for key,value in os.environ.items() if not key.startswith('OBOR_')}
            env.update(OBOR_ENGINE=profile,OBOR_EXPECT_ERROR_AT='40',OBOR_EXPECT_RECOVER_AT='95',
                       OBOR_CONTENT_RELOAD_PATH=str(work/'valid.pak'),OBOR_REQUIRE_VIDEO_EVERY_RUN='1',OBOR_CHECK_FDS='1')
            env['OBOR_CHECK_THREADS']='1'
            if phase=='later':
                env.update(OBOR_EXPECT_ERROR_AT='1150',OBOR_CONTENT_RELOAD_AT='1200',OBOR_EXPECT_RECOVER_AT='1450',
                           OBOR_INPUT='180-360:start,400-403:attack,600-603:start,900-903:attack')
            result=subprocess.run([str(host),str(core),str(work/('malformed.pak' if phase=='startup' else 'later.pak')),str(folder),'110' if phase=='startup' else '1500'],env=env,capture_output=True,text=True,timeout=45)
            output=result.stdout+result.stderr
            if result.returncode:raise RuntimeError(profile+'\n'+output)
            assert 'error_screen=320x240 black_white=1 state_rejected=1' in output,output
            assert 'content_reloaded=1' in output and 'error_screen_recovered=1' in output,output
            assert 'resource initialization complete' in output,output
            assert 'cwd_restored=1' in output,output
            if sys.platform=='linux':assert 'file_descriptors_restored=1' in output,output
            assert 'Script preprocessing failed' in output or 'Unexpected end of script' in output,output
            if phase=='later':
                error_at=min(output.find(text) for text in ('Script preprocessing failed','Unexpected end of script') if text in output)
                assert output.index('resource initialization complete')<error_at,output
            print('terminal_content profile='+profile+' phase='+phase+' error_pixels=1 responsive=1 same_core_reload=1 valid_no_final_newline=1',flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
