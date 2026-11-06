"""Check source-owned sprite-map identity, lookup and script fields.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-sprite-map-contracts.json'


def loader_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    queue = (engine / 'source/gamelib/spriteq.c').read_text()
    starts = list(re.finditer(r'(?m)^#define[ \t]+MAXQSPRITES\b', queue))
    if len(starts) != 1:
        raise ValueError('One native queue declaration required')
    end = queue.index('void spriteq_add_frame(', starts[0].start())
    parts = dict(STORAGE=queue[starts[0].start():end],
        QUEUE=function(queue, 'spriteq_add_sprite'), FUNCTIONS='\n'.join(function(core, n) for n in (
        'obor_profile_sprite_map_capacity', 'prepare_sprite_map', 'loadsprite2',
        'loadsprite', 'freesprites')),
        CONTEXTS=','.join('{%du,%d,%d}' % (r['revision'], r['legacy_entry'],
            r['full_search']) for r in data['sources']))
    text = Path(__file__).with_name('sprite_map_loader_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved sprite-map loader dependency')
    return text


def reader_program(data):
    from test_historical_sprite_stats_reads import reader_entry, reader_program as render
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    driver = Path(__file__).with_name('sprite_map_reader_contract.c.in').read_text()
    driver = driver.replace('@LEGACY@', ','.join(str(int(r['legacy_entry']))
                                               for r in data['sources']))
    return render(components=dict(entries=reader_entry(source),
        translation='static int obor_entity_get_property_native(int p){return p;}',
        helpers=function((engine / 'source/gamelib/types.h').read_text(),
                         'obor_profile_map_sprite')),
        common={n: function(variant, n) for n in
                ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')},
        contracts=[dict(revision=r['revision']) for r in data['sources']], driver=driver)


def setter_program(data):
    from test_historical_entity_complex import complex_program
    from test_historical_entity_returns import scalar_entry
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    entry, actions = scalar_entry(source, ('_ep_spritea',))
    helper = function(source, 'obor_script_sprite_filename')
    helper += '\nstatic int obor_entity_set_property_native(int p){return p;}\n'
    driver = Path(__file__).with_name('sprite_map_setter_contract.c.in').read_text()
    driver = driver.replace('@LEGACY@', ','.join(str(int(r['legacy_entry']))
                                               for r in data['sources']))
    code = complex_program(components=dict(entries=entry, actions=actions,
        helpers=helper, invoke='return openbor_changeentityproperty(args,result,count);'),
        contracts=[dict(revision=r['revision'], has_result=r['has_result'])
                   for r in data['sources']], driver=driver)
    quiet = 'static int quiet_printf(const char *format,...) { (void)format;return 0; }'
    if code.count(quiet) != 1:
        raise ValueError('One maintained callback diagnostic provider required')
    return code.replace(quiet, 'static int observed_unknown;\n'
        'static int quiet_printf(const char *format,...){\n'
        'if(!strcmp(format,"Unknown Sprite Array subproperty.\\n"))++observed_unknown;\n'
        'return 0;}')


def frame_view_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    model = function(source, 'load_cached_model')
    first = model.index('if(index>=0 && !nopalette && obor_profile_map_sprite')
    last = model.index('// Adjust coords:', first)
    block = 'if(pixelformat==PIXEL_x8 && !nopalette) {\n' + model[first:last]
    text = Path(__file__).with_name('sprite_map_frame_contract.c.in').read_text()
    return text.replace('@ASSIGNMENTS@', block).replace('@CONTEXTS@',
        ','.join('{%du,%d}' % (r['revision'], r['legacy_entry']) for r in data['sources']))


def diagnostic_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    blocks = re.findall(r'if\(obor_profile_build < 3610\)\s*'
        r'printf\("Total Ram:[\s\S]*?printf\("Total sprites mapped:[^\n]*\n[ \t]*\}', source)
    if len(blocks) != 1:
        raise ValueError('One native RAM/sprite-count diagnostic block required')
    text = Path(__file__).with_name('sprite_map_diagnostic_contract.c.in').read_text()
    return text.replace('@DIAGNOSTIC@', blocks[0]).replace('@CONTEXTS@',
        ','.join('{%du,%d}' % (r['revision'], r['full_search']) for r in data['sources']))


def lifecycle_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    unload = function(source, 'unload_level')
    start = 'temp = getFirstModel();'
    if unload.count(start) != 1:
        raise ValueError('One native model traversal required')
    first = unload.index(start)
    last = unload.index('while(temp);', first) + len('while(temp);')
    model = function(source, 'load_cached_model')
    hits = re.findall(re.escape('if((tempmodel=findmodel(name))!=NULL)') + r'\s*\{'
                      r'[\s\S]*?return tempmodel;\s*\}', model)
    if len(hits) != 1:
        raise ValueError('One native cached-model fast path required')
    parts = dict(SERVICE=function(source, 'cachesprite'), EXISTING=hits[0],
        WALK=function(source, 'cache_model_sprites'), UNLOAD=unload[first:last],
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['cache_epoch'])
                          for r in data['sources']))
    text = Path(__file__).with_name('sprite_map_lifecycle_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved sprite lifecycle dependency')
    return text


class SpriteMapContracts(unittest.TestCase):
    def fixture(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        return data

    def test_native_loader_identity_clipping_and_lookup(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(loader_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], cases=9,
            record_bytes=data['map_record_bytes']) for r in data['sources']])

    def test_source_callback_offset_reads_and_sprite_views(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(reader_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], reader='PASS')
                                  for r in data['sources']])

    def test_source_callback_offset_writes_and_aliases(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(setter_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], setter='PASS')
                                  for r in data['sources']])

    def test_native_model_frame_palette_and_mask_view(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(frame_view_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], frame='PASS')
                                  for r in data['sources']])

    def test_native_load_diagnostic_layout(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(diagnostic_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], diagnostic='PASS')
                                  for r in data['sources']])

    def test_native_cache_requests_and_model_unload_policy(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(lifecycle_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], lifecycle='PASS')
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
