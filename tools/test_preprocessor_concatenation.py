"""Check complete native macro expansion with initialized temporary tokens.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from native_allocation_policy import bind_named_allocation_support
from native_sanitizers import sanitizer_environment


HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
ENGINES = ('4432', '6391', '7142', '7533', '8023')
PREFIX = '#define JOIN(a,b) a ## b\n'
CASES = (
    (PREFIX + 'JOIN(alpha,beta)\n', 'alphabeta'),
    (PREFIX + '#define LEFT alpha\n#define RIGHT beta\nJOIN(LEFT,RIGHT)\n', 'alphabeta'),
    (PREFIX + '#define WORDS first second\nJOIN(WORDS,tail)\n', 'first|secondtail'),
    (PREFIX + '#define WORDS first second\nJOIN(head,WORDS)\n', 'headfirst|second'),
    (PREFIX + '#define WORDS first second\n#define ALIAS WORDS\nJOIN(ALIAS,tail)\n', 'first|secondtail'),
)


def validate_cases(cases):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 128:
        raise ValueError('Bounded native preprocessor cases required')
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {'source', 'accepted', 'tokens', 'diagnostic', 'exact'} or
                type(case['accepted']) is not bool or any(not isinstance(case[k], str) or
                len(case[k]) > 8192 for k in ('source', 'tokens', 'diagnostic', 'exact'))):
            raise ValueError('Explicit bounded preprocessor source/result required')


def program(engine, profiles, cases=None, case_sets=None):
    if cases is None:
        cases = [dict(source=s, accepted=True, tokens=t, diagnostic='', exact='') for s, t in CASES]
    validate_cases(cases)
    if case_sets is not None:
        if not isinstance(case_sets, dict) or not 1 <= len(case_sets) <= 1024:
            raise ValueError('Bounded profile case mapping required')
        for key, records in case_sets.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 80:
                raise ValueError('Explicit profile case identity required')
            validate_cases(records)
    checks = []
    for profile in profiles:
        revision = int(profile.get('revision', profile['build'].split('-')[0]))
        selected = case_sets.get(profile['build'], cases) if case_sets is not None else cases
        for index, case in enumerate(selected):
            checks.append('check(%du,%du,%s,%d,%s,%s,%s);' % (
                revision, index, json.dumps(case['source']), int(case['accepted']),
                json.dumps(case['tokens']), json.dumps(case['diagnostic']), json.dumps(case['exact'])))
    code = (HERE / 'classic_preprocessor_contract.c.in').read_text().replace(
        '@CHECKS@', '\n'.join(checks))
    if engine.name == '4432':
        # The native globals rename the clock and exit services. This fixture
        # supplies a fixed clock; these cases do not inspect date/time macros.
        code = '#include <time.h>\n' + code + '''
time_t borTime(time_t *destination)
{
    time_t value = 1;
    if(destination) *destination = value;
    return value;
}
void borExit(int code) { (void)code; abort(); }
'''
    if engine.name in ('3400', '3741', '3842'):
        code = '#include <stdarg.h>\n' + code + '''
void writeToLogFile(const char *format, ...)
{
    va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args);
}
'''
    return bind_named_allocation_support(code, engine)


def compile_native(engine, code):
    """Run the shared native preprocessor unit harness in owned temporary storage."""
    build = engine.name
    pp, script = engine / 'source/preprocessorlib', engine / 'source/scriptlib'
    units = [pp / 'pp_parser.c', pp / 'pp_lexer.c', script / 'List.c']
    if not all(p.is_file() for p in units):
        raise ValueError('Required native preprocessor units are missing')
    if (pp / 'pp_expr.c').is_file():
        units.insert(2, pp / 'pp_expr.c')
    with tempfile.TemporaryDirectory(prefix='preprocessor-native-') as name:
        work = Path(name)
        source, binary = work / 'probe.c', work / 'probe'
        source.write_text(code)
        service_flags = []
        if build == '4432':
            services = work / 'context_services.h'
            services.write_text('#include <time.h>\ntime_t borTime(time_t *);\nvoid borExit(int);\n')
            service_flags = ['-include', str(services)]
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
            '-std=gnu99', '-O1', '-g', '-fcommon', '-ffunction-sections', '-fdata-sections',
            '-ftrivial-auto-var-init=pattern', '-fsanitize=address,undefined',
            '-fno-sanitize-recover=all', '-DPP_TEST=1', '-DSAFEALLOC_H=1',
            '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
            '-Wno-deprecated-declarations', '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast',
            '-DOBOR_ENGINE_BUILD=' + build,
            *service_flags,
            *('-I' + str(p) for p in (pp, script, engine / 'source',
                                     engine / 'source/gamelib', ROOT / 'src/port/libretro')),
                    str(source), *map(str, units), *links, '-o', str(binary)]
        subprocess.run(command, check=True, timeout=60)
        output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                         env=sanitizer_environment())
        return json.loads(output)


class PreprocessorConcatenationTests(unittest.TestCase):
    def test_native_expansion_in_every_affected_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for build in ENGINES:
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            engine = ROOT / 'src/engines' / build
            with self.subTest(engine=build):
                result = compile_native(engine, program(engine, profiles))
                revisions = {int(p.get('revision', p['build'].split('-')[0])) for p in profiles}
                self.assertEqual(result, dict(contexts=len(revisions),
                                 cases=len(profiles) * len(CASES), status='PASS'))


if __name__ == '__main__':
    unittest.main()
