"""Check source-owned font loading, byte selection and drawing boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function
from test_early_system_callbacks import block
import font_raster_probe

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-font-epoch-contracts.json'
TEXT = b'AB\nC\x01\x81A\x82B\x81'
FLAGS = (0, 1, 2, 3, -2)
FORMATS = (0, 1, 2, 4)


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'source/gamelib/font.c').read_text()
    names = list(font_raster_probe.FONT_FUNCTIONS)
    reset = ''
    for name in ('obor_font_palette_valid', 'obor_font_loading_slot', 'obor_font_cached_dimension'):
        if 'static int ' + name + '(' in source:
            names.insert(0, name)
    if 'static int obor_font_cached_dimension(' in source:
        reset = 'for(int s=0;s<MAX_FONTS;++s)for(int a=0;a<2;++a)obor_font_cached_dimension(s,a,1,0);obor_font_loading_slot(1,-1);'
    code = Path(__file__).with_name('font_epoch_contract.c.in').read_text()
    header = (ROOT / 'src/engines' / data['engine'] / 'openbor.h').read_text()
    macros = []
    for name in ('_colx', '_liney', '_strmidx', '_menutextm'):
        matches = re.findall(r'(?m)^#define ' + name + r'\([^\n]+', header)
        matches = [line for line in matches if len(matches) == 1 or 'args...' in line]
        if len(matches) != 1:
            raise ValueError('Exact native HUD macro required: ' + name)
        macros.append(matches[0])
    methods = []
    for name in names:
        text = function(source, name)
        if name == '_font_load':
            text = '#define malloc glyph_malloc\n' + text + '\n#undef malloc'
        if name == '_font_unload':
            text = '#define free observed_free\n' + text + '\n#undef free'
        methods.append(text)
    return code.replace('@FUNCTIONS@', '\n'.join(methods)).replace(
        '@REVISIONS@', ','.join(str(r['revision'])+'u' for r in data['sources'])).replace(
        '@RESET@', reset).replace('@HUD_MACROS@', '\n'.join(macros))


def caller_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    keyboard = function(source, 'keyboard_setup')
    start = keyboard.index('else if(', keyboard.index('"fontmonospace"'))
    keyword = block(keyboard, start)
    if '"fontmbs"' not in keyword:
        raise ValueError('Exact font keyword branch required')
    code = Path(__file__).with_name('font_loader_contract.c.in').read_text()
    return code.replace('@FUNCTIONS@', '\n'.join(function(source, n) for n in
        ('load_all_fonts', 'unload_all_fonts', 'load_menu_txt'))).replace('@KEYWORD@', keyword).replace(
        '@REVISIONS@', ','.join('{%du,%d}' % (r['revision'], r['contract']['banks'])
                               for r in data['sources']))


def expected(row):
    revision, contract = row['revision'], row['contract']
    result = []
    for flag in FLAGS:
        mono = bool(flag & 1) if contract['banks'] else bool(flag)
        multibyte = bool(flag & 2) and bool(contract['banks'])

        def advance(glyph):
            if mono:
                return 12
            value = (0 if glyph == 1 else 1+glyph % 5)+1
            return 4 if value <= 1 else value

        def characters():
            i = 0
            while i < len(TEXT):
                prefix, glyph = 0, TEXT[i]
                newline = glyph == 10
                if multibyte and glyph >= 128 and i+1 < len(TEXT):
                    prefix, glyph = glyph, TEXT[i+1]
                    i += 1
                yield prefix, glyph, newline
                i += 1

        width = sum(advance(glyph) for bank, glyph, _ in characters() if bank in (0, 129))
        result.append(dict(revision=revision, flags=flag, kind=0, width=12, height=9,
                           text_width=width, loads=129 if multibyte else 1))
        result.append(dict(revision=revision, flags=flag, kind=6, col=186, line=90))
        result.append(dict(revision=revision, flags=flag, kind=7, format=0,
                           events=[[4, (320-advance(65))//2+13, 90, 0, 65]]))
        x, y, events = 7, 11, []
        for bank, glyph, newline in characters():
            if bank not in (0, 129):
                continue
            if newline and not contract['queued_newline_glyph']:
                x, y = 7, y+9
            else:
                events.append([4, x, y, bank, glyph])
                x += advance(glyph)
                if newline:
                    y += 3
        result.append(dict(revision=revision, flags=flag, kind=1, format=0, events=events))
        for fmt in FORMATS:
            x, y, events = 7, 11, []
            for bank, glyph, newline in characters():
                if bank not in (0, 129):
                    continue
                if not contract['banks']:
                    if glyph == 10:
                        x, y = 7, y+3
                    elif 32 <= glyph < 128:
                        route = {0: 0, 2: 1, 4: 2}.get(fmt) if contract['direct_screen_backend'] else 3
                        if route is not None:
                            events.append([route, x, y, bank, glyph])
                        x += advance(glyph)
                elif newline:
                    x, y = 7, y+9
                else:
                    events.append([3, x, y, bank, glyph])
                    x += advance(glyph)
            result.append(dict(revision=revision, flags=flag, kind=2, format=fmt, events=events))
        result.append(dict(revision=revision, flags=flag, kind=3,
                           width=12 if contract['legacy_dimension_cache'] else 0,
                           height=9 if contract['legacy_dimension_cache'] else 0, text_width=0))
    result.append(dict(revision=revision, kind=4, width=12 if contract['legacy_dimension_cache'] else 0,
                       height=9 if contract['legacy_dimension_cache'] else 0))
    result.append(dict(revision=revision, kind=5, width=16 if contract['legacy_dimension_cache'] else 0,
                       height=11 if contract['legacy_dimension_cache'] else 0))
    result.append(dict(revision=revision, kind=8, width=20 if contract['legacy_dimension_cache'] else 0,
                       height=13 if contract['legacy_dimension_cache'] else 0))
    for slot in range(8):
        result.append(dict(revision=revision, kind=9, slot=slot, width=8+slot, height=10+slot,
                           col=160+2*(9+slot), line=120-3*(11+slot)))
        result.append(dict(revision=revision, kind=10, slot=slot,
                           width=8+slot if contract['legacy_dimension_cache'] else 0,
                           height=10+slot if contract['legacy_dimension_cache'] else 0))
    return result


def caller_expected(row):
    rev, contract = row['revision'], row['contract']
    result = []
    raw = [-2, 0, 1, 2, 3, 4, 7, -1]
    mono = [int(bool(v)) for v in raw] if contract['banks'] else raw
    for success in (255, 254, 253, 251, 247, 0, 85):
        for optional in (0, 240):
            calls, checks, diagnostic, stopped = [], [], '', 0
            for slot in range(8):
                if contract['load_policy'] == 'required4_optional4' and slot >= 4:
                    checks.append(slot)
                    if not (optional & (1 << slot)):
                        continue
                calls.append([slot, mono[slot] | (2 if slot % 2 else 0) if contract['banks'] else mono[slot]])
                loaded = bool(success & (1 << slot))
                if contract['load_policy'] == 'required4_optional4' and slot < 4 and not loaded:
                    stopped, diagnostic = 1, 'Unable to load font #%d!\n' % (slot+1)
                    break
                if contract['load_policy'] == 'warning' and not loaded:
                    diagnostic += 'Warning: unable to load font #%d!\n' % (slot+1)
                if contract['load_policy'] == 'success_numbers' and loaded:
                    diagnostic += '%d ' % (slot+1)
            result.append(dict(revision=rev, kind=0, success=success, optional=optional,
                               calls=calls, checks=checks, stopped=stopped, diagnostic=diagnostic))
    result.append(dict(revision=rev, kind=1, unloaded=list(range(8))))
    for status in (0, 1):
        handled = status or not contract['menu_requires_parse_success']
        values = mono if handled else [17]*8
        banks = [0 if v == 0 else 2 for v in raw] if handled and contract['menu_mbs'] else [19]*8
        diagnostic = ''
        if handled:
            if not contract['menu_mbs']:
                diagnostic += "Command 'fontmbs' not understood in file 'data/menu.txt'!"
            diagnostic += "Command 'unknown' not understood in file 'data/menu.txt'!"
        result.append(dict(revision=rev, kind=2, status=status, mono=values, banks=banks,
                           diagnostic=diagnostic, keyword=contract['menu_mbs']))
    return result


class FontEpochContracts(unittest.TestCase):
    def test_native_loading_flags_dimensions_widths_and_draw_paths(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [r['revision'] for r in data['sources']]
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(set(revisions)))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [item for row in data['sources'] for item in expected(row)])

    def test_native_required_fonts_menu_flags_and_diagnostics(self):
        data = load_contract_fixture(FIXTURE)
        actual = [json.loads(line) for line in native_output(caller_program(data), data).splitlines()]
        self.assertEqual(actual, [item for row in data['sources'] for item in caller_expected(row)])

    def test_raster_helper_requires_explicit_valid_profile(self):
        data = load_contract_fixture(FIXTURE)
        engine = ROOT / 'src/engines' / data['engine']
        source = (engine / 'source/gamelib/font.c').read_text()
        if 'static int obor_font_cached_dimension(' not in source:
            self.skipTest('Preceding source control has no profile-aware font path')
        with self.assertRaisesRegex(ValueError, 'explicit profile'):
            font_raster_probe.program(engine)
        for value in (True, 0, -1, 'invalid'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'positive integer'):
                font_raster_probe.program(engine, profile=value)
        code = font_raster_probe.program(engine, profile=data['sources'][0]['revision'])
        self.assertIn('uint32_t obor_profile_build = ', code)
        self.assertIn('static int obor_font_cached_dimension(', code)


if __name__ == '__main__':
    unittest.main()
