"""Compare original animation script composition at the model load sites.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-animation-script-composition-contracts.json'
HELPERS = (
    'lcmAnimationSkipComment', 'lcmAnimationFindMain', 'lcmAnimationAfterToken', 'lcmAnimationReplace',
    'lcmScriptAddMain', 'lcmScriptJoinMain', 'lcmScriptDeleteMain', 'lcmLogAnimationScript',
)


SCAN = """if(comment_at >= 0)
    {
        body = (ptrdiff_t)lcmAnimationSkipComment(text, length, (size_t)comment_at, obor_profile_build);
    }
    else
    {
        size_t start, next;
        if(lcmAnimationFindMain(text, length, obor_profile_build, &start, &next))
        {
            if(obor_profile_build >= 4340)
            {
                begin = (ptrdiff_t)start;
            }
            if(obor_profile_build >= 4340 && obor_profile_build < 4363)
            {
                next = (size_t)(strchr(text + start, '{') - text) + 1;
            }
            body = (ptrdiff_t)next;
        }
    }"""


def loader_region(loader, pattern):
    matches = list(re.finditer(pattern, loader, re.M | re.S))
    if len(matches) != 1:
        raise ValueError('Expected one original animation script loader region')
    return matches[0][0]


def program(data, original=None):
    if original is None:
        path = ROOT / 'src/engines' / data['engine'] / 'openbor.c'
        text = path.read_text(encoding='utf-8', errors='surrogateescape')
        loader = function(text, 'load_cached_model')
        mode = loader_region(loader, r'^    const unsigned int animation_build =.*?^    const int separate_animation_script = [^;]+;')
        command = loader_region(loader, r'^            case CMD_MODEL_ANIMATIONSCRIPT:.*?(?=^            case )')
        finalize = loader_region(loader, r'^    tempInt = 1;\s*if\(separate_animation_script && animscriptbuf.*?goto lCleanup;\s*}')
        helpers = '\n'.join(function(text, name) for name in HELPERS)
        scan = SCAN
    else:
        mode, command, finalize, helpers, scan = original

    checks = []
    for row in data['sources']:
        revision = row['revision']
        checks.append(f'    obor_profile_build = {revision};')
        for index, outcome in enumerate(data['contracts'][row['contract']]):
            if outcome is not None:
                checks.append(f'    observe({index});')
        for index, outcome in enumerate(data['scan_contracts'][row['contract']]):
            if outcome is not None:
                checks.append(f'    observe_scan({index});')
    values = {
        'MODE': mode, 'COMMAND': command, 'FINALIZE': finalize, 'HELPERS': helpers,
        'CASES': ',\n'.join(
            '{%s, %s, %d}' % (json.dumps(case['directive']) if case['directive'] is not None else 'NULL',
                              json.dumps(case['body']), case['subclassed'])
            for case in data['cases']
        ),
        'SCAN': scan,
        'SCAN_CASES': ',\n'.join(
            '{%s, %d}' % (json.dumps(case['text']), case['comment_at'])
            for case in data['scan_cases']
        ),
        'CHECKS': '\n'.join(checks),
    }
    template = Path(__file__).with_name('animation_script_composition_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def observations(output):
    for line in output.splitlines():
        fields = line.split('\t')
        if fields[1] == 's':
            revision, _, case, begin, body = fields
            yield (int(revision), 'scanner', int(case)), [int(begin), int(body)]
            continue
        revision, case, trace, pos, status, appended, logged = fields
        yield (int(revision), 'loader', int(case)), [
            trace, int(pos), bool(int(status)), bytes.fromhex(appended).decode('ascii'),
            bytes.fromhex(logged).decode('ascii'),
        ]


def generated_guard_program(data, loader):
    declarations = [
        loader_region(loader, r'^    const unsigned int animation_build =.*?^    const int separate_animation_script = [^;]+;'),
        *(loader_region(loader, r'^    static const char ' + name + r'\[\].*?^    \};')
          for name in ('pre_text', 'ifid_text', 'if_text')),
    ]
    initial = re.search(r'(?ms)^    const char \*initial_frame_text = [^;]+;', loader)
    if initial:
        declarations.append(initial[0])
    skeletons = re.findall(r'buffer_append\(&scriptbuf, ([a-z_]+), 0xffffff, &sbsize, &scriptlen\);', loader)
    skeletons = [item for item in skeletons if item in ('pre_text', 'initial_frame_text')]
    animation_guards = re.findall(r'sprintf\(namebuf, ifid_text, [^;]+;', loader)
    frame_guards = re.findall(r'sprintf\(namebuf, if_text, [^;]+;', loader)
    if (len(skeletons), len(animation_guards), len(frame_guards)) != (2, 2, 1):
        raise ValueError('Expected both animation sites and one generated frame guard')
    checks = ['check_text(' + item + ', skeleton);' for item in skeletons]
    for site in animation_guards:
        checks.extend((site, 'check_text(namebuf, animation);'))
    checks.extend((frame_guards[0], 'check_text(namebuf, frame);'))
    rows = ['check_profile(%du, %s, %s, %s);' % (row['revision'],
            json.dumps(row['skeleton']), json.dumps(row['animation'].replace('%d', '37')),
            json.dumps(row['frame'].replace('%d', '2'))) for row in data['sources']]
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint32_t obor_profile_build;
static unsigned checks;
static void check_text(const char *observed, const char *expected)
{
    if(strcmp(observed, expected)) {
        fprintf(stderr, "Generated animation guard differs in revision %u at check %u\n",
                obor_profile_build, checks);
        abort();
    }
    ++checks;
}
static void check_profile(unsigned revision, const char *skeleton,
                          const char *animation, const char *frame)
{
    obor_profile_build = revision;
    char namebuf[256];
    const struct { int index; } selected = {37}, *newanim = &selected;
    int curframe = 2;
''' + '\n'.join(declarations + checks) + r'''
}
int main(void)
{
''' + '\n'.join(rows) + r'''
    printf("%u\n", checks);
}
'''


class AnimationScriptCompositionContracts(unittest.TestCase):
    def test_generated_animation_and_frame_guards(self):
        path = Path(__file__).with_name('fixtures') / 'profile-generated-animation-local-contracts.json'
        data = load_contract_fixture(path)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(data['engine'], '4432')
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        source = ROOT / 'src/engines' / data['engine'] / 'openbor.c'
        loader = function(source.read_text(encoding='latin1'), 'load_cached_model')
        result = native_output(generated_guard_program(data, loader), data)
        self.assertEqual(int(result), 5 * len(revisions))
        print(f'Generated animation guards passed {int(result)} checks across {len(revisions)} contexts.', flush=True)

    def test_checked_wrapper_for_unrecognized_legacy_main(self):
        data = load_contract_fixture(FIXTURE)
        control = data['checked_wrapper']
        contract = control['reference_contract']
        case_index = [case['name'] for case in data['cases']].index(control['case'])
        outcome = data['contracts'][contract][case_index]
        sample = data | {
            'sources': [{'revision': revision, 'contract': contract} for revision in control['revisions']],
            'contracts': {contract: [outcome if i == case_index else None for i in range(len(data['cases']))]},
            'scan_contracts': {contract: [None] * len(data['scan_cases'])},
        }
        actual = list(observations(native_output(program(sample), data)))
        self.assertEqual(actual, [((revision, 'loader', case_index), outcome) for revision in control['revisions']])

    def test_loader_route_composition_and_diagnostics(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = list(observations(native_output(program(data), data)))
        expected = []
        domains = (
            ('loader', data['cases'], data['contracts']),
            ('scanner', data['scan_cases'], data['scan_contracts']),
        )
        for row in data['sources']:
            for domain, cases, contracts in domains:
                outcomes = contracts[row['contract']]
                self.assertEqual(len(outcomes), len(cases))
                for i, outcome in enumerate(outcomes):
                    if outcome is not None:
                        expected.append(((row['revision'], domain, i), cases[i]['name'], outcome))
        self.assertEqual(len(actual), len(expected))
        for result, (identity, name, outcome) in zip(actual, expected):
            with self.subTest(revision=identity[0], domain=identity[1], case=name):
                self.assertEqual(result, (identity, outcome))



if __name__ == '__main__':
    unittest.main()
