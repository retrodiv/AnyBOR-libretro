"""Check native byte-count lowercase conversion over the ctype byte domain.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import unittest

from test_historical_player import function
from test_model_constructor_ownership import run_native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


def program(engine, profiles):
    native = function((engine / 'source/utils.c').read_text(encoding='latin1'), 'lc')
    return r'''
#include <assert.h>
#include <ctype.h>
#include <locale.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
static unsigned conversions;
static int checked_lowercase(int value) {
    assert(value >= 0 && value <= 255);
    ++conversions;
    return tolower(value);
}
#undef tolower
#define tolower checked_lowercase
@NATIVE@
#undef tolower
static unsigned char expected(unsigned char value) {
    return value >= 'A' && value <= 'Z' ? value + ('a' - 'A') : value;
}
static void check(void) {
    char bytes[258];
    memset(bytes, 57, sizeof(bytes));
    for(unsigned i = 0; i < 256; ++i) bytes[i+1] = (char)i;
    conversions = 0;
    lc(NULL, 0);
    assert(!conversions);
    lc(bytes+1, 256);
    assert(conversions == 256 && bytes[0] == 57 && bytes[257] == 57);
    for(unsigned i = 0; i < 256; ++i)
        assert((unsigned char)bytes[i+1] == expected((unsigned char)i));
    char prefix[] = {'A', 0, 'B', 'Z', 'q', '!', 0};
    conversions = 0;
    lc(prefix, 3);
    assert(conversions == 3);
    assert(!memcmp(prefix, (char[]){'a', 0, 'b', 'Z', 'q', '!', 0}, sizeof(prefix)));
}
int main(void) {
    assert(setlocale(LC_CTYPE, "C"));
    for(unsigned i = 0; i < @PROFILES@; ++i) check();
    printf("{\"profiles\":%u,\"bytes\":%u}\n", @PROFILES@, 256u*@PROFILES@);
    return 0;
}
'''.replace('@NATIVE@', native).replace('@PROFILES@', str(len(profiles))+'u')


class LowercaseByteTests(unittest.TestCase):
    def test_all_bytes_and_counted_prefixes(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            engine = ROOT / 'src/engines' / row['build']
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(profiles=len(profiles), bytes=256*len(profiles)))

    def test_signed_byte_domain_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][0]
        engine = ROOT / 'src/engines' / row['build']
        text = program(engine, [pin['profiles'][0]])
        cast = 'tolower((unsigned char)buf[i])'
        self.assertEqual(text.count(cast), 1)
        result = run_native(engine, text.replace(cast, 'tolower((signed char)buf[i])'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('value >= 0 && value <= 255', result.stderr)


if __name__ == '__main__':
    unittest.main()
