"""Check snapshot profile identities and bounded storage keys with native C.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest
import re
from test_historical_player import function
from test_historical_behavior import native as compile_native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
HEADER = Path(os.environ.get('OBOR_PROFILE_IDENTITY_HEADER',
                            ROOT / 'src/port/libretro/obor_profile_identity.h'))
STATE = Path(os.environ.get('OBOR_PROFILE_STATE_SOURCE',
                           ROOT / 'src/port/libretro/obor_state.c'))
ABI = Path(os.environ.get('OBOR_PROFILE_ABI_HEADER',
                         ROOT / 'src/glue/obor_abi.h'))


def native(program):
    compile_native(program, include_dirs=(ABI.parent,))


def array(data):
    return '{' + ','.join(str(value) for value in data) + '}'


def preamble():
    return ('#include <assert.h>\n#define OBOR_SHA256_STREAM_ONLY\n#include ' +
            json.dumps(HEADER.resolve().as_posix()) + '\n')


class ProfileIdentityTests(unittest.TestCase):
    def test_save_directories_preserve_numeric_keys_and_separate_variants(self):
        source = STATE.read_text()
        native(preamble() + '#include <stdio.h>\n' + r'''
static char g_peak_dir[4096];
static uint64_t g_peak_written;
static uint32_t g_profile_build;
SETTER
int main(void){
    assert(obor_state_set_save_dir("/saves/game",6391,"6391"));
    assert(!strcmp(g_peak_dir,"/saves/game/6391/Saves"));
    assert(g_profile_build==6391);
    assert(obor_state_set_save_dir("/saves/game",6391,"6391-mod"));
    assert(!strcmp(g_peak_dir,"/saves/game/6391-mod/Saves"));
    assert(g_profile_build==6391);
    char before[4096];memcpy(before,g_peak_dir,sizeof(before));
    assert(!obor_state_set_save_dir("/saves/game",6391,"../6391"));
    assert(!memcmp(before,g_peak_dir,sizeof(before)));
    assert(!obor_state_set_save_dir(NULL,6391,"6391"));
    assert(!obor_state_set_save_dir("",6391,"6391"));
    char too_long[4096];memset(too_long,'x',sizeof(too_long));too_long[4095]=0;
    assert(!obor_state_set_save_dir(too_long,6391,"6391-mod"));
}
'''.replace('SETTER', function(source, 'obor_state_set_save_dir')))

    def test_actual_boot_binding_and_reader_prefix_reject_cross_variant_before_restore(self):
        source = STATE.read_text()
        header = re.search(r'typedef struct \{\n    uint32_t magic, version;.*?\} obs_header;',
                           source, re.S).group()
        reader = function(source, 'unserialize_impl')
        # Compile the unmodified reader's complete identity/profile preflight.
        # The positive control marks the later restore boundary explicitly;
        # full resources/heap restoration is covered by the runtime suite.
        prefix = reader[:reader.index('    uint64_t table_bytes =')]
        prefix += '    (void)debug_restore;++restore_reached;*committed=1;return 1;\n}\n'
        native(preamble() + '#include <stdio.h>\n#include <stdlib.h>\n#include ' +
               json.dumps(ABI.resolve().as_posix()) + '\n' + r'''
#define OBOR_ENGINE_BUILD 6391
#define MAX_SEGS 16
#define OBS_MAGIC 0x3153424FU
#define OBS_VERSION 7U
#define OBS_RESOURCE_VERSION 8U
#define OBS_STABLE_RESOURCE_VERSION 9U
#define OBS_ALIGNED_RESOURCE_VERSION 10U
static int obor_live_threads,g_nsegs=1,g_segments_failed,restore_reached;
static uint64_t g_full_segment_bytes;
static uint32_t g_profile_build,g_region_count;
static uint8_t g_state_build_identity[32];
static obor_engine_region g_regions[OBOR_MAX_ENGINE_REGIONS];
static int collect_segments(void){g_nsegs=1;return 1;}
static void ensure_boot_id(void){}
HEADER
BIND
READER
int main(void){
    obor_engine_region region={0x1000,0x2000,6391};
    obor_boot_info boot={0};boot.engine_regions=&region;boot.engine_region_count=1;
    boot.profile_build=6391;boot.profile_key="6391";g_profile_build=6391;
    for(unsigned i=0;i<32;++i)boot.state_build_identity[i]=(uint8_t)i;
    assert(obor_state_set_regions(&boot));
    obs_header normal={0};normal.magic=OBS_MAGIC;normal.version=OBS_VERSION;
    normal.profile_build=6391;normal.physical_build=6391;normal.nsegs=1;
    memcpy(normal.build_identity,g_state_build_identity,32);
    int committed=0;assert(unserialize_impl(&normal,sizeof(normal),&committed));
    assert(committed==1 && restore_reached==1);
    boot.profile_key="6391-mod";boot.profile_features=3;
    assert(obor_state_set_regions(&boot));
    committed=0;assert(!unserialize_impl(&normal,sizeof(normal),&committed));
    assert(!committed && restore_reached==1);
    obs_header mod=normal;memcpy(mod.build_identity,g_state_build_identity,32);
    assert(unserialize_impl(&mod,sizeof(mod),&committed));
    assert(committed==1 && restore_reached==2);
    boot.profile_key="6391";boot.profile_features=0;
    assert(obor_state_set_regions(&boot));
    committed=0;assert(!unserialize_impl(&mod,sizeof(mod),&committed));
    assert(!committed && restore_reached==2);
    assert(unserialize_impl(&normal,sizeof(normal),&committed));
    assert(committed==1 && restore_reached==3);
    uint8_t original[32];memcpy(original,g_state_build_identity,32);
    boot.profile_key="../bad";assert(!obor_state_set_regions(&boot));
    assert(!memcmp(original,g_state_build_identity,32));
    boot.profile_key="6391";region.end=region.begin;
    assert(!obor_state_set_regions(&boot));
    assert(!memcmp(original,g_state_build_identity,32));
    assert(!obor_state_set_regions(NULL));
}
'''.replace('HEADER', header).replace('BIND', function(source, 'obor_state_set_regions'))
           .replace('READER', prefix))

    def test_module_revision_key_and_features_bind_distinct_identities(self):
        original = bytes(range(32))
        changed = bytes([value ^ 13 for value in original])
        vectors = [(original, 6391, 0, '6391'),
                   (original, 6391, 3, '6391-mod'),
                   (original, 6391, 0, '6391-mod'),
                   (original, 6392, 3, '6392'),
                   (original, 7142, 0, '7142-mod'),
                   (changed, 6391, 3, '6391-mod')]
        expected = []
        statements = []
        for index, (binary, build, features, key) in enumerate(vectors):
            raw_key = key.encode('ascii')
            digest = hashlib.sha256(b'AnyBOR state profile identity\0' + binary +
                                    struct.pack('<III', build, features, len(raw_key)) + raw_key).digest()
            expected.append(digest)
            statements.append('const uint8_t binary%d[32]=%s, expected%d[32]=%s;\n'
                              'assert(obor_profile_state_identity(binary%d,%du,%du,%s,output));\n'
                              'assert(!memcmp(output,expected%d,32));\n' %
                              (index, array(binary), index, array(digest), index,
                               build, features, json.dumps(key), index))
        self.assertEqual(len(set(expected)), len(vectors))
        native(preamble() + 'int main(void){uint8_t output[32];\n' +
               '\n'.join(statements) + '}\n')

    def test_invalid_storage_keys_refuse_without_changing_output(self):
        bad = ['', '../6391', '6391/mod', '6391\\mod', '6391.mod',
               '6391:mod', '6391 mod', '6391\nmod', '6' * 48, '6' * 256]
        values = ','.join(json.dumps(key) for key in bad)
        native(preamble() + r'''
int main(void){
    const uint8_t binary[32]={0};uint8_t output[32],sentinel[32];
    memset(sentinel,0xa5,sizeof(sentinel));memcpy(output,sentinel,sizeof(output));
    const char *bad[]={NULL,BAD_KEYS};
    for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);++i){
        assert(!obor_profile_key_length(bad[i]));
        assert(!obor_profile_state_identity(binary,6391,0,bad[i],output));
        assert(!memcmp(output,sentinel,sizeof(output)));
    }
    char longest[OBOR_PROFILE_KEY_CAPACITY];
    memset(longest,'6',sizeof(longest));longest[sizeof(longest)-1]=0;
    assert(obor_profile_key_length(longest)==sizeof(longest)-1);
    assert(obor_profile_key_length("6391-mod")==8);
    assert(!obor_profile_state_identity(NULL,6391,0,"6391",output));
    assert(!obor_profile_state_identity(binary,0,0,"6391",output));
    assert(!obor_profile_state_identity(binary,6391,0,"6391",NULL));
    assert(!memcmp(output,sentinel,sizeof(output)));
}
'''.replace('BAD_KEYS', values))


if __name__ == '__main__':
    unittest.main()
