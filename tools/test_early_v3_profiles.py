"""Check early profile contracts against independent original native results.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PUBLIC = (HERE.parent / 'src/pin.json').is_file()
DEFAULT_SOURCE = HERE.parent if PUBLIC else HERE.parents[2] / 'AnyBOR-libretro'
FIXTURE = HERE / ('early-v3-profile-contracts.json' if PUBLIC else
                  'fixtures/early-v3-profile-contracts.json')
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', DEFAULT_SOURCE))
from early_profile_probe import attack_program, shutdown_program, playback_program, cache_program, system_program, menu_flags_program, layer_program, level_commands_program, background_program, scene_program, collision_program, png_bounds_program, expression_program, keyboard_program, frame_boxes_program, menu_state_program, credits_program, credit_entry_program, shutdown_format_program, compile_program


class EarlyV3ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform == 'linux':
            sys.path.insert(0, str(HERE.parent))
            from run_guarded import require_limits
            require_limits()
        cls.contracts = json.loads(FIXTURE.read_text())['profiles']
        cls.temporary = tempfile.TemporaryDirectory(prefix='anybor-early-profiles-')
        cls.work = Path(cls.temporary.name)
        cls.executables = {}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_physical_family_has_own_source_evidence_for_every_profile(self):
        pins = json.loads((SOURCE / 'src/pin.json').read_text())
        self.assertEqual({str(p['build']) for p in pins['profiles']
                          if str(p['engine']) == '4086'},
                         {p['profile'] for p in self.contracts})
        for row in self.contracts:
            self.assertEqual(row['engine'], '4086')
            self.assertEqual(len(row['source_commit']), 40)
            self.assertEqual({p['kind'] for p in row['native_contracts']},
                             {'attack', 'shutdown', 'playback'})

    @classmethod
    def executable(cls, row, kind):
        engine = SOURCE / 'src/engines' / row['engine']
        script = (engine / 'openborscript.c').read_text()
        if kind == 'attack':
            program = attack_program(script)
        elif kind == 'shutdown':
            program = shutdown_program(script)
        elif kind == 'playback':
            program = playback_program((engine / 'source/gamelib/soundmix.c').read_text())
        elif kind == 'cache':
            program = cache_program((engine / 'source/scriptlib/ScriptVariant.c').read_text())
        elif kind == 'menu':
            program = menu_flags_program((engine / 'openbor.c').read_text())
        elif kind == 'layer':
            program = layer_program((engine / 'openbor.c').read_text())
        elif kind == 'level_commands':
            program = level_commands_program((engine / 'source/gamelib/commands.c').read_text(),
                                             (engine / 'source/gamelib/commands.h').read_text())
        elif kind == 'background':
            program = background_program((engine / 'openbor.c').read_text())
        elif kind == 'scene':
            program = scene_program((engine / 'openbor.c').read_text())
        elif kind == 'collision':
            program = collision_program((engine / 'openbor.c').read_text())
        elif kind == 'png_bounds':
            program = png_bounds_program((engine / 'source/pnglib/pngdec.c').read_text())
        elif kind == 'expression':
            program = expression_program((engine / 'source/preprocessorlib/pp_expr.c').read_text())
        elif kind == 'keyboard':
            program = keyboard_program((engine / 'openbor.c').read_text())
        elif kind == 'frame_boxes':
            program = frame_boxes_program((engine / 'openbor.c').read_text(),
                                          (engine / 'openbor.h').read_text())
        elif kind == 'menu_state':
            program = menu_state_program((engine / 'openbor.c').read_text())
        elif kind == 'credits':
            program = credits_program((engine / 'openbor.c').read_text())
        elif kind == 'credit_entry':
            program = credit_entry_program((engine / 'openbor.c').read_text())
        elif kind == 'shutdown_format':
            program = shutdown_format_program((engine / 'openbor.c').read_text())
        else:
            program = system_program(script, (engine / 'openborscript.h').read_text(),
                                     (engine / 'source/utils.c').read_text())
        digest = hashlib.sha256(program.encode()).hexdigest()
        if digest not in cls.executables:
            executable = cls.work / digest
            compile_program(program, executable)
            cls.executables[digest] = executable
        return cls.executables[digest]

    def observe(self, row, kind, values):
        result = subprocess.run([str(self.executable(row, kind)), row['profile'],
                                 *map(str, values)], capture_output=True, text=True,
                                check=True, timeout=8)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def check_profile(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for contract in row['native_contracts']:
            for case in contract['cases']:
                with self.subTest(profile=profile, kind=contract['kind'], values=case['input']):
                    self.assertEqual(self.observe(row, contract['kind'], case['input']),
                                     case['output'], row['references'])

    def check_namespace(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        names = row['source_observations']['systemvariant_names']
        queries = [(name, i) for i, name in enumerate(names)]
        if 'in_enginecreditsscreen' not in names:
            queries.append(('in_enginecreditsscreen', -1))
        run = subprocess.run([str(self.executable(row, 'namespace')), profile],
                             input=''.join('%s\t%d\n' % q for q in queries),
                             capture_output=True, text=True, check=True, timeout=8)
        observations = [json.loads(line) for line in run.stdout.splitlines()
                        if line.startswith('{')]
        self.assertEqual(len(observations), row['namespace_oracle']['observations'])
        for out in observations:
            present = out['input'] in names
            logical = names.index(out['input']) if present else -1
            numeric = out['mode'][0] == 'n'
            with self.subTest(profile=profile, name=out['input'], mode=out['mode']):
                self.assertEqual(out, dict(
                    input=out['input'], mode=out['mode'], result=0 if present else -1,
                    arg_type=1 if present or numeric else 6,
                    arg_id=logical if present or numeric else 1,
                    handler_name=out['input'] if present else '<none>',
                    null_result=int(not present)), row['references'])

    def check_menu_flags(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['menu_flags']['cases']:
            with self.subTest(profile=profile, completion=case['input']):
                self.assertEqual(self.observe(row, 'menu', [case['input']]),
                                 case['output'], row['references'])

    def check_layers(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['layers']['cases']:
            with self.subTest(profile=profile, layer=case['input']):
                self.assertEqual(self.observe(row, 'layer', [case['input']]),
                                 case['output'], row['references'])

    def check_level_commands(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        self.assertEqual(self.observe(row, 'level_commands', []),
                         row['level_commands']['output'], row['references'])

    def check_backgrounds(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['backgrounds']['cases']:
            with self.subTest(profile=profile, background=case['input']):
                self.assertEqual(self.observe(row, 'background', case['input']),
                                 case['output'], row['references'])

    def check_scene(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['scenes']['cases']:
            with self.subTest(profile=profile, scene=case['input']):
                self.assertEqual(self.observe(row, 'scene', case['input']),
                                 case['output'], row['references'])

    def check_collision(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['collisions']['cases']:
            with self.subTest(profile=profile, collision=case['input']):
                self.assertEqual(self.observe(row, 'collision', case['input']),
                                 case['output'], row['references'])

    def check_keyboard(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        self.assertEqual(self.observe(row, 'keyboard', []),
                         row['keyboard']['output'], row['references'])

    def check_frame_boxes(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['frame_boxes']['cases']:
            with self.subTest(profile=profile, frame_boxes=case['input']):
                self.assertEqual(self.observe(row, 'frame_boxes', case['input']),
                                 case['output'], row['references'])

    def check_menu_state(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['menu_state']['cases']:
            with self.subTest(profile=profile, menu_state=case['input']):
                self.assertEqual(self.observe(row, 'menu_state', case['input']),
                                 case['output'], row['references'])

    def check_credits(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['credits']['cases']:
            with self.subTest(profile=profile, credits=case['input']):
                actual = self.observe(row, 'credits', case['input'])
                digest = hashlib.sha256(json.dumps(
                    actual, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                self.assertEqual(digest, case['trace_sha256'], row['references'])

    def check_credit_entry(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['credit_entry']['cases']:
            with self.subTest(profile=profile, shutdown=case['input']):
                self.assertEqual(self.observe(row, 'credit_entry', case['input']),
                                 case['output'], row['references'])

    def check_shutdown_format(self, profile):
        row = next(p for p in self.contracts if p['profile'] == profile)
        for case in row['shutdown_format']['cases']:
            with self.subTest(profile=profile, format=case['input']):
                self.assertEqual(self.observe(row, 'shutdown_format', case['input']),
                                 case['output'], row['references'])

    def test_shutdown_preserves_defined_percent_escapes_for_every_profile(self):
        for row in self.contracts:
            with self.subTest(profile=row['profile']):
                result = self.observe(row, 'shutdown', [1, 2, 1])
                self.assertEqual(result['result'], 0)
                self.assertEqual(result['calls'], 1)
                self.assertEqual(result['percent_escape'], 1)

    def test_shutdown_rejects_formats_requiring_missing_arguments(self):
        # The mock intercepts an invalid format if the maintained entry point
        # fails to reject it; no undefined original variadic read is executed.
        for row in self.contracts:
            with self.subTest(profile=row['profile']):
                result = self.observe(row, 'shutdown', [1, 2, 2])
                self.assertEqual(result['result'], -1)
                self.assertEqual(result['calls'], 0)

    def test_shutdown_rejects_an_unreadable_legacy_cache_index_safely(self):
        # Original out-of-range reads have no defined oracle result. These
        # safety assertions apply only to the maintained implementation.
        for row in self.contracts:
            if row['source_observations']['shutdown_message_argument']:
                continue
            with self.subTest(profile=row['profile']):
                result = self.observe(row, 'shutdown', [99999, 2, 0])
                self.assertEqual(result['result'], -1)
                self.assertEqual(result['calls'], 0)

    def test_actual_cache_lookup_checks_allocation_and_logical_bounds(self):
        row = self.contracts[0]
        for index in (-1, 0, 1, 2, 3, 4, 2147483647):
            with self.subTest(index=index):
                self.assertEqual(self.observe(row, 'cache', [index, 0]),
                                 {'readable': int(index in (0, 1))})
        self.assertEqual(self.observe(row, 'cache', [0, 1]), {'readable': 0})

    def test_missing_masked_base_is_rejected_without_dereferencing_null(self):
        for row in self.contracts:
            with self.subTest(profile=row['profile']):
                self.assertEqual(self.observe(row, 'layer', ['missing_masked_base'])['error'], 1)

    def test_png_reader_stops_before_crossing_the_member_boundary(self):
        row = self.contracts[0]
        binary = self.executable(row, 'png_bounds')
        for size in (1, 2, 3):
            with self.subTest(size=size):
                run = subprocess.run([str(binary), str(size)], capture_output=True,
                                     text=True, check=True, timeout=8)
                self.assertEqual(json.loads(run.stdout), dict(
                    error=int(size > 2), first=17 if size <= 2 else 0,
                    remaining=2-size if size <= 2 else 2))

    def test_temporary_expression_has_the_same_result_and_one_owner(self):
        row = self.contracts[0]
        binary = self.executable(row, 'expression')
        for value in (-1, 0, 1, 37, 99):
            with self.subTest(value=value):
                run = subprocess.run([str(binary), str(value)], capture_output=True,
                                     text=True, check=True, timeout=8)
                self.assertEqual(json.loads(run.stdout), dict(
                    result=-1 if value == 99 else int(value != 0),
                    destroyed=int(value != 99)))

    def test_shutdown_formatter_bounds_oversized_diagnostic_text(self):
        for row in self.contracts:
            with self.subTest(profile=row['profile']):
                self.assertEqual(self.observe(row, 'shutdown_format', [3]),
                                 dict(length=1023, last=ord('a')))


def contract_test(profile):
    def check(self):
        self.check_profile(profile)
    return check


def namespace_test(profile):
    def check(self):
        self.check_namespace(profile)
    return check


def menu_test(profile):
    def check(self):
        self.check_menu_flags(profile)
    return check


def layer_test(profile):
    def check(self):
        self.check_layers(profile)
    return check


def level_commands_test(profile):
    def check(self):
        self.check_level_commands(profile)
    return check


def backgrounds_test(profile):
    def check(self):
        self.check_backgrounds(profile)
    return check


def scene_test(profile):
    def check(self):
        self.check_scene(profile)
    return check


def collision_test(profile):
    def check(self):
        self.check_collision(profile)
    return check


def keyboard_test(profile):
    def check(self):
        self.check_keyboard(profile)
    return check


def frame_boxes_test(profile):
    def check(self):
        self.check_frame_boxes(profile)
    return check


def menu_state_test(profile):
    def check(self):
        self.check_menu_state(profile)
    return check


def credits_test(profile):
    def check(self):
        self.check_credits(profile)
    return check


def credit_entry_test(profile):
    def check(self):
        self.check_credit_entry(profile)
    return check


def shutdown_format_test(profile):
    def check(self):
        self.check_shutdown_format(profile)
    return check


for _profile in ('4086', '4088', '4107', '4111', '4129', '4153'):
    setattr(EarlyV3ProfileTests, 'test_original_native_contract_' + _profile,
            contract_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_namespace_' + _profile,
            namespace_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_menu_flags_' + _profile,
            menu_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_layers_' + _profile,
            layer_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_level_commands_' + _profile,
            level_commands_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_backgrounds_' + _profile,
            backgrounds_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_scenes_' + _profile,
            scene_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_collisions_' + _profile,
            collision_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_keyboard_' + _profile,
            keyboard_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_frame_boxes_' + _profile,
            frame_boxes_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_menu_state_' + _profile,
            menu_state_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_credits_' + _profile,
            credits_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_credit_entry_' + _profile,
            credit_entry_test(_profile))
    setattr(EarlyV3ProfileTests, 'test_original_shutdown_format_' + _profile,
            shutdown_format_test(_profile))


if __name__ == '__main__':
    unittest.main()
