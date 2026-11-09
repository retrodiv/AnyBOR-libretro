"""Check system-variable namespaces, selected fields and music handles.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-system-routing-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openborscript.c').read_text()
    mixer = (engine / 'source/gamelib/soundmix.c').read_text()
    header = (engine / 'source/openborscript/config.h').read_text()
    enum = re.search(r'enum systemvariant_enum\s*\{([^}]+)\}', header, re.S)
    labels = re.findall(r'\bSYSTEM_PROPERTY_\w+', enum[1]) if enum else []
    if not labels or labels[-1] != 'SYSTEM_PROPERTY_THE_END':
        raise ValueError('Complete system namespace enum required')
    arrays = []
    for name in ('svlist', 'obor_profile_system_music_names'):
        match = re.search(r'static const char \*' + name + r'\[\]\s*=\s*\{[^}]+\};', source, re.S)
        if match is None:
            raise ValueError('Complete source-owned system name table required')
        arrays.append(match[0])
    selected = ('SYSTEM_PROPERTY_MAX_WALL_HEIGHT', 'SYSTEM_PROPERTY_MUSICVOL',
                'SYSTEM_PROPERTY_SAMPLE_PLAY_ID', 'SYSTEM_PROPERTY_MUSIC_CHANNEL')
    callbacks = []
    for name in ('getsyspropertybyindex', 'changesyspropertybyindex'):
        body, cases = switch_cases(source, name, 'index', outermost=True)
        required = selected if name.startswith('get') else selected[:1]
        callbacks.append(body[:body.index('switch(index)')] + 'switch(index){' +
            ''.join('case ' + key + ':' + cases[key]['body'] for key in required) +
            'default:' + cases['default']['body'] + '}\nreturn 1;\n}\n')
    types = {m[1]: m[0] for m in re.finditer(
        r'(?ms)^typedef struct(?:\s+\w+)?\s*\{.*?^\}\s*(\w+)\s*;', mixer)}
    rows = []
    for row in data['sources']:
        names = row['names'] + data['extra_queries']
        rows.append('{%du,%d,{%s},{%s}}' % (row['revision'], len(names),
            ','.join(json.dumps(n) for n in names), ','.join(str(n) for n in row['field_ids'])))
    parts = dict(ARRAYS='\n'.join(arrays), TYPES='\n'.join(types[n] for n in
            ('samplestruct', 's_soundcache', 's_audio_global')),
        LABELS=','.join(json.dumps(n) for n in labels[:-1]),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        VARIANTS='\n'.join(function((engine / 'source/scriptlib/ScriptVariant.c').read_text(), n)
            for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        COUNTER=function(mixer, 'sound_profile_sample_play_id'),
        HELPERS='\n'.join(function(source, n) for n in
            ('obor_profile_system_property_count', 'obor_profile_system_native_index', 'mapstrings_systemvariant')),
        FIELDS='\n'.join(callbacks), METHODS='\n'.join(function(source, n) for n in
            ('openbor_systemvariant', 'openbor_setsystemvariant')), CONTEXTS=','.join(rows))
    code = Path(__file__).with_name('modern_system_routing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved system routing contract input')
    return code


class ModernSystemRoutingContracts(unittest.TestCase):
    def test_names_numeric_ids_music_pointer_counter_and_wall_setter(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', integer_bytes=4, profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
