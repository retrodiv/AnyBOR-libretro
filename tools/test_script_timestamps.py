"""Script timestamps must retain their values across logical profiles.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
ENGINE = Path(os.environ.get('OBOR_PROFILE_ENGINE', SOURCE / 'src/engines/6391'))


def property_body(source, function, property_name):
    start = source.index('HRESULT ' + function + '(')
    start = source.index('case ' + property_name + ':', start)
    start = source.index('{', start)
    end, depth = start + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class ProfileScriptBoundariesTests(unittest.TestCase):
    def test_nextanim_is_a_timestamp_in_every_profile(self):
        source = (ENGINE / 'openborscript.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        header = re.sub(r'/\*.*?\*/|//[^\n]*', '', header, flags=re.S)
        families = {'e_animations', 'e_animation_properties', 'e_entity_type_sub',
                    'e_spawn_type', 'e_attack_types'}
        enums = '\n'.join('typedef enum {' + body + '} ' + name + ';'
            for body, name in re.findall(r'typedef\s+enum[^{}]*\{([^{}]*)\}\s*(\w+)\s*;', header, re.S)
            if name in families)
        getter = property_body(source, 'openbor_getentityproperty', '_ep_nextanim')
        setter = property_body(source, 'openbor_changeentityproperty', '_ep_nextanim')
        program = r'''
#include <assert.h>
#include <stdint.h>
ENUMS
static uint32_t obor_profile_build;
#include "source/openborscript/profile_ids.h"
typedef long LONG;
typedef struct { LONG lVal; int vt; } ScriptVariant;
typedef struct { unsigned int nextanim; } entity;
#define VT_INTEGER 1
#define SUCCEEDED(value) ((value) >= 0)
static void ScriptVariant_ChangeType(ScriptVariant *value, int type) { value->vt=type; }
static int ScriptVariant_IntegerValue(ScriptVariant *value, LONG *result) {
    *result=value->lVal; return 0;
}
static LONG get_timestamp(entity *ent) {
    ScriptVariant result={0}, *pointer=&result, **pretvar=&pointer;
    do GETTER while(0);
    assert(result.vt == VT_INTEGER);
    return result.lVal;
}
static void set_timestamp(entity *ent, LONG timestamp) {
    ScriptVariant value={timestamp, VT_INTEGER}, *varlist[]={0,0,&value};
    LONG ltemp=0;
    do SETTER while(0);
}
int main(void) {
    const unsigned profiles[]={6330,6391,6412,6510};
    const unsigned ticks[]={0,1,236,237,238,239,240,241,4096,1000000,1000000000};
    for(unsigned p=0;p<4;++p) {
        obor_profile_build=profiles[p];
        for(unsigned t=0;t<sizeof(ticks)/sizeof(*ticks);++t) {
            /* Check each boundary independently: inverse mistakes can hide in a round trip. */
            entity subject={ticks[t]};
            assert(get_timestamp(&subject) == ticks[t]);
            subject.nextanim=123;
            set_timestamp(&subject, ticks[t]);
            assert(subject.nextanim == ticks[t]);
        }
    }
    return 0;
}
'''.replace('ENUMS', enums).replace('GETTER', getter).replace('SETTER', setter)
        with tempfile.TemporaryDirectory(prefix='anybor-profile-timestamps-') as temporary:
            work = Path(temporary)
            (work / 'probe.c').write_text(program)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-g', '-I', str(ENGINE),
                            str(work / 'probe.c'), '-o', str(work / 'probe')], check=True, timeout=60)
            subprocess.run([str(work / 'probe')], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
