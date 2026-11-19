"""Execute source-owned argument extents, selection bytes and saved records.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_line_arguments import ARGUMENT_PROGRAM, FINDER_PROGRAM
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-content-capacity-contracts.json'
NAME_FIXTURE = FIXTURE.with_name('profile-4432-name-capacity-contracts.json')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own capacity sources and exact controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values()) or
                row['line_capacity'] not in (511, 512) or row['argument_limit'] != 64 or
                row['allowed_bytes'] not in (512, 1024) or type(row['final_byte']) is not bool):
            raise ValueError('Own argument and selection extents required')
    for record in data['records']:
        if hashlib.sha256(record['record'].encode()).hexdigest() != record['record_sha256']:
            raise ValueError('Original saved record identity changed')
    return data


def source():
    engine = ROOT / 'src/engines/4432'
    return ((engine / 'openbor.c').read_text(), (engine / 'openbor.h').read_text(),
            (engine / 'openborscript.c').read_text())


def argument_programs(data):
    core, header, script = source()
    helper = ''
    constants = '\n'.join(re.findall(r'^#define[ \t]+MAX_ARG_(?:LEN|COUNT)[^\r\n]*', header, re.M))
    record = re.search(r'typedef\s+struct\s+ArgList\s*\{[^{}]*\}\s*ArgList;', header)[0]
    contracts = ','.join('{%du,%du,%du}' % (r['revision'], r['argument_limit'], r['line_capacity'])
                         for r in data['sources'])
    parser = ARGUMENT_PROGRAM.replace('CONSTANTS', constants + '\n' + helper)
    parser = parser.replace('RECORD', record).replace('PARSER',
        '#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
        function(core, 'ParseArgs') + '\n#pragma GCC diagnostic pop\n')
    parser = parser.replace('CONTRACTS', contracts)
    constant = re.search(r'else if\(stricmp\(constname, "MAX_ARG_LEN"\)==0\)\s*\{[^{}]*\}', script)[0]
    finder = FINDER_PROGRAM.replace('MAXIMUM', constants + '\n' + helper)
    finder = finder.replace('FINDARG', function(core, 'findarg')).replace('CONSTANT', constant)
    finder = finder.replace('size_t argument_limit,line_capacity;', 'size_t argument_limit,line_capacity;int final_byte;')
    finder = finder.replace('CONTRACTS', ','.join('{%du,%du,%du,%d}' %
        (r['revision'], r['argument_limit'], r['line_capacity'], r['final_byte']) for r in data['sources']))
    cases = ','.join('{%s,%d,%s,%s}' %
        (json.dumps(c['text']), c['which'], json.dumps(c['before']), json.dumps(c['after']))
        for c in data['finder_cases'])
    finder = finder.replace('int main(void) {', 'static const struct {const char *text;int which;'
        'const char *before,*after;} cases[]={' + cases + '};\nint main(void) {')
    end = finder.rfind('\n    }\n}')
    if end < 0:
        raise ValueError('Complete native finder contract loop required')
    finder = finder[:end] + r'''
        for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);c++) {
            char prime[514];memset(prime,'P',513);prime[513]=0;
            (void)findarg(prime,0);
            assert(!strcmp(findarg((char*)cases[c].text,cases[c].which),
                contracts[i].final_byte?cases[c].after:cases[c].before));
        }
''' + finder[end:]
    return parser, finder


def allowed_program(data):
    core, header, _ = source()
    constants = '\n'.join(re.findall(
        r'^#define[ \t]+(?:MAX_ARG_(?:LEN|COUNT)|MAX_ALLOWSELECT_LEN)[^\r\n]*', header, re.M))
    record = re.search(r'typedef\s+struct\s+ArgList\s*\{[^{}]*\}\s*ArgList;', header)[0]
    values = dict(CONSTANTS=constants, RECORD=record + '\n' +
        re.search(r'^#define GET_ARG\([^\r\n]+', header, re.M)[0],
        FUNCTIONS='\n'.join(function(core, n) for n in ('ParseArgs', 'load_playable_list')),
        CONTEXTS=','.join(str(r['revision']) + 'u' for r in data['sources']),
        CASES=','.join(json.dumps(c['text']) for c in data['allowed_cases']))
    text = Path(__file__).with_name('content_capacity_allowed_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    return text


def saved_program(data):
    core, _, _ = source()
    start = core.index('/* Logical input extents and saved bytes')
    helpers = core[start:core.index('void clearSavedGame()', start)]
    if ('obor_profile_write_saved_game(handle)' not in function(core, 'saveGameFile') or
            'obor_profile_read_saved_game(handle)' not in function(core, 'loadGameFile') or
            'obor_saved_level_record_size()' not in function(core, 'loadGameFile')):
        raise ValueError('Native callers must use the selected saved-record view')
    names = data['records'][-1]['fields']
    ids = {name: i + 1 for i, name in enumerate(names)}
    definitions, runners, sizes = [], [], []
    for index, entry in enumerate(data['records']):
        typename = 'oracle_record_' + str(index)
        definitions.append(re.sub(r'\bs_savelevel\b', typename, entry['record']))
        fill = ['static void oracle_fill_%d(%s *v,unsigned seed){memset(v,0x6d,sizeof(*v));' % (index, typename)]
        check = ['static void oracle_check_%d(const %s *v,const s_savelevel *actual,const unsigned char *before){' %
                 (index, typename)]
        if index == len(data['records']) - 1:
            check.append('CHECK(sizeof(*v)==sizeof(*actual));CHECK(!memcmp(v,actual,sizeof(*v)));}')
        else:
            check.append('static unsigned char mask[sizeof(s_savelevel)];memset(mask,0,sizeof(mask));')
        offsets = ['0', '1', '2', '3', '4', 'sizeof(' + typename + ')', '2*sizeof(' + typename + ')+17']
        for name in entry['fields']:
            declaration = re.search(r'(?m)^\s*(unsigned|int|char)\s+' + name + r'\s*([^;]*);', entry['record'])
            kind, dims = declaration[1], declaration[2].count('[')
            if kind == 'char' and dims == 2:
                fill.append('for(size_t i=0;i<sizeof(v->%s)/sizeof(v->%s[0]);i++)fill_ascii(v->%s[i],sizeof(v->%s[i]),seed+%d+i);' %
                            (name, name, name, name, ids[name]))
            elif kind == 'char':
                fill.append('fill_ascii(v->%s,sizeof(v->%s),seed+%d);' % (name, name, ids[name]))
            elif dims:
                fill.append('for(size_t i=0;i<sizeof(v->%s)/sizeof(v->%s[0]);i++)v->%s[i]=number(seed,%d+i);' %
                            (name, name, name, ids[name]))
            else:
                fill.append('v->%s=%s;' % (name, '2' if name == 'selectLoadCount' else 'number(seed,%d)' % ids[name]))
            if index != len(data['records']) - 1:
                if kind == 'char' and dims == 2:
                    check.append('for(size_t i=0;i<sizeof(v->%s)/sizeof(v->%s[0]);i++){'
                        'CHECK(!memcmp(actual->%s[i],v->%s[i],sizeof(v->%s[i])));'
                        'memset(mask+((const unsigned char*)actual->%s[i]-(const unsigned char*)actual),1,sizeof(v->%s[i]));}' %
                        (name, name, name, name, name, name, name))
                else:
                    check.append('CHECK(!memcmp(&actual->%s,&v->%s,sizeof(v->%s)));'
                        'memset(mask+offsetof(s_savelevel,%s),1,sizeof(v->%s));' % (name, name, name, name, name))
            off = 'offsetof(%s,%s)' % (typename, name)
            length = 'sizeof(((%s*)0)->%s)' % (typename, name)
            offsets += ['(' + off + '?'+off+'-1:0)', off, off + '+1',
                        off + '+' + length + '-1', off + '+' + length]
            if kind == 'char' and dims == 2:
                row = 'sizeof(((%s*)0)->%s[0])' % (typename, name)
                offsets += [off+'+'+row+'-1', off+'+'+row, off+'+2*'+row+'-1']
        fill.append('}')
        if index != len(data['records']) - 1:
            check.append('for(size_t i=0;i<sizeof(*actual);i++)if(!mask[i])CHECK(((const unsigned char*)actual)[i]==before[i]);}')
        definitions += ['\n'.join(fill), '\n'.join(check)]
        definitions.append('static const size_t offsets_%d[]={%s};' % (index, ','.join(offsets)))
        definitions.append('static void run_%d(const struct contract *c){RUN_RECORD(%s,%d);}' %
                           (index, typename, index))
        runners.append('run_' + str(index))
        sizes.append('sizeof(' + typename + ')')
    declarations = {name: re.search(r'(?m)^\s*(unsigned|int|char)\s+' + name + r'\s*([^;]*);',
                                    data['records'][-1]['record']) for name in names}
    native_fill = []
    for name in names:
        kind, dims = declarations[name][1], declarations[name][2].count('[')
        prefix = ''
        if name in ('selectFlag', 'selectMusic', 'selectBackground', 'selectLoad', 'selectLoadCount'):
            prefix = 'if(c->extended)'
        elif name == 'selectSkipSelect':
            prefix = 'if(c->skip)'
        if kind == 'char':
            width = ('c->name+1' if name in ('dName', 'pName') else
                     'c->allowed' if name == 'allowSelectArgs' else 'c->line+1')
            if dims == 2:
                operation = 'for(size_t i=0;i<sizeof(v->%s)/sizeof(v->%s[0]);i++)fill_ascii(v->%s[i],%s,seed+%d+i);' % (
                    name, name, name, width, ids[name])
            else:
                operation = 'fill_ascii(v->%s,%s,seed+%d);' % (name, width, ids[name])
        elif dims:
            operation = 'for(size_t i=0;i<sizeof(v->%s)/sizeof(v->%s[0]);i++)v->%s[i]=number(seed,%d+i);' % (
                name, name, name, ids[name])
        else:
            operation = 'v->%s=%s;' % (name, '2' if name == 'selectLoadCount' else 'number(seed,%d)' % ids[name])
        native_fill.append(prefix + '{' + operation + '}' if prefix else operation)
    values = dict(HELPERS=helpers, NATIVE_FILL='\n'.join(native_fill), DEFINITIONS='\n'.join(definitions),
        RUNNERS=','.join(runners), SIZES=','.join(sizes),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d,%d,%d,%d}' % (r['revision'], r['record'],
            r['line_capacity'], r['allowed_bytes'], r['name_capacity'], r['extended_record'],
            r['skip_record'], r['revision'] in data['partial_controls']) for r in data['sources']))
    text = Path(__file__).with_name('content_capacity_saved_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    return text


def saved_scores_program(data):
    core, _, script = source()
    native = data['layout']['record']
    if hashlib.sha256(native.encode()).hexdigest() != data['layout']['record_sha256']:
        raise ValueError('Original high-score record identity changed')
    widths = sorted({row['name_bytes'] for row in data['sources']})
    definitions = []
    for width in widths:
        definition = re.sub(r'\bMAX_NAME_LEN\b', str(width), native)
        definitions.append(re.sub(r'\bs_savescore\b', f'native_score_{width}', definition))
    helpers = ['obor_profile_legacy_saved_game', 'obor_pack_saved_scores',
               'obor_profile_write_saved_scores', 'obor_profile_read_saved_scores',
               'obor_profile_name_limit']
    for entry, helper in [('saveHighScoreFile', 'obor_profile_write_saved_scores'),
                          ('loadHighScoreFile', 'obor_profile_read_saved_scores')]:
        if helper + '(handle)' not in function(core, entry):
            raise ValueError('Native high-score route must use the selected record format')
    parts = dict(
        RECORDS='\n'.join(definitions),
        PHYSICAL=re.search(r'typedef struct\s*\{[^{}]*\}\s*obor_saved_score_before_4429;', core)[0],
        HELPERS='\n'.join(function(core, helper) for helper in helpers),
        CONSTANT=re.search(r'else if\(stricmp\(constname, "MAX_NAME_LEN"\)==0\)\s*\{[^{}]*\}',
                           function(script, 'mapstrings_transconst'))[0],
        CHECKERS='\n'.join(f'DEFINE_CHECKER({width})' for width in widths),
        CHECKS='\n'.join(f"    check_{row['name_bytes']}({row['revision']}u);"
                         for row in data['sources']))
    template = Path(__file__).with_name('content_capacity_scores_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)


def name_runtime_program(data):
    core, _, script = source()
    variant = (ROOT / 'src/engines/4432/source/scriptlib/ScriptVariant.c').read_text()
    helpers = [function(variant, 'ScriptVariant_IntegerValue')]
    if 'void obor_profile_copy_name(' in core:
        helpers.extend(function(core, name) for name in
                       ('obor_profile_name_limit', 'obor_profile_copy_name'))
        helpers.append('#define PROFILE_NAME_COPY 1')
    parts = dict(
        HELPERS='\n'.join(helpers),
        BRANCH=function(script, 'openbor_jumptobranch'),
        CHECKS='\n'.join(f"    check_names({row['revision']}u, {row['name_bytes']});"
                         for row in data['sources']))
    template = Path(__file__).with_name('content_capacity_names_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)


class ContentCapacityContracts(unittest.TestCase):
    def test_native_argument_counts_extents_finder_and_script_constant(self):
        data = fixture_data()
        for code in argument_programs(data):
            self.assertEqual(native_output(code, data), '')

    def test_native_allowed_list_and_stored_bytes(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(allowed_program(data), data).splitlines()]
        wanted = [(r, i, c) for r in data['sources'] for i, c in enumerate(data['allowed_cases'])]
        self.assertEqual(len(actual), len(wanted))
        for result, (row, index, case) in zip(actual, wanted):
            label = 'revision=%s case=%s' % (row['revision'], index)
            modern = row['line_capacity'] == 512
            self.assertEqual({k: result[k] for k in ('revision', 'case', 'status', 'reset', 'selected', 'calls', 'diagnostic')},
                dict(revision=row['revision'], case=index, status=case['status'], reset=case['reset'],
                     selected=case.get('selected_modern', case['selected']) if modern else case['selected'],
                     calls=case.get('calls_modern', case['calls']) if modern else case['calls'],
                     diagnostic=case['diagnostic']), label)
            raw = bytes.fromhex(result['bytes'])
            expected = bytearray(b'Z' * 1024)
            if case['accepted']:
                prefix = case['prefix'].encode()[:row['line_capacity'] - 1]
                expected[:row['allowed_bytes']] = prefix.ljust(row['allowed_bytes'] - 1, b' ') + b'\0'
            if raw != expected:
                bad = next((i for i, (a, b) in enumerate(zip(raw, expected)) if a != b), min(len(raw), len(expected)))
                self.fail(label + ' stored-byte=' + str(bad))

    def test_native_saved_record_bytes_and_partial_field_boundaries(self):
        data = fixture_data()
        result = json.loads(native_output(saved_program(data), data))
        self.assertEqual(result['contexts'], len(data['sources']))
        self.assertEqual(result['status'], 'PASS')
        self.assertGreater(result['partial_cases'], 100)
        self.assertEqual(len(result['record_sizes']), len(data['records']))

    def test_4432_native_score_record_bytes_and_name_capacity(self):
        data = load_contract_fixture(NAME_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(data, pin['profiles'], source_range=data['range']):
            if profile['engine'] == data['engine']:
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'], data['engine'])
            self.assertIn(row['name_bytes'], (47, 50))
            if '_contract_boundaries' not in data:
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
        actual = json.loads(native_output(saved_scores_program(data), data,
                                          extra_cflags=('-fgnu89-inline',)))
        expected_partials = sum((524 if row['name_bytes'] == 47 else 556) + 1
                                for row in data['sources'])
        self.assertEqual(actual, {'contexts': len(revisions), 'partial_records': expected_partials})

    def test_4432_name_writers_and_script_branch(self):
        data = load_contract_fixture(NAME_FIXTURE)
        actual = json.loads(native_output(name_runtime_program(data), data,
                                          extra_cflags=('-fgnu89-inline',)))
        self.assertEqual(actual, {'contexts': len(data['sources']), 'checks': 14 * len(data['sources'])})
        core, _, script = source()
        writers = {
            'load_cached_model': ('newchar->branch, value',),
            'load_levelorder': ('branch_name, GET_ARG(1)', 'rush_names[0], GET_ARG(3)',
                                'rush_names[1], GET_ARG(6)'),
            'load_level': ('next.alias, GET_ARG(1)', 'next.itemalias, GET_ARG(1)'),
            'updatestatus': ('player[i].name, model->name',),
            'spawn': ('e->name, e->modeldata.name',),
            'player_think': ('branch_name, other->modeldata.branch',),
            'smartspawn': ('e->name, props->alias', 'e->itemalias, props->itemalias'),
            'selectplayer': ('player[i].name, skipselect[i]', 'player[i].name, example[i]->model->name'),
            'playgame': ('player[i].name, save->pName[i]', 'skipselect[i], le->skipselect[i]'),
        }
        for method, assignments in writers.items():
            body = function(core, method)
            for assignment in assignments:
                self.assertIn(f'obor_profile_copy_name({assignment});', body, method)
        for assignment in ('save->pName[i], player[i].name', 'save->dName, set->name'):
            self.assertIn(f'strncpy({assignment}, obor_profile_name_limit());',
                          function(core, 'savelevelinfo'))
        self.assertIn(
            'strncpy(savelevel[saveslot].dName, levelsets[saveslot].name, obor_profile_name_limit() + 1);',
            function(core, 'menu_difficulty'))
        for assignment in ('ent->name, StrCache_Get(varlist[2]->strVal)',
                           'spawnentry.alias, StrCache_Get(arg->strVal)',
                           'spawnentry.itemalias, StrCache_Get(arg->strVal)'):
            self.assertIn(f'obor_profile_copy_name({assignment});', script)


if __name__ == '__main__':
    unittest.main()
