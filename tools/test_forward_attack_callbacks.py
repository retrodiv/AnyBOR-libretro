"""Execute native attack callback locals, cleanup and caller arguments.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-attack-callbacks-contracts.json'


def source_calls(source, names):
    """Extract complete direct calls, excluding comments and literal text."""
    if (not isinstance(source, str) or not source.strip() or len(source) > 262144 or
            not isinstance(names, (list, tuple)) or not names or
            any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w*', name) for name in names) or
            len(set(names)) != len(names)):
        raise ValueError('Explicit native callees required')
    masked = re.sub(r'/\*.*?\*/|//(?:\\(?:\r?\n|[\s\S])|[^\n\\])*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: re.sub(r'[^\n]', ' ', m[0]), source, flags=re.S)
    rows = []
    for match in re.finditer(r'\b('+'|'.join(re.escape(n) for n in names)+r')\s*\(', masked):
        start = match.end(); depth = 1; cursor = start; boundaries = [start]
        while cursor < len(masked) and depth:
            value = masked[cursor]
            if value == ',' and depth == 1:
                boundaries.append(cursor + 1)
            depth += (value == '(') - (value == ')'); cursor += 1
        if depth:
            raise ValueError('Incomplete native callback call')
        if masked[cursor:].lstrip().startswith('{'):
            continue
        ends = [i - 1 for i in boundaries[1:]] + [cursor - 1]
        args = [source[a:b].strip() for a, b in zip(boundaries, ends)]
        rows.append(dict(callee=match[1], arguments=args, text=source[match.start():cursor]))
    return rows


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    contexts = ','.join('{%du,%d}' % (r['revision'], r['tag']) for r in data['sources'])
    keys = ['{'+','.join(json.dumps(n) for n in row['keys'])+'}' for row in data['callbacks']]
    sizes = ','.join(str(len(row['keys'])) for row in data['callbacks'])
    observed = []
    for owner in data['caller_functions']:
        for index, row in enumerate(source_calls(function(core, owner), data['callees'])):
            observed.append(row | dict(owner=owner, ordinal=index))
    if [(r['owner'], r['ordinal'], r['callee']) for r in observed] != [
            (r['owner'], r['ordinal'], r['callee']) for r in data['calls']]:
        raise ValueError('Complete independently inventoried callback caller sequence required')
    cases = '\n'.join('case %d:%s;break;' % (i, row['text']) for i, row in enumerate(observed))
    expected = ','.join('{%d,%d,%d,{%s},%d}' % (r['kind'], r['entity'], r['other'],
        ','.join(map(str, r['values'])), r['attack_tag']) for r in data['calls'])
    values = dict(CONTEXTS=contexts, KEYS=','.join(keys), KEY_COUNTS=sizes,
        CALLBACKS='\n'.join(function(core, name) for name in data['functions']),
        FALL=function(core, 'set_fall'), CALLS=cases, EXPECTED_CALLS=expected,
        TAG_VALUES=','.join(map(str, data['tag_values'])),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')))
    text = Path(__file__).with_name('forward_attack_callbacks_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack callback input')
    return text


class ForwardAttackCallbackTests(unittest.TestCase):
    def test_native_callback_locals_cleanup_and_caller_arguments(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
