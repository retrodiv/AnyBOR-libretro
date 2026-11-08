"""Render source-owned scrolling and indexed startup admission controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import json
import re

from test_historical_player import function


def program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    update = function(source, 'update_animation')
    first = update.index('    if(level)')
    last = update.index('    if(!(self->idling & 2)', first)
    branch = update[first:last]
    startup = function(source, 'startup')
    palette = startup.index('standard_palette(1);')
    first = startup.rfind('\n    if(', 0, palette) + 1
    last = startup.index('    printf("Loading fonts', palette)
    admission = startup[first:last]
    if admission.count('standard_palette(1);') != 1 or admission.count('load_menu_txt();') != 1:
        raise ValueError('One native palette/menu segment required')
    fields = dict(SCROLL=branch, STARTUP=admission,
        CONTEXTS=','.join('{%du,%d,%d}' % (r['revision'], r['altitude_base'], r['palette8'])
                          for r in data['sources']),
        CASES=',\n'.join('{%s}' % ','.join(str(r[name]) for name in
            ('level', 'panel', 'up', 'speed', 'scroll', 'dx', 'dy', 'x', 'y', 'base_written'))
            for r in data['scroll_cases']))
    text = Path(__file__).with_name('classic_loading_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native loading control input')
    return text


def shutdown_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    text = Path(__file__).with_name('classic_shutdown_contract.c.in').read_text()
    values = dict(SHUTDOWN=function(source, 'openbor_shutdown'),
        CONTEXTS=','.join('{%du,%s,%d}' % (row['revision'], json.dumps(row['body']),
                          row['custom_message_argument'])
                          for row in data['sources']))
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved shutdown contract input')
    return text


def policy_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    startup = function(source, 'startup')
    # Execute the complete prefix before the first initialization service.
    # This must precede menu and script settings rather than overwrite them.
    prefix = startup[startup.index('{') + 1:startup.index('printf("FileCaching')]
    if 'loadingbarstatus.size.y' not in prefix:
        raise ValueError('Native loading-height initialization must precede services')
    initializer = re.search(r'(?m)^s_barstatus loadingbarstatus\s*=\s*\{.*?^\};',
                            source, re.S)
    if initializer is None:
        raise ValueError('Native loading-bar initializer required')
    fields = dict(INITIALIZER=initializer[0], STARTUP=prefix,
        FUNCTIONS='\n'.join(function(source, name) for name in
            ('fill_s_loadingbar', 'isLoadingScreenTypeBg', 'isLoadingScreenTypeBar', 'bar')),
        CONTEXTS=','.join('{%du,%d,%d,{%s}}' %
            (row['revision'], row['height'], row['bar_mask'],
             ','.join(str(n) for n in row['stored_modes'])) for row in data['sources']))
    text = Path(__file__).with_name('classic_loading_policy_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved loading-policy control input')
    return text
