"""Check attack stores, scalar getters, defaults and freeze argument conversion.

Native statements and records execute with controlled arguments/results.
Collision, frame effects, script dispatch and whole-record IO remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import sys
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions, contract_profiles
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-attack-field-contracts.json'
RISE_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-rise-invincibility-contracts.json'


def selected_statements(source, choices, count):
    if (not isinstance(source,str) or len(source)>8<<20 or
            type(count) is not int or not 0<count<=1024 or
            not isinstance(choices,list) or not 0<len(choices)<=8 or
            any(not isinstance(text,str) or not 0<len(text)<=65536 for text in choices)):
        raise ValueError('Bounded statement source, choices and positive count required')
    found = []
    total = 0
    for text in dict.fromkeys(choices):
        matches = re.findall(r'(?m)^[ \t]*(' + re.escape(text) + ')', source)
        if matches:
            found.append(matches[0])
            total += len(matches)
    if not found or total != count:
        raise ValueError('Exact native statement inventory required')
    return found


def energy_statements(source):
    """Require the complete native cost command and its single disable default."""
    if not isinstance(source, str) or len(source) > 8 << 20:
        raise ValueError('Bounded native energy source required')
    defaults = re.findall(r'(?m)^[ \t]*newanim->energycost\.disable[^\n]*;[^\n]*', source)
    commands = re.findall(r'(?m)^[ \t]*case CMD_MODEL_ENERGYCOST: case CMD_MODEL_MPCOST:'
                          r'[\s\S]*?^[ \t]*break;', source)
    # A nested assignment is the command, rather than an initializer.
    defaults = [line for line in defaults if 'GET_INT_ARG' not in line]
    if len(defaults) != 1 or len(commands) != 1 or len(commands[0]) > 8192:
        raise ValueError('One native energy default and complete command required')
    return defaults[0], commands[0]


def energy_program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    default, command = energy_statements(core)
    rows = []
    for row in data['sources']:
        contract = row['energy']
        if (type(contract['default']) is not int or type(contract['guarded']) is not bool or
                contract['width'] not in (8, 16)):
            raise ValueError('Explicit original energy contract required')
        rows.append('{%du,%d,%d,%d}' % (row['revision'], contract['default'],
                                      contract['guarded'], contract['width']))
    text = Path(__file__).with_name('energy_defaults_contract.c.in').read_text()
    replacements = dict(DEFAULT=default, COMMAND=command, PROFILES=',\n'.join(rows),
        PARSERS='\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt')),
        VALUES=','.join(str(v) for v in data['energy_values']))
    for key, value in replacements.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native energy dependency')
    return text


def program(data, section='all'):
    if section not in ('all', 'values', 'freeze'):
        raise ValueError('Explicit attack contract section required')
    engine = ROOT / 'src/engines' / data['engine']
    files = {name: (engine / name).read_text() for name in ('openbor.c', 'openborscript.c')}
    core, script = files['openbor.c'], files['openborscript.c']
    header = (engine / 'openbor.h').read_text()
    constant = re.findall(r'(?m)^const s_attack emptyattack\s*=\s*\{[\s\S]*?^\};', core)
    if len(constant) != 1:
        raise ValueError('One complete native empty attack required')
    getters = []
    for index, row in enumerate(data['getters']):
        found = re.findall(r'case\s+' + re.escape(row['label']) + r':([\s\S]*?\bbreak;)', script)
        if len(found) != 1:
            raise ValueError('One native attack scalar getter required')
        getters.append('static LONG get_%s(void){ScriptVariant result={0},*out=&result,**pretvar=&out;'
                       's_attack *value=&attack;do{%s}while(0);'
                       'CHECK(result.vt==VT_INTEGER,"getter type");return result.lVal;}' %
                       (row['field'], found[0].replace('attack->', 'value->')))
    writers = []
    for row in data['writers']:
        for statement in selected_statements(files[row['file']], row['alternatives'], row['occurrences']):
            target = row.get('original_target', 'original.' + row['field'])
            reference = row['original_statement'].replace(row['lhs'], target, 1)
            writers.append('attack=emptyattack;original=old_empty_%d;'
                           '%s\n%s\nCHECK(get_%s()==(LONG)%s,"store %s");++writes;' %
                           (0, statement, reference, row.get('getter', row['field']), target, row['field']))
    freezes = [selected_statements(core, row['alternatives'], 1)[0] for row in data['freeze']]
    declarations, checks, calls = [], [], []
    for i, group in enumerate(data['declaration_groups']):
        declarations.append(group['attack_type'].replace('s_attack', 'own_attack_%d' % i))
        # Some originals rely on standard implicit zero initialization for
        # their trailing fields. Keep the actual initializer unchanged.
        declarations.append('#pragma GCC diagnostic push\n'
            '#pragma GCC diagnostic ignored "-Wmissing-field-initializers"\n' +
            group['empty'].replace('s_attack', 'own_attack_%d' % i).replace(
                'emptyattack', 'old_empty_%d' % i) + '\n#pragma GCC diagnostic pop')
        record_variables, scalar_checks = [], []
        for record, fields in group['scalar_records'].items():
            declarations.append('struct own_%d_%s {%s};' % (i, record, '\n'.join(fields)))
            record_variables.append('%s actual_%s;struct own_%d_%s original_%s;' %
                                    (record, record, i, record, record))
        for row in group['same_width_fields']:
            record, name = row['record'], row['name']
            a = 'attack' if record == 's_attack' else 'actual_' + record
            b = 'original' if record == 's_attack' else 'original_' + record
            helper = data.get('scalar_store_helpers', {}).get(record + '.' + name)
            value = helper + '(input,obor_profile_build)' if helper and helper + '(' in header else 'input'
            scalar_checks.append('%s.%s=%s;%s.%s=input;'
                'CHECK((long long)%s.%s==(long long)%s.%s,"scalar %s.%s");++scalars;' %
                (a,name,value,b,name,a,name,b,name,record,name))
        defaults = []
        for row in group['default_members']:
            for index in range(row.get('elements', 1)):
                name = row['name'] + ('[%d]' % index if 'elements' in row else '')
                defaults.append('CHECK(emptyattack.%s==old_empty_%d.%s,"default %s");++defaults;' %
                                (name, i, name, name))
        freeze_checks = []
        for statement, reference in zip(freezes, group['freeze']):
            freeze_checks.append('attack=emptyattack;original=old_empty_%d;'
                                 '%s\n%s\nCHECK(attack.freezetime==original.freezetime,"freeze");++freezes;' %
                                 (i, statement, reference.replace('pattack->', 'original.').replace(
                                     'attack.freezetime', 'original.freezetime')))
        code = '''static void check_@I@(void){
 own_attack_@I@ original;@RECORDS@
 unsigned writes=0,scalars=0,defaults=0,freezes=0;
 @DEFAULTS@
 if(@VALUES@)for(unsigned v=0;v<sizeof(numbers)/sizeof(*numbers);++v){
  setup(v);int input=numbers[v];
  @WRITERS@
  @SCALARS@
  attack.attack_type=input;
  CHECK((int)(short)attack.attack_type==(int)attack.attack_type,"attack type index conversion");
 }
 if(@FREEZE@)for(unsigned n=0;n<sizeof(freeze_numbers)/sizeof(*freeze_numbers);++n){
  setup(0);for(unsigned a=0;a<16;++a)arguments[a]=freeze_numbers[n];
  @FREEZE_CHECKS@
 }
 printf("{\\"revision\\":%u,\\"writes\\":%u,\\"scalars\\":%u,\\"defaults\\":%u,\\"freezes\\":%u,\\"attack_bytes\\":%zu}\\n",obor_profile_build,writes,scalars,defaults,freezes,sizeof(s_attack));
}'''
        replacements = dict(I=str(i), RECORDS='\n'.join(record_variables), DEFAULTS='\n'.join(defaults),
            VALUES=str(int(section != 'freeze')), FREEZE=str(int(section != 'values')),
            WRITERS='\n'.join(writers).replace('old_empty_0', 'old_empty_%d' % i),
            SCALARS='\n'.join(scalar_checks), FREEZE_CHECKS='\n'.join(freeze_checks))
        for key, value in replacements.items():
            code = code.replace('@' + key + '@', value)
        checks.append(code)
        calls.extend('obor_profile_build=%du;check_%d();' % (r['revision'],i)
                     for r in data['sources'] if r['contract'] == group['key'])
    text = Path(__file__).with_name('attack_fields_contract.c.in').read_text()
    replacements = dict(DECLARATIONS='\n'.join(declarations), CHECKS='\n'.join(checks),
        CALLS='\n'.join(calls), DEFAULT=constant[0], GETTERS='\n'.join(getters),
        PARSERS='\n'.join(function(core,n) for n in ('isNumeric','getValidInt','getValidFloat')),
        NUMBERS=','.join(str(v) for v in data['values']),
        FREEZE_NUMBERS=','.join(json.dumps(v) for v in data['freeze_values']))
    for key,value in replacements.items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack dependency')
    return text


class AttackFieldContracts(unittest.TestCase):
    def test_native_rise_invincibility_argument_conversion(self):
        data = load_contract_fixture(RISE_FIXTURE)
        rows = data['sources']
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        commands = re.findall(r'(?m)^[ \t]*case CMD_MODEL_RISEINV:[\s\S]*?^[ \t]*break;', core)
        if len(commands) != 1:
            raise ValueError('One complete native riseinv command required')
        macros = []
        for name in ('GET_INT_ARG', 'GET_FLOAT_ARG'):
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', core)
            if len(found) != 1:
                raise ValueError('One native numeric argument macro required')
            macros.append('#undef ' + name + '\n' + found[0])
        parts = dict(COMMAND=commands[0], MACROS='\n'.join(macros),
            PARSERS='\n'.join(function(core,n) for n in ('isNumeric','getValidInt','getValidFloat')),
            PROFILES=','.join('{%du,%d}' % (r['revision'],r['float_input']) for r in rows),
            VALUES=','.join('{%s,%d,%d}' % (json.dumps(v['text']),v['integer'],v['floating']) for v in data['values']),
            FLAGS=','.join(str(v) for v in data['flags']))
        code = Path(__file__).with_name('rise_invincibility_contract.c.in').read_text()
        for name, value in parts.items():
            code = code.replace('@'+name+'@',value)
        if re.search(r'@[A-Z_]+@',code):
            raise ValueError('Unresolved native riseinv dependency')
        actual = [json.loads(line) for line in native_output(code,data).splitlines()]
        count = len(data['values'])*len(data['flags'])
        self.assertEqual(actual,[dict(revision=r['revision'],cases=count) for r in rows])
        print(json.dumps(dict(riseinv_contexts=len(rows),riseinv_cases=count*len(rows))),file=sys.stderr)

    def test_energy_default_and_complete_command_arguments(self):
        data = load_contract_fixture(FIXTURE)
        actual = [json.loads(line) for line in native_output(energy_program(data), data).splitlines()]
        self.assertEqual([row['revision'] for row in actual],
                         [row['revision'] for row in data['sources']])
        for row in actual:
            self.assertEqual(row['cases'], 1 + 2 * 5 * len(data['energy_values']))
        print(json.dumps(dict(energy_contexts=len(actual),
                              energy_cases=sum(row['cases'] for row in actual))), file=sys.stderr)

    def test_native_stores_getters_defaults_and_freeze_arguments(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual(revisions,contract_revisions(data,data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data),data).splitlines()]
        self.assertEqual({r['revision'] for r in actual},revisions)
        self.assertEqual(len(actual),len(data['sources']))
        groups = {g['key']:g for g in data['declaration_groups']}
        rows = {r['revision']:r for r in data['sources']}
        for row in actual:
            with self.subTest(revision=row['revision']):
                self.assertGreater(row['writes'],0)
                group = groups[rows[row['revision']]['contract']]
                self.assertEqual(row['scalars'],len(group['same_width_fields'])*len(data['values']))
                self.assertEqual(row['freezes'],len(data['freeze'])*len(data['freeze_values']))
                self.assertGreater(row['defaults'],0)
                self.assertGreater(row['attack_bytes'],0)
        print(json.dumps(dict(contexts=len(actual), attack_bytes=sorted({r['attack_bytes'] for r in actual}),
            writes=sum(r['writes'] for r in actual), scalars=sum(r['scalars'] for r in actual),
            defaults=sum(r['defaults'] for r in actual), freezes=sum(r['freezes'] for r in actual))),
            file=sys.stderr)




def pain_program(data):
    root = ROOT / 'src/engines' / data['engine']
    core = (root / 'openbor.c').read_text()
    header = (root / 'openbor.h').read_text()
    attack = function(core, 'do_attack')
    start = attack.index('if( ent_list[i]->exists')
    gate = attack[start:attack.index('{', start)] + '\n'
    increments = re.findall(r'(?m)^[ \t]*\+\+[^\n]*->animhits;', attack)
    if len(increments) != 3:
        raise ValueError('All three native hit increments required')
    def statements(name, text):
        return [line.strip() for line in function(core, name).splitlines()
                if text in line and not line.strip().startswith('//')]
    caller = statements('do_attack', 'self->pain_time =')
    common = statements('common_takedamage', 'self->pain_time =')
    obstacle = statements('obstacle_takedamage', 'self->pain_time =')
    killed = statements('kill', 'self->lasthit == victim')
    if len(caller) != 1 or len(common) > 1 or len(obstacle) > 1 or len(killed) != 1:
        raise ValueError('Exact native deadline/retained-target inventory required')
    empty = re.findall(r'(?m)^const s_attack emptyattack\s*=\s*\{[\s\S]*?^\};', core)
    command = re.findall(r'\bcase CMD_MODEL_FASTATTACK:[\s\S]*?\bbreak;', core)
    default = re.findall(r'(?m)^[ \t]*(?://)?newanim->(?:obor_legacy_)?fastattack[ \t]*=[ \t]*0[ \t]*;[^\n]*', core)
    if len(empty) != 1 or len(command) != 1 or len(default) != 1:
        raise ValueError('Native attack default and complete fastattack command required')
    flag = ('#define SET_FLAG(a,v) ((a)->obor_legacy_fastattack=(unsigned char)(v))\n'
            '#define GET_FLAG(a) ((a)->obor_legacy_fastattack)') if 'obor_legacy_fastattack;' in header else (
            '#define SET_FLAG(a,v) ((void)(a),(void)(v))\n#define GET_FLAG(a) 0')
    rows = []
    for row in data['sources']:
        contract = data['contracts'][row['contract']]
        rows.append('{%du,%s}' % (row['revision'], ','.join(str(contract[k])
            for k in ('flag','cached','clear','caller','common','obstacle'))))
    text = Path(__file__).with_name('pain_time_contract.c.in').read_text()
    parts = dict(FLAG_ACCESS=flag, EMPTY=empty[0], COMMAND=command[0],
        DEFAULT='' if default[0].strip().startswith('//') else default[0],
        HELPER=function(core, 'obor_profile_pain_deadline') if 'static u32 obor_profile_pain_deadline(' in core else '',
        GATE=gate, INCREMENT_A=increments[0], INCREMENT_B=increments[1], INCREMENT_C=increments[2],
        KILL=killed[0], COMMON='\n'.join(common), OBSTACLE='\n'.join(obstacle), CALLER=caller[0],
        PROFILES=',\n'.join(rows), GAME_SPEED=str(data['game_speed']),
        DEFAULT_DELAY=str(data['default_delay']), FAST_DELAY=str(data['fast_delay']))
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native pain contract input')
    return text


class PainTimeContracts(unittest.TestCase):
    def test_native_fastattack_guards_counters_and_deadlines(self):
        data = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-pain-time-contracts.json')
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 3500 <= revision <= 3665:
                self.assertIn(revision, revisions)
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertTrue(all(re.fullmatch('[0-9a-f]{64}', value) for value in row['source_sha256'].values()))
        result = json.loads(native_output(pain_program(data), data))
        self.assertEqual(result['contexts'], len(revisions))
        self.assertEqual(result['cases'], len(revisions) * (8 + 6 + 6 + 2 + 4*6*3))
        print(json.dumps(result), file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
