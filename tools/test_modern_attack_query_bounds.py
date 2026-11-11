"""Check native attack table extents and historical instance contracts.

Real records, the native table allocation block, complete getters and variant
conversions run with bounded allocation/string/diagnostic providers. This does
not test arbitrary foreign object pointers or complete animation destruction.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_early_system_callbacks import block
from test_historical_player import function, switch_cases
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, remove_frame_guard=False, remove_slot_guard=False):
    game = (engine / 'openbor.c').read_text(encoding='latin1')
    script = engine / 'source/openborscript/collision_attack.c'
    if not script.is_file():
        script = engine / 'openborscript.c'
    source = script.read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    collection = function(source, 'openbor_get_attack_collection')
    instance = function(source, 'openbor_get_attack_instance')
    prop, cases = switch_cases(source, 'openbor_get_attack_property', 'property')
    handle = re.search(r'\b(s_\w+)\s*\*\s*handle\s*=\s*NULL', prop)
    if handle is None:
        raise ValueError('Native attack property handle type required')
    guarded, defined_null = [], []
    force = None
    for label, case in cases.items():
        if label == 'default':
            continue
        body = re.sub(r'/\*.*?\*/|//[^\n]*', '', case['body'], flags=re.S)
        if 'handle->attack_force' in body:
            force = label
        if 'OBOR_ATTACK_REQUIRE_HANDLE();' in body:
            guarded.append(label)
        elif 'ScriptVariant_ChangeType(*pretvar, VT_INTEGER);' in body and 'handle->' not in body:
            defined_null.append(label)
    if not guarded or force is None:
        raise ValueError('Native guarded attack property cases required')
    if remove_frame_guard:
        guard = 'if(!obor_attack_frame_is_valid(handle, frame))'
        if collection.count(guard) != 1:
            raise ValueError('One native frame-table guard required')
        collection = collection.replace(guard, 'if(0)', 1)
    if remove_slot_guard:
        guard = 'index < handle->slot_capacity && '
        if instance.count(guard) != 1:
            raise ValueError('One native dynamic-slot capacity guard required')
        instance = instance.replace(guard, '', 1)
    producer = function(game, 'collision_attack_initialize_frame_property' if
                        'void collision_attack_initialize_frame_property(' in game else 'addframe')
    allocation = re.search(r'\bif\s*\(\s*!(?:a|data->animation)->collision_attack\s*\)', producer)
    if allocation is None:
        raise ValueError('Native attack frame-table producer required')
    allocate = block(producer, allocation.start()).replace('data->animation', 'a').replace('data->framecount', 'framecount')
    if 'a->obor_attack_frame_capacity = (size_t)framecount;' not in allocate:
        raise ValueError('Native producer must retain its owned capacity')
    stop = re.search(r'(?m)^void\s+(borShutdown|shutdown)\s*\(', game)
    if stop is None:
        raise ValueError('Native controlled-stop signature required')
    signature = function(game, stop[1]).split('{', 1)[0]
    diagnostics = re.findall(r'(?m)^(?:static\s+const\s+char\s*\*\s*E_OUT_OF_MEMORY|char\s+E_OUT_OF_MEMORY\[\])[^;]*;', game)
    values = dict(
        CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        PROFILE_HEADER='#include "source/openborscript/profile_ids.h"' if engine.name == '6391' else '',
        DIAGNOSTIC='\n'.join(diagnostics), STOP=signature+'{(void)status;(void)msg;abort();}',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in
            (engine / 'source/scriptlib/ScriptVariant.h').read_text() else 'void',
        CONVERSIONS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue')),
        ALLOCATION=allocate, COLLECTION=collection, INSTANCE=instance, PROPERTY=prop,
        BODY_INSTANCE=function((engine / 'source/openborscript/collision_body.c').read_text(encoding='latin1'),
                               'openbor_get_body_collision_instance') if 'active_bit' in instance else '',
        ATTACK_TYPE=handle[1], FORCE=force, INDEXED='1' if 'active_bit' in instance else '0',
        GUARDED_CASES=','.join(guarded),
        NULL_CASES=','.join(defined_null) if defined_null else '0',
        NULL_CASE_COUNT=str(len(defined_null)),
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'modern_attack_query_bounds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved modern attack contract dependency')
    return text


class ModernAttackQueryBoundsTests(unittest.TestCase):
    def test_native_table_capacity_arguments_and_instances_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for name in ('4432', '6391', '7142', '7533', '8023'):
            engine = ROOT / 'src/engines' / name
            profiles = [p for p in pin['profiles'] if p['engine'] == name]
            with self.subTest(engine=name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['queries'], 80*len(profiles))

    def test_missing_logical_endpoint_guard_is_detected_without_invalid_access(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/4432'
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        text = '#define ENDPOINT_ONLY 1\n'+program(engine, [profile], remove_frame_guard=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('status==', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)

    def test_missing_dynamic_slot_extent_is_detected_in_spare_backing(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/8023'
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, program(engine, [profile], remove_slot_guard=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('result.vt==VT_EMPTY', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
