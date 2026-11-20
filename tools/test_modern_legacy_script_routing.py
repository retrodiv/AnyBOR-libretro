"""Check runtime entity-property names and legacy projectile flag targets.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-legacy-script-routing-contracts.json'
SPAWN_SCRIPT_FIXTURE = FIXTURE.with_name('profile-script-spawn-entry.json')


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    core = (engine / 'openbor.c').read_text()
    enums = re.findall(r'(?ms)^enum[ \t]+\w+[ \t]*(?://[^\n]*)?\s*\{[^}]*^};', source)
    names = [re.search(r'static const char\s*\*\s*' + name + r'\[\]\s*=\s*\{[^}]+\};', source, re.S)
             for name in ('eplist', 'eplist_aiflag', 'eplist_edgerange')]
    default = re.search(r'(?ms)^const s_projectile projectile_default_config\s*=\s*\{.*?^};', core)
    if any(match is None for match in names) or default is None or not enums:
        raise ValueError('Complete native legacy names/enums/default required')
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){' + ''.join(
        'case ' + key + ':' + cases[key]['body'] for key in ('_ep_a', '_ep_y', '_ep_health')) +
        'default:' + cases['default']['body'] + '}\nreturn S_OK;\n}\n')
    parts = dict(ENUMS='\n'.join(enums), NAMES='\n'.join(match[0] for match in names), DEFAULT=default[0], GETTER=getter,
        VARIANTS='\n'.join(function(variant, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
            'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        MAPPER=function(source, 'mapstrings_entityproperty'), PROJECTILE=function(source, 'openbor_projectile'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(n) for n in row) + '}' for row in data['projectile_cases']))
    code = Path(__file__).with_name('modern_legacy_script_routing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved legacy routing input')
    return code


class ModernLegacyScriptRoutingContracts(unittest.TestCase):
    def check_script_spawn_entry(self, physical):
        data = load_contract_fixture(SPAWN_SCRIPT_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        names = ('item', '2pitem', '3pitem', '4pitem', 'itemhealth', 'itemalias', 'itemmap')
        setter, cases = switch_cases(source, 'openbor_setspawnentry', 'prop', outermost=True)
        prefix = re.split(r'\bswitch\s*\(prop\)', setter, maxsplit=1)[0]
        branches = ''.join('case _sse_' + name + ':' + cases['_sse_' + name]['body'] for name in names)
        error = setter[setter.index('\nsetspawnentry_error:'):]
        methods = ('mapstrings_setspawnentry', 'openbor_clearspawnentry', 'openbor_spawn', 'openbor_projectile')
        macro_source = (engine / 'source/openborscript/scriptcommon.h').read_text() if physical == '6391' else source
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', macro_source)[0]
        name_helpers = ''
        if physical == '4432':
            core = (engine / 'openbor.c').read_text(encoding='latin-1')
            name_helpers = '\n'.join(function(core, name) for name in
                                     ('obor_profile_name_limit', 'obor_profile_copy_name'))
        methods = '\n'.join(function(source, name) for name in methods)
        if 'obor_profile_uses_5134_script_ids(' in setter + methods:
            profile_ids = (engine / 'source/openborscript/profile_ids.h').read_text()
            name_helpers += function(profile_ids, 'obor_profile_uses_5134_script_ids') + '\n'
        values = {
            'VARIANTS': '\n'.join(function(variant, name) for name in ('ScriptVariant_Clear',
                                      'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
            'SEARCH': function(utility, 'searchList'), 'MAP_MACRO': macro,
            'ENUM': re.search(r'enum setspawnentry_enum\s*\{[^}]*\};', source)[0],
            'METHODS': name_helpers + methods,
            'SETTER': prefix + 'switch(prop){' + branches + 'default: abort();}\nreturn S_OK;\n' + error,
            'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['zero_prime'], row['nonzero_prime'])
                             for row in rows),
        }
        template = Path(__file__).with_name('script_spawn_entry_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_script_spawn_entry(self):
        self.check_script_spawn_entry('4432')

    def test_6391_script_spawn_entry(self):
        self.check_script_spawn_entry('6391')

    def test_runtime_names_and_projectile_prime_recipient(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', flags=[1,16,2,8,4], profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
